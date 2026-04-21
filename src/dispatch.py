"""
src/optimization/dispatch.py
Traffic-aware route optimization + smart dispatch.

Алгоритм:
  - Weighted shortest path (Dijkstra/A*)
  - Edge weight = travel_time + congestion_penalty
  - 3 маршрут харьцуулалт
  - Smart vs Nearest dispatch харьцуулалт
"""

from __future__ import annotations
import json
import random
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import networkx as nx
import osmnx as ox

from src.utils import get_logger, ensure_dir, haversine_m, eta_minutes, is_rush_hour

log = get_logger(__name__)


# ── Өгөгдлийн бүтэц ───────────────────────────────────────

@dataclass
class Driver:
    id:   str
    name: str
    node: int
    lat:  float
    lon:  float
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
    """Нэг маршрутын сонголт."""
    rank:          int
    weight_type:   str     # "distance" | "normal" | "peak"
    path_length_m: float
    eta_min:       float
    n_nodes:       int


@dataclass
class DispatchRecord:
    order_id:      str
    method:        str     # "nearest" | "smart"
    driver_id:     str
    eta_min:       float
    best_route:    dict


# ── Граф жин ──────────────────────────────────────────────

def get_weight_key(hour: int, rush_hours: list) -> str:
    """
    Тухайн цагт ямар жин ашиглах.

    Args:
        hour:       0-23
        rush_hours: [[7,9],[17,19]]

    Returns:
        "weight_peak" | "weight_normal"
    """
    return "weight_peak" if is_rush_hour(hour, rush_hours) else "weight_normal"


# ── Multi-route comparison ────────────────────────────────

def get_multi_routes(G, from_node: int, to_node: int,
                     hour: int, rush_hours: list,
                     speed_kmh: float) -> list[RouteOption]:
    """
    3 өөр жингээр маршрут тооцоолж харьцуулна.

    Args:
        G:          osmnx граф (жин нэмсэн)
        from_node:  эхлэлийн зангилаа
        to_node:    очих зангилаа
        hour:       тухайн цаг
        rush_hours: оргил цагийн мужууд
        speed_kmh:  тухайн цагийн хурд

    Returns:
        RouteOption жагсаалт (3 маршрут)
    """
    options = []
    configs = [
        ("distance",     "length"),
        ("normal",       "weight_normal"),
        ("peak",         "weight_peak"),
    ]

    for rank, (label, weight) in enumerate(configs, start=1):
        try:
            path = nx.shortest_path(G, from_node, to_node, weight=weight)
            length_m = sum(
                G[u][v][0].get("length", 50)
                for u, v in zip(path[:-1], path[1:])
            )
            eta = eta_minutes(length_m, speed_kmh)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Холбоогүй бол Euclidean таамаглал
            n1, n2 = G.nodes[from_node], G.nodes[to_node]
            length_m = haversine_m(n1["y"], n1["x"], n2["y"], n2["x"])
            eta      = eta_minutes(length_m, speed_kmh)
            path     = [from_node, to_node]

        options.append(RouteOption(
            rank          = rank,
            weight_type   = label,
            path_length_m = round(length_m, 1),
            eta_min       = eta,
            n_nodes       = len(path),
        ))

    return options


def best_route(routes: list[RouteOption]) -> RouteOption:
    """ETA хамгийн бага маршрутыг буцаана."""
    return min(routes, key=lambda r: r.eta_min)


# ── ETA нэг жолоочид ──────────────────────────────────────

def get_driver_eta(G, driver: Driver, order: Order,
                   speed_kmh: float, rush_hours: list,
                   hour: int) -> float:
    """
    Жолоочоос захиалга руу ETA тооцооллоно.
    Графийн shortest path эсвэл Euclidean fallback.

    Args:
        G:          граф
        driver:     жолоочийн мэдээлэл
        order:      захиалгын мэдээлэл
        speed_kmh:  тухайн цагийн хурд
        rush_hours: оргил цагийн мужууд
        hour:       тухайн цаг

    Returns:
        ETA минутаар
    """
    weight = get_weight_key(hour, rush_hours)
    try:
        length_m = nx.shortest_path_length(
            G, driver.node, order.node, weight=weight
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        length_m = haversine_m(driver.lat, driver.lon,
                               order.lat,  order.lon)
    return eta_minutes(length_m, speed_kmh)


# ── Dispatch стратегиуд ────────────────────────────────────

def nearest_dispatch(order: Order, drivers: list[Driver]) -> Driver:
    """
    Шулуун зайгаар хамгийн ойр чөлөөт жолоочийг сонгоно.
    (Хуучин арга — харьцуулалтад ашиглана)

    Args:
        order:   захиалга
        drivers: жолоочдын жагсаалт

    Returns:
        Сонгогдсон Driver
    """
    free = [d for d in drivers if d.free]
    if not free:
        raise ValueError("Чөлөөт жолооч байхгүй")
    return min(free,
               key=lambda d: haversine_m(d.lat, d.lon, order.lat, order.lon))


def smart_dispatch(order: Order, drivers: list[Driver],
                   G, hour: int, rush_hours: list,
                   speed_kmh: float) -> tuple[Driver, float]:
    """
    Замын графаар бодит ETA тооцоолж хамгийн хурдан жолоочийг сонгоно.

    Args:
        order:      захиалга
        drivers:    жолоочдын жагсаалт
        G:          осмнx граф
        hour:       тухайн цаг
        rush_hours: оргил цагийн мужууд
        speed_kmh:  тухайн цагийн хурд

    Returns:
        (Сонгогдсон Driver, ETA минут)
    """
    free = [d for d in drivers if d.free]
    if not free:
        raise ValueError("Чөлөөт жолооч байхгүй")

    best, best_eta = None, float("inf")
    for d in free:
        eta = get_driver_eta(G, d, order, speed_kmh, rush_hours, hour)
        if eta < best_eta:
            best_eta, best = eta, d

    return best, round(best_eta, 2)


# ── Харьцуулалт ───────────────────────────────────────────

def compare_dispatch(G, drivers: list[Driver], orders: list[Order],
                     hour: int, cfg: dict) -> dict:
    """
    N захиалгад nearest vs smart dispatch харьцуулж,
    хэмнэлт тооцооллоно.

    Args:
        G:       граф
        drivers: жолоочдын жагсаалт
        orders:  захиалгын жагсаалт
        hour:    тухайн цаг
        cfg:     settings.yaml dict

    Returns:
        Харьцуулалтын дүн dict
    """
    traffic    = cfg["traffic"]
    rush_hours = traffic["rush_hours"]
    rush       = is_rush_hour(hour, rush_hours)
    speed      = (traffic["speed_peak_kmh"] if rush
                  else traffic["speed_normal_kmh"])
    label      = "Оргил цаг" if rush else "Ердийн цаг"

    nearest_etas, smart_etas = [], []

    for order in orders:
        nd      = nearest_dispatch(order, drivers)
        n_dist  = haversine_m(nd.lat, nd.lon, order.lat, order.lon)
        n_eta   = eta_minutes(n_dist, speed)
        nearest_etas.append(n_eta)

        sd, s_eta = smart_dispatch(order, drivers, G, hour, rush_hours, speed)
        smart_etas.append(s_eta)

    avg_n = sum(nearest_etas) / len(nearest_etas)
    avg_s = sum(smart_etas)   / len(smart_etas)
    impr  = (avg_n - avg_s) / avg_n * 100

    result = {
        "hour":               hour,
        "scenario":           label,
        "n_orders":           len(orders),
        "avg_nearest_min":    round(avg_n, 2),
        "avg_smart_min":      round(avg_s, 2),
        "improvement_pct":    round(impr, 1),
        "time_saved_min":     round(avg_n - avg_s, 2),
    }
    log.info("%-12s │ Ойр: %.1f мин → Smart: %.1f мин │ ↓%.1f%%",
             label, avg_n, avg_s, impr)
    return result


# ── Actor үүсгэх (граф дээр) ─────────────────────────────

def generate_actors(G, n_drivers: int, n_orders: int,
                    seed: int) -> tuple[list[Driver], list[Order]]:
    """
    Графийн зангилаан дээр жолооч, захиалга санамсаргүй байршуулна.

    Args:
        G:         граф
        n_drivers: жолоочийн тоо
        n_orders:  захиалгын тоо
        seed:      random seed

    Returns:
        (drivers жагсаалт, orders жагсаалт)
    """
    random.seed(seed)
    nodes = list(G.nodes(data=True))

    NAMES = ["Б.Болд","Д.Мөнх","Г.Ган","Н.Бат",
             "О.Дорж","Т.Сүх","Э.Нар","Х.Бямба",
             "Ц.Ган","А.Нар"]
    ZONES = ["Сүхбаатар","Баянзүрх","Чингэлтэй",
             "Баянгол","Хан-Уул","Сонгинохайрхан"]

    drivers = []
    for i in range(n_drivers):
        nid, data = random.choice(nodes)
        drivers.append(Driver(
            id=f"D{i+1:02d}", name=NAMES[i % len(NAMES)],
            node=nid, lat=data["y"], lon=data["x"],
            free=random.random() > 0.2,
        ))

    orders = []
    for i in range(n_orders):
        nid, data = random.choice(nodes)
        orders.append(Order(
            id=f"#{1000+i}", node=nid,
            lat=data["y"], lon=data["x"],
            zone=random.choice(ZONES),
        ))

    return drivers, orders


# ── Pipeline entry point ───────────────────────────────────

def run(cfg: dict) -> None:
    """
    Config-оор бүтэн dispatch pipeline ажиллуулна.

    Args:
        cfg: settings.yaml dict
    """
    graphml = cfg["paths"]["graphml"]
    if not Path(graphml).exists():
        log.error("GraphML олдсонгүй. Эхлээд fetch + build ажиллуулна уу.")
        return

    G = ox.load_graphml(graphml)

    dc   = cfg["dispatch"]
    sim  = cfg["simulation"]
    results = []

    for sc in sim["scenarios"]:
        hour = sc["hour"]
        drivers, orders = generate_actors(
            G, dc["n_drivers"], dc["n_orders"],
            seed=sim["random_seed"] + hour,
        )
        res = compare_dispatch(G, drivers, orders, hour, cfg)
        results.append(res)

    out = ensure_dir(cfg["paths"]["output_dir"])
    path = out / "dispatch_results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("Dispatch үр дүн → %s", path)