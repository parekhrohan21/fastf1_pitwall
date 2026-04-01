"""
Pit Wall Dashboard — FastF1 + Streamlit
Visualise lap telemetry for any F1 session since 2018.
"""

import os
import warnings
import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import plotly.graph_objects as go

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
st.markdown("""
<style>
    html, body, * { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol" !important; font-weight: 300; }

    /* ── Base */
    [data-testid="stAppViewContainer"] {
        background: #000000; color: #ffffff;

        overflow-x: hidden;          /* prevent horizontal scroll */
    }
    [data-testid="stSidebar"] { background: #0c0c0c; border-right: 1px solid #1f1f1f; }
    [data-testid="stSidebar"] * { color: #d0d0d0 !important; }
    [data-testid="stSidebar"] .stButton > button { width: 100%; }

    /* All images & iframes scale with their container */
    img, iframe, canvas, video {
        max-width: 100% !important;
        height: auto !important;
    }

    /* ── Typography */
    h1, h2, h3 { color: #fff; letter-spacing: -0.5px; font-weight: 300; }
    .section-title {
        font-size: 12px; font-weight: 400; letter-spacing: 1px;
        text-transform: uppercase; color: #8e8e93; margin: 32px 0 16px;
        display: flex; align-items: center; gap: 12px;
    }
    .section-title::after {
        content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.1);
    }

    /* ── Metric cards — fluid, wrap at narrow viewports */
    .metric-card {
        background: rgba(30, 30, 30, 0.5);
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 16px 16px 14px;
        text-align: center;
        transition: opacity 0.2s, transform 0.15s;
        position: relative;
        overflow: hidden;
        min-width: 0;                 /* flex/grid child: don't overflow */
        box-sizing: border-box;
    }
    .metric-card:hover { opacity: 0.8; transform: scale(0.98); }
    .metric-label {
        font-size: 10px; color: #8e8e93; letter-spacing: 1.5px;
        text-transform: uppercase; font-weight: 400;
    }
    .metric-value {
        font-size: clamp(16px, 2.5vw, 24px); font-weight: 300; color: #fff;
        margin-top: 8px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        letter-spacing: -0.5px;
    }
    .metric-sub { font-size: 11px; color: #8e8e93; margin-top: 4px; font-weight: 300; }

    /* ── Driver banner */
    .driver-banner {
        border-radius: 16px;
        padding: 14px 20px;
        margin-bottom: 12px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(30,30,30,0.5); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        display: flex; align-items: center; gap: 12px;
        min-width: 0; box-sizing: border-box; flex-wrap: wrap;
    }
    .driver-code {
        font-size: clamp(24px, 4vw, 32px); font-weight: 300; letter-spacing: -1px;
        color: var(--colour, #FF8700); line-height: 1;
    }
    .driver-meta { font-size: 11px; color: #8e8e93; letter-spacing: 1px; text-transform: uppercase; font-weight: 400; }

    /* ── Tyre badge */
    .tyre-badge {
        display: inline-flex; align-items: center; gap: 8px;
        border-radius: 20px; padding: 4px 12px 4px 4px;
        font-size: 12px; font-weight: 600;
        background: #151515; border: 1px solid #222;
        max-width: 100%; box-sizing: border-box;
    }
    .tyre-dot {
        width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 10px; font-weight: 800;
    }

    /* ── Weather strip */
    .weather-strip {
        display: flex; gap: 16px; flex-wrap: wrap;
        background: rgba(30, 30, 30, 0.5); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px; padding: 12px 16px;
        font-size: 13px; color: #a0a0a0; font-weight: 300;
        margin-top: 8px;
        width: 100%; box-sizing: border-box;
    }
    .weather-item { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
    .weather-item strong { color: #fff; font-weight: 500; }

    /* ── Buttons */
    .stButton > button {
        background: #FF8700; color: #fff; border: none;
        border-radius: 40px; font-weight: 500; font-size: 15px;
        padding: 12px 24px; letter-spacing: 0.2px;
        transition: opacity 0.15s, transform 0.1s;
        box-shadow: none;
        width: 100%;
    }
    .stButton > button:hover {
        opacity: 0.8; transform: scale(0.98);
        background: #FF8700; color: #fff;

    }

    /* ── Misc */
    hr { border-color: #1a1a1a; margin: 20px 0; }
    [data-testid="stRadio"] label { font-size: 13px !important; }
    [data-testid="stRadio"] > div { gap: 12px; }
    .stCheckbox label { font-size: 13px; }
    .stSelectbox label { font-size: 12px; color: #888 !important; letter-spacing: 0.5px; }

    /* Ensure Streamlit block containers don't overflow */
    [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"] {
        min-width: 0;
    }
    .element-container { min-width: 0; max-width: 100%; }

    /* ── Narrow viewport tweaks (< 768 px) */
    @media (max-width: 768px) {
        .driver-code { font-size: 20px; }
        .metric-value { font-size: 14px; }
        .weather-strip { gap: 10px; font-size: 11px; }
        .tyre-badge { font-size: 11px; }
        .section-title { font-size: 10px; letter-spacing: 2px; }
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TEAM_COLOURS = {
    "Red Bull Racing": "#3671C6", "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2", "McLaren": "#FF8000",
    "Aston Martin": "#229971", "Alpine": "#FF87BC",
    "Williams": "#64C4FF", "RB": "#6692FF",
    "Kick Sauber": "#52E252", "Haas F1 Team": "#B6BABD",
}

COMPOUND_COLOURS = {
    "SOFT": ("#FF3333", "S"), "MEDIUM": ("#FFD700", "M"),
    "HARD": ("#FFFFFF", "H"), "INTERMEDIATE": ("#39B54A", "I"),
    "WET": ("#0067FF", "W"),
}

TRACK_STATUS_MAP = {
    "1": ("🟢", "Clear"), "2": ("🟡", "Yellow"),
    "4": ("🚗", "Safety Car"), "5": ("🔴", "Red Flag"),
    "6": ("🐢", "VSC"), "7": ("🐢", "VSC End"),
}

MATPLOTLIB_THEME = {
    "figure.facecolor": "#080808", "axes.facecolor": "#0e0e0e",
    "axes.edgecolor": "#1e1e1e", "axes.labelcolor": "#aaaaaa",
    "xtick.color": "#999999", "ytick.color": "#999999",
    "grid.color": "#141414", "text.color": "#ffffff",
    "font.family": "DejaVu Sans",
    "xtick.labelsize": 10, "ytick.labelsize": 10,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _team_colour(team: str) -> str:
    for k, v in TEAM_COLOURS.items():
        if k.lower() in team.lower():
            return v
    return "#FF8700"


@st.cache_data(show_spinner=False, ttl=3600)
def load_schedule(year: int) -> pd.DataFrame:
    return fastf1.get_event_schedule(year, include_testing=False)


@st.cache_data(show_spinner=False, ttl=3600)
def load_session(year: int, gp: str, session_type: str = "R"):
    sess = fastf1.get_session(year, gp, session_type)
    sess.load(telemetry=True, laps=True, weather=True, messages=True)
    return sess


def format_laptime(td) -> str:
    try:
        if pd.isna(td):
            return "N/A"
        total = td.total_seconds()
        return f"{int(total // 60)}:{total % 60:06.3f}"
    except Exception:
        return "N/A"


def driver_colour(sess, driver: str) -> str:
    try:
        return _team_colour(sess.get_driver(driver).get("TeamName", ""))
    except Exception:
        return "#FF8700"


def get_telemetry_cached(driver: str, lap, sess_key: str):
    if lap is None:
        return None
    try:
        lap_num = int(lap["LapNumber"])
    except Exception:
        lap_num = -1
    key = f"tel_{sess_key}_{driver}_{lap_num}"
    if key not in st.session_state:
        try:
            st.session_state[key] = lap.get_car_data().add_distance()
        except Exception as exc:
            st.warning(f"⚠️ No telemetry for {driver}: {exc}")
            st.session_state[key] = None
    return st.session_state[key]


def style_ax(ax, ylabel: str, special: str = ""):
    ax.set_ylabel(ylabel, fontsize=11, color="#aaaaaa", labelpad=8)
    ax.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
    ax.tick_params(axis="both", length=3, color="#666666", labelsize=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e1e1e")
    if special == "brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"], fontsize=10)
    elif special == "drs":
        ax.set_ylim(-1, 15)
        ax.set_yticks([0, 8, 12])
        ax.set_yticklabels(["Off", "On", "On"], fontsize=9)
    else:
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding: 4px 0 16px'>"
        "<div style='font-size:22px; font-weight:800; letter-spacing:-0.5px; color:#fff;'>🏎 Pit Wall</div>"
        "<div style='font-size:11px; color:#444; letter-spacing:2px; text-transform:uppercase; margin-top:2px;'>F1 Telemetry Explorer</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:0 0 16px'>", unsafe_allow_html=True)

    year = st.selectbox("Season", list(range(2026, 2017, -1)), index=0, label_visibility="visible")

    with st.spinner("Loading calendar…"):
        try:
            schedule = load_schedule(year)
            gp_names = schedule["EventName"].tolist()
        except Exception as e:
            st.error(f"Could not load {year} schedule: {e}")
            st.stop()

    gp = st.selectbox("Grand Prix", gp_names, index=min(4, len(gp_names) - 1))

    session_map = {
        "Race": "R", "Qualifying": "Q", "Sprint": "S",
        "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
    }
    session_label = st.selectbox("Session", list(session_map.keys()))
    session_type = session_map[session_label]

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)
    load_btn = st.button("⬇️  Load Session", use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10px; color:#333; letter-spacing:0.5px; text-align:center;'>"
        "Data © FastF1 / Ergast / F1<br>Educational use only"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "session" not in st.session_state:
    st.session_state["session"] = None
    st.session_state["sess_key"] = None

sess_key = f"{year}_{gp}_{session_type}"

if load_btn:
    with st.spinner(f"Loading {gp} {year} {session_label}…  (first load ~30 s)"):
        try:
            sess = load_session(year, gp, session_type)
            st.session_state["session"] = sess
            st.session_state["sess_key"] = sess_key
        except Exception as e:
            st.error(f"❌ {e}")
            st.stop()

sess = st.session_state.get("session")

# ── Landing ───────────────────────────────────────────────────────────────────
if sess is None:
    st.markdown(
        "<div style='max-width:560px; margin:80px auto; text-align:center;'>"
        "<div style='font-size:64px; margin-bottom:16px;'>🏎</div>"
        "<h1 style='font-size:36px; font-weight:800; color:#fff; margin-bottom:8px;'>Pit Wall</h1>"
        "<p style='color:#555; font-size:15px; line-height:1.6; margin-bottom:32px;'>"
        "Professional F1 lap telemetry explorer. Select a season, Grand Prix and session "
        "in the sidebar, then hit <strong style='color:#FF8700;'>Load Session</strong>."
        "</p>"
        "<div style='display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; text-align:left;'>"
        "<div style='background:#111; border:1px solid #1e1e1e; border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>📈</div><div style='font-size:13px; color:#888; margin-top:4px;'>Speed · Throttle · Brake<br>RPM · Gear · DRS</div></div>"
        "<div style='background:#111; border:1px solid #1e1e1e; border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>⏱</div><div style='font-size:13px; color:#888; margin-top:4px;'>Lap time &amp; sector splits<br>Tyre compound &amp; age</div></div>"
        "<div style='background:#111; border:1px solid #1e1e1e; border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>👥</div><div style='font-size:13px; color:#888; margin-top:4px;'>Head-to-head comparison<br>Overlapping or separate</div></div>"
        "<div style='background:#111; border:1px solid #1e1e1e; border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>🌤</div><div style='font-size:13px; color:#888; margin-top:4px;'>Weather conditions<br>Track status per lap</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Driver & lap controls ──────────────────────────────────────────────────────
all_drivers = sorted(sess.laps["Driver"].dropna().unique().tolist())

st.markdown("<div class='section-title'>Driver Selection</div>", unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1])
with col_a:
    driver1 = st.selectbox("Driver 1", all_drivers, key="d1")
with col_b:
    compare = st.checkbox("Compare with Driver 2", value=False)
    driver2 = None
    if compare:
        remaining = [d for d in all_drivers if d != driver1]
        driver2 = st.selectbox("Driver 2", remaining, key="d2")


def lap_selector(driver: str, suffix: str = ""):
    dlaps = sess.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    if dlaps.empty:
        dlaps = sess.laps.pick_drivers(driver).dropna(subset=["LapTime"]).reset_index(drop=True)
    if dlaps.empty:
        st.warning(f"No valid laps for {driver}.")
        return None, None
    opts = ["Fastest"] + [str(int(ln)) for ln in dlaps["LapNumber"].tolist()]
    choice = st.selectbox(f"Lap — {driver}", opts, key=f"lap_{driver}{suffix}")
    lap = dlaps.loc[dlaps["LapTime"].idxmin()] if choice == "Fastest" \
        else dlaps[dlaps["LapNumber"] == int(choice)].iloc[0]
    return lap, dlaps


col_c, col_d = st.columns([1, 1] if compare else [1, 2])
with col_c:
    lap1, laps1 = lap_selector(driver1, "_1")
with col_d:
    if compare and driver2:
        lap2, laps2 = lap_selector(driver2, "_2")
    else:
        lap2 = laps2 = None

# Chart mode toggle
chart_mode = "Overlapping"
if compare and driver2:
    chart_mode = st.radio(
        "Chart View", ["Overlapping", "Separate"], horizontal=True, index=0,
        help="Overlapping: both drivers on same axes | Separate: individual side-by-side charts",
    )

# ── Telemetry ─────────────────────────────────────────────────────────────────
tel1 = get_telemetry_cached(driver1, lap1, sess_key)
tel2 = get_telemetry_cached(driver2, lap2, sess_key) if (compare and driver2 and lap2 is not None) else None

colour1 = driver_colour(sess, driver1)
colour2 = driver_colour(sess, driver2) if driver2 else "#27F4D2"

matplotlib.rcParams.update(MATPLOTLIB_THEME)

# ── Lap Summary ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Lap Summary</div>", unsafe_allow_html=True)


def tyre_badge_html(compound: str, age_str: str, fresh: bool) -> str:
    raw = str(compound).upper() if compound and compound != "?" else "?"
    col, letter = COMPOUND_COLOURS.get(raw, ("#888", raw[0] if raw else "?"))
    worn_label = "fresh" if fresh else f"{age_str} laps"
    text_col = "#000" if raw in ("MEDIUM", "HARD", "INTERMEDIATE") else "#fff"
    return (
        f"<span class='tyre-badge'>"
        f"<span class='tyre-dot' style='background:{col}; color:{text_col};'>{letter}</span>"
        f"<span style='color:#ccc;'>{raw.title()}</span>"
        f"<span style='color:#555; font-size:11px;'>· {worn_label}</span>"
        f"</span>"
    )


def weather_strip_html(lap) -> str:
    try:
        w = lap.get_weather_data()
        air = f"{w['AirTemp']:.1f}°C" if not pd.isna(w.get("AirTemp")) else "—"
        trk = f"{w['TrackTemp']:.1f}°C" if not pd.isna(w.get("TrackTemp")) else "—"
        hum = f"{w['Humidity']:.0f}%" if not pd.isna(w.get("Humidity")) else "—"
        rain = "Yes" if w.get("Rainfall") else "No"

        ts = str(lap.get("TrackStatus", "1"))
        if len(ts) > 1:
            status_str = "Multiple"
        else:
            ico, lbl = TRACK_STATUS_MAP.get(ts, ("🟢", "Clear"))
            status_str = f"{ico} {lbl}"

        return (
            f"<div class='weather-strip'>"
            f"<div class='weather-item'>🌡 <strong>{air}</strong> air</div>"
            f"<div class='weather-item'>☀️ <strong>{trk}</strong> track</div>"
            f"<div class='weather-item'>💧 <strong>{hum}</strong> humidity</div>"
            f"<div class='weather-item'>🌧 Rain: <strong>{rain}</strong></div>"
            f"<div class='weather-item' style='margin-left:auto;'>Track: <strong>{status_str}</strong></div>"
            f"</div>"
        )
    except Exception:
        return ""


def render_summary(lap, driver: str, colour: str = "#FF8700"):
    if lap is None:
        return
    try:
        lap_num_str = f"Lap {int(lap.get('LapNumber', '?'))}"
    except Exception:
        lap_num_str = ""

    st.markdown(
        f"<div class='driver-banner' style='--colour:{colour}; --colour-dim:{colour}18;'>"
        f"<div class='driver-code'>{driver}</div>"
        f"<div class='driver-meta'>{lap_num_str}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Lap time + sectors
    c1, c2, c3, c4 = st.columns(4)

    def mc(col_obj, label, value):
        col_obj.markdown(
            f"<div class='metric-card' style='--accent:{colour};'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    mc(c1, "Lap Time",  format_laptime(lap.get("LapTime")))
    mc(c2, "Sector 1",  format_laptime(lap.get("Sector1Time")))
    mc(c3, "Sector 2",  format_laptime(lap.get("Sector2Time")))
    mc(c4, "Sector 3",  format_laptime(lap.get("Sector3Time")))

    # ── Speed traps (if available)
    si1 = lap.get("SpeedI1"); si2 = lap.get("SpeedI2")
    sfl = lap.get("SpeedFL"); sst = lap.get("SpeedST")
    speed_cols = [
        ("I1  Speed",  f"{si1:.0f} km/h"  if si1 and not pd.isna(si1) else "—"),
        ("I2  Speed",  f"{si2:.0f} km/h"  if si2 and not pd.isna(si2) else "—"),
        ("FL  Speed",  f"{sfl:.0f} km/h"  if sfl and not pd.isna(sfl) else "—"),
        ("ST  Speed",  f"{sst:.0f} km/h"  if sst and not pd.isna(sst) else "—"),
    ]
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col_obj, (lbl, val) in zip([sc1, sc2, sc3, sc4], speed_cols):
        col_obj.markdown(
            f"<div class='metric-card' style='--accent:#333;'>"
            f"<div class='metric-label'>{lbl}</div>"
            f"<div class='metric-value' style='font-size:16px; color:#aaa;'>{val}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Tyre badge + weather
    compound = lap.get("Compound", "?")
    tyre_age = lap.get("TyreLife", "?")
    try:
        tyre_age_str = str(int(tyre_age)) if tyre_age != "?" and not pd.isna(tyre_age) else "?"
    except Exception:
        tyre_age_str = "?"
    fresh = lap.get("FreshTyre", False)

    st.markdown(
        f"<div style='margin-top:10px; display:flex; align-items:center; gap:10px;'>"
        f"{tyre_badge_html(compound, tyre_age_str, fresh)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(weather_strip_html(lap), unsafe_allow_html=True)


if compare and lap2 is not None:
    s1, s2 = st.columns(2)
    with s1:
        render_summary(lap1, driver1, colour1)
    with s2:
        render_summary(lap2, driver2, colour2)
else:
    render_summary(lap1, driver1, colour1)

# ── Telemetry charts ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Telemetry</div>", unsafe_allow_html=True)

if tel1 is None:
    st.warning("No telemetry available for the selected lap.")
    st.stop()

# channel definitions: (subplot_title, df_col, y_label, special_flag)
CHANNELS = [
    ("Speed",    "Speed",    "km/h",   ""),
    ("Throttle", "Throttle", "%",       ""),
    ("Brake",    "Brake",    "",        "brake"),
    ("RPM",      "RPM",      "RPM",    ""),
    ("Gear",     "nGear",    "Gear",   "gear"),
    ("DRS",      "DRS",      "DRS",    "drs"),
]
N = len(CHANNELS)

# Height ratios — brake/DRS rows are shorter
H_RATIOS = [3, 2, 1, 2, 1.5, 1]


def build_chart(drivers_telemetry: list, title_str: str, fig_width: float = 14):
    """drivers_telemetry: list of (driver_label, colour, tel_df)"""
    fig = plt.figure(figsize=(fig_width, 11), facecolor=MATPLOTLIB_THEME["figure.facecolor"])
    gs = gridspec.GridSpec(N, 1, figure=fig, hspace=0.04,
                           height_ratios=H_RATIOS, top=0.94, bottom=0.06,
                           left=0.07, right=0.97)
    axes = [fig.add_subplot(gs[i]) for i in range(N)]

    for ax_i, (_, col, ylabel, special) in enumerate(CHANNELS):
        ax = axes[ax_i]
        for drv_label, colour, tel in drivers_telemetry:
            if tel is not None and col in tel.columns:
                lw = 1.7 if drv_label == drivers_telemetry[0][0] else 1.5
                ls = "-" if drv_label == drivers_telemetry[0][0] else "--"
                al = 0.95 if drv_label == drivers_telemetry[0][0] else 0.80
                ax.plot(tel["Distance"], tel[col],
                        color=colour, linewidth=lw, linestyle=ls, alpha=al,
                        label=drv_label, solid_capstyle="round")
                if col == "Speed" and drv_label == drivers_telemetry[0][0]:
                    ax.fill_between(tel["Distance"], tel[col], alpha=0.05, color=colour)

        unit = f" ({ylabel})" if ylabel else ""
        style_ax(ax, col if not ylabel else ylabel + unit if special not in ("brake","drs","gear") else col, special)

        # gear: integer y ticks
        if special == "gear":
            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))
            ax.set_ylim(0.5, 8.5)
            ax.set_yticks(range(1, 9))

        if ax_i < N - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Distance (m)", fontsize=11, color="#aaaaaa", labelpad=8)

    # Row labels on right side
    for ax_i, (label, _, _, _) in enumerate(CHANNELS):
        axes[ax_i].yaxis.set_label_position("left")
        axes[ax_i].text(1.002, 0.5, label, transform=axes[ax_i].transAxes,
                        fontsize=10, color="#999999", va="center", ha="left",
                        rotation=0, fontweight="600")

    fig.suptitle(title_str, fontsize=12, fontweight="bold", color="#fff", y=0.98)

    # Legend
    handles = [mpatches.Patch(color=c, label=d) for d, c, _ in drivers_telemetry]
    if len(handles) > 1:
        fig.legend(handles=handles, loc="upper right",
                   bbox_to_anchor=(0.97, 0.965), fontsize=9,
                   facecolor="#111", edgecolor="#222", labelcolor="#ddd",
                   framealpha=0.9, handlelength=1.2, handleheight=0.8)
    return fig


# ── Overlapping ───────────────────────────────────────────────────────────────
if chart_mode == "Overlapping" or not compare:
    drv_list = [(driver1, colour1, tel1)]
    if compare and tel2 is not None:
        drv_list.append((driver2, colour2, tel2))

    title = f"{gp} {year}  ·  {session_label}"
    if compare and driver2:
        title += f"  ·  {driver1} vs {driver2}"
    else:
        title += f"  ·  {driver1}"

    fig = build_chart(drv_list, title)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

# ── Separate ──────────────────────────────────────────────────────────────────
else:
    lc, rc = st.columns(2)
    for col_ctx, driver, tel, colour, lap_obj in [
        (lc, driver1, tel1, colour1, lap1),
        (rc, driver2, tel2, colour2, lap2),
    ]:
        with col_ctx:
            if tel is None:
                st.warning(f"No telemetry for {driver}")
                continue
            try:
                lt = format_laptime(lap_obj.get("LapTime"))
            except Exception:
                lt = ""
            title = f"{driver}  ·  {lt}"
            fig = build_chart([(driver, colour, tel)], title, fig_width=7)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

# ── Speed delta (overlapping + comparison) ────────────────────────────────────
if compare and chart_mode == "Overlapping" and tel1 is not None and tel2 is not None:
    if "Speed" in tel1.columns and "Speed" in tel2.columns:
        st.markdown("<div class='section-title'>Speed Delta</div>", unsafe_allow_html=True)

        speed2_i = np.interp(tel1["Distance"], tel2["Distance"], tel2["Speed"])
        delta = tel1["Speed"].values - speed2_i

        fig_d, ax_d = plt.subplots(figsize=(14, 2.8),
                                   facecolor=MATPLOTLIB_THEME["figure.facecolor"])
        ax_d.set_facecolor(MATPLOTLIB_THEME["axes.facecolor"])
        ax_d.axhline(0, color="#333", linewidth=0.8)
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta >= 0), color=colour1, alpha=0.6,
                          label=f"{driver1} faster", interpolate=True)
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta < 0),  color=colour2, alpha=0.6,
                          label=f"{driver2} faster", interpolate=True)
        ax_d.set_ylabel("Δ Speed (km/h)", fontsize=11, color="#aaaaaa")
        ax_d.set_xlabel("Distance (m)", fontsize=11, color="#aaaaaa")
        ax_d.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        for spine in ax_d.spines.values():
            spine.set_edgecolor("#1e1e1e")
        ax_d.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
        ax_d.tick_params(colors="#999999", labelsize=10)
        ax_d.legend(fontsize=10, facecolor="#111", edgecolor="#222",
                    labelcolor="#ddd", framealpha=0.9)
        fig_d.tight_layout()
        st.pyplot(fig_d, width='stretch')
        plt.close(fig_d)

# ── Track Map ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Track Map</div>", unsafe_allow_html=True)

map_tab1, map_tab2 = st.tabs(["🎨  Speed Map", "🎬  Race Replay"])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — Static speed-coloured track map
# ────────────────────────────────────────────────────────────────────────────
with map_tab1:
    @st.cache_data(show_spinner=False, ttl=600)
    def _get_telemetry_for_map(_lap, driver: str, sess_k: str):
        """Return merged position + car telemetry for a lap."""
        try:
            return _lap.get_telemetry()
        except Exception:
            return None

    def _speed_map_fig(lap, driver: str, colour: str, lap2=None, driver2=None, colour2=None):
        tel = _get_telemetry_for_map(lap, driver, sess_key)
        if tel is None or tel.empty:
            return None

        # Need X, Y and Speed columns
        needed = {"X", "Y", "Speed"}
        if not needed.issubset(tel.columns):
            return None

        fig = go.Figure()

        # ── Track outline (thick dark grey line)
        fig.add_trace(go.Scatter(
            x=tel["X"], y=tel["Y"],
            mode="lines",
            line=dict(color="#1c1c1c", width=16),
            showlegend=False, hoverinfo="skip",
        ))

        # ── Driver 2 path (solid team colour, lower opacity)
        if lap2 is not None and driver2:
            tel2 = _get_telemetry_for_map(lap2, driver2, sess_key)
            if tel2 is not None and needed.issubset(tel2.columns):
                fig.add_trace(go.Scatter(
                    x=tel2["X"], y=tel2["Y"],
                    mode="markers",
                    marker=dict(color=colour2, size=3, opacity=0.45),
                    name=f"{driver2} path",
                    hoverinfo="skip",
                ))

        # ── Driver 1 speed-coloured scatter
        fig.add_trace(go.Scatter(
            x=tel["X"], y=tel["Y"],
            mode="markers",
            marker=dict(
                color=tel["Speed"],
                colorscale=[
                    [0.0,  "#1a1aff"],
                    [0.35, "#00c8ff"],
                    [0.65, "#00e400"],
                    [0.85, "#ffd700"],
                    [1.0,  "#ff2200"],
                ],
                size=4,
                colorbar=dict(
                    title=dict(text="Speed (km/h)", font=dict(color="#666", size=10)),
                    tickfont=dict(color="#555", size=9),
                    thickness=10, len=0.7,
                    bgcolor="rgba(0,0,0,0)",
                    bordercolor="#1e1e1e",
                    x=1.02,
                ),
                showscale=True,
            ),
            name=driver,
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Speed: %{marker.color:.0f} km/h<br>"
                "X: %{x:.0f}  Y: %{y:.0f}"
                "<extra></extra>"
            ),
        ))

        # ── Start / finish marker
        fig.add_trace(go.Scatter(
            x=[tel["X"].iloc[0]], y=[tel["Y"].iloc[0]],
            mode="markers",
            marker=dict(symbol="circle", size=14, color="#FF8700",
                        line=dict(color="#ffffff", width=2)),
            name="Start / Finish",
            hovertemplate="Start / Finish<extra></extra>",
        ))

        fig.update_layout(
            paper_bgcolor="#080808", plot_bgcolor="#080808",
            showlegend=True,
            legend=dict(font=dict(color="#888", size=11),
                        bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
            yaxis=dict(visible=False),
            height=520,
            margin=dict(l=0, r=80, t=10, b=10),
            hoverlabel=dict(bgcolor="#111", font_color="#eee",
                            bordercolor="#333"),
        )
        return fig

    if lap1 is not None:
        sm_fig = _speed_map_fig(
            lap1, driver1, colour1,
            lap2=(lap2 if compare else None),
            driver2=(driver2 if compare else None),
            colour2=colour2,
        )
        if sm_fig:
            st.plotly_chart(sm_fig, use_container_width=True)
        else:
            st.info("Position data not available for this lap.")
    else:
        st.info("Load a session and select a lap to view the speed map.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — Animated race replay with all cars
# ────────────────────────────────────────────────────────────────────────────
with map_tab2:
    replay_key = f"replay_{sess_key}"
    if replay_key not in st.session_state:
        st.session_state[replay_key] = None

    # ── Placeholder / button
    if st.session_state[replay_key] is None:
        st.markdown(
            "<div style='text-align:center; padding:56px 24px; border:1px dashed #1e1e1e; "
            "border-radius:12px; margin:8px 0;'>"
            "<div style='font-size:52px; margin-bottom:14px;'>🎬</div>"
            "<div style='font-size:14px; color:#666;'>Animated replay of all cars on track.</div>"
            "<div style='font-size:12px; color:#333; margin-top:6px;'>"
            "Samples every 5 s · up to 500 frames · ~20 s to build"
            "</div></div>",
            unsafe_allow_html=True,
        )

    gen_col, _ = st.columns([1, 3])
    with gen_col:
        gen_btn = st.button("🎬  Generate Race Replay", key="gen_replay",
                            use_container_width=True)

    if gen_btn:
        st.session_state[replay_key] = None   # reset so we rebuild
        with st.spinner("Building animation — sampling all car positions…"):
            try:
                # ── Build driver number → abbr + colour map
                drv_meta = {}
                for drv_num in sess.drivers:
                    try:
                        info = sess.get_driver(drv_num)
                        abbr   = info.get("Abbreviation", drv_num)
                        colour = _team_colour(info.get("TeamName", ""))
                        drv_meta[drv_num] = {"abbr": abbr, "colour": colour}
                    except Exception:
                        drv_meta[drv_num] = {"abbr": drv_num, "colour": "#888"}

                # ── Extract position time series for each driver
                T_STEP   = 5          # seconds between animation frames
                MAX_SECS = 7200       # cap at 2 hours
                MAX_FRAMES = 500

                all_data = {}         # drv_num -> {t, x, y}
                for drv_num in sess.drivers:
                    try:
                        pdf = sess.pos_data[drv_num]
                        if pdf is None or pdf.empty:
                            continue
                        t_s = pdf["SessionTime"].dt.total_seconds().values
                        all_data[drv_num] = {
                            "t": t_s,
                            "x": pdf["X"].values,
                            "y": pdf["Y"].values,
                        }
                    except Exception:
                        pass

                if not all_data:
                    st.warning("No position data available for this session.")
                    st.stop()

                # ── Build common time grid
                t_min = min(d["t"][0]  for d in all_data.values())
                t_max = min(max(d["t"][-1] for d in all_data.values()), t_min + MAX_SECS)
                t_grid = np.arange(t_min, t_max, T_STEP)
                if len(t_grid) > MAX_FRAMES:
                    t_grid = t_grid[:MAX_FRAMES]

                # ── Pre-interpolate positions for every driver onto t_grid
                grids = {}
                valid_drvs = []
                for drv_num, d in all_data.items():
                    if len(d["t"]) < 10:
                        continue
                    xi = np.interp(t_grid, d["t"], d["x"],
                                   left=np.nan, right=np.nan)
                    yi = np.interp(t_grid, d["t"], d["y"],
                                   left=np.nan, right=np.nan)
                    # Mark frames where driver has retired as NaN
                    retired_at = d["t"][-1]
                    xi[t_grid > retired_at + T_STEP] = np.nan
                    yi[t_grid > retired_at + T_STEP] = np.nan
                    grids[drv_num] = (xi, yi)
                    valid_drvs.append(drv_num)

                if not valid_drvs:
                    st.warning("Insufficient position data for animation.")
                    st.stop()

                # ── Track outline from the driver with most data points
                longest = max(all_data, key=lambda k: len(all_data[k]["t"]))
                track_x = all_data[longest]["x"]
                track_y = all_data[longest]["y"]

                # Thin track to ~1000 pts for display
                thin = max(1, len(track_x) // 1000)
                track_x = track_x[::thin]
                track_y = track_y[::thin]

                # ── Helper: format seconds as MM:SS
                def _fmt(sec: float) -> str:
                    m, s = int(sec // 60), int(sec % 60)
                    return f"{m:02d}:{s:02d}"

                # ── Build initial traces
                init_traces = [
                    go.Scatter(
                        x=track_x, y=track_y, mode="lines",
                        line=dict(color="#1c1c1c", width=14),
                        showlegend=False, hoverinfo="skip",
                    )
                ]
                for drv_num in valid_drvs:
                    meta  = drv_meta.get(drv_num, {"abbr": drv_num, "colour": "#888"})
                    xi, yi = grids[drv_num]
                    x0 = [xi[0]] if not np.isnan(xi[0]) else []
                    y0 = [yi[0]] if not np.isnan(yi[0]) else []
                    init_traces.append(go.Scatter(
                        x=x0, y=y0,
                        mode="markers+text",
                        marker=dict(
                            color=meta["colour"], size=14,
                            line=dict(color="#000", width=1.5),
                        ),
                        text=[meta["abbr"]],
                        textposition="top center",
                        textfont=dict(size=8, color=meta["colour"]),
                        name=meta["abbr"],
                        hovertemplate=f"<b>{meta['abbr']}</b><extra></extra>",
                        showlegend=True,
                    ))

                # ── Build animation frames
                frames = []
                slider_steps = []
                n_drvs = len(valid_drvs)

                for f_i, t_sec in enumerate(t_grid):
                    label = _fmt(t_sec)
                    fdata = [
                        go.Scatter(
                            x=track_x, y=track_y, mode="lines",
                            line=dict(color="#1c1c1c", width=14),
                            showlegend=False, hoverinfo="skip",
                        )
                    ]
                    for drv_num in valid_drvs:
                        meta  = drv_meta.get(drv_num, {"abbr": drv_num, "colour": "#888"})
                        xi, yi = grids[drv_num]
                        px, py = xi[f_i], yi[f_i]
                        fdata.append(go.Scatter(
                            x=[px] if not np.isnan(px) else [],
                            y=[py] if not np.isnan(py) else [],
                            mode="markers+text",
                            marker=dict(
                                color=meta["colour"], size=14,
                                line=dict(color="#000", width=1.5),
                            ),
                            text=[meta["abbr"]],
                            textposition="top center",
                            textfont=dict(size=8, color=meta["colour"]),
                            name=meta["abbr"],
                            hovertemplate=f"<b>{meta['abbr']}</b><extra></extra>",
                        ))

                    frames.append(go.Frame(data=fdata, name=label))
                    # Add slider step only every ~5 frames to reduce clutter
                    slider_steps.append(dict(
                        args=[[label], dict(
                            frame=dict(duration=150, redraw=False),
                            transition=dict(duration=0),
                            mode="immediate",
                        )],
                        label=label if f_i % 12 == 0 else "",
                        method="animate",
                    ))

                # ── Compose layout
                layout = go.Layout(
                    paper_bgcolor="#080808", plot_bgcolor="#080808",
                    showlegend=True,
                    legend=dict(
                        font=dict(color="#888", size=10),
                        bgcolor="rgba(15,15,15,0.85)",
                        bordercolor="#222", borderwidth=1,
                        orientation="v", x=1.01, y=0.5,
                        yanchor="middle",
                        itemsizing="constant",
                    ),
                    xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                    yaxis=dict(visible=False),
                    height=560,
                    margin=dict(l=0, r=130, t=20, b=70),
                    hoverlabel=dict(bgcolor="#111", font_color="#eee",
                                   bordercolor="#333"),
                    updatemenus=[dict(
                        type="buttons", showactive=False,
                        x=0.04, y=-0.10, xanchor="left",
                        buttons=[
                            dict(
                                label="▶  Play",
                                method="animate",
                                args=[None, dict(
                                    frame=dict(duration=150, redraw=False),
                                    transition=dict(duration=0),
                                    fromcurrent=True, mode="immediate",
                                )],
                            ),
                            dict(
                                label="⏸  Pause",
                                method="animate",
                                args=[[None], dict(
                                    frame=dict(duration=0, redraw=False),
                                    transition=dict(duration=0),
                                    mode="immediate",
                                )],
                            ),
                        ],
                        font=dict(color="#ccc", size=12),
                        bgcolor="#1a1a1a", bordercolor="#333",
                        pad=dict(r=10, t=8),
                    )],
                    sliders=[dict(
                        active=0,
                        steps=slider_steps,
                        currentvalue=dict(
                            prefix="Session time  ",
                            font=dict(color="#777", size=11),
                            visible=True, xanchor="center",
                        ),
                        pad=dict(t=45, b=8),
                        font=dict(color="#444", size=8),
                        bgcolor="#111", bordercolor="#1e1e1e",
                        tickcolor="#2a2a2a",
                        len=0.88, x=0.06,
                    )],
                )

                replay_fig = go.Figure(
                    data=init_traces, layout=layout, frames=frames
                )
                st.session_state[replay_key] = replay_fig

            except Exception as exc:
                import traceback
                st.error(f"Could not build replay: {exc}")
                with st.expander("Full traceback"):
                    st.code(traceback.format_exc())

    if st.session_state[replay_key] is not None:
        st.plotly_chart(st.session_state[replay_key], use_container_width=True)
        n_frames = len(st.session_state[replay_key].frames)
        session_secs = n_frames * 5
        st.caption(
            f"⏱  {n_frames} frames · {session_secs // 60} min {session_secs % 60} s covered · "
            "5 s per frame · Click ▶ Play or drag the slider"
        )
