"""
02_build_graph.py
GraphML-аас NetworkX граф ачааллаж, SUMO net.xml болгон хөрвүүлнэ.
Зангилаа бүрт оргил / ердийн цагийн travel_time нэмнэ.
"""

import osmnx as ox
import networkx as nx
import subprocess
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Тохиргоо ──────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SPEED_PEAK   = 10
SPEED_NORMAL = 30
RUSH_HOURS   = [(7, 9), (17, 19)]
# ──────────────────────────────────────────────────────────


def load_graph(data_dir: str):
    path = os.path.join(data_dir, "ulaanbaatar.graphml")
    log.info("Граф ачааллаж байна: %s", path)
    G = ox.load_graphml(path)
    log.info("Зангилаа: %d | Ирмэг: %d", len(G.nodes), len(G.edges))
    return G


def is_rush_hour(hour: int) -> bool:
    return any(start <= hour < end for start, end in RUSH_HOURS)


def add_weighted_travel_times(G):
    log.info("Оргил / ердийн цагийн travel_time тооцоолж байна...")
    for u, v, data in G.edges(data=True):
        length_m = data.get("length", 50)
        data["travel_time_peak"]   = (length_m / 1000) / SPEED_PEAK   * 3600
        data["travel_time_normal"] = (length_m / 1000) / SPEED_NORMAL * 3600
    return G


def compute_stats(G):
    lengths = [d["length"] for _, _, d in G.edges(data=True) if "length" in d]
    stats = {
        "nodes"      : len(G.nodes),
        "edges"      : len(G.edges),
        "total_km"   : round(sum(lengths) / 1000, 1),
        "avg_edge_m" : round(sum(lengths) / len(lengths), 1) if lengths else 0,
    }
    log.info("Статистик: %s", json.dumps(stats, ensure_ascii=False))
    return stats


def save_stats(stats: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "graph_stats.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    log.info("Статистик хадгаллаа → %s", path)


def build_sumo_network(data_dir: str):
    osm_path = os.path.join(data_dir, "ulaanbaatar.osm")
    net_path = os.path.join(data_dir, "ulaanbaatar.net.xml")

    cmd = [
        "netconvert",
        "--osm-files",        osm_path,
        "--output-file",      net_path,
        "--geometry.remove",
        "--roundabouts.guess",
        "--ramps.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--tls.discard-simple",
        "--tls.join",
        "--no-warnings",
    ]

    log.info("netconvert ажиллаж байна...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        log.info("✅  net.xml үүслээ → %s", net_path)
    else:
        log.warning("netconvert алдаа (SUMO суулгаагүй байж болно):\n%s", result.stderr[:300])

    return net_path


def plot_with_peaks(G):
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor="#1a1a2e")

    for ax, mode in zip(axes, ["peak", "normal"]):
        key   = f"travel_time_{mode}"
        times = [d.get(key, 60) for _, _, d in G.edges(data=True)]
        max_t = max(times) if times else 1
        edge_colors = [cm.RdYlGn_r(t / max_t) for t in times]

        ox.plot_graph(
            G, ax=ax, node_size=3, edge_linewidth=0.7,
            edge_color=edge_colors, bgcolor="#1a1a2e",
            show=False, close=False,
        )
        label = "Оргил цаг (07-09, 17-19)" if mode == "peak" else "Ердийн цаг"
        ax.set_title(label, color="white", fontsize=12, pad=8)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, "graph_heatmap.png")
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close()
    log.info("Хит зураг хадгаллаа → %s", out)


def main():
    G = load_graph(DATA_DIR)
    G = add_weighted_travel_times(G)
    stats = compute_stats(G)
    save_stats(stats)
    build_sumo_network(DATA_DIR)
    plot_with_peaks(G)
    log.info("02_build_graph.py дууслаа")


if __name__ == "__main__":
    main()