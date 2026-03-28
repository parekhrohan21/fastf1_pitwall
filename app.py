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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        * { font-family: 'Inter', sans-serif !important; }

        /* Dark racing aesthetic */
        [data-testid="stAppViewContainer"] {
            background: #0a0a0a;
            color: #e8e8e8;
        }
        [data-testid="stSidebar"] {
            background: #0f0f0f;
            border-right: 2px solid #e10600;
        }
        [data-testid="stSidebar"] * { color: #e8e8e8 !important; }
        h1, h2, h3 { color: #e10600; letter-spacing: -0.3px; }

        /* Metric cards */
        .metric-card {
            background: linear-gradient(145deg, #1a1a1a, #141414);
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            padding: 14px 18px;
            text-align: center;
            transition: border-color 0.2s;
        }
        .metric-card:hover { border-color: #444; }
        .metric-label { font-size: 10px; color: #666; letter-spacing: 1.5px; text-transform: uppercase; }
        .metric-value { font-size: 22px; font-weight: 700; color: #ffffff; margin-top: 5px; }
        .metric-sub   { font-size: 12px; color: #aaa; margin-top: 2px; }

        /* Driver comparison banner */
        .driver-banner {
            border-radius: 10px;
            padding: 10px 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .driver-code {
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        .driver-label {
            font-size: 11px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            opacity: 0.7;
        }

        /* Chart view toggle */
        .chart-toggle-label {
            font-size: 11px;
            color: #888;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 4px;
        }

        /* Buttons */
        .stButton > button {
            background: #e10600; color: white; border: none;
            border-radius: 8px; font-weight: 600; letter-spacing: 0.3px;
            transition: background 0.15s, transform 0.1s;
        }
        .stButton > button:hover { background: #c00500; transform: translateY(-1px); }

        /* Radio buttons */
        [data-testid="stRadio"] label { font-size: 13px !important; }

        hr { border-color: #1e1e1e; }

        /* Divider with text */
        .vs-divider {
            text-align: center;
            color: #444;
            font-size: 11px;
            letter-spacing: 3px;
            text-transform: uppercase;
            padding: 4px 0 8px;
        }
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
    sess.load(telemetry=True, laps=True, weather=True, messages=True)
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
        - 🔀 Toggle between **Overlapping** and **Separate** chart views

        *Data powered by [FastF1](https://docs.fastf1.dev)*
        """
    )
    st.stop()

# ── Driver & lap controls ──────────────────────────────────────────────────────
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

# ── Lap selector helper ────────────────────────────────────────────────────────
def lap_selector(driver: str, suffix: str = ""):
    driver_laps = sess.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    if driver_laps.empty:
        driver_laps = sess.laps.pick_drivers(driver).dropna(subset=["LapTime"]).reset_index(drop=True)
    if driver_laps.empty:
        st.warning(f"No valid laps found for {driver}.")
        return None, None
    lap_options = ["Fastest"] + [str(int(ln)) for ln in driver_laps["LapNumber"].tolist()]
    choice = st.selectbox(f"🔢 Lap — {driver}", lap_options, key=f"lap_{driver}{suffix}")
    if choice == "Fastest":
        lap = driver_laps.loc[driver_laps["LapTime"].idxmin()]
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

# ── Chart view mode (only shown during comparison) ─────────────────────────────
chart_mode = "Overlapping"
if compare and driver2:
    st.markdown("")
    chart_mode = st.radio(
        "📊 Chart View",
        ["Overlapping", "Separate"],
        index=0,
        horizontal=True,
        help="**Overlapping** — both drivers on the same axes  |  **Separate** — individual charts side-by-side",
    )

# ── Telemetry fetching ─────────────────────────────────────────────────────────
def get_telemetry_cached(driver: str, lap):
    if lap is None:
        return None
    try:
        lap_num = int(lap["LapNumber"])
    except Exception:
        lap_num = -1
    cache_key = f"tel_{sess_key}_{driver}_{lap_num}"
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = lap.get_car_data().add_distance()
        except Exception as exc:
            st.warning(f"⚠️ Could not load telemetry for {driver}: {exc}")
            st.session_state[cache_key] = None
    return st.session_state[cache_key]


tel1 = get_telemetry_cached(driver1, lap1)
tel2 = get_telemetry_cached(driver2, lap2) if (compare and driver2 and lap2 is not None) else None

# ── Matplotlib theme ───────────────────────────────────────────────────────────
matplotlib.rcParams.update({
    "figure.facecolor":  "#0a0a0a",
    "axes.facecolor":    "#111111",
    "axes.edgecolor":    "#2a2a2a",
    "axes.labelcolor":   "#aaaaaa",
    "xtick.color":       "#666666",
    "ytick.color":       "#666666",
    "grid.color":        "#1e1e1e",
    "text.color":        "#cccccc",
    "font.family":       "DejaVu Sans",
})

channels = [
    ("Speed",    "Speed",    "km/h"),
    ("Throttle", "Throttle", "%"),
    ("Brake",    "Brake",    ""),
]

colour1 = driver_colour(sess, driver1)
colour2 = driver_colour(sess, driver2) if driver2 else "#27F4D2"

# ── Lap summary cards ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### ⏱  Lap Summary")


def lap_metric_html(label: str, value: str, sub: str = "", accent: str = "#e10600") -> str:
    return f"""
    <div class="metric-card" style="border-top: 3px solid {accent};">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {'<div class="metric-sub">'+sub+'</div>' if sub else ''}
    </div>"""


def driver_banner_html(driver: str, colour: str, lap_num: str = "") -> str:
    return f"""
    <div class="driver-banner" style="background: linear-gradient(90deg, {colour}22, #0a0a0a); border-left: 4px solid {colour};">
        <div>
            <div class="driver-code" style="color: {colour};">{driver}</div>
            <div class="driver-label">{lap_num}</div>
        </div>
    </div>"""


def render_summary(lap, driver: str, colour: str = "#e10600"):
    if lap is None:
        return
    try:
        lap_num_str = f"Lap {int(lap.get('LapNumber', '?'))}"
    except Exception:
        lap_num_str = ""
    st.markdown(driver_banner_html(driver, colour, lap_num_str), unsafe_allow_html=True)
    cols = st.columns(4)
    fields = [
        ("Lap Time",  format_laptime(lap.get("LapTime")),     ""),
        ("Sector 1",  format_laptime(lap.get("Sector1Time")), ""),
        ("Sector 2",  format_laptime(lap.get("Sector2Time")), ""),
        ("Sector 3",  format_laptime(lap.get("Sector3Time")), ""),
    ]
    for col, (lbl, val, sub) in zip(cols, fields):
        col.markdown(lap_metric_html(lbl, val, sub, accent=colour), unsafe_allow_html=True)

    compound = lap.get("Compound", "?")
    tyre_age = lap.get("TyreLife", "?")
    try:
        tyre_age_str = str(int(tyre_age)) if tyre_age != "?" and not pd.isna(tyre_age) else "?"
    except (ValueError, TypeError):
        tyre_age_str = "?"
    try:
        w = lap.get_weather_data()
        air = f"{w['AirTemp']:.1f}°C" if not pd.isna(w.get("AirTemp")) else "?"
        track = f"{w['TrackTemp']:.1f}°C" if not pd.isna(w.get("TrackTemp")) else "?"
        hum = f"{w['Humidity']:.0f}%" if not pd.isna(w.get("Humidity")) else "?"
        weather_str = f"&nbsp;&nbsp;🌡️ **Air:** {air} &nbsp;|&nbsp; ☀️ **Track:** {track} &nbsp;|&nbsp; 💧 **Humidity:** {hum}"
    except Exception:
        weather_str = ""

    try:
        track_status = str(lap.get("TrackStatus", "1"))
        status_map = {
            "1": "🟢 Clear",
            "2": "🟡 Yellow Flag",
            "3": "🔵 Unused",
            "4": "🚓 Safety Car",
            "5": "🔴 Red Flag",
            "6": "🐢 VSC",
            "7": "🐢 VSC Ending"
        }
        if len(track_status) > 1:
            status_str = f"🏁 Multiple ({track_status})"
        else:
            status_str = status_map.get(track_status, "🟢 Clear")
    except Exception:
        status_str = "🟢 Clear"

    st.markdown(
        f"<div style='margin-bottom: 4px;'>"
        f"&nbsp;&nbsp;🔴 **Tyre:** {compound} &nbsp;|&nbsp; **Age:** {tyre_age_str} laps"
        f"</div><div>"
        f"&nbsp;&nbsp;🛣️ **Track:** {status_str} {weather_str}"
        f"</div>",
        unsafe_allow_html=True,
    )


if compare and lap2 is not None:
    sum_c1, sum_c2 = st.columns(2)
    with sum_c1:
        render_summary(lap1, driver1, colour1)
    with sum_c2:
        render_summary(lap2, driver2, colour2)
else:
    render_summary(lap1, driver1, colour1)

# ── Telemetry chart ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📈  Telemetry")

if tel1 is None:
    st.warning("No telemetry data available for the selected lap.")
    st.stop()


def style_ax(ax, title: str, unit: str):
    ax.set_ylabel(f"{title}" + (f" ({unit})" if unit else ""), fontsize=10, color="#aaaaaa")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
    for spine in ax.spines.values():
        spine.set_edgecolor("#2a2a2a")
    if title == "Brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"])


# ── OVERLAPPING chart ──────────────────────────────────────────────────────────
if chart_mode == "Overlapping" or not compare:
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True,
                             gridspec_kw={"hspace": 0.06, "top": 0.92})

    for ax, (title, col, unit) in zip(axes, channels):
        if col in tel1.columns:
            ax.plot(tel1["Distance"], tel1[col],
                    color=colour1, linewidth=1.8, label=driver1, alpha=0.95)
        if tel2 is not None and col in tel2.columns:
            ax.plot(tel2["Distance"], tel2[col],
                    color=colour2, linewidth=1.8, label=driver2, alpha=0.85,
                    linestyle="--")
        style_ax(ax, title, unit)

    axes[-1].set_xlabel("Distance (m)", fontsize=10, color="#aaaaaa")

    title_str = f"{gp} {year} — {session_label}  |  {driver1}"
    if compare and driver2:
        title_str += f"  vs  {driver2}"
    fig.suptitle(title_str, fontsize=13, fontweight="bold", color="#e10600", y=0.97)

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper right", fontsize=10,
                   facecolor="#1a1a1a", edgecolor="#2a2a2a", labelcolor="#e8e8e8",
                   bbox_to_anchor=(0.99, 0.96))

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

# ── SEPARATE charts ────────────────────────────────────────────────────────────
else:
    left_col, right_col = st.columns(2)

    for col_ctx, driver, tel, colour in [
        (left_col,  driver1, tel1, colour1),
        (right_col, driver2, tel2, colour2),
    ]:
        with col_ctx:
            # Coloured driver header
            st.markdown(
                f"<div style='border-left: 4px solid {colour}; padding-left: 10px; "
                f"margin-bottom: 8px;'>"
                f"<span style='font-size:20px; font-weight:700; color:{colour};'>{driver}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            if tel is None:
                st.warning(f"No telemetry for {driver}")
                continue

            fig, axes = plt.subplots(3, 1, figsize=(7, 8), sharex=True,
                                     gridspec_kw={"hspace": 0.06, "top": 0.92})

            for ax, (title, ch, unit) in zip(axes, channels):
                if ch in tel.columns:
                    ax.plot(tel["Distance"], tel[ch],
                            color=colour, linewidth=1.8, alpha=0.95)
                    # Shade under the speed curve
                    if title == "Speed":
                        ax.fill_between(tel["Distance"], tel[ch], alpha=0.08, color=colour)
                style_ax(ax, title, unit)

            axes[-1].set_xlabel("Distance (m)", fontsize=9, color="#aaaaaa")

            try:
                lap_obj = lap1 if driver == driver1 else lap2
                lap_time = format_laptime(lap_obj.get("LapTime"))
            except Exception:
                lap_time = ""

            fig.suptitle(f"{driver}  —  {lap_time}", fontsize=12,
                         fontweight="bold", color=colour, y=0.97)

            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

# ── Delta bar (Overlapping mode only, when comparing) ─────────────────────────
if compare and chart_mode == "Overlapping" and tel1 is not None and tel2 is not None:
    if "Speed" in tel1.columns and "Speed" in tel2.columns:
        st.markdown("#### ⚡ Speed Delta  *(Driver 1 − Driver 2)*")
        # Interpolate tel2 onto tel1's distance axis
        speed2_interp = np.interp(tel1["Distance"], tel2["Distance"], tel2["Speed"])
        delta = tel1["Speed"].values - speed2_interp

        fig_d, ax_d = plt.subplots(figsize=(14, 2.5))
        ax_d.axhline(0, color="#444", linewidth=0.8, linestyle="--")
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta >= 0), color=colour1, alpha=0.55, label=f"{driver1} faster")
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta < 0),  color=colour2, alpha=0.55, label=f"{driver2} faster")
        ax_d.set_ylabel("Δ Speed (km/h)", fontsize=9, color="#aaaaaa")
        ax_d.set_xlabel("Distance (m)", fontsize=9, color="#aaaaaa")
        ax_d.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        for spine in ax_d.spines.values():
            spine.set_edgecolor("#2a2a2a")
        ax_d.grid(True, linestyle=":", linewidth=0.4)
        ax_d.legend(fontsize=9, facecolor="#1a1a1a", edgecolor="#2a2a2a", labelcolor="#e8e8e8")
        st.pyplot(fig_d, use_container_width=True)
        plt.close(fig_d)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#333;font-size:12px;padding-top:32px;'>"
    "Data © FastF1 / Ergast / F1. For educational use only.</div>",
    unsafe_allow_html=True,
)
