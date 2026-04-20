"""
04_smart_dispatch.py
Traffic-aware Smart Dispatch System for Ulaanbaatar

Энгийн (ойр жолооч) dispatch vs Smart (хурдан жолооч) dispatch харьцуулна.
Үр дүн → output/dispatch_results.json
"""

import os
import json
import random
import logging
import networkx as nx
import osmnx as ox
from dataclasses import dataclass, asdict
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Тохиргоо ──────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SPEED_PEAK   = 10   # km/h — оргил цагт
SPEED_NORMAL = 30   # km/h — ердийн цагт
RUSH_HOURS   = [(7, 9), (17, 19)]

N_DRIVERS    = 8    # нэг симуляцид жолооч
N_ORDERS     = 100  # нийт захиалга
RANDOM_SEED  = 42
# ──────────────────────────────────────────────────────────


@dataclass
class Driver:
    id:   str
    node: int       # графийн зангилаа
    lat:  float
    lon:  float


@dataclass
class Order:
    id:   str
    node: int
    lat:  float
    lon:  float


@dataclass
class DispatchResult:
    order_id:    str
    driver_id:   str
    eta_min:     float
    method:      str    # "random" | "smart"


# ── Туслах функцүүд ────────────────────────────────────────

def is_rush_hour(hour: int) -> bool:
    return any(s <= hour < e for s, e in RUSH_HOURS)


def get_speed(hour: int) -> float:
    return SPEED_PEAK if is_rush_hour(hour) else SPEED_NORMAL


def get_eta(G, from_node: int, to_node: int, speed_kmh: float) -> float:
    """
    Хоёр зангилааны хооронд богино замын ETA (минут) тооцооллоно.
    Граф холбоогүй бол Euclidean таамаглал ашиглана.
    """
    try:
        length_m = nx.shortest_path_length(
            G, from_node, to_node, weight="length"
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # Холбоогүй бол шулуун зайгаар тооцно
        n1 = G.nodes[from_node]
        n2 = G.nodes[to_node]
        dlat = (n1["y"] - n2["y"]) * 111_000
        dlon = (n1["x"] - n2["x"]) * 85_000
        length_m = (dlat**2 + dlon**2) ** 0.5

    eta_min = (length_m / 1000) / speed_kmh * 60
    return round(eta_min, 2)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Хоёр цэгийн шулуун зай (метр)"""
    import math
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(a ** 0.5)


# ── Dispatch стратегиуд ────────────────────────────────────

def nearest_dispatch(order: Order, drivers: List[Driver]) -> Driver:
    """
    Хуучин арга: шулуун зайгаар хамгийн ойр жолоочийг сонгоно.
    Замын нөхцөл, түгжрэл харгалздаггүй.
    """
    return min(
        drivers,
        key=lambda d: haversine_m(d.lat, d.lon, order.lat, order.lon)
    )


def smart_dispatch(order: Order, drivers: List[Driver],
                   G, hour: int) -> Tuple[Driver, float]:
    """
    Smart арга: бодит замын графаар ETA тооцоолж
    тухайн агшинд хамгийн хурдан хүрэх жолоочийг сонгоно.
    """
    speed = get_speed(hour)
    best_driver, best_eta = None, float("inf")

    for driver in drivers:
        eta = get_eta(G, driver.node, order.node, speed)
        if eta < best_eta:
            best_eta, best_driver = eta, driver

    return best_driver, round(best_eta, 2)


# ── Симуляци ──────────────────────────────────────────────

def generate_actors(G, n_drivers: int, n_orders: int,
                    seed: int) -> Tuple[List[Driver], List[Order]]:
    """Жолооч болон захиалгыг графийн зангилаан дээр байршуулна"""
    random.seed(seed)
    nodes = list(G.nodes(data=True))

    def make_driver(i):
        nid, data = random.choice(nodes)
        return Driver(id=f"D{i:02d}", node=nid,
                      lat=data["y"], lon=data["x"])

    def make_order(i):
        nid, data = random.choice(nodes)
        return Order(id=f"O{i:03d}", node=nid,
                     lat=data["y"], lon=data["x"])

    drivers = [make_driver(i) for i in range(n_drivers)]
    orders  = [make_order(i)  for i in range(n_orders)]
    return drivers, orders


def run_comparison(G, drivers: List[Driver],
                   orders: List[Order], hour: int):
    """
    100 захиалгад хоёр аргыг харьцуулж
    дундаж ETA болон хэмнэлтийг тооцооллоно.
    """
    speed = get_speed(hour)
    label = "оргил цаг" if is_rush_hour(hour) else "ердийн цаг"
    log.info("Харьцуулалт эхэллээ — %s (цаг %02d:00)", label, hour)

    nearest_etas, smart_etas = [], []

    for order in orders:
        # ── Ойр жолооч (хуучин арга) ──
        nd = nearest_dispatch(order, drivers)
        n_eta = get_eta(G, nd.node, order.node, speed)
        nearest_etas.append(n_eta)

        # ── Smart dispatch (манай арга) ──
        sd, s_eta = smart_dispatch(order, drivers, G, hour)
        smart_etas.append(s_eta)

    avg_nearest = sum(nearest_etas) / len(nearest_etas)
    avg_smart   = sum(smart_etas)   / len(smart_etas)
    improvement = (avg_nearest - avg_smart) / avg_nearest * 100

    result = {
        "hour"              : hour,
        "scenario"          : label,
        "n_orders"          : len(orders),
        "avg_nearest_min"   : round(avg_nearest, 2),
        "avg_smart_min"     : round(avg_smart, 2),
        "improvement_pct"   : round(improvement, 1),
    }

    log.info("  Ойр dispatch дундаж ETA : %.1f мин", avg_nearest)
    log.info("  Smart dispatch дундаж ETA: %.1f мин", avg_smart)
    log.info("  ✅ Хэмнэлт               : %.1f%%", improvement)

    return result


def run_all_scenarios(G):
    """Оргил болон ердийн цагийн хоёр сценарийг ажиллуулна"""
    results = []

    for hour in [8, 14]:   # 08:00 оргил | 14:00 ердийн
        drivers, orders = generate_actors(
            G, N_DRIVERS, N_ORDERS, seed=RANDOM_SEED + hour
        )
        res = run_comparison(G, drivers, orders, hour)
        results.append(res)

    return results


def save_results(results):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "dispatch_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("Үр дүн хадгаллаа → %s", path)


def print_summary(results):
    log.info("=" * 45)
    log.info("  DISPATCH ХАРЬЦУУЛАЛТЫН ДҮГНЭЛТ")
    log.info("=" * 45)
    for r in results:
        log.info(
            "  %s | Ойр: %.1f мин → Smart: %.1f мин | Хэмнэлт: %.1f%%",
            r["scenario"].upper(),
            r["avg_nearest_min"],
            r["avg_smart_min"],
            r["improvement_pct"],
        )
    log.info("=" * 45)


def main():
    graphml = os.path.join(DATA_DIR, "sukhbaatar.graphml")

    if not os.path.exists(graphml):
        log.error("GraphML олдсонгүй. Эхлээд 01_fetch_osm.py ажиллуулна уу.")
        return

    log.info("Граф ачааллаж байна...")
    G = ox.load_graphml(graphml)
    log.info("Зангилаа: %d | Ирмэг: %d", len(G.nodes), len(G.edges))

    results = run_all_scenarios(G)
    print_summary(results)
    save_results(results)

    log.info("04_smart_dispatch.py дууслаа")


if __name__ == "__main__":
    main()