"""
src/optimization/mock_data.py
Demo-д зориулсан бодитой mock өгөгдөл үүсгэнэ.
"""

from __future__ import annotations
import random
import math
import pandas as pd
from src.utils import get_logger, is_rush_hour, eta_minutes, haversine_m

log = get_logger(__name__)

UB_CENTER  = (47.9184, 106.9177)
RADIUS_DEG = 0.025

DRIVER_NAMES = ["Б.Болд","Д.Мөнх","Г.Ган","Н.Бат","О.Дорж",
                "Т.Сүх","Э.Нар","Х.Бямба","Ц.Ган","А.Нар"]
COMPANY_NAMES = ["UB Express","Хурдан Хүргэлт","Green Delivery",
                 "City Post","Ачаа.мн","Монгол Карго"]
DISTRICTS = ["Сүхбаатар","Баянзүрх","Чингэлтэй",
             "Баянгол","Хан-Уул","Сонгинохайрхан"]
STATUSES  = ["Хүргэсэн","Хүргэсэн","Хүргэсэн","Явж байна","Хойшлогдсон"]


def _rand_point(seed_offset: int = 0) -> tuple[float, float]:
    lat = UB_CENTER[0] + random.uniform(-RADIUS_DEG, RADIUS_DEG)
    lon = UB_CENTER[1] + random.uniform(-RADIUS_DEG * 1.4, RADIUS_DEG * 1.4)
    return lat, lon


def generate_orders(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """
    Захиалгын mock DataFrame үүсгэнэ.

    Args:
        n:    захиалгын тоо
        seed: random seed

    Returns:
        DataFrame — id, district, lat, lon, hour,
                    status, company, n_items
    """
    random.seed(seed)
    rows = []
    for i in range(n):
        lat, lon = _rand_point(i)
        hour = random.choice([7,7,8,8,9,10,11,12,13,14,15,16,17,17,18,18,19])
        rows.append({
            "order_id": f"#{1000+i}",
            "district": random.choice(DISTRICTS),
            "lat":      round(lat, 6),
            "lon":      round(lon, 6),
            "hour":     hour,
            "status":   random.choice(STATUSES),
            "company":  random.choice(COMPANY_NAMES),
            "n_items":  random.randint(1, 8),
        })
    log.info("%d захиалга үүсгэлээ", n)
    return pd.DataFrame(rows)


def generate_drivers(n: int = 10, seed: int = 42) -> pd.DataFrame:
    """
    Жолоочийн mock DataFrame үүсгэнэ.

    Args:
        n:    жолоочийн тоо
        seed: random seed

    Returns:
        DataFrame — id, name, lat, lon, status, district,
                    completed_today, rating
    """
    random.seed(seed + 1)
    rows = []
    for i in range(n):
        lat, lon = _rand_point(i + 100)
        rows.append({
            "driver_id":       f"D{i+1:02d}",
            "name":            DRIVER_NAMES[i % len(DRIVER_NAMES)],
            "lat":             round(lat, 6),
            "lon":             round(lon, 6),
            "status":          random.choice(["Чөлөөтэй","Чөлөөтэй","Явж байна"]),
            "district":        random.choice(DISTRICTS),
            "completed_today": random.randint(2, 12),
            "rating":          round(random.uniform(4.2, 5.0), 1),
        })
    log.info("%d жолооч үүсгэлээ", n)
    return pd.DataFrame(rows)


def generate_route_options(orders: pd.DataFrame,
                           drivers: pd.DataFrame,
                           rush_hours: list,
                           speed_peak: float,
                           speed_normal: float,
                           seed: int = 42) -> pd.DataFrame:
    """
    Захиалга бүрт 3 маршрутын сонголт үүсгэнэ.
    Nearest, Smart, Alternative гэсэн гурван арга.

    Args:
        orders:       захиалгын DataFrame
        drivers:      жолоочийн DataFrame
        rush_hours:   [[7,9],[17,19]]
        speed_peak:   оргил цагийн хурд km/h
        speed_normal: ердийн цагийн хурд km/h
        seed:         random seed

    Returns:
        DataFrame — order_id, route_rank, method,
                    driver_id, eta_peak_min, eta_normal_min,
                    distance_m, congestion_lvl
    """
    random.seed(seed + 2)
    rows = []
    free_drivers = drivers[drivers["status"] == "Чөлөөтэй"]

    for _, order in orders.iterrows():
        hour  = order["hour"]
        rush  = is_rush_hour(hour, rush_hours)
        speed = speed_peak if rush else speed_normal

        dists = []
        for _, d in free_drivers.iterrows():
            dm = haversine_m(d["lat"], d["lon"], order["lat"], order["lon"])
            dists.append((dm, d))

        dists.sort(key=lambda x: x[0])
        top3 = dists[:3] if len(dists) >= 3 else dists

        methods = ["Nearest","Smart","Alternative"]
        for rank, (dist_m, drv) in enumerate(top3, start=1):
            # Smart: замын жингээр 10-20% богино
            factor  = 1.0 if rank==1 else random.uniform(0.80, 0.92)
            real_dm = dist_m * factor * random.uniform(0.95, 1.05)

            eta_peak   = eta_minutes(real_dm, speed_peak)
            eta_normal = eta_minutes(real_dm, speed_normal)
            cong       = random.choice(["Өндөр","Дунд","Бага"]) if rush else "Бага"

            rows.append({
                "order_id":      order["order_id"],
                "route_rank":    rank,
                "method":        methods[rank-1],
                "driver_id":     drv["driver_id"],
                "driver_name":   drv["name"],
                "eta_peak_min":  eta_peak,
                "eta_normal_min":eta_normal,
                "distance_m":    round(real_dm),
                "congestion_lvl":cong,
            })

    log.info("Маршрутын сонголт үүсгэлээ: %d мөр", len(rows))
    return pd.DataFrame(rows)


def generate_kpi_summary(orders: pd.DataFrame,
                         routes: pd.DataFrame,
                         speed_peak: float,
                         speed_normal: float) -> dict:
    """
    Dashboard-д хэрэгтэй KPI тооцооллоно.

    Args:
        orders:       захиалгын DataFrame
        routes:       маршрутын DataFrame
        speed_peak:   оргил цагийн хурд
        speed_normal: ердийн цагийн хурд

    Returns:
        KPI dict
    """
    smart   = routes[routes["method"] == "Smart"]
    nearest = routes[routes["method"] == "Nearest"]

    avg_smart   = smart["eta_peak_min"].mean()
    avg_nearest = nearest["eta_peak_min"].mean()
    improvement = (avg_nearest - avg_smart) / avg_nearest * 100

    # CO₂ хэмнэлт: дундаж авто 120g/km
    avg_dist_km  = routes[routes["method"]=="Smart"]["distance_m"].mean() / 1000
    saved_km     = (routes[routes["method"]=="Nearest"]["distance_m"].mean()
                    - routes[routes["method"]=="Smart"]["distance_m"].mean()) / 1000
    co2_saved_g  = saved_km * 120 * len(orders)

    return {
        "total_orders":      len(orders),
        "completed":         int((orders["status"] == "Хүргэсэн").sum()),
        "avg_smart_eta":     round(avg_smart, 1),
        "avg_nearest_eta":   round(avg_nearest, 1),
        "improvement_pct":   round(improvement, 1),
        "time_saved_min":    round(avg_nearest - avg_smart, 1),
        "co2_saved_kg":      round(co2_saved_g / 1000, 2),
        "peak_orders":       int((orders["hour"].apply(
                                 lambda h: is_rush_hour(h, [[7,9],[17,19]]))).sum()),
    }


def run_all(cfg: dict) -> dict:
    """
    Бүх mock өгөгдөл үүсгэж dict болгон буцаана.

    Args:
        cfg: settings.yaml dict

    Returns:
        {orders, drivers, routes, kpi} dict
    """
    mc = cfg["mock"]
    tr = cfg["traffic"]

    orders  = generate_orders(mc["n_orders"])
    drivers = generate_drivers(mc["n_drivers"])
    routes  = generate_route_options(
        orders, drivers,
        rush_hours   = tr["rush_hours"],
        speed_peak   = tr["speed_peak_kmh"],
        speed_normal = tr["speed_normal_kmh"],
    )
    kpi = generate_kpi_summary(orders, routes,
                               tr["speed_peak_kmh"],
                               tr["speed_normal_kmh"])
    log.info("KPI: хэмнэлт %.1f%% | CO₂ %.2f кг хэмнэлт",
             kpi["improvement_pct"], kpi["co2_saved_kg"])
    return {"orders": orders, "drivers": drivers,
            "routes": routes, "kpi": kpi}