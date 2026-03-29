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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, * { font-family: 'Inter', sans-serif !important; }

    /* ── Base */
    [data-testid="stAppViewContainer"] { background: #080808; color: #e0e0e0; }
    [data-testid="stSidebar"] { background: #0c0c0c; border-right: 1px solid #1f1f1f; }
    [data-testid="stSidebar"] * { color: #d0d0d0 !important; }
    [data-testid="stSidebar"] .stButton > button { width: 100%; }

    /* ── Typography */
    h1, h2, h3 { color: #fff; letter-spacing: -0.5px; font-weight: 700; }
    .section-title {
        font-size: 11px; font-weight: 600; letter-spacing: 2.5px;
        text-transform: uppercase; color: #555; margin: 24px 0 12px;
        display: flex; align-items: center; gap: 8px;
    }
    .section-title::after {
        content: ''; flex: 1; height: 1px; background: #1e1e1e;
    }

    /* ── Metric cards */
    .metric-card {
        background: #111;
        border: 1px solid #1e1e1e;
        border-radius: 10px;
        padding: 14px 16px 12px;
        text-align: center;
        transition: border-color 0.2s, transform 0.15s;
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0;
        height: 2px; background: var(--accent, #e10600);
    }
    .metric-card:hover { border-color: #333; transform: translateY(-1px); }
    .metric-label {
        font-size: 9px; color: #505050; letter-spacing: 2px;
        text-transform: uppercase; font-weight: 500;
    }
    .metric-value {
        font-size: 20px; font-weight: 700; color: #fff;
        margin-top: 6px; font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: -0.5px;
    }
    .metric-sub { font-size: 11px; color: #555; margin-top: 3px; }

    /* ── Driver banner */
    .driver-banner {
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-left: 3px solid var(--colour);
        background: linear-gradient(90deg, var(--colour-dim), transparent 60%);
        display: flex; align-items: center; gap: 10px;
    }
    .driver-code {
        font-size: 28px; font-weight: 800; letter-spacing: -1px;
        color: var(--colour); line-height: 1;
    }
    .driver-meta { font-size: 10px; color: #555; letter-spacing: 1.5px; text-transform: uppercase; }

    /* ── Tyre badge */
    .tyre-badge {
        display: inline-flex; align-items: center; gap: 8px;
        border-radius: 20px; padding: 4px 12px 4px 4px;
        font-size: 12px; font-weight: 600;
        background: #151515; border: 1px solid #222;
    }
    .tyre-dot {
        width: 24px; height: 24px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 10px; font-weight: 800;
    }

    /* ── Weather strip */
    .weather-strip {
        display: flex; gap: 16px; flex-wrap: wrap;
        background: #0e0e0e; border: 1px solid #1a1a1a;
        border-radius: 8px; padding: 10px 14px;
        font-size: 12px; color: #888;
        margin-top: 8px;
    }
    .weather-item { display: flex; align-items: center; gap: 5px; }
    .weather-item strong { color: #ccc; font-weight: 500; }

    /* ── Buttons */
    .stButton > button {
        background: #e10600; color: #fff; border: none;
        border-radius: 8px; font-weight: 600; font-size: 13px;
        padding: 10px 20px; letter-spacing: 0.2px;
        transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
        box-shadow: 0 2px 12px rgba(225,6,0,0.3);
    }
    .stButton > button:hover {
        background: #c00400; transform: translateY(-1px);
        box-shadow: 0 4px 20px rgba(225,6,0,0.5);
    }

    /* ── Misc */
    hr { border-color: #1a1a1a; margin: 20px 0; }
    [data-testid="stRadio"] label { font-size: 13px !important; }
    [data-testid="stRadio"] > div { gap: 12px; }
    .stCheckbox label { font-size: 13px; }
    .stSelectbox label { font-size: 12px; color: #888 !important; letter-spacing: 0.5px; }
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
    "axes.edgecolor": "#1e1e1e", "axes.labelcolor": "#666",
    "xtick.color": "#444", "ytick.color": "#444",
    "grid.color": "#141414", "text.color": "#ccc",
    "font.family": "DejaVu Sans",
    "xtick.labelsize": 8, "ytick.labelsize": 8,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
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
        return "#e10600"


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
    ax.set_ylabel(ylabel, fontsize=9, color="#555", labelpad=8)
    ax.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
    ax.tick_params(axis="both", length=3, color="#333")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e1e1e")
    if special == "brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"], fontsize=8)
    elif special == "drs":
        ax.set_ylim(-1, 15)
        ax.set_yticks([0, 8, 12])
        ax.set_yticklabels(["Off", "On", "On"], fontsize=7)
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
        "in the sidebar, then hit <strong style='color:#e10600;'>Load Session</strong>."
        "</p>"
        "<div style='display:grid; grid-template-columns:1fr 1fr; gap:12px; text-align:left;'>"
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


def render_summary(lap, driver: str, colour: str = "#e10600"):
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
            ax.set_xlabel("Distance (m)", fontsize=9, color="#555", labelpad=6)

    # Row labels on right side
    for ax_i, (label, _, _, _) in enumerate(CHANNELS):
        axes[ax_i].yaxis.set_label_position("left")
        axes[ax_i].text(1.002, 0.5, label, transform=axes[ax_i].transAxes,
                        fontsize=8, color="#444", va="center", ha="left",
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
        ax_d.set_ylabel("Δ Speed (km/h)", fontsize=9, color="#555")
        ax_d.set_xlabel("Distance (m)", fontsize=9, color="#555")
        ax_d.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        for spine in ax_d.spines.values():
            spine.set_edgecolor("#1e1e1e")
        ax_d.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
        ax_d.tick_params(colors="#444", labelsize=8)
        ax_d.legend(fontsize=9, facecolor="#111", edgecolor="#222",
                    labelcolor="#ddd", framealpha=0.9)
        fig_d.tight_layout()
        st.pyplot(fig_d, use_container_width=True)
        plt.close(fig_d)
