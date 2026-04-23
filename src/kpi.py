"""
src/kpi.py
Нэгдсэн KPI тооцооллын модуль — Single Source of Truth.

Зорилго:
  simulation_results.json + dispatch_results.json → нэг нэгдсэн KPI
  Dashboard болон CLI хоёулаа энэ модулийг ашиглана.

Аль ч газраас import хийж ашиглах боломжтой:
  from src.kpi import build_unified_kpi, format_for_presentation
"""

from __future__ import annotations
from typing import Optional


def build_unified_kpi(
    dispatch_results: list[dict],
    sim_results: list[dict],
    vehicle_type: str = "van",
) -> dict:
    """
    Dispatch + Simulation үр дүнгээс нэгдсэн KPI бүтээнэ.

    Зарчим:
      - Baseline time:   simulation-ийн avg_travel_time_m (ердийн цаг)
      - Optimized time:  dispatch-ийн avg_smart_min (оргил цаг)
      - improvement_pct: нэг томьёогоор — зөрөлгүй

    Args:
        dispatch_results: dispatch_results.json-ийн list
        sim_results:      simulation_results.json-ийн list
        vehicle_type:     "car" | "van" | "truck"

    Returns:
        Нэгдсэн KPI dict
    """
    # Simulation-оос baseline travel time (ердийн цаг)
    normal_sim = next(
        (s for s in sim_results if s.get("speed_kmh", 0) >= 25),
        sim_results[-1] if sim_results else {},
    )
    baseline_time_min = normal_sim.get("avg_travel_time_m", 0)

    # Dispatch-аас оргил цагийн Smart ETA
    peak_disp = next(
        (d for d in dispatch_results if d.get("speed_kmh", 50) < 20),
        dispatch_results[0] if dispatch_results else {},
    )
    peak_kpi = peak_disp.get("kpi", {})
    smart_time_min   = peak_kpi.get("avg_smart_min", 0)
    nearest_time_min = peak_kpi.get("avg_nearest_min", 0)

    # Improvement: smart vs nearest (dispatch дотроо)
    dispatch_improvement = peak_kpi.get("improvement_pct", 0)

    # Simulation-ийн congestion
    peak_sim = next(
        (s for s in sim_results if s.get("speed_kmh", 50) < 20),
        sim_results[0] if sim_results else {},
    )
    congestion_pct   = peak_sim.get("congestion_pct", 0)
    peak_time_min    = peak_sim.get("avg_travel_time_m", 0)

    # Simulation-ийн хэмнэлт: оргил vs ердийн
    sim_improvement = 0.0
    if peak_time_min > 0 and baseline_time_min > 0:
        sim_improvement = (peak_time_min - baseline_time_min) / peak_time_min * 100

    return {
        "dispatch": {
            "avg_nearest_min":   round(nearest_time_min, 1),
            "avg_smart_min":     round(smart_time_min, 1),
            "improvement_pct":   round(dispatch_improvement, 1),
            "time_saved_min":    round(nearest_time_min - smart_time_min, 1),
            "co2_saved_kg":      peak_kpi.get("co2_saved_kg", 0),
            "n_orders":          peak_kpi.get("n_orders", 0),
        },
        "simulation": {
            "peak_avg_min":      round(peak_time_min, 1),
            "normal_avg_min":    round(baseline_time_min, 1),
            "congestion_pct":    congestion_pct,
            "delay_vs_normal_s": peak_sim.get("avg_delay_s", 0),
        },
        "summary": {
            "headline_improvement_pct": round(dispatch_improvement, 1),
            "data_source": "dispatch pipeline (graph-based)",
            "vehicle_type": vehicle_type,
            "note": (
                "Бүх KPI dispatch pipeline-аас — graph shortest path дээр суурилна. "
                "Simulation нь speed/congestion контекст өгнө."
            ),
        },
    }


def format_for_presentation(kpi: dict) -> str:
    """
    Шүүгчид зориулсан товч тайлбар.

    Args:
        kpi: build_unified_kpi()-ийн буцаасан dict

    Returns:
        Formatted string
    """
    d = kpi["dispatch"]
    s = kpi["simulation"]
    lines = [
        "=" * 55,
        "  CityFlow — KPI Summary (Graph-based, Reproducible)",
        "=" * 55,
        f"  Nearest dispatch:   {d['avg_nearest_min']:>6.1f} мин (Haversine зайгаар)",
        f"  Smart dispatch:     {d['avg_smart_min']:>6.1f} мин (Graph shortest path)",
        f"  Хэмнэлт:           {d['improvement_pct']:>6.1f}%  ↓{d['time_saved_min']:.1f} мин",
        f"  CO₂ хэмнэлт:       {d['co2_saved_kg']:>6.2f} кг",
        "-" * 55,
        f"  Оргил цагийн хурд:  {s['congestion_pct']:.0f}% түгжрэл",
        f"  Peak avg travel:   {s['peak_avg_min']:.1f} мин",
        f"  Normal avg travel: {s['normal_avg_min']:.1f} мин",
        "=" * 55,
        "  Route calculation: NetworkX shortest_path (GraphML)",
        "  SUMO fallback: deterministic (distance/speed)",
        "  Random.uniform: ашиглаагүй",
        "=" * 55,
    ]
    return "\n".join(lines)