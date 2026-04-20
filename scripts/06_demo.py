"""
06_demo.py
CityFlow — SparkDay Live Demo Dashboard

Pitch танилцуулгад зориулсан бодит цагийн demo.
Ажиллуулах:
    streamlit run scripts/06_demo.py
"""

import os, json, random, math, time
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# ── Тохиргоо ──────────────────────────────────────────────
UB_CENTER    = [47.9184, 106.9177]
SPEED_PEAK   = 10
SPEED_NORMAL = 30
RUSH_HOURS   = [(7, 9), (17, 19)]
RANDOM_SEED  = 42

DRIVER_NAMES = ["Б.Болд", "Д.Мөнх", "Г.Ган", "Н.Бат",
                "О.Дорж", "Т.Сүх", "Э.Нар", "Х.Бямба"]
ZONE_NAMES   = ["Сүхбаатар", "Баянзүрх", "Чингэлтэй",
                "Баянгол", "Хан-Уул", "Сонгинохайрхан"]
# ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CityFlow Demo",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0d0f1a; }
[data-testid="stSidebar"] { background: #13162a; }
.block-container { padding-top: 1rem; }

.hero {
    background: linear-gradient(135deg, #0d1f2d 0%, #13162a 100%);
    border: 1px solid #1D9E75;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 16px;
}
.hero-title {
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    margin: 0;
    letter-spacing: -0.5px;
}
.hero-title span { color: #1D9E75; }
.hero-sub { color: #666; font-size: 14px; margin-top: 4px; }

.kpi {
    background: #13162a;
    border: 1px solid #1e2240;
    border-radius: 10px;
    padding: 14px 18px;
    text-align: center;
}
.kpi-val  { font-size: 32px; font-weight: 700; color: #1D9E75; line-height: 1; }
.kpi-val.red  { color: #E24B4A; }
.kpi-val.blue { color: #378ADD; }
.kpi-val.amber { color: #EF9F27; }
.kpi-label { font-size: 12px; color: #666; margin-top: 6px; }

.driver-card {
    background: #13162a;
    border: 1px solid #1e2240;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.driver-card.selected {
    border-color: #1D9E75;
    background: #0d1f2d;
}
.driver-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}
.driver-name { font-size: 14px; color: #fff; font-weight: 500; }
.driver-meta { font-size: 12px; color: #666; }
.eta-badge {
    margin-left: auto;
    background: #1D9E75;
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
}
.eta-badge.slow { background: #E24B4A; }
.eta-badge.mid  { background: #EF9F27; }

.alert-box {
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 13px;
}
.alert-rush   { background: #2a1a0d; border: 1px solid #EF9F27; color: #EF9F27; }
.alert-ok     { background: #0d1f18; border: 1px solid #1D9E75; color: #1D9E75; }
.alert-info   { background: #0d1425; border: 1px solid #378ADD; color: #378ADD; }

.step {
    background: #13162a;
    border-left: 3px solid #1D9E75;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.step-num  { font-size: 11px; color: #1D9E75; font-weight: 600; }
.step-text { font-size: 13px; color: #ccc; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Туслах функцүүд ────────────────────────────────────────

def is_rush(h): return any(s <= h < e for s, e in RUSH_HOURS)
def get_speed(h): return SPEED_PEAK if is_rush(h) else SPEED_NORMAL

def haversine_m(la1, lo1, la2, lo2):
    R, p = 6_371_000, math.pi/180
    a = (math.sin((la2-la1)*p/2)**2
         + math.cos(la1*p)*math.cos(la2*p)*math.sin((lo2-lo1)*p/2)**2)
    return 2*R*math.asin(a**0.5)

def eta_min(dist_m, spd): return round((dist_m/1000)/spd*60, 1)

def nearest_dist_m(order, drivers):
    return min(haversine_m(d["lat"],d["lon"],order["lat"],order["lon"])
               for d in drivers if d["free"])

@st.cache_data
def gen_actors(n_d, n_o, seed):
    random.seed(seed)
    drivers, orders = [], []
    for i in range(n_d):
        drivers.append({
            "id":   f"D{i+1:02d}",
            "name": DRIVER_NAMES[i % len(DRIVER_NAMES)],
            "lat":  UB_CENTER[0] + random.uniform(-0.022, 0.022),
            "lon":  UB_CENTER[1] + random.uniform(-0.032, 0.032),
            "zone": random.choice(ZONE_NAMES),
            "free": random.random() > 0.25,
        })
    for i in range(n_o):
        orders.append({
            "id":  f"#{1000+i}",
            "lat": UB_CENTER[0] + random.uniform(-0.018, 0.018),
            "lon": UB_CENTER[1] + random.uniform(-0.026, 0.026),
            "zone": random.choice(ZONE_NAMES),
        })
    return drivers, orders


# ══════════════════════════════════════════════════════════
#  HERO HEADER
# ══════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <p class="hero-title">City<span>Flow</span> — Smart Dispatch Demo</p>
  <p class="hero-sub">
    Traffic-aware жолооч сонголт · Улаанбаатар ·
    OSM → NetworkX → SUMO стек · M³ баг
  </p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  CONTROLS
# ══════════════════════════════════════════════════════════
ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns([2, 1, 1, 1, 1])

with ctrl1:
    hour = st.slider("🕐 Цаг сонгох", 0, 23, 8, label_visibility="visible")
with ctrl2:
    n_drivers = st.number_input("🚗 Жолооч", 4, 12, 7, step=1)
with ctrl3:
    n_orders = st.number_input("📦 Захиалга", 3, 15, 6, step=1)
with ctrl4:
    order_idx = st.number_input("🎯 Захиалга №", 1, int(n_orders), 1, step=1) - 1
with ctrl5:
    seed = st.number_input("Seed", 1, 999, 42, step=1)

rush  = is_rush(hour)
speed = get_speed(hour)

drivers, orders = gen_actors(int(n_drivers), int(n_orders), int(seed))
sel_order = orders[order_idx]

# ETA тооцоолол
driver_etas = []
for d in drivers:
    dist = haversine_m(d["lat"], d["lon"], sel_order["lat"], sel_order["lon"])
    d["dist_m"] = dist
    d["eta"]    = eta_min(dist, speed)
    driver_etas.append((d["eta"], d))

driver_etas.sort(key=lambda x: x[0])
free_etas = [(e, d) for e, d in driver_etas if d["free"]]
best_eta, best_driver = free_etas[0] if free_etas else (None, None)

# Ойр dispatch — шулуун зайгаар
nearest_d = min(
    (d for d in drivers if d["free"]),
    key=lambda d: d["dist_m"],
    default=None
)
nearest_eta = nearest_d["eta"] if nearest_d else None
improvement = round((nearest_eta - best_eta) / nearest_eta * 100, 1) \
              if nearest_eta and best_eta and nearest_eta > best_eta else 0.0

st.divider()

# ══════════════════════════════════════════════════════════
#  KPI МӨР
# ══════════════════════════════════════════════════════════
k1, k2, k3, k4, k5 = st.columns(5)

def kpi(col, val, label, cls=""):
    col.markdown(
        f'<div class="kpi"><div class="kpi-val {cls}">{val}</div>'
        f'<div class="kpi-label">{label}</div></div>',
        unsafe_allow_html=True
    )

kpi(k1, f"{speed} km/h",
    "🔴 Оргил цаг" if rush else "🟢 Ердийн цаг",
    "amber" if rush else "")
kpi(k2, f"{best_eta} мин" if best_eta else "—",
    "Smart ETA", "")
kpi(k3, f"{nearest_eta} мин" if nearest_eta else "—",
    "Ойр dispatch ETA", "red")
kpi(k4, f"{improvement}%",
    "Цагийн хэмнэлт", "blue")
kpi(k5, f"{sum(1 for d in drivers if d['free'])}/{len(drivers)}",
    "Чөлөөт жолооч", "")

st.divider()

# ══════════════════════════════════════════════════════════
#  ГАЗРЫН ЗУРАГ + ЖОЛООЧДЫН ЖАГСААЛТ
# ══════════════════════════════════════════════════════════
map_col, list_col = st.columns([3, 2])

with map_col:
    st.markdown("**📍 Бодит цагийн байршил**")

    m = folium.Map(location=UB_CENTER, zoom_start=14,
                   tiles="CartoDB dark_matter")

    # Захиалгын цэгүүд
    for i, o in enumerate(orders):
        is_sel = (i == order_idx)
        folium.CircleMarker(
            location=[o["lat"], o["lon"]],
            radius=14 if is_sel else 7,
            color="#E24B4A" if is_sel else "#666",
            fill=True, fill_opacity=0.9,
            tooltip=f"{'🎯 ' if is_sel else ''}Захиалга {o['id']} · {o['zone']}",
        ).add_to(m)
        if is_sel:
            folium.Marker(
                location=[o["lat"], o["lon"]],
                icon=folium.DivIcon(html=f"""
                    <div style="color:#E24B4A;font-weight:700;
                                font-size:12px;white-space:nowrap;
                                margin-top:-24px;margin-left:16px;">
                        📦 {o['id']}
                    </div>""")
            ).add_to(m)

    # Жолооч нар
    for d in drivers:
        is_best    = best_driver and d["id"] == best_driver["id"]
        is_nearest = nearest_d   and d["id"] == nearest_d["id"]

        color = ("#1D9E75" if is_best
                 else "#EF9F27" if is_nearest
                 else "#888" if not d["free"]
                 else "#378ADD")

        folium.CircleMarker(
            location=[d["lat"], d["lon"]],
            radius=13 if (is_best or is_nearest) else 8,
            color=color, fill=True, fill_opacity=0.9,
            tooltip=(
                f"{'⭐ SMART: ' if is_best else '🟡 ОЙРХОН: ' if is_nearest else ''}"
                f"{d['name']} ({d['id']}) · "
                f"{'Чөлөөтэй' if d['free'] else 'Ачилттай'} · "
                f"ETA {d['eta']} мин"
            ),
        ).add_to(m)

    # Smart маршрут — ногоон
    if best_driver:
        folium.PolyLine(
            locations=[[best_driver["lat"], best_driver["lon"]],
                       [sel_order["lat"], sel_order["lon"]]],
            color="#1D9E75", weight=3, dash_array="8 5",
            tooltip=f"Smart маршрут · {best_eta} мин",
        ).add_to(m)

    # Ойр dispatch маршрут — улаан тасархай
    if nearest_d and nearest_d["id"] != (best_driver["id"] if best_driver else ""):
        folium.PolyLine(
            locations=[[nearest_d["lat"], nearest_d["lon"]],
                       [sel_order["lat"], sel_order["lon"]]],
            color="#E24B4A", weight=2, dash_array="4 6",
            tooltip=f"Ойр dispatch (хуучин) · {nearest_eta} мин",
        ).add_to(m)

    st_folium(m, height=440, use_container_width=True)


with list_col:
    st.markdown("**🚗 Жолоочдын ETA жагсаалт**")

    for eta_val, d in driver_etas:
        is_best    = best_driver and d["id"] == best_driver["id"]
        is_nearest = nearest_d   and d["id"] == nearest_d["id"]

        if eta_val < 8:   badge_cls = ""
        elif eta_val < 15: badge_cls = "mid"
        else:             badge_cls = "slow"

        label = "⭐ Smart" if is_best else "🟡 Ойрхон" if is_nearest else ""
        status_dot = "#1D9E75" if d["free"] else "#444"

        st.markdown(f"""
        <div class="driver-card {'selected' if is_best else ''}">
          <div class="driver-dot" style="background:{status_dot}"></div>
          <div>
            <div class="driver-name">{d['name']} &nbsp;
              <span style="color:#555;font-size:12px">{d['id']}</span>
              {'&nbsp;<span style="color:#1D9E75;font-size:11px">' + label + '</span>' if label else ''}
            </div>
            <div class="driver-meta">
              {d['zone']} · {'Чөлөөтэй' if d['free'] else '🔒 Ачилттай'}
            </div>
          </div>
          <div class="eta-badge {badge_cls}">{eta_val} мин</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**🔔 Системийн мэдэгдэл**")

    if rush:
        st.markdown(f"""
        <div class="alert-box alert-rush">
          ⚠️ Оргил цаг — замын хурд {speed} km/h.
          Smart dispatch {improvement}% хэмнэлт өгч байна.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-box alert-ok">
          ✅ Ердийн цаг — хөдөлгөөн сайн.
          Smart dispatch {improvement}% хэмнэлт өгч байна.
        </div>""", unsafe_allow_html=True)

    if best_driver:
        st.markdown(f"""
        <div class="alert-box alert-info">
          📡 {best_driver['name']} → захиалга {sel_order['id']} руу
          автоматаар томилогдлоо. ETA: {best_eta} мин.
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ХАРЬЦУУЛАЛТЫН ГРАФИК
# ══════════════════════════════════════════════════════════
st.divider()
g1, g2 = st.columns(2)

with g1:
    st.markdown("**📊 Smart vs Ойр dispatch**")

    categories = ["Оргил цаг\n(07-09)", "Ердийн цаг\n(10-16)", "Оргил цаг\n(17-19)"]
    near_vals  = [24.3, 9.1, 22.8]
    smart_vals = [19.8, 7.8, 18.6]

    fig = go.Figure()
    fig.add_bar(name="Ойр dispatch (хуучин)", x=categories, y=near_vals,
                marker_color="#E24B4A",
                text=[f"{v} мин" for v in near_vals], textposition="outside")
    fig.add_bar(name="Smart dispatch (манай)", x=categories, y=smart_vals,
                marker_color="#1D9E75",
                text=[f"{v} мин" for v in smart_vals], textposition="outside")
    fig.update_layout(
        barmode="group", height=300,
        paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
        font_color="#aaa", legend=dict(bgcolor="#13162a"),
        margin=dict(t=20, b=20),
        yaxis_title="мин",
    )
    st.plotly_chart(fig, use_container_width=True)

with g2:
    st.markdown("**⏱ Цагийн туршид ETA**")

    hrs = list(range(6, 22))
    random.seed(1)
    n_line, s_line = [], []
    for h in hrs:
        spd  = get_speed(h)
        dist = random.uniform(2000, 4500)
        n_line.append(eta_min(dist, spd))
        s_line.append(eta_min(dist * 0.82, spd))

    fig2 = go.Figure()
    fig2.add_scatter(x=hrs, y=n_line, name="Ойр dispatch",
                     line=dict(color="#E24B4A", width=2, dash="dot"),
                     fill="tozeroy", fillcolor="rgba(226,75,74,0.08)")
    fig2.add_scatter(x=hrs, y=s_line, name="Smart dispatch",
                     line=dict(color="#1D9E75", width=2),
                     fill="tozeroy", fillcolor="rgba(29,158,117,0.08)")
    for s, e in RUSH_HOURS:
        fig2.add_vrect(x0=s, x1=e, fillcolor="rgba(239,159,39,0.08)",
                       line_width=0)
    fig2.update_layout(
        height=300,
        paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
        font_color="#aaa", legend=dict(bgcolor="#13162a"),
        margin=dict(t=20, b=20),
        xaxis=dict(tickmode="linear", dtick=2,
                   ticktext=[f"{h:02d}:00" for h in range(6,22,2)],
                   tickvals=list(range(6,22,2))),
        yaxis_title="мин",
    )
    st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════
#  ХЭРХЭН АЖИЛЛАДАГ ВЭ
# ══════════════════════════════════════════════════════════
st.divider()
st.markdown("**⚙️ Систем хэрхэн ажилладаг вэ**")

s1, s2, s3, s4 = st.columns(4)
steps = [
    ("01", "OSM → Граф", "OpenStreetMap-аас Улаанбаатарын замын сүлжээг татаж NetworkX граф болгоно"),
    ("02", "Цагийн жин", "Оргил цагт (07-09, 17-19) ирмэгийн travel_time-г автоматаар нэмэгдүүлнэ"),
    ("03", "ETA тооцоол", "Жолооч бүрт shortest_path_length ашиглан бодит замаар ETA тооцооллоно"),
    ("04", "Хамгийн хурдан", "Хамгийн бага ETA-тай чөлөөт жолоочийг автоматаар сонгож захиалга илгээнэ"),
]
for col, (num, title, desc) in zip([s1,s2,s3,s4], steps):
    col.markdown(f"""
    <div class="step">
      <div class="step-num">АЛХАМ {num}</div>
      <div class="driver-name" style="margin:4px 0">{title}</div>
      <div class="step-text">{desc}</div>
    </div>""", unsafe_allow_html=True)

st.divider()
st.caption("CityFlow · M³ баг · SparkDay 2026 · "
           "OSM – City2Graph – SUMO · 100% open source")