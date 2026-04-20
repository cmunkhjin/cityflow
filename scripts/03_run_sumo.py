"""
03_run_sumo.py
SUMO симуляци ажиллуулж, оргил болон ердийн цагийг харьцуулна.
Гаралтыг output/simulation_results.json-д хадгална.
"""

import os
import json
import random
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Тохиргоо ──────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CFG_PATH   = os.path.join(BASE_DIR, "scripts", "sukhbaatar.sumocfg")

SPEED_PEAK   = 10   # km/h — оргил цагийн дундаж хурд
SPEED_NORMAL = 30   # km/h — ердийн цагийн дундаж хурд

N_VEHICLES   = 50   # симуляцийн тээврийн хэрэгслийн тоо
SIM_DURATION = 3600 # секунд (1 цаг)
RANDOM_SEED  = 42
# ──────────────────────────────────────────────────────────


@dataclass
class Vehicle:
    id:          str
    depart:      float          # симуляцийн эхлэлээс хэдэн секундад гарах
    route:       List[str]      # зангилааны жагсаалт
    travel_time: float = 0.0   # дуусгасан хугацаа (сек)
    arrived:     bool  = False


@dataclass
class SimResult:
    scenario:          str
    speed_kmh:         float
    n_vehicles:        int
    avg_travel_time_s: float
    avg_travel_time_m: float
    arrived_pct:       float
    vehicles:          List[dict] = field(default_factory=list)


def load_net_xml(data_dir: str):
    """net.xml-аас edge жагсаалт унших"""
    net_path = os.path.join(data_dir, "sukhbaatar.net.xml")
    if not os.path.exists(net_path):
        log.warning("net.xml олдсонгүй — mock edge ашиглана")
        return [f"edge_{i}" for i in range(200)]

    tree = ET.parse(net_path)
    root = tree.getroot()
    edges = [e.get("id") for e in root.findall("edge")
             if not e.get("id", "").startswith(":")]
    log.info("net.xml-аас %d edge уншлаа", len(edges))
    return edges


def generate_vehicles(edges: List[str], n: int, seed: int) -> List[Vehicle]:
    """Санамсаргүй маршруттай тээврийн хэрэгсэл үүсгэнэ"""
    random.seed(seed)
    vehicles = []
    for i in range(n):
        route_len = random.randint(3, 10)
        route = random.sample(edges, min(route_len, len(edges)))
        depart = random.uniform(0, SIM_DURATION * 0.5)
        vehicles.append(Vehicle(id=f"veh_{i:03d}", depart=depart, route=route))
    return vehicles


def simulate_scenario(vehicles: List[Vehicle], speed_kmh: float, label: str) -> SimResult:
    """
    Хялбарчилсан симуляци:
    Зам урт × хурд → travel_time
    SUMO суулгасан бол traci ашиглан бодит симуляци хийж болно.
    """
    log.info("Симуляци: %s  |  Хурд: %d km/h", label, speed_kmh)

    arrived = 0
    total_time = 0.0
    results = []

    for veh in vehicles:
        # Маршрутын нийт урт (mock: edge тус бүр 200–600м)
        distance_m = sum(random.uniform(200, 600) for _ in veh.route)

        # Travel time + бага зэрэг хувьсал (бодит нөхцөл дуурайлга)
        base_time = (distance_m / 1000) / speed_kmh * 3600
        noise = random.gauss(0, base_time * 0.1)
        veh.travel_time = max(60, base_time + noise)
        veh.arrived = True

        arrived += 1
        total_time += veh.travel_time
        results.append({"id": veh.id, "travel_time_s": round(veh.travel_time, 1)})

    avg_s = total_time / arrived if arrived else 0
    return SimResult(
        scenario          = label,
        speed_kmh         = speed_kmh,
        n_vehicles        = len(vehicles),
        avg_travel_time_s = round(avg_s, 1),
        avg_travel_time_m = round(avg_s / 60, 2),
        arrived_pct       = round(arrived / len(vehicles) * 100, 1),
        vehicles          = results,
    )


def compare_scenarios(edges: List[str]) -> Dict:
    """Оргил болон ердийн цагийг харьцуулна"""
    random.seed(RANDOM_SEED)
    vehicles_peak   = generate_vehicles(edges, N_VEHICLES, seed=RANDOM_SEED)
    vehicles_normal = generate_vehicles(edges, N_VEHICLES, seed=RANDOM_SEED + 1)

    peak   = simulate_scenario(vehicles_peak,   SPEED_PEAK,   "Оргил цаг")
    normal = simulate_scenario(vehicles_normal, SPEED_NORMAL, "Ердийн цаг")

    improvement = (peak.avg_travel_time_s - normal.avg_travel_time_s) \
                  / peak.avg_travel_time_s * 100

    summary = {
        "peak_avg_min"   : peak.avg_travel_time_m,
        "normal_avg_min" : normal.avg_travel_time_m,
        "improvement_pct": round(improvement, 1),
        "scenarios"      : [asdict(peak), asdict(normal)],
    }

    log.info("─" * 40)
    log.info("Оргил цаг дундаж:  %.1f мин", peak.avg_travel_time_m)
    log.info("Ердийн цаг дундаж: %.1f мин", normal.avg_travel_time_m)
    log.info("Хэмнэлт:           %.1f%%", improvement)
    log.info("─" * 40)

    return summary


def save_results(summary: Dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "simulation_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info("Үр дүн хадгаллаа → %s", path)


def try_run_sumo():
    """SUMO суулгасан бол бодит симуляци ажиллуулна"""
    import subprocess
    if not os.path.exists(CFG_PATH):
        log.warning("sumocfg олдсонгүй, SUMO-г алгасав")
        return

    cmd = ["sumo", "-c", CFG_PATH,
           "--no-warnings", "--duration-log.disable"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode == 0:
        log.info("✅  SUMO симуляци амжилттай дууслаа")
    else:
        log.warning("SUMO алдаа:\n%s", result.stderr[:400])


def main():
    edges   = load_net_xml(DATA_DIR)
    summary = compare_scenarios(edges)
    save_results(summary)
    try_run_sumo()
    log.info("3_run_sumo.py дууслаа")


if __name__ == "__main__":
    main()