"""
Pit Wall Dashboard — FastF1 + Streamlit
Visualise lap telemetry (Speed, Throttle, Brake) for any F1 session since 2018.
"""

import os
import warnings
import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── FastF1 cache ──────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏎  Pit Wall — F1 Telemetry",
    page_icon="🏎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* Dark racing aesthetic */
        [data-testid="stAppViewContainer"] {
            background: #0d0d0d;
            color: #e8e8e8;
        }
        [data-testid="stSidebar"] {
            background: #111111;
            border-right: 1px solid #e10600;
        }
        [data-testid="stSidebar"] * { color: #e8e8e8 !important; }
        h1, h2, h3 { color: #e10600; }
        .metric-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 14px 18px;
            text-align: center;
        }
        .metric-label { font-size: 11px; color: #888; letter-spacing: 1px; text-transform: uppercase; }
        .metric-value { font-size: 24px; font-weight: 700; color: #e10600; margin-top: 4px; }
        .metric-sub   { font-size: 12px; color: #aaa; margin-top: 2px; }
        .stButton > button {
            background: #e10600; color: white; border: none;
            border-radius: 6px; font-weight: 600;
        }
        .stButton > button:hover { background: #c00500; }
        hr { border-color: #333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

TEAM_COLOURS = {
    "Red Bull Racing":    "#3671C6",
    "Ferrari":            "#E8002D",
    "Mercedes":           "#27F4D2",
    "McLaren":            "#FF8000",
    "Aston Martin":       "#229971",
    "Alpine":             "#FF87BC",
    "Williams":           "#64C4FF",
    "RB":                 "#6692FF",
    "Kick Sauber":        "#52E252",
    "Haas F1 Team":       "#B6BABD",
}

def _team_colour(team: str) -> str:
    for k, v in TEAM_COLOURS.items():
        if k.lower() in team.lower():
            return v
    return "#e10600"


@st.cache_data(show_spinner=False, ttl=3600)
def load_schedule(year: int) -> pd.DataFrame:
    return fastf1.get_event_schedule(year, include_testing=False)


@st.cache_data(show_spinner=False, ttl=3600)
def load_session(year: int, gp: str, session_type: str = "R"):
    sess = fastf1.get_session(year, gp, session_type)
    sess.load(telemetry=True, laps=True, weather=False, messages=False)
    return sess


def format_laptime(td) -> str:
    if pd.isna(td):
        return "N/A"
    total = td.total_seconds()
    mins = int(total // 60)
    secs = total % 60
    return f"{mins}:{secs:06.3f}"


def driver_colour(sess, driver: str) -> str:
    try:
        info = sess.get_driver(driver)
        team = info.get("TeamName", "")
        return _team_colour(team)
    except Exception:
        return "#e10600"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏎  Pit Wall")
    st.markdown("*F1 Lap Telemetry Explorer*")
    st.markdown("---")

    current_year = 2026
    year = st.selectbox("📅 Season", list(range(current_year, 2017, -1)), index=0)

    with st.spinner("Loading calendar…"):
        try:
            schedule = load_schedule(year)
            gp_names = schedule["EventName"].tolist()
        except Exception as e:
            st.error(f"Could not load {year} schedule: {e}")
            st.stop()

    gp = st.selectbox("🏁 Grand Prix", gp_names, index=min(4, len(gp_names) - 1))

    session_map = {
        "Race (R)": "R",
        "Qualifying (Q)": "Q",
        "Sprint (S)": "S",
        "Practice 1 (FP1)": "FP1",
        "Practice 2 (FP2)": "FP2",
        "Practice 3 (FP3)": "FP3",
    }
    session_label = st.selectbox("📋 Session", list(session_map.keys()))
    session_type  = session_map[session_label]

    st.markdown("---")
    load_btn = st.button("⬇️  Load Session", use_container_width=True)

# ── Session loading state ─────────────────────────────────────────────────────
if "session" not in st.session_state:
    st.session_state["session"] = None
    st.session_state["sess_key"] = None

sess_key = f"{year}_{gp}_{session_type}"

if load_btn or st.session_state["sess_key"] != sess_key:
    if load_btn:
        with st.spinner(f"Loading {gp} {year} — {session_label}…  (first load may take 30 s)"):
            try:
                sess = load_session(year, gp, session_type)
                st.session_state["session"] = sess
                st.session_state["sess_key"] = sess_key
            except Exception as e:
                st.error(f"❌ Could not load session: {e}")
                st.stop()

sess = st.session_state.get("session")

# ── Landing screen ─────────────────────────────────────────────────────────────
if sess is None:
    st.markdown("# 🏎  Pit Wall")
    st.markdown("### F1 Lap Telemetry Dashboard")
    st.markdown(
        """
        Select a **season**, **Grand Prix**, and **session** in the sidebar, then hit **⬇️ Load Session**.

        ---
        **What you'll see:**
        - 📈 Speed, Throttle, and Brake telemetry traces for the fastest lap
        - ⏱  Lap time, sector splits, tyre compound & age
        - 👥 Optional second-driver overlay for head-to-head comparison

        *Data powered by [FastF1](https://docs.fastf1.dev)*
        """
    )
    st.stop()

# ── Driver & lap controls (post-load) ──────────────────────────────────────────
all_drivers = sorted(sess.laps["Driver"].dropna().unique().tolist())

col_a, col_b = st.columns([1, 1])

with col_a:
    driver1 = st.selectbox("🪖 Driver 1", all_drivers, key="d1")

with col_b:
    compare = st.checkbox("👥 Compare with Driver 2", value=False)
    if compare:
        remaining = [d for d in all_drivers if d != driver1]
        driver2 = st.selectbox("🪖 Driver 2", remaining, key="d2")
    else:
        driver2 = None

# Lap selector helper
def lap_selector(driver: str, suffix: str = ""):
    driver_laps = sess.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    if driver_laps.empty:
        st.warning(f"No valid laps found for {driver}.")
        return None, None
    lap_options = ["Fastest"] + [str(int(ln)) for ln in driver_laps["LapNumber"].tolist()]
    choice = st.selectbox(f"🔢 Lap — {driver}", lap_options, key=f"lap_{driver}{suffix}")
    if choice == "Fastest":
        lap = driver_laps.pick_fastest()
    else:
        lap = driver_laps[driver_laps["LapNumber"] == int(choice)].iloc[0]
    return lap, driver_laps

col_c, col_d = st.columns([1, 1] if compare else [1, 2])
with col_c:
    lap1, laps1 = lap_selector(driver1, "_1")
with col_d:
    if compare and driver2:
        lap2, laps2 = lap_selector(driver2, "_2")
    else:
        lap2 = laps2 = None

# ── Telemetry fetching ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def get_telemetry(_lap):
    return _lap.get_car_data().add_distance()


def safe_telemetry(lap):
    if lap is None:
        return None
    try:
        return get_telemetry(lap)
    except Exception:
        return None


tel1 = safe_telemetry(lap1)
tel2 = safe_telemetry(lap2) if compare else None

# ── Lap summary cards ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### ⏱  Lap Summary")

def lap_metric_html(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {'<div class="metric-sub">'+sub+'</div>' if sub else ''}
    </div>"""


def render_summary(lap, driver: str):
    if lap is None:
        return
    cols = st.columns(5)
    fields = [
        ("Driver",    driver, ""),
        ("Lap Time",  format_laptime(lap.get("LapTime")), ""),
        ("Sector 1",  format_laptime(lap.get("Sector1Time")), ""),
        ("Sector 2",  format_laptime(lap.get("Sector2Time")), ""),
        ("Sector 3",  format_laptime(lap.get("Sector3Time")), ""),
    ]
    for col, (lbl, val, sub) in zip(cols, fields):
        col.markdown(lap_metric_html(lbl, val, sub), unsafe_allow_html=True)

    compound = lap.get("Compound", "?")
    tyre_age = lap.get("TyreLife", "?")
    st.markdown(
        f"&nbsp;&nbsp;🔴 **Tyre:** {compound} &nbsp;|&nbsp; "
        f"**Age:** {int(tyre_age) if not pd.isna(tyre_age) else '?'} laps",
        unsafe_allow_html=True,
    )


render_summary(lap1, driver1)
if compare and lap2:
    st.markdown("")
    render_summary(lap2, driver2)

# ── Telemetry chart ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📈  Telemetry")

if tel1 is None:
    st.warning("No telemetry data available for the selected lap.")
    st.stop()

matplotlib.rcParams.update({
    "figure.facecolor":  "#0d0d0d",
    "axes.facecolor":    "#111111",
    "axes.edgecolor":    "#333333",
    "axes.labelcolor":   "#cccccc",
    "xtick.color":       "#888888",
    "ytick.color":       "#888888",
    "grid.color":        "#222222",
    "text.color":        "#cccccc",
    "font.family":       "DejaVu Sans",
})

fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True,
                         gridspec_kw={"hspace": 0.08, "top": 0.92})

colour1 = driver_colour(sess, driver1)
colour2 = driver_colour(sess, driver2) if driver2 else "#27F4D2"

channels = [
    ("Speed",    "Speed",    "km/h"),
    ("Throttle", "Throttle", "%"),
    ("Brake",    "Brake",    ""),
]

for ax, (title, col, unit) in zip(axes, channels):
    if col in tel1.columns:
        ax.plot(tel1["Distance"], tel1[col],
                color=colour1, linewidth=1.6, label=driver1, alpha=0.95)
    if tel2 is not None and col in tel2.columns:
        ax.plot(tel2["Distance"], tel2[col],
                color=colour2, linewidth=1.6, label=driver2, alpha=0.80,
                linestyle="--")
    ax.set_ylabel(f"{title}" + (f" ({unit})" if unit else ""), fontsize=10)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
    if title == "Brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"])

axes[-1].set_xlabel("Distance (m)", fontsize=10)

# Title
title_str = f"{gp} {year} — {session_label}  |  {driver1}"
if compare and driver2:
    title_str += f" vs {driver2}"
fig.suptitle(title_str, fontsize=14, fontweight="bold", color="#e10600", y=0.97)

# Legend
handles, labels = axes[0].get_legend_handles_labels()
if handles:
    fig.legend(handles, labels, loc="upper right", fontsize=10,
               facecolor="#1a1a1a", edgecolor="#333", labelcolor="#e8e8e8",
               bbox_to_anchor=(0.99, 0.96))

st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#555;font-size:12px;padding-top:24px;'>"
    "Data © FastF1 / Ergast / F1. For educational use only.</div>",
    unsafe_allow_html=True,
)
