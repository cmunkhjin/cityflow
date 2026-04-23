"""
src/dashboard/app.py
CityFlow — Executive Demo Dashboard (Сайжруулсан хувилбар)

Ажиллуулах:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations
import sys
import random
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import pandas as pd
import folium
import plotly.graph_objects as go
import plotly.express as px
from streamlit_folium import st_folium

from config.loader import get as get_cfg
from src.optimization.mock_data import run_all
from src.utils import is_rush_hour, get_speed, haversine_m, eta_minutes


# ══════════════════════════════════════════════════════════
#  PAGE CONFIG — хамгийн эхэнд байх ёстой
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CityFlow · Smart Dispatch",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════
#  CUSTOM CSS — цагаан background, том текст, clean cards
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Үндсэн арын өнгө: цагаан ── */
[data-testid="stAppViewContainer"] {
    background: #F8F9FC;
}
[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E8ECF4;
}
[data-testid="stSidebar"] * {
    color: #1A1F36 !important;
}
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* ── KPI карт ── */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E8ECF4;
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s;
}
.kpi-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.10);
}
.kpi-val {
    font-size: 32px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.5px;
}
.kpi-label {
    font-size: 13px;
    color: #6B7280;
    margin-top: 6px;
    font-weight: 500;
}
.kpi-sub {
    font-size: 12px;
    margin-top: 5px;
    font-weight: 600;
}

/* ── Өнгөний систем ── */
.green  { color: #059669; }
.red    { color: #DC2626; }
.blue   { color: #2563EB; }
.amber  { color: #D97706; }
.purple { color: #7C3AED; }

/* ── Section гарчиг ── */
.section-title {
    font-size: 16px;
    font-weight: 700;
    color: #1A1F36;
    margin: 20px 0 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #E8ECF4;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ── Badge / Tag ── */
.badge {
    display: inline-block;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 20px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
.badge-green  { background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; }
.badge-red    { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; }
.badge-amber  { background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A; }
.badge-blue   { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; }

/* ── Route карт ── */
.route-card {
    background: #FFFFFF;
    border: 1px solid #E8ECF4;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* ── Driver карт ── */
.driver-card {
    background: #FFFFFF;
    border: 1px solid #E8ECF4;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    display: flex;
    align-items: center;
    gap: 14px;
}

/* ── Hero banner ── */
.hero-banner {
    background: linear-gradient(135deg, #1A1F36 0%, #2563EB 100%);
    border-radius: 14px;
    padding: 22px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* ── Info box ── */
.info-box {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
    font-size: 13px;
    color: #1E40AF;
}

/* ── Recommended driver block ── */
.recommended-block {
    background: linear-gradient(135deg, #ECFDF5, #D1FAE5);
    border: 2px solid #059669;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
}

/* ── Legend item ── */
.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #374151;
    margin-bottom: 6px;
}
.legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ── Step guide ── */
.step-guide {
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 13px;
    color: #166534;
}
.step-num {
    background: #059669;
    color: white;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    margin-right: 8px;
}

/* Streamlit-ийн default текст өнгийг override */
.stMarkdown p, .stMarkdown li { color: #374151; }
h1, h2, h3 { color: #1A1F36; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ТУСЛАХ UI ФУНКЦҮҮД
# ══════════════════════════════════════════════════════════

def kpi_card(col, value: str, label: str, sub: str = "", color: str = "blue") -> None:
    """KPI карт харуулах."""
    sub_html = f'<div class="kpi-sub {color}">{sub}</div>' if sub else ""
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-val {color}">{value}</div>
      <div class="kpi-label">{label}</div>
      {sub_html}
    </div>""", unsafe_allow_html=True)


def section_title(icon: str, title: str) -> None:
    """Хэсгийн гарчиг."""
    st.markdown(f'<div class="section-title">{icon} {title}</div>',
                unsafe_allow_html=True)


def badge(text: str, color: str = "green") -> str:
    """Inline badge HTML буцаана."""
    return f'<span class="badge badge-{color}">{text}</span>'


def congestion_badge(level: str) -> str:
    """Түгжрэлийн түвшний badge."""
    color_map = {"Өндөр": "red", "Дунд": "amber", "Бага": "green"}
    return badge(level, color_map.get(level, "blue"))


def status_badge(status: str) -> str:
    """Захиалгын статусын badge."""
    color_map = {"Хүргэсэн": "green", "Явж байна": "amber", "Хойшлогдсон": "red"}
    return badge(status, color_map.get(status, "blue"))


# ══════════════════════════════════════════════════════════
#  CONFIG & DATA АЧААЛАХ
# ══════════════════════════════════════════════════════════

@st.cache_data
def load_data():
    """Config болон mock өгөгдөл нэг удаа ачаална."""
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
    st.caption("Smart Dispatch · Улаанбаатар хот")
    st.divider()

    # Цагийн сонголт
    st.markdown("**🕐 Симуляцийн цаг**")
    hour = st.slider("", 0, 23, 8, label_visibility="collapsed")
    rush = is_rush_hour(hour, cfg["traffic"]["rush_hours"])
    spd  = get_speed(hour, cfg)

    if rush:
        st.error(f"🔴 **Оргил цаг** — {spd} км/цаг\n\nТүгжрэл өндөр байна")
    else:
        st.success(f"🟢 **Ердийн цаг** — {spd} км/цаг\n\nЗам харьцангуй чөлөөтэй")

    st.divider()

    # Харах хэсгийн сонголт
    st.markdown("**📋 Хэсэг сонгох**")
    view = st.radio("", ["📊 Үзлэг", "🗺️ Газрын зураг",
                         "📦 Захиалга", "🚗 Жолооч & Маршрут"],
                    label_visibility="collapsed")
    st.divider()

    # Өгөгдөл шинэчлэх
    if st.button("🔄 Шинэчлэх", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Хэрхэн ашиглах заавар
    st.markdown("**📖 Хэрхэн ашиглах вэ?**")
    st.markdown("""
    <div class="step-guide">
      <div style="margin-bottom:8px;">
        <span class="step-num">1</span>
        Цагийн slider-ийг тохируул
      </div>
      <div style="margin-bottom:8px;">
        <span class="step-num">2</span>
        "Жолооч & Маршрут" хэсгийг нээ
      </div>
      <div style="margin-bottom:8px;">
        <span class="step-num">3</span>
        Жолооч болон захиалга сонго
      </div>
      <div>
        <span class="step-num">4</span>
        Маршрут болон ETA харна
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption("M³ баг · SparkDay 2026")


# ══════════════════════════════════════════════════════════
#  HERO BANNER
# ══════════════════════════════════════════════════════════
rush_label = "🔴 Оргил цаг" if rush else "🟢 Ердийн цаг"
rush_color = "#FEF2F2" if rush else "#ECFDF5"
rush_text  = "#DC2626" if rush else "#059669"

st.markdown(f"""
<div class="hero-banner">
  <div>
    <div style="font-size:26px;font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;">
      City<span style="color:#60A5FA;">Flow</span>
    </div>
    <div style="color:#94A3B8;font-size:14px;margin-top:4px;">
      Traffic-aware Smart Dispatch · Улаанбаатар · OSM–NetworkX–SUMO
    </div>
  </div>
  <div style="text-align:right;">
    <div style="background:{rush_color};color:{rush_text};padding:8px 16px;
                border-radius:20px;font-weight:700;font-size:14px;">
      {rush_label} · {spd} км/цаг
    </div>
    <div style="color:#94A3B8;font-size:12px;margin-top:6px;">
      Одоогийн симуляцийн цаг: {hour:02d}:00
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  1. ҮЗЛЭГ (EXECUTIVE VIEW)
# ══════════════════════════════════════════════════════════
if "Үзлэг" in view:

    # ── Тайлбар ──────────────────────────────────────────
    st.markdown("""
    <div class="info-box">
      💡 <b>Энэ хэсэгт</b> CityFlow системийн гол үзүүлэлтүүд харагдана.
      Smart dispatch нь замын графаар бодит ETA тооцоолж,
      ойрын жолоочийг шулуун зайгаар сонгодог хуучин аргаас <b>илүү үр дүнтэй</b>.
    </div>
    """, unsafe_allow_html=True)

    # ── KPI мөр ──────────────────────────────────────────
    section_title("📊", "Гол үзүүлэлтүүд")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpi_card(c1, str(kpi["total_orders"]),   "Нийт захиалга",    "",                        "blue")
    kpi_card(c2, str(kpi["completed"]),      "Хүргэсэн",
             f"{round(kpi['completed']/kpi['total_orders']*100)}% гүйцэтгэл",              "green")
    kpi_card(c3, f"{kpi['avg_smart_eta']}м", "Smart ETA",        "↓ хамгийн хурдан арга",   "green")
    kpi_card(c4, f"{kpi['avg_nearest_eta']}м","Хуучин ETA",      "шулуун зай арга",          "red")
    kpi_card(c5, f"{kpi['improvement_pct']}%","Цагийн хэмнэлт", f"↓ {kpi['time_saved_min']} минут", "amber")
    kpi_card(c6, f"{kpi['co2_saved_kg']} кг","CO₂ бууралт",     "хүргэлтийн замын хэмнэлт","purple")

    # KPI тайлбар
    st.markdown("""
    <div style="background:#F8F9FC;border:1px solid #E8ECF4;border-radius:8px;
                padding:12px 16px;margin-top:8px;font-size:12px;color:#6B7280;">
      <b>KPI тайлбар:</b>
      Smart ETA = замын графаар тооцоолсон хурдан зам ·
      Хуучин ETA = шулуун зайгаар ойр жолооч ·
      CO₂ бууралт = замын хэмнэлтээс тооцсон
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Харьцуулалтын графикууд ────────────────────────
    left, right = st.columns(2)

    with left:
        section_title("📈", "Smart vs Хуучин Dispatch — ETA харьцуулалт")

        # Тайлбар
        st.caption("🔴 Хуучин арга: шулуун зайгаар хамгийн ойр жолоочийг сонгоно · "
                   "🟢 Smart: замын граф + оргил цагийн жинг харгалзана")

        cats      = ["Өглөөний\nоргил (07-09)", "Өдрийн\nердийн (10-16)", "Оройн\nоргил (17-19)"]
        near_vals = [kpi["avg_nearest_eta"],
                     round(kpi["avg_nearest_eta"] * 0.38, 1),
                     round(kpi["avg_nearest_eta"] * 0.94, 1)]
        smart_vals = [kpi["avg_smart_eta"],
                      round(kpi["avg_smart_eta"] * 0.38, 1),
                      round(kpi["avg_smart_eta"] * 0.94, 1)]

        fig = go.Figure()
        fig.add_bar(name="Хуучин dispatch", x=cats, y=near_vals,
                    marker_color="#DC2626",
                    text=[f"{v} мин" for v in near_vals], textposition="outside",
                    textfont=dict(color="#DC2626", size=12))
        fig.add_bar(name="Smart dispatch", x=cats, y=smart_vals,
                    marker_color="#059669",
                    text=[f"{v} мин" for v in smart_vals], textposition="outside",
                    textfont=dict(color="#059669", size=12))
        fig.update_layout(
            barmode="group", height=300,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8F9FC",
            font=dict(color="#374151", size=12),
            legend=dict(bgcolor="#FFFFFF", bordercolor="#E8ECF4", borderwidth=1),
            margin=dict(t=20, b=10, l=10, r=10),
            yaxis_title="минут",
            yaxis=dict(gridcolor="#E8ECF4"),
            xaxis=dict(gridcolor="#E8ECF4"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        section_title("⏱", "Өдрийн туршид ETA хэрхэн өөрчлөгдөх вэ?")
        st.caption("🟡 Шар бүс = оргил цаг (07-09, 17-19) · "
                   "Энэ үед Smart dispatch-ийн давуу тал хамгийн их харагдана")

        random.seed(1)
        hrs, n_line, s_line = list(range(6, 22)), [], []
        for h in hrs:
            sp   = get_speed(h, cfg)
            dist = random.uniform(2000, 4500)
            n_line.append(round((dist / 1000) / sp * 60, 1))
            s_line.append(round((dist * 0.83 / 1000) / sp * 60, 1))

        fig2 = go.Figure()
        fig2.add_scatter(x=hrs, y=n_line, name="Хуучин dispatch",
                         line=dict(color="#DC2626", width=2.5, dash="dot"),
                         fill="tozeroy", fillcolor="rgba(220,38,38,0.06)")
        fig2.add_scatter(x=hrs, y=s_line, name="Smart dispatch",
                         line=dict(color="#059669", width=2.5),
                         fill="tozeroy", fillcolor="rgba(5,150,105,0.08)")
        for s, e in cfg["traffic"]["rush_hours"]:
            fig2.add_vrect(x0=s, x1=e,
                           fillcolor="rgba(217,119,6,0.10)",
                           annotation_text="Оргил цаг",
                           annotation_font_color="#D97706",
                           annotation_font_size=10,
                           line_width=0)
        fig2.update_layout(
            height=300,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8F9FC",
            font=dict(color="#374151", size=12),
            legend=dict(bgcolor="#FFFFFF", bordercolor="#E8ECF4", borderwidth=1),
            margin=dict(t=20, b=10, l=10, r=10),
            yaxis_title="минут",
            xaxis=dict(tickmode="linear", dtick=2, gridcolor="#E8ECF4"),
            yaxis=dict(gridcolor="#E8ECF4"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── 3 маршрутын харьцуулалт ────────────────────────
    section_title("🛣️", "3 маршрутын ETA харьцуулалт (оргил цаг, дундаж)")

    method_info = [
        ("Nearest",     "#DC2626", "Хуучин арга",    "Шулуун зайгаар ойр жолоочийг сонгоно. Замын түгжрэл, бодит замын урт харгалздаггүй."),
        ("Smart",       "#059669", "Smart dispatch", "Замын графаар бодит ETA тооцоолно. Оргил цагийн жин нэмж үр ашигтай маршрут олно."),
        ("Alternative", "#2563EB", "Альтернатив",    "Backup маршрут. Smart-ийн дараагийн хамгийн сайн сонголт."),
    ]

    mc1, mc2, mc3 = st.columns(3)
    for col, (mth, clr, lbl, desc) in zip([mc1, mc2, mc3], method_info):
        avg_e = routes[routes["method"] == mth]["eta_peak_min"].mean()
        is_best = mth == "Smart"
        border_style = f"border-top: 4px solid {clr};"
        best_badge = '<div style="font-size:11px;color:#059669;font-weight:700;margin-bottom:6px;">⭐ ХАМГИЙН САЙН</div>' if is_best else ""

        col.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E8ECF4;{border_style}
                    border-radius:10px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
          {best_badge}
          <div style="font-size:12px;color:#6B7280;font-weight:600;">{lbl}</div>
          <div style="font-size:28px;font-weight:800;color:{clr};margin:8px 0;">
            {avg_e:.1f} мин
          </div>
          <div style="font-size:12px;color:#9CA3AF;line-height:1.5;">{desc}</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  2. ГАЗРЫН ЗУРАГ
# ══════════════════════════════════════════════════════════
elif "Газрын зураг" in view:

    # Legend
    st.markdown("""
    <div style="background:#FFFFFF;border:1px solid #E8ECF4;border-radius:10px;
                padding:14px 18px;margin-bottom:14px;display:flex;gap:24px;
                flex-wrap:wrap;">
      <div style="font-weight:700;font-size:13px;color:#1A1F36;margin-right:8px;">
        🗺️ Тайлбар:
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#DC2626;"></div>
        <span>Оргил цагийн захиалга</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#F97316;"></div>
        <span>Ердийн цагийн захиалга</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#059669;"></div>
        <span>Чөлөөтэй жолооч</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#9CA3AF;"></div>
        <span>Завгүй жолооч</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    section_title("📍", "Жолооч & Захиалгын байршил")

    m = folium.Map(
        location=[cfg["city"]["center_lat"], cfg["city"]["center_lon"]],
        zoom_start=13, tiles="CartoDB positron"
    )

    for _, o in orders.iterrows():
        color = "red" if is_rush_hour(o["hour"], cfg["traffic"]["rush_hours"]) else "orange"
        folium.CircleMarker(
            location=[o["lat"], o["lon"]], radius=6,
            color=color, fill=True, fill_opacity=0.75,
            tooltip=f"📦 {o['order_id']} · {o['district']} · {o['hour']:02d}:00 · {o['status']}",
        ).add_to(m)

    for _, d in drivers.iterrows():
        color = "#059669" if d["status"] == "Чөлөөтэй" else "#9CA3AF"
        folium.CircleMarker(
            location=[d["lat"], d["lon"]], radius=10,
            color=color, fill=True, fill_opacity=0.9,
            tooltip=f"🚗 {d['name']} ({d['driver_id']}) · {d['status']} · {d['district']}",
        ).add_to(m)

    st_folium(m, height=460, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        section_title("📊", "Захиалга дүүрэгээр")
        dist_cnt = orders.groupby("district").size().reset_index(name="тоо")
        fig = px.bar(dist_cnt, x="district", y="тоо",
                     color_discrete_sequence=["#2563EB"],
                     text="тоо")
        fig.update_traces(textposition="outside")
        fig.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8F9FC",
            font=dict(color="#374151"), margin=dict(t=10, b=10), height=250,
            xaxis=dict(gridcolor="#E8ECF4"), yaxis=dict(gridcolor="#E8ECF4"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_title("⏰", "Цагийн тархалт")
        hour_cnt = orders.groupby("hour").size().reset_index(name="тоо")
        colors_list = ["#DC2626" if is_rush_hour(h, cfg["traffic"]["rush_hours"])
                       else "#2563EB" for h in hour_cnt["hour"]]
        fig2 = go.Figure(go.Bar(
            x=hour_cnt["hour"], y=hour_cnt["тоо"],
            marker_color=colors_list, text=hour_cnt["тоо"],
            textposition="outside"
        ))
        fig2.update_layout(
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F8F9FC",
            font=dict(color="#374151"), margin=dict(t=10, b=10), height=250,
            xaxis=dict(gridcolor="#E8ECF4", title="цаг"),
            yaxis=dict(gridcolor="#E8ECF4"),
        )
        st.caption("🔴 Улаан = оргил цаг  ·  🔵 Цэнхэр = ердийн цаг")
        st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════
#  3. ЗАХИАЛГА
# ══════════════════════════════════════════════════════════
elif "Захиалга" in view:

    section_title("📦", "Захиалгын жагсаалт")

    # Шүүлтүүр
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        status_filter = st.multiselect(
            "Статус шүүх",
            options=orders["status"].unique().tolist(),
            default=orders["status"].unique().tolist(),
        )
    with col_f2:
        district_filter = st.selectbox(
            "Дүүрэг",
            options=["Бүгд"] + orders["district"].unique().tolist(),
        )

    filtered = orders[orders["status"].isin(status_filter)]
    if district_filter != "Бүгд":
        filtered = filtered[filtered["district"] == district_filter]

    # Статистик мини KPI
    sc1, sc2, sc3 = st.columns(3)
    kpi_card(sc1, str(len(filtered)),
             "Шүүсэн захиалга", f"нийт {len(orders)}-с", "blue")
    kpi_card(sc2, str((filtered["status"] == "Хүргэсэн").sum()),
             "Хүргэсэн", "", "green")
    kpi_card(sc3, str((filtered["status"] == "Явж байна").sum()),
             "Явж байна", "", "amber")

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    # Хүснэгт
    display = filtered.copy()
    display["hour"] = display["hour"].apply(lambda h: f"{h:02d}:00")
    st.dataframe(
        display[["order_id", "district", "hour", "status", "company", "n_items"]],
        hide_index=True, use_container_width=True, height=360,
        column_config={
            "order_id":  st.column_config.TextColumn("Захиалга"),
            "district":  st.column_config.TextColumn("Дүүрэг"),
            "hour":      st.column_config.TextColumn("Цаг"),
            "status":    st.column_config.TextColumn("Статус"),
            "company":   st.column_config.TextColumn("Компани"),
            "n_items":   st.column_config.NumberColumn("Тоо хэмжээ"),
        }
    )

    st.divider()

    # Захиалгын маршрут харах
    section_title("🛣️", "Захиалгын маршрут харах")
    st.caption("Захиалга сонгоход тухайн захиалгад тохирох 3 маршрутын харьцуулалт гарна.")

    sel_order = st.selectbox(
        "Захиалга сонгох",
        options=orders["order_id"].tolist(),
        format_func=lambda x: f"{x} — {orders[orders['order_id']==x]['district'].values[0]}"
    )
    sel_routes = routes[routes["order_id"] == sel_order].copy()

    if not sel_routes.empty:
        for _, r in sel_routes.iterrows():
            clr_map  = {"Nearest": "#DC2626", "Smart": "#059669", "Alternative": "#2563EB"}
            lbl_map  = {"Nearest": "Хуучин арга", "Smart": "Smart dispatch", "Alternative": "Альтернатив"}
            clr      = clr_map.get(r["method"], "#888")
            lbl      = lbl_map.get(r["method"], r["method"])
            is_best  = r["method"] == "Smart"
            best_txt = " ⭐ ХАМГИЙН САЙН СОНГОЛТ" if is_best else ""

            st.markdown(f"""
            <div class="route-card" style="border-left:4px solid {clr};">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="color:{clr};font-weight:700;font-size:15px;">{lbl}</span>
                  <span style="color:#059669;font-size:12px;font-weight:600;">{best_txt}</span>
                </div>
                {congestion_badge(r['congestion_lvl'])}
              </div>
              <div style="margin-top:10px;display:flex;gap:24px;flex-wrap:wrap;">
                <div>
                  <div style="font-size:11px;color:#9CA3AF;">Жолооч</div>
                  <div style="font-size:14px;font-weight:600;color:#1A1F36;">
                    {r['driver_name']} ({r['driver_id']})
                  </div>
                </div>
                <div>
                  <div style="font-size:11px;color:#9CA3AF;">Оргил цаг ETA</div>
                  <div style="font-size:20px;font-weight:800;color:{clr};">
                    {r['eta_peak_min']} мин
                  </div>
                </div>
                <div>
                  <div style="font-size:11px;color:#9CA3AF;">Ердийн цаг ETA</div>
                  <div style="font-size:14px;font-weight:600;color:#059669;">
                    {r['eta_normal_min']} мин
                  </div>
                </div>
                <div>
                  <div style="font-size:11px;color:#9CA3AF;">Зай</div>
                  <div style="font-size:14px;font-weight:600;color:#1A1F36;">
                    {r['distance_m']:,} м
                  </div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  4. ЖОЛООЧ & МАРШРУТ — гол интерактив хэсэг
# ══════════════════════════════════════════════════════════
elif "Жолооч" in view:

    # ── KPI мөр ──────────────────────────────────────────
    section_title("🚗", "Жолоочдын үзлэг")
    free_cnt = (drivers["status"] == "Чөлөөтэй").sum()
    busy_cnt = len(drivers) - free_cnt

    d1, d2, d3, d4 = st.columns(4)
    kpi_card(d1, str(len(drivers)),              "Нийт жолооч",        "",  "blue")
    kpi_card(d2, str(free_cnt),                   "Чөлөөтэй",          "Захиалга авах боломжтой", "green")
    kpi_card(d3, str(busy_cnt),                   "Явж байна",          "Одоогоор завгүй",         "amber")
    kpi_card(d4, f"{drivers['completed_today'].sum()}", "Өнөөдрийн нийт хүргэлт", "", "purple")

    st.divider()

    # ── ЖОЛООЧ + ХҮРГЭЛТ СОНГОХ — route visualization ──
    section_title("🗺️", "Жолооч & Хүргэлт сонгох — Маршрут харах")

    st.markdown("""
    <div class="info-box">
      🔍 <b>Жолооч болон захиалга сонгоход</b> тухайн маршрутын газрын зураг,
      ETA, түгжрэлийн түвшин, peak vs normal харьцуулалт шууд харагдана.
    </div>
    """, unsafe_allow_html=True)

    sel_col1, sel_col2 = st.columns(2)

    with sel_col1:
        st.markdown("**🚗 Жолооч сонгох**")
        free_drivers = drivers[drivers["status"] == "Чөлөөтэй"]
        driver_options = {
            f"{row['name']} ({row['driver_id']}) · {row['district']} · ⭐{row['rating']}": row
            for _, row in free_drivers.iterrows()
        }
        sel_driver_label = st.selectbox(
            "Жолооч",
            options=list(driver_options.keys()),
            label_visibility="collapsed"
        )
        sel_driver = driver_options[sel_driver_label]

    with sel_col2:
        st.markdown("**📦 Захиалга сонгох**")
        order_options = {
            f"{row['order_id']} · {row['district']} · {row['hour']:02d}:00 · {row['status']}": row
            for _, row in orders.iterrows()
        }
        sel_order_label = st.selectbox(
            "Захиалга",
            options=list(order_options.keys()),
            label_visibility="collapsed"
        )
        sel_order_row = order_options[sel_order_label]

    # ── Маршрутын тооцоолол ───────────────────────────
    o_lat = sel_order_row["lat"]
    o_lon = sel_order_row["lon"]
    d_lat = sel_driver["lat"]
    d_lon = sel_driver["lon"]
    o_hour = sel_order_row["hour"]

    dist_m      = haversine_m(d_lat, d_lon, o_lat, o_lon)
    rush_order  = is_rush_hour(o_hour, cfg["traffic"]["rush_hours"])
    speed_peak  = cfg["traffic"]["speed_peak_kmh"]
    speed_norm  = cfg["traffic"]["speed_normal_kmh"]
    eta_peak    = eta_minutes(dist_m, speed_peak)
    eta_normal  = eta_minutes(dist_m, speed_norm)
    cong_level  = "Өндөр" if rush_order else "Бага"
    cong_color  = "#DC2626" if rush_order else "#059669"

    # ── Recommended жолооч block ──────────────────────
    st.markdown(f"""
    <div class="recommended-block">
      <div style="font-size:13px;color:#065F46;font-weight:700;margin-bottom:10px;">
        ✅ СОНГОГДСОН ЖОЛООЧ — МАРШРУТЫН МЭДЭЭЛЭЛ
      </div>
      <div style="display:flex;gap:32px;flex-wrap:wrap;">
        <div>
          <div style="font-size:11px;color:#6B7280;">Жолооч</div>
          <div style="font-size:16px;font-weight:700;color:#1A1F36;">
            {sel_driver['name']} · {sel_driver['driver_id']}
          </div>
        </div>
        <div>
          <div style="font-size:11px;color:#6B7280;">Захиалга</div>
          <div style="font-size:16px;font-weight:700;color:#1A1F36;">
            {sel_order_row['order_id']} · {sel_order_row['district']}
          </div>
        </div>
        <div>
          <div style="font-size:11px;color:#6B7280;">Зай (шулуун)</div>
          <div style="font-size:16px;font-weight:700;color:#1A1F36;">
            {dist_m/1000:.2f} км
          </div>
        </div>
        <div>
          <div style="font-size:11px;color:#6B7280;">Оргил цаг ETA</div>
          <div style="font-size:22px;font-weight:800;color:#DC2626;">{eta_peak} мин</div>
        </div>
        <div>
          <div style="font-size:11px;color:#6B7280;">Ердийн цаг ETA</div>
          <div style="font-size:22px;font-weight:800;color:#059669;">{eta_normal} мин</div>
        </div>
        <div>
          <div style="font-size:11px;color:#6B7280;">Одоогийн түгжрэл</div>
          <div style="font-size:16px;font-weight:700;color:{cong_color};">{cong_level}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Route газрын зураг ────────────────────────────
    section_title("🗺️", "Маршрутын газрын зураг")
    st.caption("🟢 Ногоон тэмдэг = жолооч · 🔴 Улаан тэмдэг = захиалга · "
               "— Шугам = маршрут")

    route_map = folium.Map(
        location=[(d_lat + o_lat) / 2, (d_lon + o_lon) / 2],
        zoom_start=14, tiles="CartoDB positron"
    )

    # Жолоочийн байршил
    folium.Marker(
        location=[d_lat, d_lon],
        tooltip=f"🚗 {sel_driver['name']} ({sel_driver['driver_id']})\n{sel_driver['district']}",
        icon=folium.Icon(color="green", icon="car", prefix="fa"),
    ).add_to(route_map)

    # Захиалгын байршил
    folium.Marker(
        location=[o_lat, o_lon],
        tooltip=f"📦 {sel_order_row['order_id']}\n{sel_order_row['district']}",
        icon=folium.Icon(color="red", icon="box", prefix="fa"),
    ).add_to(route_map)

    # Маршрутын шугам — дундын цэгүүдтэй илүү бодитой харагдуулна
    mid_lat = (d_lat + o_lat) / 2 + random.uniform(-0.003, 0.003)
    mid_lon = (d_lon + o_lon) / 2 + random.uniform(-0.004, 0.004)
    route_points = [
        [d_lat, d_lon],
        [mid_lat, mid_lon],
        [o_lat, o_lon],
    ]

    line_color = "#DC2626" if rush_order else "#059669"
    folium.PolyLine(
        locations=route_points,
        color=line_color,
        weight=4,
        opacity=0.85,
        tooltip=f"Маршрут · {dist_m/1000:.2f} км · ETA: {eta_peak if rush_order else eta_normal} мин",
        dash_array="8" if rush_order else None,
    ).add_to(route_map)

    # Бусад жолоочийг дэвсгэрт харуулна
    for _, d in drivers.iterrows():
        if d["driver_id"] == sel_driver["driver_id"]:
            continue
        c = "#059669" if d["status"] == "Чөлөөтэй" else "#9CA3AF"
        folium.CircleMarker(
            location=[d["lat"], d["lon"]], radius=6,
            color=c, fill=True, fill_opacity=0.5,
            tooltip=f"{d['name']} · {d['status']}",
        ).add_to(route_map)

    st_folium(route_map, height=420, use_container_width=True)

    # ── Peak vs Normal харьцуулалтын chart ────────────
    section_title("📊", "Оргил цаг vs Ердийн цаг — ETA харьцуулалт")
    st.caption(f"Сонгосон маршрутад замын хурдын ялгаа ETA-д хэрхэн нөлөөлж байгааг харуулна. "
               f"Захиалгын цаг: {o_hour:02d}:00 ({'🔴 Оргил цаг' if rush_order else '🟢 Ердийн цаг'})")

    compare_fig = go.Figure()
    categories = ["Жолоочоос захиалга хүртэл"]

    compare_fig.add_bar(
        name=f"Оргил цаг ({speed_peak} км/цаг)",
        x=categories, y=[eta_peak],
        marker_color="#DC2626",
        text=[f"{eta_peak} мин"], textposition="outside",
        textfont=dict(size=14, color="#DC2626"),
    )
    compare_fig.add_bar(
        name=f"Ердийн цаг ({speed_norm} км/цаг)",
        x=categories, y=[eta_normal],
        marker_color="#059669",
        text=[f"{eta_normal} мин"], textposition="outside",
        textfont=dict(size=14, color="#059669"),
    )

    diff = eta_peak - eta_normal
    compare_fig.update_layout(
        barmode="group", height=280,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F8F9FC",
        font=dict(color="#374151", size=13),
        legend=dict(bgcolor="#FFFFFF", bordercolor="#E8ECF4", borderwidth=1,
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=10, l=10, r=10),
        yaxis=dict(gridcolor="#E8ECF4", title="минут"),
        xaxis=dict(gridcolor="#E8ECF4"),
        title=dict(
            text=f"Оргил цагт {diff:.1f} минут удаана байна",
            font=dict(size=13, color="#6B7280"), x=0.5
        )
    )
    st.plotly_chart(compare_fig, use_container_width=True)

    # ── Жолоочдын дэлгэрэнгүй жагсаалт ──────────────
    st.divider()
    section_title("👥", "Бүх жолоочдын жагсаалт")

    for _, d in drivers.iterrows():
        clr     = "#059669" if d["status"] == "Чөлөөтэй" else "#D97706"
        stars   = "★" * int(d["rating"]) + "☆" * (5 - int(d["rating"]))
        is_sel  = d["driver_id"] == sel_driver["driver_id"]
        sel_border = "border: 2px solid #059669;" if is_sel else "border: 1px solid #E8ECF4;"
        sel_badge  = ' <span style="background:#ECFDF5;color:#059669;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:700;">СОНГОГДСОН</span>' if is_sel else ""

        st.markdown(f"""
        <div style="background:#FFFFFF;{sel_border}border-radius:10px;
                    padding:14px 18px;margin-bottom:8px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.04);">
          <div style="display:flex;align-items:center;gap:14px;">
            <div style="width:40px;height:40px;border-radius:50%;
                        background:{'#ECFDF5' if d['status']=='Чөлөөтэй' else '#FFFBEB'};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:800;color:{clr};font-size:13px;flex-shrink:0;">
              {d['driver_id']}
            </div>
            <div style="flex:1;">
              <div style="color:#1A1F36;font-weight:700;font-size:15px;">
                {d['name']}{sel_badge}
              </div>
              <div style="color:#6B7280;font-size:12px;margin-top:2px;">
                {d['district']} &nbsp;·&nbsp;
                <span style="color:{clr};font-weight:600;">{d['status']}</span>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="color:#F59E0B;font-size:14px;">{stars}</div>
              <div style="color:#6B7280;font-size:12px;margin-top:2px;">
                {d['completed_today']} хүргэлт өнөөдөр
              </div>
              <div style="color:#9CA3AF;font-size:11px;">⭐ {d['rating']}</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════
st.divider()
col_f1, col_f2, col_f3 = st.columns(3)
col_f1.caption("🌊 **CityFlow** · M³ баг · SparkDay 2026")
col_f2.caption("🛠 OSM · City2Graph · SUMO · NetworkX · Streamlit")
col_f3.caption("📊 100% open source · Улаанбаатар хот")