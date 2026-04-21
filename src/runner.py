"""
src/simulation/runner.py
SUMO симуляци — оргил vs ердийн цагийн харьцуулалт.
SUMO суулгаагүй бол physics-based mock ажиллана.
"""

from __future__ import annotations
import json
import random
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from src.utils import get_logger, ensure_dir, is_rush_hour

log = get_logger(__name__)


# ── Өгөгдлийн бүтэц ───────────────────────────────────────

@dataclass
class ScenarioResult:
    """Нэг сценарийн дүн."""
    scenario:          str
    hour:              int
    speed_kmh:         float
    n_vehicles:        int
    avg_travel_time_s: float
    avg_travel_time_m: float
    avg_delay_s:       float        # ердийн цагтай харьцуулсан хоцролт
    congestion_pct:    float        # ачааллын хувь
    arrived_pct:       float
    vehicles:          list = field(default_factory=list)


# ── SUMO config үүсгэх ────────────────────────────────────

def generate_sumo_config(net_path: str | Path,
                         cfg_path: str | Path,
                         n_vehicles: int,
                         duration: int,
                         seed: int) -> None:
    """
    .sumocfg XML файл үүсгэнэ.

    Args:
        net_path:   .net.xml файлын зам
        cfg_path:   гаралтын .sumocfg зам
        n_vehicles: тээврийн хэрэгслийн тоо
        duration:   симуляцийн үргэлжлэх хугацаа (сек)
        seed:       санамсаргүй тоон үр
    """
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="{net_path}"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="{duration}"/>
  </time>
  <random>
    <seed value="{seed}"/>
  </random>
  <report>
    <no-warnings value="true"/>
    <no-step-log value="true"/>
  </report>
</configuration>"""
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(xml)
    log.info("SUMO config үүслээ → %s", cfg_path)


# ── Mock симуляци (SUMO байхгүй үед) ─────────────────────

def _mock_scenario(hour: int, speed_kmh: float, n_vehicles: int,
                   label: str, rush_hours: list,
                   normal_speed: float, seed: int) -> ScenarioResult:
    """
    Physics-based mock симуляци.
    Замын урт × хурд → travel_time, Gaussian noise нэмнэ.

    Args:
        hour:         симуляцийн цаг
        speed_kmh:    тухайн цагийн хурд
        n_vehicles:   тооны тоо
        label:        "Оргил цаг" | "Ердийн цаг"
        rush_hours:   оргил цагийн мужууд
        normal_speed: ердийн цагийн хурд (хоцролт тооцоонд)
        seed:         random seed

    Returns:
        ScenarioResult
    """
    random.seed(seed)
    rush = is_rush_hour(hour, rush_hours)

    total_time = 0.0
    vehicles   = []

    for i in range(n_vehicles):
        # Маршрутын урт: оргил цагт илүү урт (traffic re-routing)
        dist_m = random.uniform(1_500, 5_000) * (1.15 if rush else 1.0)
        base_s = (dist_m / 1000) / speed_kmh * 3600
        noise  = random.gauss(0, base_s * 0.08)
        tt     = max(60, base_s + noise)
        total_time += tt
        vehicles.append({"id": f"veh_{i:03d}",
                          "travel_time_s": round(tt, 1)})

    avg_s       = total_time / n_vehicles
    normal_avg  = (3_000 / 1000) / normal_speed * 3600   # baseline
    delay_s     = max(0.0, avg_s - normal_avg)
    congestion  = min(95, 30 + (speed_kmh < 15) * 45 + random.uniform(-5, 5))

    return ScenarioResult(
        scenario          = label,
        hour              = hour,
        speed_kmh         = speed_kmh,
        n_vehicles        = n_vehicles,
        avg_travel_time_s = round(avg_s, 1),
        avg_travel_time_m = round(avg_s / 60, 2),
        avg_delay_s       = round(delay_s, 1),
        congestion_pct    = round(congestion, 1),
        arrived_pct       = 100.0,
        vehicles          = vehicles,
    )


# ── SUMO бодит симуляци ───────────────────────────────────

def _run_sumo(cfg_path: str | Path) -> Optional[dict]:
    """
    SUMO суулгасан бол бодит симуляци ажиллуулна.

    Args:
        cfg_path: .sumocfg файлын зам

    Returns:
        Үр дүн dict эсвэл None (алдаа гарвал)
    """
    cmd = ["sumo", "-c", str(cfg_path),
           "--no-warnings", "--duration-log.disable"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            log.info("SUMO симуляци амжилттай дууслаа")
            return {"status": "ok", "output": result.stdout}
        log.warning("SUMO алдаа:\n%s", result.stderr[:200])
        return None
    except FileNotFoundError:
        log.info("SUMO суулгаагүй — mock ашиглана")
        return None


# ── Pipeline entry point ───────────────────────────────────

def run(cfg: dict) -> list[dict]:
    """
    Бүх сценарийг ажиллуулж JSON хадгална.

    Args:
        cfg: settings.yaml dict

    Returns:
        ScenarioResult dict-уудын жагсаалт
    """
    sim      = cfg["simulation"]
    traffic  = cfg["traffic"]
    out_dir  = ensure_dir(cfg["paths"]["output_dir"])

    results = []
    for sc in sim["scenarios"]:
        hour  = sc["hour"]
        rush  = is_rush_hour(hour, traffic["rush_hours"])
        speed = (traffic["speed_peak_kmh"] if rush
                 else traffic["speed_normal_kmh"])

        res = _mock_scenario(
            hour         = hour,
            speed_kmh    = speed,
            n_vehicles   = sim["n_vehicles"],
            label        = sc["label"],
            rush_hours   = traffic["rush_hours"],
            normal_speed = traffic["speed_normal_kmh"],
            seed         = sim["random_seed"] + hour,
        )

        log.info("%-12s │ avg %.1f мин │ хоцролт %.0f сек │ түгжрэл %.0f%%",
                 res.scenario, res.avg_travel_time_m,
                 res.avg_delay_s, res.congestion_pct)
        results.append(asdict(res))

    out_path = out_dir / "simulation_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("Симуляцийн үр дүн → %s", out_path)
    return results