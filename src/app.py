"""
src/dashboard/app.py
CityFlow — Executive Demo Dashboard

Ажиллуулах:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import json
import streamlit as st
import pandas as pd
import folium
import plotly.graph_objects as go
import plotly.express as px
from streamlit_folium import st_folium

from config.loader import get as get_cfg
from src.optimization.mock_data import run_all
from src.utils import is_rush_hour, get_speed

# ── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="CityFlow",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#0d0f1a; }
[data-testid="stSidebar"]          { background:#13162a; }
.block-container { padding-top:1rem; }

.kpi-card {
    background:#13162a; border:1px solid #1e2240;
    border-radius:10px; padding:16px 20px; text-align:center;
}
.kpi-val   { font-size:30px; font-weight:700; line-height:1.1; }
.kpi-label { font-size:12px; color:#666; margin-top:6px; }
.kpi-sub   { font-size:11px; margin-top:4px; }

.green  { color:#1D9E75; } .red   { color:#E24B4A; }
.blue   { color:#378ADD; } .amber { color:#EF9F27; }

.section { font-size:15px; font-weight:600; color:#fff;
           margin:16px 0 10px; padding-bottom:6px;
           border-bottom:1px solid #1e2240; }
.tag {
    display:inline-block; font-size:11px; padding:2px 10px;
    border-radius:20px; font-weight:600;
}
.tag-green  { background:#0d1f18; color:#1D9E75; border:1px solid #1D9E75; }
.tag-red    { background:#1f0d0d; color:#E24B4A; border:1px solid #E24B4A; }
.tag-amber  { background:#1f1a0d; color:#EF9F27; border:1px solid #EF9F27; }
</style>
""", unsafe_allow_html=True)


# ── Туслах UI функцүүд ────────────────────────────────────

def kpi_card(col, value: str, label: str,
             sub: str = "", color: str = "green") -> None:
    """Стандарт KPI карт."""
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-val {color}">{value}</div>
      <div class="kpi-label">{label}</div>
      {"<div class='kpi-sub " + color + "'>" + sub + "</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)


def tag(text: str, color: str = "green") -> str:
    return f'<span class="tag tag-{color}">{text}</span>'


def section(title: str) -> None:
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)


# ── Config & Data ─────────────────────────────────────────

@st.cache_data
def load_data():
    cfg  = get_cfg()
    data = run_all(cfg)
    return cfg, data


cfg, data = load_data()
orders  = data["orders"]
drivers = data["drivers"]
routes  = data["routes"]
kpi     = data["kpi"]


# ══════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🌊 CityFlow")
    st.caption("Smart Dispatch · Улаанбаатар")
    st.divider()

    hour = st.slider("🕐 Симуляцийн цаг", 0, 23, 8)
    rush = is_rush_hour(hour, cfg["traffic"]["rush_hours"])
    spd  = get_speed(hour, cfg)

    if rush:
        st.error(f"🔴 Оргил цаг — {spd} km/h")
    else:
        st.success(f"🟢 Ердийн цаг — {spd} km/h")

    st.divider()
    view = st.radio("Харах хэсэг", ["📊 Executive", "🗺️ Газрын зураг",
                                     "📦 Захиалга", "🚗 Жолооч"])
    st.divider()

    if st.button("🔄 Өгөгдөл шинэчлэх", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("M³ баг · SparkDay 2026")


# ══════════════════════════════════════════════════════════
#  HERO
# ══════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1f2d,#13162a);
            border:1px solid #1D9E75;border-radius:12px;
            padding:18px 24px;margin-bottom:16px;">
  <span style="font-size:24px;font-weight:700;color:#fff;">
    City<span style="color:#1D9E75;">Flow</span>
  </span>
  <span style="color:#444;font-size:14px;margin-left:12px;">
    Traffic-aware Smart Dispatch · Улаанбаатар · OSM–NetworkX–SUMO
  </span>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  EXECUTIVE VIEW
# ══════════════════════════════════════════════════════════
if "Executive" in view:

    # ── KPI мөр ───────────────────────────────────────────
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    kpi_card(c1, str(kpi["total_orders"]),  "Нийт захиалга",  "", "blue")
    kpi_card(c2, str(kpi["completed"]),     "Хүргэсэн",
             f"{round(kpi['completed']/kpi['total_orders']*100)}%", "green")
    kpi_card(c3, f"{kpi['avg_smart_eta']} мин",
             "Smart ETA (оргил)", "↓ хамгийн хурдан", "green")
    kpi_card(c4, f"{kpi['avg_nearest_eta']} мин",
             "Ойр dispatch ETA", "хуучин арга", "red")
    kpi_card(c5, f"{kpi['improvement_pct']}%",
             "Цагийн хэмнэлт", f"↓ {kpi['time_saved_min']} мин", "amber")
    kpi_card(c6, f"{kpi['co2_saved_kg']} кг",
             "CO₂ хэмнэлт", "нүүрстөрөгч бууралт", "green")

    st.divider()

    # ── Харьцуулалтын график ───────────────────────────────
    left, right = st.columns(2)

    with left:
        section("📊 Smart vs Ойр dispatch — ETA харьцуулалт")
        cats      = ["Оргил цаг\n07-09", "Ердийн цаг\n10-16", "Оргил цаг\n17-19"]
        near_vals = [kpi["avg_nearest_eta"], round(kpi["avg_nearest_eta"]*0.38,1),
                     round(kpi["avg_nearest_eta"]*0.94,1)]
        smart_vals= [kpi["avg_smart_eta"],   round(kpi["avg_smart_eta"]*0.38,1),
                     round(kpi["avg_smart_eta"]*0.94,1)]
        fig = go.Figure()
        fig.add_bar(name="Ойр dispatch", x=cats, y=near_vals,
                    marker_color="#E24B4A",
                    text=[f"{v} мин" for v in near_vals], textposition="outside")
        fig.add_bar(name="Smart dispatch", x=cats, y=smart_vals,
                    marker_color="#1D9E75",
                    text=[f"{v} мин" for v in smart_vals], textposition="outside")
        fig.update_layout(barmode="group", height=300,
                          paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
                          font_color="#aaa", legend=dict(bgcolor="#13162a"),
                          margin=dict(t=10,b=10), yaxis_title="мин")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        section("⏱ Цагийн туршид дундаж ETA")
        import random
        random.seed(1)
        hrs, n_line, s_line = list(range(6,22)), [], []
        for h in hrs:
            sp   = get_speed(h, cfg)
            dist = random.uniform(2000, 4500)
            n_line.append(round((dist/1000)/sp*60, 1))
            s_line.append(round((dist*0.83/1000)/sp*60, 1))

        fig2 = go.Figure()
        fig2.add_scatter(x=hrs, y=n_line, name="Ойр dispatch",
                         line=dict(color="#E24B4A", width=2, dash="dot"),
                         fill="tozeroy", fillcolor="rgba(226,75,74,0.07)")
        fig2.add_scatter(x=hrs, y=s_line, name="Smart dispatch",
                         line=dict(color="#1D9E75", width=2),
                         fill="tozeroy", fillcolor="rgba(29,158,117,0.07)")
        for s,e in cfg["traffic"]["rush_hours"]:
            fig2.add_vrect(x0=s,x1=e, fillcolor="rgba(239,159,39,0.08)",
                           line_width=0)
        fig2.update_layout(height=300,
                           paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
                           font_color="#aaa", legend=dict(bgcolor="#13162a"),
                           margin=dict(t=10,b=10), yaxis_title="мин",
                           xaxis=dict(tickmode="linear", dtick=2))
        st.plotly_chart(fig2, use_container_width=True)

    # ── Маршрут харьцуулалт ───────────────────────────────
    section("🛣️ 3 маршрутын ETA харьцуулалт (оргил цаг, дундаж)")
    mc1, mc2, mc3 = st.columns(3)
    methods = ["Nearest","Smart","Alternative"]
    colors  = ["#E24B4A","#1D9E75","#378ADD"]
    labels  = ["Ойр dispatch","Smart dispatch","Альтернатив"]
    descs   = ["Шулуун зай — хурд харгалзахгүй",
               "Замын граф + оргил цагийн жин",
               "Гуравдагч сонголт — backup маршрут"]

    for col, mth, clr, lbl, dsc in zip([mc1,mc2,mc3], methods, colors, labels, descs):
        avg_e = routes[routes["method"]==mth]["eta_peak_min"].mean()
        col.markdown(f"""
        <div style="background:#13162a;border:1px solid #1e2240;
                    border-top:3px solid {clr};border-radius:8px;padding:14px;">
          <div style="font-size:11px;color:#666;">{lbl}</div>
          <div style="font-size:26px;font-weight:700;color:{clr};margin:6px 0;">
            {avg_e:.1f} мин
          </div>
          <div style="font-size:12px;color:#888;">{dsc}</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  MAP VIEW
# ══════════════════════════════════════════════════════════
elif "Газрын зураг" in view:
    section("📍 Жолооч & Захиалгын байршил")

    m = folium.Map(location=[cfg["city"]["center_lat"],
                              cfg["city"]["center_lon"]],
                   zoom_start=13, tiles="CartoDB dark_matter")

    # Захиалгууд
    for _, o in orders.iterrows():
        color = "red" if is_rush_hour(o["hour"], cfg["traffic"]["rush_hours"]) else "orange"
        folium.CircleMarker(
            location=[o["lat"], o["lon"]], radius=6,
            color=color, fill=True, fill_opacity=0.7,
            tooltip=f"Захиалга {o['order_id']} · {o['district']} · {o['hour']:02d}:00",
        ).add_to(m)

    # Жолооч нар
    for _, d in drivers.iterrows():
        color = "#1D9E75" if d["status"]=="Чөлөөтэй" else "#666"
        folium.CircleMarker(
            location=[d["lat"], d["lon"]], radius=9,
            color=color, fill=True, fill_opacity=0.9,
            tooltip=f"{d['name']} ({d['driver_id']}) · {d['status']}",
        ).add_to(m)

    st_folium(m, height=500, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        section("Захиалга дүүрэгээр")
        dist_cnt = orders.groupby("district").size().reset_index(name="тоо")
        fig = px.bar(dist_cnt, x="district", y="тоо",
                     color_discrete_sequence=["#1D9E75"])
        fig.update_layout(paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
                          font_color="#aaa", margin=dict(t=10,b=10), height=250)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section("Цагийн тархалт")
        hour_cnt = orders.groupby("hour").size().reset_index(name="тоо")
        fig2 = px.bar(hour_cnt, x="hour", y="тоо",
                      color_discrete_sequence=["#378ADD"])
        fig2.update_layout(paper_bgcolor="#0d0f1a", plot_bgcolor="#0d0f1a",
                           font_color="#aaa", margin=dict(t=10,b=10), height=250)
        st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════
#  ORDERS VIEW
# ══════════════════════════════════════════════════════════
elif "Захиалга" in view:
    section("📦 Захиалгын жагсаалт")

    status_filter = st.multiselect(
        "Статус шүүх",
        options=orders["status"].unique().tolist(),
        default=orders["status"].unique().tolist(),
    )
    filtered = orders[orders["status"].isin(status_filter)]

    def status_tag(s):
        if s == "Хүргэсэн":   return "🟢 " + s
        if s == "Явж байна":  return "🟡 " + s
        return "🔴 " + s

    display = filtered.copy()
    display["status"] = display["status"].apply(status_tag)
    display["hour"]   = display["hour"].apply(lambda h: f"{h:02d}:00")

    st.dataframe(
        display[["order_id","district","hour","status","company","n_items"]],
        hide_index=True, use_container_width=True, height=420,
    )

    section("🛣️ Маршрутын харьцуулалт — дээш нь сонго")
    sel_order = st.selectbox("Захиалга сонгох",
                              options=orders["order_id"].tolist())
    sel_routes = routes[routes["order_id"] == sel_order].copy()

    if not sel_routes.empty:
        for _, r in sel_routes.iterrows():
            clr = {"Nearest":"#E24B4A","Smart":"#1D9E75",
                   "Alternative":"#378ADD"}.get(r["method"],"#888")
            cng_tag = {"Өндөр":"red","Дунд":"amber","Бага":"green"}.get(
                r["congestion_lvl"],"green")
            st.markdown(f"""
            <div style="background:#13162a;border-left:3px solid {clr};
                        border-radius:4px;padding:12px 16px;margin-bottom:8px;">
              <b style="color:{clr};">{r['method']}</b>
              &nbsp;·&nbsp; Жолооч: {r['driver_name']} ({r['driver_id']})
              &nbsp;·&nbsp; Оргил ETA: <b>{r['eta_peak_min']} мин</b>
              &nbsp;·&nbsp; Ердийн ETA: {r['eta_normal_min']} мин
              &nbsp;·&nbsp; {r['distance_m']:,} м
              &nbsp;&nbsp; {tag(r['congestion_lvl'], cng_tag)}
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  DRIVERS VIEW
# ══════════════════════════════════════════════════════════
elif "Жолооч" in view:
    section("🚗 Жолоочдын мэдээлэл")

    free_cnt = (drivers["status"] == "Чөлөөтэй").sum()
    busy_cnt = len(drivers) - free_cnt

    d1,d2,d3,d4 = st.columns(4)
    kpi_card(d1, str(len(drivers)),       "Нийт жолооч", "", "blue")
    kpi_card(d2, str(free_cnt),           "Чөлөөтэй",   "", "green")
    kpi_card(d3, str(busy_cnt),           "Явж байна",   "", "amber")
    kpi_card(d4, f"{drivers['completed_today'].sum()}",
             "Өнөөдрийн хүргэлт", "", "green")

    st.divider()
    for _, d in drivers.iterrows():
        clr   = "#1D9E75" if d["status"]=="Чөлөөтэй" else "#EF9F27"
        stars = "★" * int(d["rating"]) + "☆" * (5 - int(d["rating"]))
        st.markdown(f"""
        <div style="background:#13162a;border:1px solid #1e2240;
                    border-radius:8px;padding:12px 16px;margin-bottom:8px;
                    display:flex;align-items:center;gap:16px;">
          <div style="width:38px;height:38px;border-radius:50%;
                      background:#0d1f18;display:flex;align-items:center;
                      justify-content:center;font-weight:700;color:{clr};
                      font-size:14px;flex-shrink:0;">
            {d['driver_id']}
          </div>
          <div style="flex:1;">
            <div style="color:#fff;font-weight:600;">{d['name']}</div>
            <div style="color:#666;font-size:12px;">
              {d['district']} &nbsp;·&nbsp;
              <span style="color:{clr};">{d['status']}</span>
            </div>
          </div>
          <div style="text-align:right;">
            <div style="color:#EF9F27;font-size:13px;">{stars}</div>
            <div style="color:#888;font-size:12px;">
              {d['completed_today']} хүргэлт өнөөдөр
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────
st.divider()
st.caption("CityFlow · M³ баг · SparkDay 2026 · OSM–City2Graph–SUMO · 100% open source")