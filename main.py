"""
main.py
CityFlow — Unified CLI Pipeline

Хэрэглээ:
    python main.py --step fetch       # OSM өгөгдөл татах
    python main.py --step build       # граф байгуулах
    python main.py --step simulate    # SUMO симуляци
    python main.py --step dispatch    # smart dispatch
    python main.py --step all         # бүгдийг дараалан
    python main.py --step dashboard   # Streamlit demo
    python main.py --step demo        # SparkDay demo
"""

import argparse
import json
import sys
import time
from pathlib import Path

from config.loader import load_config as get_cfg
from src.utils import get_logger, ensure_dir

log = get_logger("cityflow.main")

STEPS = ["fetch", "build", "simulate", "dispatch", "all", "dashboard", "demo"]


# ── Cache шалгах ──────────────────────────────────────────

def _is_cached(path: str | Path) -> bool:
    return Path(path).exists()


def _print_step(name: str) -> None:
    line = "─" * 50
    log.info(line)
    log.info("  АЛХАМ: %s", name.upper())
    log.info(line)


# ── KPI нэгтгэлт (simulate + dispatch хоёулаа дууссаны дараа) ──

def _print_unified_kpi(cfg: dict) -> None:
    """
    simulation_results.json + dispatch_results.json хоёулаа байвал
    src/kpi.py ашиглан нэгдсэн KPI хэвлэнэ.

    Байршил: src/kpi.py
    Import: from src.kpi import build_unified_kpi, format_for_presentation
    """
    from src.kpi import build_unified_kpi, format_for_presentation

    sim_path      = cfg["paths"]["simulation_results"]
    dispatch_path = cfg["paths"]["dispatch_results"]

    if not _is_cached(sim_path):
        log.info("KPI алгасав — simulation үр дүн байхгүй (%s)", sim_path)
        log.info("  → эхлээд: python main.py --step simulate")
        return

    if not _is_cached(dispatch_path):
        log.info("KPI алгасав — dispatch үр дүн байхгүй (%s)", dispatch_path)
        log.info("  → эхлээд: python main.py --step dispatch")
        return

    with open(dispatch_path, encoding="utf-8") as f:
        dispatch_data = json.load(f)
    with open(sim_path, encoding="utf-8") as f:
        sim_data = json.load(f)

    kpi = build_unified_kpi(dispatch_data, sim_data)
    print(format_for_presentation(kpi))


# ── Step функцүүд ─────────────────────────────────────────

def step_fetch(cfg: dict, force: bool = False) -> None:
    """OSM өгөгдөл татах."""
    graphml = cfg["paths"]["graphml"]
    if not force and _is_cached(graphml):
        log.info("Cache байна → %s  (--force ашиглан дахин татах)", graphml)
        return

    _print_step("fetch — OSM өгөгдөл татах")
    from src.fetch_osm import run
    t = time.time()
    run(cfg)
    log.info("✅  fetch дууслаа (%.1f сек)", time.time() - t)


def step_build(cfg: dict, force: bool = False) -> None:
    """Граф байгуулах + SUMO хөрвүүлэлт."""
    net_xml = cfg["paths"]["net_xml"]
    if not force and _is_cached(net_xml):
        log.info("Cache байна → %s", net_xml)
        return

    _print_step("build — граф байгуулах")
    from src.build import run
    t = time.time()
    run(cfg)
    log.info("✅  build дууслаа (%.1f сек)", time.time() - t)


def step_simulate(cfg: dict, force: bool = False) -> None:
    """SUMO симуляци (SUMO байхгүй бол deterministic fallback)."""
    result = cfg["paths"]["simulation_results"]
    if not force and _is_cached(result):
        log.info("Cache байна → %s", result)
        return

    _print_step("simulate — SUMO симуляци")
    from src.runner import run
    t = time.time()
    run(cfg)
    log.info("✅  simulate дууслаа (%.1f сек)", time.time() - t)

    # Dispatch үр дүн байвал хоёрыг нэгтгэж KPI харуулна
    _print_unified_kpi(cfg)


def step_dispatch(cfg: dict, force: bool = False) -> None:
    """Smart dispatch харьцуулалт."""
    result = cfg["paths"]["dispatch_results"]
    if not force and _is_cached(result):
        log.info("Cache байна → %s", result)
        return

    _print_step("dispatch — smart dispatch")
    from src.dispatch import run
    t = time.time()
    run(cfg)
    log.info("✅  dispatch дууслаа (%.1f сек)", time.time() - t)

    # Simulation үр дүн байвал хоёрыг нэгтгэж KPI харуулна
    _print_unified_kpi(cfg)


def step_all(cfg: dict, force: bool = False) -> None:
    """Бүх алхмыг дараалан ажиллуулна."""
    for fn in [step_fetch, step_build, step_simulate, step_dispatch]:
        fn(cfg, force=force)

    log.info("=" * 50)
    log.info("  ✅  БҮТЭН PIPELINE ДУУСЛАА")
    log.info("=" * 50)

    # step_dispatch дотор аль хэдийн хэвлэгдсэн боловч
    # --step all дууссаны дараа нэг удаа дахин харуулна
    _print_unified_kpi(cfg)


def step_dashboard(cfg: dict) -> None:
    """Streamlit dashboard ажиллуулна."""
    import subprocess
    log.info("Dashboard эхлүүлж байна → http://localhost:8501")
    subprocess.run([sys.executable, "-m", "streamlit",
                    "run", "src/app.py"], check=False)


def step_demo(cfg: dict) -> None:
    """SparkDay demo ажиллуулна."""
    import subprocess
    log.info("Demo эхлүүлж байна → http://localhost:8501")
    subprocess.run([sys.executable, "-m", "streamlit",
                    "run", "scripts/06_demo.py"], check=False)


# ── CLI ───────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cityflow",
        description="CityFlow — Smart Traffic Dispatch Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Жишээнүүд:
  python main.py --step fetch
  python main.py --step simulate
  python main.py --step dispatch
  python main.py --step all
  python main.py --step all --force
  python main.py --step dashboard
        """,
    )
    parser.add_argument(
        "--step",
        choices=STEPS,
        required=True,
        help="Ажиллуулах алхам",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Cache-г үл харгалзан дахин ажиллуулна",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Config файлын зам (default: config/settings.yaml)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from config.loader import load_config
    cfg = load_config(args.config)

    # Output хавтас бэлдэх
    ensure_dir(cfg["paths"]["data_dir"])
    ensure_dir(cfg["paths"]["output_dir"])

    dispatch_map = {
        "fetch":     lambda: step_fetch(cfg, args.force),
        "build":     lambda: step_build(cfg, args.force),
        "simulate":  lambda: step_simulate(cfg, args.force),
        "dispatch":  lambda: step_dispatch(cfg, args.force),
        "all":       lambda: step_all(cfg, args.force),
        "dashboard": lambda: step_dashboard(cfg),
        "demo":      lambda: step_demo(cfg),
    }

    try:
        dispatch_map[args.step]()
    except KeyboardInterrupt:
        log.info("Зогсоосон.")
    except Exception as e:
        log.error("Алдаа гарлаа: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()