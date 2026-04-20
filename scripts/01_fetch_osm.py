"""
01_fetch_osm.py
Улаанбаатар хотын бүх дүүргийн OSM өгөгдлийг татаж, граф байгуулна.
"""

import osmnx as ox
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Тохиргоо ──────────────────────────────────────────────
# Улаанбаатар хотын бүх дүүргийг хамарсан bounding box
# (north, south, east, west)
BBOX       = (48.0200, 47.8000, 107.1500, 106.6000)
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
NETWORK    = "drive"   # явган: "walk" | нийтийн тээвр: "all"

SPEED_PEAK   = 10   # 07-09, 17-19
SPEED_NORMAL = 30
# ──────────────────────────────────────────────────────────


def fetch_graph(bbox: tuple, network: str):
    north, south, east, west = bbox
    log.info(
        "OSM-аас граф татаж байна (bbox): N=%.4f S=%.4f E=%.4f W=%.4f",
        north, south, east, west,
    )
    G = ox.graph_from_bbox(
        bbox=(north, south, east, west),
        network_type=network,
        simplify=True,
    )
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    log.info("Нийт зангилаа: %d | Ирмэг: %d", len(G.nodes), len(G.edges))
    return G


def save_graph(G, data_dir: str):
    os.makedirs(data_dir, exist_ok=True)
    graphml_path = os.path.join(data_dir, "ulaanbaatar.graphml")
    osm_path     = os.path.join(data_dir, "ulaanbaatar.osm")

    ox.save_graphml(G, graphml_path)
    log.info("GraphML хадгаллаа → %s", graphml_path)

    ox.save_graph_xml(G, osm_path)
    log.info("OSM XML хадгаллаа → %s", osm_path)


def plot_graph(G, data_dir: str):
    out_dir = os.path.join(data_dir, "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    fig, _ = ox.plot_graph(
        G,
        node_size=5,
        edge_linewidth=0.8,
        bgcolor="#1a1a2e",
        node_color="#1D9E75",
        edge_color="#4a9eda",
        show=False,
        close=True,
        save=True,
        filepath=os.path.join(out_dir, "graph.png"),
        dpi=200,
    )
    log.info("Граф зураг хадгаллаа → output/graph.png")


def main():
    G = fetch_graph(BBOX, NETWORK)
    save_graph(G, DATA_DIR)
    plot_graph(G, DATA_DIR)
    log.info("01_fetch_osm.py дууслаа")


if __name__ == "__main__":
    main()