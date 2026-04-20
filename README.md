# CityFlow — Улаанбаатарын Ухаалаг Замын Хөдөлгөөний Дижитал Загвар

M³ баг · SparkDay 2026

## Ажиллуулах дараалал

```bash
python scripts/01_fetch_osm.py      # OSM татах (2-5 мин)
python scripts/02_build_graph.py    # Граф байгуулах
python scripts/03_run_sumo.py       # Симуляци
python scripts/04_smart_dispatch.py # Dispatch харьцуулалт
streamlit run scripts/05_dashboard.py  # Dashboard
streamlit run scripts/06_demo.py       # Live demo
```

## Гарч ирэх файлууд

- `data/ulaanbaatar.graphml` — NetworkX граф
- `data/ulaanbaatar.osm`     — SUMO netconvert-д
- `data/ulaanbaatar.net.xml` — SUMO сүлжээ
- `output/graph.png`         — Граф зураг
- `output/graph_heatmap.png` — Оргил/ердийн цагийн харьцуулалт
- `output/simulation_results.json`
- `output/dispatch_results.json`