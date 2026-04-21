"""
src/graph/build.py
GraphML ачааллаж, оргил / ердийн цагийн жин нэмж,
SUMO net.xml үүсгэнэ.
"""

from __future__ import annotations
import json
import subprocess
from pathlib import Path

import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.cm as cm

from src.utils import get_logger, ensure_dir

log = get_logger(__name__)


# ── Граф ачаалах ──────────────────────────────────────────

def load_graph(graphml_path: str | Path):
    """
    GraphML файлаас osmnx граф ачаална.

    Args:
        graphml_path: .graphml файлын зам

    Returns:
        osmnx MultiDiGraph

    Raises:
        FileNotFoundError: файл байхгүй бол
    """
    path = Path(graphml_path)
    if not path.exists():
        raise FileNotFoundError(
            f"GraphML олдсонгүй: {path}\n"
            "Эхлээд `python main.py --step fetch` ажиллуулна уу."
        )
    log.info("Граф ачааллаж байна: %s", path)
    G = ox.load_graphml(path)
    log.info("Зангилаа: %d | Ирмэг: %d", len(G.nodes), len(G.edges))
    return G


# ── Жин нэмэх ─────────────────────────────────────────────

def add_traffic_weights(G, speed_peak: float, speed_normal: float,
                        congestion_penalty: float):
    """
    Ирмэг бүрт оргил / ердийн цагийн travel_time болон
    congestion weight нэмнэ.

    Args:
        G:                   osmnx граф
        speed_peak:          оргил цагийн хурд km/h
        speed_normal:        ердийн цагийн хурд km/h
        congestion_penalty:  оргил цагийн жинг хэд дахин нэмэгдүүлэх

    Returns:
        Жин нэмсэн граф (inplace + return)
    """
    for _, _, data in G.edges(data=True):
        length_m = data.get("length", 50)
        tt_normal = (length_m / 1000) / speed_normal * 3600
        tt_peak   = (length_m / 1000) / speed_peak   * 3600

        data["travel_time_normal"] = round(tt_normal, 2)
        data["travel_time_peak"]   = round(tt_peak,   2)
        data["weight_normal"]      = round(tt_normal, 2)
        data["weight_peak"]        = round(tt_peak * congestion_penalty, 2)

    log.info("Замын жин нэмэгдлээ (peak penalty ×%.1f)", congestion_penalty)
    return G


# ── Статистик ─────────────────────────────────────────────

def compute_stats(G) -> dict:
    """
    Графийн үндсэн статистик тооцооллоно.

    Args:
        G: osmnx граф

    Returns:
        Dict: nodes, edges, total_km, avg_edge_m
    """
    lengths = [d["length"] for _, _, d in G.edges(data=True) if "length" in d]
    return {
        "nodes":      len(G.nodes),
        "edges":      len(G.edges),
        "total_km":   round(sum(lengths) / 1000, 1),
        "avg_edge_m": round(sum(lengths) / max(len(lengths), 1), 1),
    }


# ── SUMO хөрвүүлэлт ───────────────────────────────────────

def build_sumo_network(osm_path: str | Path,
                       net_path: str | Path) -> bool:
    """
    osmnx OSM XML-ийг SUMO net.xml болгон хөрвүүлнэ.

    Args:
        osm_path: .osm файлын зам
        net_path: гаралтын .net.xml зам

    Returns:
        True бол амжилттай, False бол SUMO суулгаагүй
    """
    cmd = [
        "netconvert",
        "--osm-files",        str(osm_path),
        "--output-file",      str(net_path),
        "--geometry.remove",
        "--roundabouts.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--tls.join",
        "--no-warnings",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log.info("SUMO net.xml → %s", net_path)
        return True
    log.warning("netconvert алдаа (SUMO суулгаагүй байж болно)")
    return False


# ── Дулааны зураг ─────────────────────────────────────────

def plot_heatmap(G, output_path: str | Path) -> None:
    """
    Оргил / ердийн цагийн travel_time-г өнгөөр харуулна.

    Args:
        G:           жин нэмсэн граф
        output_path: .png файлын зам
    """
    ensure_dir(Path(output_path).parent)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor="#1a1a2e")

    for ax, mode in zip(axes, ["peak", "normal"]):
        times = [d.get(f"travel_time_{mode}", 60)
                 for _, _, d in G.edges(data=True)]
        max_t = max(times) or 1
        edge_colors = [cm.RdYlGn_r(t / max_t) for t in times]
        ox.plot_graph(G, ax=ax, node_size=3, edge_linewidth=0.7,
                      edge_color=edge_colors, bgcolor="#1a1a2e",
                      show=False, close=False)
        ax.set_title(
            "Оргил цаг (07-09, 17-19)" if mode == "peak" else "Ердийн цаг",
            color="white", fontsize=12
        )

    plt.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close()
    log.info("Дулааны зураг → %s", output_path)


# ── Pipeline entry point ───────────────────────────────────

def run(cfg: dict) -> None:
    """
    Config-оор бүтэн build pipeline ажиллуулна.

    Args:
        cfg: settings.yaml dict
    """
    G = load_graph(cfg["paths"]["graphml"])
    G = add_traffic_weights(
        G,
        speed_peak        = cfg["traffic"]["speed_peak_kmh"],
        speed_normal      = cfg["traffic"]["speed_normal_kmh"],
        congestion_penalty= cfg["traffic"]["congestion_penalty"],
    )
    stats = compute_stats(G)
    out   = Path(cfg["paths"]["output_dir"])
    ensure_dir(out)

    with open(out / "graph_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    log.info("Статистик → %s", out / "graph_stats.json")

    build_sumo_network(cfg["paths"]["osm"], cfg["paths"]["net_xml"])
    plot_heatmap(G, out / "graph_heatmap.png")