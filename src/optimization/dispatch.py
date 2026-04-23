"""
src/dispatch.py
Traffic-aware route optimization + smart dispatch.

ӨМНӨХ АСУУДАЛ:
  - generate_actors: random.choice(nodes) → reproduce боломжгүй
  - mock_data.py: random.uniform factor → KPI consistent биш
  - Simulation KPI vs Dispatch KPI зөрж байна

ШИЙДЭЛ:
  - Жолооч/захиалга: seed + index-ээр тогтмол node сонгоно
  - Бүх distance: nx.shortest_path_length (бодит граф)
  - KPI: нэг pipeline-аас — baseline vs optimized
  - CO₂: configurable emission factor (van/car/truck)

Алгоритм:
  - Weighted shortest path (Dijkstra)
  - edge weight = travel_time (peak/normal)
  - Nearest dispatch vs Smart dispatch харьцуулалт
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import networkx as nx
import osmnx as ox

from src.utils import get_logger, ensure_dir, haversine_m, eta_minutes, is_rush_hour

log = get_logger(__name__)


# ── Улаанбаатарын бодит байршлууд ─────────────────────────
# random lat/lon-г устгаж бодит газрын нэртэй цэгүүдээр орлуулна.
# Эдгээр нь dispatch simulation-д fallback байршил болно.
UB_LANDMARKS = [
    {"name": "Сүхбаатарын талбай",  "lat": 47.9184, "lon": 106.9177},
    {"name": "МУИС",                 "lat": 47.9208, "lon": 106.9365},
    {"name": "Зайсан",               "lat": 47.8839, "lon": 106.9108},
    {"name": "Драгон центр",         "lat": 47.9097, "lon": 106.8831},
    {"name": "Нарны зам",            "lat": 47.9001, "lon": 106.9490},
    {"name": "Интерактив музей",     "lat": 47.9225, "lon": 106.8980},
    {"name": "Улаанбаатар зочид буудал", "lat": 47.9178, "lon": 106.9259},
    {"name": "Сансар",               "lat": 47.9290, "lon": 106.9440},
    {"name": "Баянзүрх дүүрэг",      "lat": 47.9050, "lon": 107.0010},
    {"name": "Хан-Уул дүүрэг",       "lat": 47.8720, "lon": 106.9010},
    {"name": "Чингэлтэй дүүрэг",     "lat": 47.9350, "lon": 106.9100},
    {"name": "Баянгол дүүрэг",       "lat": 47.9100, "lon": 106.8700},
    {"name": "Яармаг",               "lat": 47.8900, "lon": 106.9700},
    {"name": "Мах импекс",           "lat": 47.9230, "lon": 106.8750},
    {"name": "Элдэв-Очирын гудамж",  "lat": 47.9170, "lon": 106.9050},
    {"name": "Их Тойруу",            "lat": 47.9120, "lon": 106.9300},
    {"name": "Дэлгэрхаан",           "lat": 47.8650, "lon": 107.0200},
    {"name": "Налайх",               "lat": 47.7600, "lon": 107.2700},
    {"name": "Хайлааст",             "lat": 47.9400, "lon": 107.0100},
    {"name": "Хороо 1, СБД",         "lat": 47.9200, "lon": 106.9150},
]

DRIVER_NAMES = ["Б.Болд", "Д.Мөнх", "Г.Ган", "Н.Бат", "О.Дорж",
                "Т.Сүх", "Э.Нар", "Х.Бямба", "Ц.Ган", "А.Нар"]
ZONES = ["Сүхбаатар", "Баянзүрх", "Чингэлтэй",
         "Баянгол", "Хан-Уул", "Сонгинохайрхан"]

# CO₂ хүчин зүйл (g/km) — тээврийн хэрэгслийн төрлөөр
CO2_FACTORS = {
    "car":   120,  # жижиг авто
    "van":   180,  # хүргэлтийн фургон
    "truck": 250,  # ачааны машин
}


# ── Өгөгдлийн бүтэц ───────────────────────────────────────

@dataclass
class Driver:
    id:   str
    name: str
    node: int
    lat:  float
    lon:  float
    zone: str
    free: bool = True


@dataclass
class Order:
    id:   str
    node: int
    lat:  float
    lon:  float
    zone: str


@dataclass
class RouteOption:
    rank:          int
    weight_type:   str      # "distance" | "normal" | "peak"
    path_length_m: float
    eta_min:       float
    n_nodes:       int


@dataclass
class DispatchRecord:
    order_id:    str
    method:      str        # "nearest" | "smart"
    driver_id:   str
    distance_m:  float
    eta_min:     float
    best_route:  dict


# ── Граф edge жин ─────────────────────────────────────────

def add_travel_time_weights(G, speed_peak_kmh: float, speed_normal_kmh: float) -> None:
    """
    Graph-ийн edge бүрт travel_time жин нэмнэ.

    weight_peak   = length / (speed_peak   m/s)  — оргил цаг
    weight_normal = length / (speed_normal m/s)  — ердийн цаг

    Энэ нь shortest_path-д ашиглагдана.

    Args:
        G:               osmnx DiGraph
        speed_peak_kmh:  оргил цагийн хурд
        speed_normal_kmh: ердийн цагийн хурд
    """
    peak_ms   = speed_peak_kmh   / 3.6   # km/h → m/s
    normal_ms = speed_normal_kmh / 3.6

    for u, v, data in G.edges(data=True):
        length = data.get("length", 50)   # default 50m хэрэв байхгүй бол
        data["weight_peak"]   = length / peak_ms
        data["weight_normal"] = length / normal_ms


def get_weight_key(hour: int, rush_hours: list) -> str:
    """Тухайн цагт ямар edge жин ашиглах вэ."""
    return "weight_peak" if is_rush_hour(hour, rush_hours) else "weight_normal"


# ── Multi-route comparison ────────────────────────────────

def get_multi_routes(G, from_node: int, to_node: int,
                     hour: int, rush_hours: list,
                     speed_kmh: float) -> list[RouteOption]:
    """
    3 өөр жингээр маршрут тооцоолж харьцуулна:
      1. distance   — хамгийн богино зам (метрээр)
      2. normal     — ердийн цагийн travel time жин
      3. peak       — оргил цагийн travel time жин

    Бүх edge length GraphML-аас авна (random биш).
    """
    options = []
    configs = [
        ("distance", "length"),
        ("normal",   "weight_normal"),
        ("peak",     "weight_peak"),
    ]

    for rank, (label, weight) in enumerate(configs, start=1):
        try:
            path = nx.shortest_path(G, from_node, to_node, weight=weight)
            # Бодит граф дахь edge length нийлбэр
            length_m = sum(
                G[u][v][0].get("length", 50)
                for u, v in zip(path[:-1], path[1:])
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Холбоогүй бол шулуун зай (Haversine fallback)
            n1, n2   = G.nodes[from_node], G.nodes[to_node]
            length_m = haversine_m(n1["y"], n1["x"], n2["y"], n2["x"])
            path     = [from_node, to_node]

        options.append(RouteOption(
            rank=rank,
            weight_type=label,
            path_length_m=round(length_m, 1),
            eta_min=eta_minutes(length_m, speed_kmh),
            n_nodes=len(path),
        ))

    return options


# ── ETA тооцоолол ─────────────────────────────────────────

def get_driver_eta(G, driver: Driver, order: Order,
                   speed_kmh: float, rush_hours: list,
                   hour: int) -> tuple[float, float]:
    """
    Жолоочоос захиалга руу ETA + distance тооцооллоно.
    Граф дахь shortest_path_length ашиглана (Haversine биш).

    Returns:
        (eta_minutes, distance_meters)
    """
    weight = get_weight_key(hour, rush_hours)
    try:
        # GraphML дахь бодит замын урт (метр)
        dist_m = nx.shortest_path_length(G, driver.node, order.node, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # Fallback: шулуун зай
        dist_m = haversine_m(driver.lat, driver.lon, order.lat, order.lon)

    return eta_minutes(dist_m, speed_kmh), round(dist_m, 1)


# ── Dispatch стратегиуд ────────────────────────────────────

def nearest_dispatch(order: Order, drivers: list[Driver],
                     speed_kmh: float) -> tuple[Driver, float, float]:
    """
    Haversine (шулуун) зайгаар хамгийн ойр жолоочийг сонгоно.
    Baseline хэмжүүр болгон ашиглана.

    Returns:
        (driver, eta_min, distance_m)
    """
    free = [d for d in drivers if d.free]
    if not free:
        raise ValueError("Чөлөөт жолооч байхгүй")

    best = min(free, key=lambda d: haversine_m(d.lat, d.lon, order.lat, order.lon))
    dist_m = haversine_m(best.lat, best.lon, order.lat, order.lon)
    return best, eta_minutes(dist_m, speed_kmh), round(dist_m, 1)


def smart_dispatch(order: Order, drivers: list[Driver],
                   G, hour: int, rush_hours: list,
                   speed_kmh: float) -> tuple[Driver, float, float]:
    """
    Граф дахь shortest path ашиглан хамгийн хурдан жолоочийг сонгоно.

    Nearest dispatch-аас ялгаа:
      - Haversine биш → nx.shortest_path_length (замаар)
      - Оргил/ердийн цагийн edge жин тооцооно

    Returns:
        (driver, eta_min, distance_m)
    """
    free = [d for d in drivers if d.free]
    if not free:
        raise ValueError("Чөлөөт жолооч байхгүй")

    best, best_eta, best_dist = None, float("inf"), 0.0
    for d in free:
        eta, dist = get_driver_eta(G, d, order, speed_kmh, rush_hours, hour)
        if eta < best_eta:
            best_eta, best_dist, best = eta, dist, d

    return best, round(best_eta, 2), best_dist


# ── KPI тооцоолол (нэг эх сурвалж) ───────────────────────

def compute_kpi(
    nearest_etas: list[float],
    smart_etas: list[float],
    nearest_dists_m: list[float],
    smart_dists_m: list[float],
    vehicle_type: str = "van",
) -> dict:
    """
    Бүх KPI-г нэг газраас тооцооллоно (single source of truth).

    Тооцооллын логик:
      improvement_pct = (nearest - smart) / nearest * 100
      co2_saved_kg    = saved_km * emission_g_per_km / 1000

    Args:
        nearest_etas:    nearest dispatch ETA жагсаалт (мин)
        smart_etas:      smart dispatch ETA жагсаалт (мин)
        nearest_dists_m: nearest dispatch distance жагсаалт (м)
        smart_dists_m:   smart dispatch distance жагсаалт (м)
        vehicle_type:    "car" | "van" | "truck"

    Returns:
        KPI dict
    """
    n = len(nearest_etas)
    if n == 0:
        return {}

    avg_nearest = sum(nearest_etas) / n
    avg_smart   = sum(smart_etas) / n
    improvement = (avg_nearest - avg_smart) / avg_nearest * 100 if avg_nearest > 0 else 0

    avg_nearest_km = sum(nearest_dists_m) / n / 1000
    avg_smart_km   = sum(smart_dists_m) / n / 1000
    saved_km       = avg_nearest_km - avg_smart_km

    emission_g_per_km = CO2_FACTORS.get(vehicle_type, CO2_FACTORS["van"])
    # Нийт CO₂ хэмнэлт: захиалга бүрт saved_km * emission → нийт n захиалга
    co2_saved_g  = saved_km * emission_g_per_km * n
    co2_saved_kg = co2_saved_g / 1000

    return {
        "n_orders":          n,
        "avg_nearest_min":   round(avg_nearest, 2),
        "avg_smart_min":     round(avg_smart, 2),
        "improvement_pct":   round(improvement, 1),
        "time_saved_min":    round(avg_nearest - avg_smart, 2),
        "avg_nearest_km":    round(avg_nearest_km, 2),
        "avg_smart_km":      round(avg_smart_km, 2),
        "distance_saved_km": round(saved_km, 2),
        "vehicle_type":      vehicle_type,
        "co2_factor_g_km":   emission_g_per_km,
        "co2_saved_kg":      round(co2_saved_kg, 3),
    }


# ── Congestion score ──────────────────────────────────────

def congestion_score(speed_kmh: float, edge_length_m: float,
                     is_main_road: bool = False) -> float:
    """
    Edge-ийн түгжрэлийн оноо тооцооллоно (0.0–1.0).

    Томьёо:
      base_score = 1 - speed / MAX_SPEED
      length_factor: урт зам → илүү нөлөөтэй
      road_factor: гол зам бол 1.2 дахин их нөлөө

    Args:
        speed_kmh:    тухайн цагийн хурд
        edge_length_m: edge урт (метр)
        is_main_road: гол зам мөн эсэх

    Returns:
        0.0 (цэвэр) → 1.0 (бүрэн түгжрэл)
    """
    MAX_SPEED = 50.0

    # Хурд буурах тусам congestion нэмэгдэнэ
    base_score = 1.0 - min(speed_kmh, MAX_SPEED) / MAX_SPEED

    # Урт зам → 20% хүртэл нэмэлт нөлөө (2km-ийн зам = +10%)
    length_factor = min(0.2, edge_length_m / 10_000)

    # Гол зам → 20% нэмэлт нөлөө (илүү машин дайрдаг)
    road_factor = 1.2 if is_main_road else 1.0

    score = (base_score + length_factor) * road_factor
    return round(min(1.0, max(0.0, score)), 3)


# ── Actor үүсгэх (граф дээр) ─────────────────────────────

def generate_actors(G, n_drivers: int, n_orders: int,
                    seed: int) -> tuple[list[Driver], list[Order]]:
    """
    Графийн node дээр жолооч, захиалга байршуулна.

    Арга:
      nodes жагсаалтыг эрэмбэлж (node ID-гаар) тогтмол болгоно.
      seed + index → тогтмол offset → reproduce хийгдэнэ.

    random.seed()-г зөвхөн жагсаалтаас сонгоход ашиглана (random.choice биш).
    """
    # Node-уудыг эрэмбэлж тогтмол дараалал авна
    nodes = sorted(G.nodes(data=True), key=lambda x: x[0])
    n_nodes = len(nodes)

    if n_nodes == 0:
        raise ValueError("Граф хоосон байна")

    # Deterministic index: seed + i → hash → node index
    def pick_node(i: int) -> tuple:
        idx = (seed * 31 + i * 17) % n_nodes
        return nodes[idx]

    drivers = []
    for i in range(n_drivers):
        nid, data = pick_node(i)
        # n_drivers-ын 80% нь чөлөөтэй (тогтмол, random биш)
        free = (i % 5) != 0   # 4/5 = 80% free
        drivers.append(Driver(
            id=f"D{i+1:02d}",
            name=DRIVER_NAMES[i % len(DRIVER_NAMES)],
            node=nid,
            lat=data["y"],
            lon=data["x"],
            zone=ZONES[i % len(ZONES)],
            free=free,
        ))

    orders = []
    for i in range(n_orders):
        nid, data = pick_node(n_drivers + i)   # жолоочтой давхцахгүй offset
        orders.append(Order(
            id=f"#{1000 + i}",
            node=nid,
            lat=data["y"],
            lon=data["x"],
            zone=ZONES[i % len(ZONES)],
        ))

    return drivers, orders


# ── Харьцуулалт (нэг сценарий) ────────────────────────────

def compare_dispatch(G, drivers: list[Driver], orders: list[Order],
                     hour: int, cfg: dict) -> dict:
    """
    N захиалгад nearest vs smart dispatch харьцуулж KPI тооцооллоно.
    KPI бүр нэг pipeline-аас — зөрөлгүй.

    Returns:
        {hour, scenario, kpi, records}
    """
    traffic    = cfg["traffic"]
    rush_hours = traffic["rush_hours"]
    rush       = is_rush_hour(hour, rush_hours)
    speed      = traffic["speed_peak_kmh"] if rush else traffic["speed_normal_kmh"]
    label      = "Оргил цаг" if rush else "Ердийн цаг"
    vtype      = cfg.get("dispatch", {}).get("vehicle_type", "van")

    nearest_etas, smart_etas         = [], []
    nearest_dists, smart_dists       = [], []
    records                           = []

    for order in orders:
        # Nearest dispatch (Haversine — baseline)
        nd, n_eta, n_dist = nearest_dispatch(order, drivers, speed)
        nearest_etas.append(n_eta)
        nearest_dists.append(n_dist)

        # Smart dispatch (Graph shortest path)
        sd, s_eta, s_dist = smart_dispatch(order, drivers, G, hour, rush_hours, speed)
        smart_etas.append(s_eta)
        smart_dists.append(s_dist)

        records.append({
            "order_id":         order.id,
            "nearest_driver":   nd.id,
            "nearest_eta_min":  n_eta,
            "nearest_dist_m":   n_dist,
            "smart_driver":     sd.id,
            "smart_eta_min":    s_eta,
            "smart_dist_m":     s_dist,
        })

    kpi = compute_kpi(nearest_etas, smart_etas, nearest_dists, smart_dists, vtype)

    log.info(
        "%-12s │ Nearest: %.1f мин → Smart: %.1f мин │ ↓%.1f%%",
        label, kpi["avg_nearest_min"], kpi["avg_smart_min"], kpi["improvement_pct"],
    )

    return {
        "hour":     hour,
        "scenario": label,
        "speed_kmh": speed,
        "kpi":      kpi,
        "records":  records,
    }


# ── Pipeline entry point ───────────────────────────────────

def run(cfg: dict) -> None:
    """
    Config-оор бүтэн dispatch pipeline ажиллуулна.
    GraphML → edge weights → actors → compare → JSON хадгална.
    """
    graphml = cfg["paths"]["graphml"]
    if not Path(graphml).exists():
        log.error("GraphML олдсонгүй: %s", graphml)
        return

    log.info("GraphML ачааллаж байна …")
    G = ox.load_graphml(graphml)

    # Edge жин нэмнэ (нэг удаа, бүх сценарийд ашиглана)
    traffic = cfg["traffic"]
    add_travel_time_weights(G, traffic["speed_peak_kmh"], traffic["speed_normal_kmh"])
    log.info("Edge жин нэмлээ (%d зангилаа, %d ирмэг)", G.number_of_nodes(), G.number_of_edges())

    dc       = cfg["dispatch"]
    sim      = cfg["simulation"]
    results  = []

    for sc in sim["scenarios"]:
        hour = sc["hour"]
        drivers, orders = generate_actors(
            G,
            n_drivers=dc["n_drivers"],
            n_orders=dc["n_orders"],
            seed=sim["random_seed"] + hour,
        )
        res = compare_dispatch(G, drivers, orders, hour, cfg)
        results.append(res)

    out = ensure_dir(cfg["paths"]["output_dir"])
    path = out / "dispatch_results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("Dispatch үр дүн → %s", path)