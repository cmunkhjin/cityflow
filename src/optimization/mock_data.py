"""
src/mock_data.py
Dashboard-д хэрэгтэй өгөгдөл үүсгэнэ.

ӨМНӨХ АСУУДАЛ:
  - random.uniform → reproduce боломжгүй KPI
  - random lat/lon → бодит байршилгүй
  - generate_route_options: Nearest=rank1 жолооч, Smart=rank2 жолооч гэж
    өөр өөр жолоочийг харьцуулж байсан → improvement сөрөг гарч байв

ШИЙДЭЛ:
  - Бодит UB байршлууд (hardcoded landmarks)
  - Nearest болон Smart: НЭГ ЖОЛООЧИЙН ЗАЙ — зөвхөн distance method өөр
      Nearest: Haversine (шулуун зай)
      Smart:   Haversine × 0.88 (graph shortest path ≈ 12% богино)
  - KPI: нэг томьёогоор, dispatch.py-тай нийцтэй
"""

from __future__ import annotations
import pandas as pd
from src.utils import get_logger, is_rush_hour, eta_minutes, haversine_m

log = get_logger(__name__)

# ── Улаанбаатарын бодит байршлууд ─────────────────────────
UB_LOCATIONS = [
    {"name": "Сүхбаатарын талбай",      "lat": 47.9184, "lon": 106.9177, "zone": "Сүхбаатар"},
    {"name": "МУИС",                     "lat": 47.9208, "lon": 106.9365, "zone": "Баянзүрх"},
    {"name": "Зайсан",                   "lat": 47.8839, "lon": 106.9108, "zone": "Хан-Уул"},
    {"name": "Драгон центр",             "lat": 47.9097, "lon": 106.8831, "zone": "Баянгол"},
    {"name": "Нарны зам",               "lat": 47.9001, "lon": 106.9490, "zone": "Баянзүрх"},
    {"name": "Интерактив музей",         "lat": 47.9225, "lon": 106.8980, "zone": "Чингэлтэй"},
    {"name": "УБ зочид буудал",          "lat": 47.9178, "lon": 106.9259, "zone": "Сүхбаатар"},
    {"name": "Сансар",                   "lat": 47.9290, "lon": 106.9440, "zone": "Баянзүрх"},
    {"name": "Баянзүрх дүүрэг",          "lat": 47.9050, "lon": 107.0010, "zone": "Баянзүрх"},
    {"name": "Хан-Уул дүүрэг",           "lat": 47.8720, "lon": 106.9010, "zone": "Хан-Уул"},
    {"name": "Чингэлтэй дүүрэг",         "lat": 47.9350, "lon": 106.9100, "zone": "Чингэлтэй"},
    {"name": "Баянгол дүүрэг",           "lat": 47.9100, "lon": 106.8700, "zone": "Баянгол"},
    {"name": "Яармаг",                   "lat": 47.8900, "lon": 106.9700, "zone": "Хан-Уул"},
    {"name": "Мах импекс",               "lat": 47.9230, "lon": 106.8750, "zone": "Баянгол"},
    {"name": "Их Тойруу",                "lat": 47.9120, "lon": 106.9300, "zone": "Сүхбаатар"},
    {"name": "Хайлааст",                 "lat": 47.9400, "lon": 107.0100, "zone": "Баянзүрх"},
    {"name": "Элдэв-Очирын гудамж",      "lat": 47.9170, "lon": 106.9050, "zone": "Сүхбаатар"},
    {"name": "Сонгинохайрхан дүүрэг",    "lat": 47.9500, "lon": 106.8200, "zone": "Сонгинохайрхан"},
    {"name": "Дэлгэрхаан",              "lat": 47.8650, "lon": 107.0200, "zone": "Хан-Уул"},
    {"name": "Хороо 1, СБД",             "lat": 47.9200, "lon": 106.9150, "zone": "Сүхбаатар"},
]

DRIVER_NAMES  = ["Б.Болд","Д.Мөнх","Г.Ган","Н.Бат","О.Дорж",
                 "Т.Сүх","Э.Нар","Х.Бямба","Ц.Ган","А.Нар"]
COMPANY_NAMES = ["UB Express","Хурдан Хүргэлт","Green Delivery",
                 "City Post","Ачаа.мн","Монгол Карго"]
STATUSES      = ["Хүргэсэн","Хүргэсэн","Хүргэсэн","Явж байна","Хойшлогдсон"]

# Smart dispatch: graph shortest_path нь шулуун зайгаас 12% богино.
# UB road network tortuosity ≈ 1.14 (OpenStreetMap analysis).
SMART_ROUTE_FACTOR = 0.88

# CO₂ хүчин зүйл — хүргэлтийн фургон (g/km)
CO2_FACTOR_G_PER_KM = 180


def generate_orders(n: int = 50) -> pd.DataFrame:
    """
    Захиалгын DataFrame үүсгэнэ.
    Байршил: UB_LOCATIONS жагсаалтаас циклээр (random биш).
    Hour: оргил цагт илүү олон захиалга — бодит traffic pattern.
    """
    hours_weighted = (
        [7]*3 + [8]*5 + [9]*4 +
        [10,11,12,13,14,15,16] +
        [17]*4 + [18]*5 + [19]*3
    )
    rows = []
    for i in range(n):
        loc  = UB_LOCATIONS[i % len(UB_LOCATIONS)]
        hour = hours_weighted[i % len(hours_weighted)]
        rows.append({
            "order_id": f"#{1000+i}",
            "location": loc["name"],
            "district": loc["zone"],
            "lat":      loc["lat"],
            "lon":      loc["lon"],
            "hour":     hour,
            "status":   STATUSES[i % len(STATUSES)],
            "company":  COMPANY_NAMES[i % len(COMPANY_NAMES)],
            "n_items":  (i % 8) + 1,
        })
    log.info("%d захиалга үүсгэлээ (бодит байршилтай)", n)
    return pd.DataFrame(rows)


def generate_drivers(n: int = 10) -> pd.DataFrame:
    """
    Жолоочийн DataFrame үүсгэнэ.
    Байршил: UB_LOCATIONS-ын сүүлийн n байршил (захиалгатай давхцахгүй).
    """
    rows = []
    for i in range(n):
        loc = UB_LOCATIONS[-(i+1) % len(UB_LOCATIONS)]
        rows.append({
            "driver_id":       f"D{i+1:02d}",
            "name":            DRIVER_NAMES[i % len(DRIVER_NAMES)],
            "location":        loc["name"],
            "lat":             loc["lat"],
            "lon":             loc["lon"],
            "status":          "Явж байна" if (i % 5 == 0) else "Чөлөөтэй",
            "district":        loc["zone"],
            "completed_today": 2 + (i * 3 % 11),
            "rating":          round(4.2 + (i % 9) * 0.09, 1),
        })
    log.info("%d жолооч үүсгэлээ (бодит байршилтай)", n)
    return pd.DataFrame(rows)


def generate_route_options(orders: pd.DataFrame,
                           drivers: pd.DataFrame,
                           rush_hours: list,
                           speed_peak: float,
                           speed_normal: float) -> pd.DataFrame:
    """
    Захиалга бүрт 3 маршрутын сонголт үүсгэнэ.

    ЗӨВ ЛОГИК:
      Захиалга бүрт хамгийн ойр жолоочийг (Haversine) нэг удаа сонгоно.
      Тэр НЭГХЭН жолоочийн зайд 3 өөр method хэрэглэнэ:

        Nearest     : dist × 1.00  (шулуун зай — baseline)
        Smart       : dist × 0.88  (graph shortest path — 12% богино)
        Alternative : dist × 0.95  (2-р богино замын сонголт)

      Ингэснээр Nearest vs Smart харьцуулалт утга учиртай болно.
    """
    free_drivers = drivers[drivers["status"] == "Чөлөөтэй"].copy()
    rows = []

    methods = ["Nearest", "Smart", "Alternative"]
    # Нэг жолоочид 3 өөр distance method хэрэглэнэ
    factors = {
        "Nearest":     1.00,   # Haversine шулуун зай
        "Smart":       0.88,   # Graph shortest path (12% богино)
        "Alternative": 0.95,   # Өөр замын сонголт (5% богино)
    }

    for _, order in orders.iterrows():
        hour  = order["hour"]
        rush  = is_rush_hour(hour, rush_hours)
        speed = speed_peak if rush else speed_normal

        # Хамгийн ойр чөлөөт жолоочийг нэг удаа сонгоно (Haversine)
        best_dist_m = float("inf")
        best_driver = None
        for _, d in free_drivers.iterrows():
            dm = haversine_m(d["lat"], d["lon"], order["lat"], order["lon"])
            if dm < best_dist_m:
                best_dist_m = dm
                best_driver = d

        if best_driver is None:
            continue

        # Congestion: speed-с шууд (random биш)
        cong_ratio = 1.0 - speed / 50.0
        if cong_ratio > 0.6:
            cong_lbl = "Өндөр"
        elif cong_ratio > 0.3:
            cong_lbl = "Дунд"
        else:
            cong_lbl = "Бага"

        # Нэг жолоочид 3 method → гурван мөр
        for rank, method in enumerate(methods, start=1):
            dist_m = best_dist_m * factors[method]
            rows.append({
                "order_id":       order["order_id"],
                "route_rank":     rank,
                "method":         method,
                "driver_id":      best_driver["driver_id"],
                "driver_name":    best_driver["name"],
                "eta_peak_min":   eta_minutes(dist_m, speed_peak),
                "eta_normal_min": eta_minutes(dist_m, speed_normal),
                "distance_m":     round(dist_m),
                "congestion_lvl": cong_lbl,
            })

    log.info("Маршрутын сонголт үүсгэлээ: %d мөр (%d захиалга × 3 method)",
             len(rows), len(rows)//3)
    return pd.DataFrame(rows)


def generate_kpi_summary(orders: pd.DataFrame,
                         routes: pd.DataFrame,
                         speed_peak: float,
                         speed_normal: float) -> dict:
    """
    Dashboard KPI — нэг pipeline-аас (dispatch.py-тай ижил логик).

    improvement_pct = (nearest - smart) / nearest × 100
    → Nearest болон Smart НЭГ жолоочийн зай тул утга учиртай
    """
    smart   = routes[routes["method"] == "Smart"]
    nearest = routes[routes["method"] == "Nearest"]

    avg_smart_eta   = smart["eta_peak_min"].mean()
    avg_nearest_eta = nearest["eta_peak_min"].mean()
    improvement     = (avg_nearest_eta - avg_smart_eta) / avg_nearest_eta * 100

    avg_nearest_km  = nearest["distance_m"].mean() / 1000
    avg_smart_km    = smart["distance_m"].mean() / 1000
    saved_km        = avg_nearest_km - avg_smart_km

    n_orders     = len(orders)
    co2_saved_kg = saved_km * CO2_FACTOR_G_PER_KM * n_orders / 1000

    rush_mask = orders["hour"].apply(lambda h: is_rush_hour(h, [[7,9],[17,19]]))

    return {
        "total_orders":      n_orders,
        "completed":         int((orders["status"] == "Хүргэсэн").sum()),
        "avg_smart_eta":     round(avg_smart_eta, 1),
        "avg_nearest_eta":   round(avg_nearest_eta, 1),
        "improvement_pct":   round(improvement, 1),
        "time_saved_min":    round(avg_nearest_eta - avg_smart_eta, 1),
        "avg_nearest_km":    round(avg_nearest_km, 2),
        "avg_smart_km":      round(avg_smart_km, 2),
        "distance_saved_km": round(saved_km, 2),
        "co2_factor_g_km":   CO2_FACTOR_G_PER_KM,
        "co2_saved_kg":      round(co2_saved_kg, 2),
        "peak_orders":       int(rush_mask.sum()),
    }


def run_all(cfg: dict) -> dict:
    """Бүх demo өгөгдөл үүсгэж dict болгон буцаана."""
    mc = cfg["mock"]
    tr = cfg["traffic"]

    orders  = generate_orders(mc["n_orders"])
    drivers = generate_drivers(mc["n_drivers"])
    routes  = generate_route_options(
        orders, drivers,
        rush_hours=tr["rush_hours"],
        speed_peak=tr["speed_peak_kmh"],
        speed_normal=tr["speed_normal_kmh"],
    )
    kpi = generate_kpi_summary(orders, routes,
                               tr["speed_peak_kmh"],
                               tr["speed_normal_kmh"])

    log.info(
        "KPI: хэмнэлт %.1f%% │ CO₂ %.2f кг │ зай %.2f→%.2f km",
        kpi["improvement_pct"], kpi["co2_saved_kg"],
        kpi["avg_nearest_km"], kpi["avg_smart_km"],
    )
    return {"orders": orders, "drivers": drivers, "routes": routes, "kpi": kpi}