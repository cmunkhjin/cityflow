"""
src/ingestion/fetch_osm.py
OpenStreetMap-аас замын өгөгдөл татаж хадгална.
"""

from __future__ import annotations
import osmnx as ox
from pathlib import Path
from src.utils import get_logger, ensure_dir

log = get_logger(__name__)


def fetch_graph(place: str, network_type: str = "drive"):
    """
    OSM-аас замын граф татна.

    Args:
        place:        хайлтын газрын нэр (OSM-д байгаа хэлбэрээр)
        network_type: "drive" | "walk" | "all"

    Returns:
        osmnx MultiDiGraph — хурд болон travel_time нэмсэн
    """
    log.info("OSM граф татаж байна: %s", place)
    G = ox.graph_from_place(place, network_type=network_type)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    log.info("Зангилаа: %d | Ирмэг: %d", len(G.nodes), len(G.edges))
    return G


def save_graph(G, graphml_path: str | Path, osm_path: str | Path) -> None:
    """
    Графийг GraphML болон OSM XML форматаар хадгална.

    Args:
        G:            osmnx граф
        graphml_path: .graphml файлын зам
        osm_path:     .osm файлын зам
    """
    ensure_dir(Path(graphml_path).parent)
    ox.save_graphml(G, graphml_path)
    ox.save_graph_xml(G, osm_path)
    log.info("GraphML → %s", graphml_path)
    log.info("OSM XML → %s", osm_path)


def plot_graph(G, output_path: str | Path) -> None:
    """
    Графийг зурагласан PNG хадгална.

    Args:
        G:           osmnx граф
        output_path: .png файлын зам
    """
    ensure_dir(Path(output_path).parent)
    ox.plot_graph(
        G,
        node_size=5, edge_linewidth=0.8,
        bgcolor="#1a1a2e", node_color="#1D9E75", edge_color="#4a9eda",
        show=False, close=True, save=True,
        filepath=str(output_path), dpi=180,
    )
    log.info("Граф зураг → %s", output_path)


def run(cfg: dict) -> None:
    """
    Config-оор бүтэн fetch pipeline ажиллуулна.

    Args:
        cfg: settings.yaml-н dict
    """
    G = fetch_graph(cfg["city"]["name"], cfg["city"]["network_type"])
    save_graph(G, cfg["paths"]["graphml"], cfg["paths"]["osm"])
    plot_graph(G, Path(cfg["paths"]["output_dir"]) / "graph.png")