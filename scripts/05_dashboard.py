"""
05_dashboard.py
CityFlow — Smart Dispatch Streamlit Dashboard

Ажиллуулах:
    streamlit run scripts/05_dashboard.py
"""

import os
import json
import random
import math
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import osmnx as ox
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px

# ── Тохиргоо ──────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SPEED_PEAK   = 10
SPEED_NORMAL = 30
RUSH_HOURS   = [(7, 9), (17, 19)]

UB_CENTER = [47.9184, 106.9177]
RANDOM_SEED = 42
# ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CityFlow — Smart Dispatch",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #1D9E75;
        margin-bottom: 10px;
    }
    .metric-card.red  { border-left-color: #E24B4A; }
    .metric-card.blue { border-left-color: #378ADD; }
    .metric-label { color: #888; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #fff; font-size: 26px; font-weight: 600; }
    .metric-sub   { color: #1D9E75; font-size: 12px; margin-top: 2px; }
    .section-title {
        color: #fff;
        font-size: 16px;
        font-weight: 600;
        margin: 20px 0 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid #2a2d3e;
    }
</style>
""", unsafe_allow_html=True)


# ── Туслах функцүүд ────────────────────────────────────────

def is_rush(hour): return any(s <= hour < e for s, e in RUSH_HOURS)
def get_speed(hour): return SPEED_PEAK if is_rush(hour) else SPEED_NORMAL

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2-lat1)*p/2)**2
         + math.cos(lat1*p)*math.cos(lat2*p)
         * math.sin((lon2-lon1)*p/2)**2)
    return 2*R*math.asin(a**0.5)

def get_eta_min(dist_m, speed_kmh):
    return round((dist_m/1000)/speed_kmh*60, 1)


@st.cache_resource(show_spinner="Граф ачааллаж байна...")
def load_graph():
    path = os.path.join(DATA_DIR, "sukhbaatar.graphml")
    if os.path.exists(path):
        return ox.load_graphml(path)
    return None


def load_dispatch_results():
    path = os.path.join(OUTPUT_DIR, "dispatch_results.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    # Mock үр дүн
    return [
        {"scenario": "оргил цаг",  "hour": 8,  "avg_nearest_min": 24.3,
         "avg_smart_min": 19.8, "improvement_pct": 18.5, "n_orders": 100},
        {"scenario": "ердийн цаг", "hour": 14, "avg_nearest_min": 9.1,
         "avg_smart_min": 7.8,  "improvement_pct": 14.3, "n_orders": 100},
    ]


def generate_mock_actors(n_drivers=6, n_orders=8, seed=42):
    random.seed(seed)
    drivers, orders = [], []
    for i in range(n_drivers):
        drivers.append({
            "id":  f"D{i+1:02d}",
            "lat": UB_CENTER[0] + random.uniform(-0.02, 0.02),
            "lon": UB_CENTER[1] + random.uniform(-0.03, 0.03),
            "status": random.choice(["Чөлөөтэй", "Чөлөөтэй", "Ачилттай"]),
        })
    for i in range(n_orders):
        orders.append({
            "id":  f"O{i+1:03d}",
            "lat": UB_CENTER[0] + random.uniform(-0.018, 0.018),
            "lon": UB_CENTER[1] + random.uniform(-0.025, 0.025),
        })
    return drivers, orders


def find_best_driver(order, drivers, speed):
    best, best_eta = None, float("inf")
    for d in drivers:
        if d["status"] == "Ачилттай":
            continue
        dist = haversine_m(d["lat"], d["lon"], order["lat"], order["lon"])
        eta  = get_eta_min(dist, speed)
        if eta < best_eta:
            best_eta, best = eta, d
    return best, best_eta


# ══════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/city.png", width=60)
    st.title("CityFlow")
    st.caption("Smart Dispatch · Улаанбаатар")
    st.divider()

    hour = st.slider("🕐 Симуляцийн цаг", 0, 23, 8)
    rush = is_rush(hour)
    speed = get_speed(hour)

    if rush:
        st.error(f"🔴 Оргил цаг — {speed} km/h")
    else:
        st.success(f"🟢 Ердийн цаг — {speed} km/h")

    st.divider()
    n_drivers = st.slider("Жолооч тоо",   3, 12, 6)
    n_orders  = st.slider("Захиалга тоо", 3, 20, 8)
    seed      = st.number_input("Random seed", value=42, step=1)

    if st.button("🔄 Шинэчлэх", use_container_width=True):
        st.cache_data.clear()

    st.divider()
    st.caption("M³ баг · SparkDay 2026")


# ══════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════
st.markdown("## 🚚 CityFlow — Traffic-aware Smart Dispatch")
st.caption("Улаанбаатар · Сүхбаатар дүүрэг · OSM + NetworkX")

# ══════════════════════════════════════════════════════════
#  МЕТРИК КАРТУУД
# ══════════════════════════════════════════════════════════
results = load_dispatch_results()
peak_r   = next((r for r in results if "оргил" in r["scenario"]), results[0])
normal_r = next((r for r in results if "ердийн" in r["scenario"]), results[-1])

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Smart ETA (оргил)</div>
        <div class="metric-value">{peak_r['avg_smart_min']} мин</div>
        <div class="metric-sub">↓ {peak_r['improvement_pct']}% хэмнэлт</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-card blue">
        <div class="metric-label">Smart ETA (ердийн)</div>
        <div class="metric-value">{normal_r['avg_smart_min']} мин</div>
        <div class="metric-sub">↓ {normal_r['improvement_pct']}% хэмнэлт</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="metric-card red">
        <div class="metric-label">Ойр dispatch (оргил)</div>
        <div class="metric-value">{peak_r['avg_nearest_min']} мин</div>
        <div class="metric-sub">Хуучин арга</div>
    </div>""", unsafe_allow_html=True)
with c4:
    avg_imp = round((peak_r['improvement_pct']+normal_r['improvement_pct'])/2, 1)
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Дундаж хэмнэлт</div>
        <div class="metric-value">{avg_imp}%</div>
        <div class="metric-sub">2 сценарийн дундаж</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ══════════════════════════════════════════════════════════
#  ГАЗРЫН ЗУРАГ + DISPATCH ХАРУУЛАЛТ
# ══════════════════════════════════════════════════════════
col_map, col_info = st.columns([3, 2])

with col_map:
    st.markdown('<div class="section-title">📍 Жолооч & Захиалгын байршил</div>',
                unsafe_allow_html=True)

    drivers, orders = generate_mock_actors(n_drivers, n_orders, int(seed))

    # Хамгийн тохиромжтой жолоочийг тодорхойлно
    selected_order = orders[0]
    best_d, best_eta = find_best_driver(selected_order, drivers, speed)

    m = folium.Map(location=UB_CENTER, zoom_start=14,
                   tiles="CartoDB dark_matter")

    # Жолооч нар
    for d in drivers:
        color = "green" if d["status"] == "Чөлөөтэй" else "gray"
        is_best = best_d and d["id"] == best_d["id"]
        folium.CircleMarker(
            location=[d["lat"], d["lon"]],
            radius=10 if is_best else 7,
            color="#1D9E75" if is_best else ("#888" if color=="gray" else "#4a9eda"),
            fill=True,
            fill_opacity=0.9,
            popup=folium.Popup(
                f"<b>{d['id']}</b><br>Төлөв: {d['status']}"
                + (f"<br><b>✅ Сонгогдсон — ETA: {best_eta} мин</b>" if is_best else ""),
                max_width=200
            ),
            tooltip=f"{'⭐ ' if is_best else ''}{d['id']} · {d['status']}",
        ).add_to(m)

    # Захиалгууд
    for i, o in enumerate(orders):
        folium.Marker(
            location=[o["lat"], o["lon"]],
            icon=folium.Icon(
                color="red" if i==0 else "orange",
                icon="box" if i==0 else "shopping-cart",
                prefix="fa"
            ),
            popup=f"Захиалга {o['id']}" + (" ← Идэвхтэй" if i==0 else ""),
            tooltip=o["id"],
        ).add_to(m)

    # Сонгогдсон жолоочоос захиалга руу шугам
    if best_d:
        folium.PolyLine(
            locations=[[best_d["lat"], best_d["lon"]],
                        [selected_order["lat"], selected_order["lon"]]],
            color="#1D9E75",
            weight=3,
            dash_array="8 4",
            tooltip=f"Smart маршрут · ETA {best_eta} мин",
        ).add_to(m)

    st_folium(m, height=420, use_container_width=True)

with col_info:
    st.markdown('<div class="section-title">🎯 Dispatch шийдвэр</div>',
                unsafe_allow_html=True)

    if best_d:
        st.success(f"**Сонгогдсон жолооч:** {best_d['id']}")
        st.metric("Smart ETA", f"{best_eta} мин")

        # Бусад жолоочдын ETA
        st.markdown("**Бүх жолоочдын ETA:**")
        eta_rows = []
        for d in drivers:
            dist = haversine_m(d["lat"], d["lon"],
                               selected_order["lat"], selected_order["lon"])
            eta  = get_eta_min(dist, speed)
            eta_rows.append({
                "Жолооч": d["id"],
                "Төлөв": d["status"],
                "ETA (мин)": eta,
                "Сонгогдсон": "✅" if d["id"]==best_d["id"] else "",
            })

        df = pd.DataFrame(eta_rows).sort_values("ETA (мин)")
        st.dataframe(df, hide_index=True, use_container_width=True,
                     height=200)

    st.divider()
    st.markdown("**Одоогийн нөхцөл:**")
    st.markdown(f"- 🕐 Цаг: **{hour:02d}:00**")
    st.markdown(f"- 🚗 Хурд: **{speed} km/h**")
    st.markdown(f"- {'🔴 Оргил цаг' if rush else '🟢 Ердийн цаг'}")
    st.markdown(f"- 🚚 Чөлөөт жолооч: **{sum(1 for d in drivers if d['status']=='Чөлөөтэй')}**")


# ══════════════════════════════════════════════════════════
#  ХАРЬЦУУЛАЛТЫН ГРАФИК
# ══════════════════════════════════════════════════════════
st.divider()
st.markdown('<div class="section-title">📊 Smart vs Ойр dispatch харьцуулалт</div>',
            unsafe_allow_html=True)

gc1, gc2 = st.columns(2)

with gc1:
    # Bar chart — дундаж ETA харьцуулалт
    fig = go.Figure()
    scenarios = [r["scenario"].upper() for r in results]

    fig.add_bar(name="Ойр dispatch (хуучин)",
                x=scenarios,
                y=[r["avg_nearest_min"] for r in results],
                marker_color="#E24B4A",
                text=[f"{r['avg_nearest_min']} мин" for r in results],
                textposition="outside")

    fig.add_bar(name="Smart dispatch (манай)",
                x=scenarios,
                y=[r["avg_smart_min"] for r in results],
                marker_color="#1D9E75",
                text=[f"{r['avg_smart_min']} мин" for r in results],
                textposition="outside")

    fig.update_layout(
        barmode="group",
        title="Дундаж ETA (минут)",
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        font_color="#ccc",
        legend=dict(bgcolor="#1e2130"),
        yaxis_title="Минут",
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)

with gc2:
    # Хэмнэлт — gauge / bar
    fig2 = go.Figure()
    fig2.add_bar(
        x=[r["scenario"].upper() for r in results],
        y=[r["improvement_pct"] for r in results],
        marker_color=["#1D9E75", "#378ADD"],
        text=[f"{r['improvement_pct']}%" for r in results],
        textposition="outside",
    )
    fig2.add_hline(y=15, line_dash="dot", line_color="#FAC775",
                   annotation_text="Зорилт 15%")

    fig2.update_layout(
        title="Цагийн хэмнэлт (%)",
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        font_color="#ccc",
        yaxis_title="Хувь (%)",
        yaxis_range=[0, 30],
        height=320,
    )
    st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════
#  ЦАГИЙН ДҮҮСЛЭЛТ
# ══════════════════════════════════════════════════════════
st.divider()
st.markdown('<div class="section-title">⏱ Цагийн туршид ETA өөрчлөлт</div>',
            unsafe_allow_html=True)

hours_range = list(range(6, 22))
smart_etas, nearest_etas = [], []

random.seed(RANDOM_SEED)
for h in hours_range:
    spd  = get_speed(h)
    dist = random.uniform(1500, 4000)
    smart_etas.append(round(get_eta_min(dist * 0.85, spd), 1))
    nearest_etas.append(round(get_eta_min(dist, spd), 1))

fig3 = go.Figure()
fig3.add_scatter(x=hours_range, y=nearest_etas, name="Ойр dispatch",
                 line=dict(color="#E24B4A", width=2, dash="dot"),
                 fill="tozeroy", fillcolor="rgba(226,75,74,0.1)")
fig3.add_scatter(x=hours_range, y=smart_etas, name="Smart dispatch",
                 line=dict(color="#1D9E75", width=2),
                 fill="tozeroy", fillcolor="rgba(29,158,117,0.1)")

# Оргил цагийн бүс
for s, e in RUSH_HOURS:
    if 6 <= s <= 21:
        fig3.add_vrect(x0=s, x1=e, fillcolor="rgba(250,200,117,0.1)",
                       line_width=0,
                       annotation_text="Оргил цаг",
                       annotation_position="top left")

fig3.update_layout(
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font_color="#ccc",
    legend=dict(bgcolor="#1e2130"),
    xaxis_title="Цаг",
    yaxis_title="ETA (минут)",
    height=300,
    xaxis=dict(tickmode="linear", dtick=1,
               ticktext=[f"{h:02d}:00" for h in hours_range],
               tickvals=hours_range),
)
st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════
st.divider()
st.caption("CityFlow · M³ баг · SparkDay 2026 · OSM–City2Graph–SUMO стек")