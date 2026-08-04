import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# Streamlit Page Config MUST be run first before any other Streamlit widgets!
st.set_page_config(
    page_title="Pitwall · F1 Live Telemetry & Insights",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modular imports
from src.ui.styles import inject_styles, _toggle_theme, TEAM_COLOURS, COMPOUND_COLOURS, TRACK_STATUS_MAP
from src.data.loader import (
    load_schedule, load_session, clear_session_cache, format_laptime, driver_colour,
    _build_driver_labels, get_telemetry_cached, _format_classification_time,
    _map_driver_id_to_number, _get_session_winner, _get_default_gp_index,
    get_constructor_colour, is_same_team, _build_constructor_standings,
    get_driver_standings_points, _build_driver_standings, _build_final_classification,
    _fmt_driver1, _fmt_driver2, _build_lap_history, _build_fuel_adjusted,
    _build_fuel_sim_leaderboard, _build_stints, _build_pit_stops, _build_tyre_deg_data,
    _build_leaderboard, _build_ideal_lap, _build_gap_data, _build_position_data,
    _get_telemetry_for_map, _get_round, start_live_recorder, stop_live_recorder,
    get_live_recorder_status, load_live_session, _PATCH_STATUS, test_curl_cffi_request
)
from src.ui.components import (
    _render_constructor_standings, _render_final_classification, _render_footer,
    _session_info_header, lap_selector, tyre_badge_html, weather_strip_html,
    render_summary, render_session_stats, _render_fuel_sim_leaderboard,
    _render_pit_table, _render_leaderboard, _render_ideal_lap_section,
    _render_gap_to_leader_section, _render_position_section, render_maps_block,
    render_live_status_banner, _render_grid_heatmap_section
)
from src.charts.plotly import (
    _lap_history_fig, _fuel_pace_fig, _stint_fig, _gap_chart_fig,
    build_tyre_deg_fig, build_undercut_chart
)
from src.charts.matplotlib import style_ax, build_chart, build_delta_chart, build_time_delta_chart

# ── Sidebar ───────────────────────────────────────────────────────────────────
# Inject design system & dark/light theme CSS early on every render
inject_styles("#FF8700")

with st.sidebar:
    st.markdown(
        "<a href='http://rohanparekh.uk' target='_top' class='back-home-link'>"
        "<span>👈</span>"
        "<span>rohanparekh.uk</span>"
        "</a>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='padding: 4px 0 16px'>"
        "<div style='font-size:22px; font-weight:800; letter-spacing:-0.5px;'>🏎 Pit Wall</div>"
        "<div style='font-size:11px; letter-spacing:2px; text-transform:uppercase; margin-top:2px; opacity: 0.6;'>F1 Telemetry Explorer</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:0 0 16px'>", unsafe_allow_html=True)

    _years = list(range(2026, 2017, -1))
    year = st.selectbox("Season", _years, index=0, label_visibility="visible")

    with st.spinner("Loading calendar…"):
        try:
            schedule = load_schedule(year)
            gp_names = schedule["EventName"].tolist()
        except Exception as e:
            st.error(f"Could not load {year} schedule: {e}")
            _render_footer()
            st.stop()

    _def_gp_idx = _get_default_gp_index(schedule, gp_names)
    gp = st.selectbox("Grand Prix", gp_names, index=_def_gp_idx)

    _session_code_map = {
        "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
        "Qualifying": "Q", "Sprint Qualifying": "SQ", "Sprint Shootout": "SS",
        "Sprint": "S", "Race": "R"
    }

    # Determine dynamic sessions for primary session selection
    gp_row = schedule[schedule["EventName"] == gp]
    if not gp_row.empty:
        row = gp_row.iloc[0]
        primary_sessions = []
        for i in range(1, 6):
            s_val = row.get(f"Session{i}")
            if pd.notna(s_val) and str(s_val).strip() != "":
                primary_sessions.append(str(s_val).strip())
    else:
        primary_sessions = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]

    _def_sess_idx = primary_sessions.index("Race") if "Race" in primary_sessions else len(primary_sessions) - 1
    session_label = st.selectbox("Session", primary_sessions, index=_def_sess_idx)
    session_type = _session_code_map.get(session_label, session_label)

    # --- Session 2 Selector ---
    compare_sessions = st.checkbox("Compare with another session", value=False, key="compare_sessions_chk")
    year2 = None
    gp2 = None
    session_type2 = None
    session_label2 = None

    if compare_sessions:
        st.markdown("<hr style='margin:12px 0 8px; border-style: dashed; opacity:0.5;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px; font-weight:700; text-transform:uppercase; margin-bottom:8px; opacity:0.8;'>Session 2 Selection</div>", unsafe_allow_html=True)
        year2 = st.selectbox("Season 2", _years, index=0, key="year2")
        with st.spinner("Loading calendar 2…"):
            try:
                schedule2 = load_schedule(year2)
                gp_names2 = schedule2["EventName"].tolist()
            except Exception as e:
                st.error(f"Could not load {year2} schedule: {e}")
                _render_footer()
                st.stop()
        _def_gp_idx2 = _get_default_gp_index(schedule2, gp_names2)
        gp2 = st.selectbox("Grand Prix 2", gp_names2, index=_def_gp_idx2, key="gp2")
        
        # Determine dynamic sessions for secondary session selection
        gp_row2 = schedule2[schedule2["EventName"] == gp2]
        if not gp_row2.empty:
            row2 = gp_row2.iloc[0]
            secondary_sessions = []
            for i in range(1, 6):
                s_val = row2.get(f"Session{i}")
                if pd.notna(s_val) and str(s_val).strip() != "":
                    secondary_sessions.append(str(s_val).strip())
        else:
            secondary_sessions = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]

        if session_label in secondary_sessions:
            _def_sess_idx2 = secondary_sessions.index(session_label)
        else:
            _def_sess_idx2 = secondary_sessions.index("Race") if "Race" in secondary_sessions else len(secondary_sessions) - 1

        session_label2 = st.selectbox("Session 2", secondary_sessions, index=_def_sess_idx2, key="session2")
        session_type2 = _session_code_map.get(session_label2, session_label2)

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    mode_label = "☀️  Light Mode" if st.session_state["dark_mode"] else "🌙  Dark Mode"
    st.button(mode_label, key="theme_toggle", on_click=_toggle_theme, use_container_width=True)

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    live_mode = st.toggle("🔴 Real-Time Live Timing Mode", value=False, key="live_mode_toggle")

    live_filename = "live_timing.txt"
    auto_refresh_sec = 0

    if live_mode:
        with st.expander("📡 Live Streamer Controls", expanded=True):
            live_filename = st.text_input("Live Timing File", value="live_timing.txt", key="live_filename_input")
            col_rec1, col_rec2 = st.columns(2)
            if col_rec1.button("▶ Start Stream", use_container_width=True):
                res = start_live_recorder(live_filename)
                if res["success"]:
                    st.success("Recorder started.")
                else:
                    st.error(res["message"])
            if col_rec2.button("⏹ Stop Stream", use_container_width=True):
                res = stop_live_recorder(live_filename)
                if res["success"]:
                    st.info("Recorder stopped.")
                else:
                    st.warning(res["message"])

            auto_refresh_choice = st.selectbox("Auto-Refresh Rate", ["OFF", "5s", "10s", "15s", "30s"], index=0, key="auto_refresh_choice")
            if auto_refresh_choice != "OFF":
                auto_refresh_sec = int(auto_refresh_choice.replace("s", ""))

            live_status = get_live_recorder_status(live_filename)
            st.caption(f"Status: {'Active Stream' if live_status['active'] else 'Idle'} | Packets: {live_status['line_count']:,} | Size: {live_status['size_bytes']/1024:.1f} KB")

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    load_btn = st.button("⬇️  Load Session(s)", use_container_width=True)

    # ── Diagnostics expander ──────────────────────────────────────────────────
    with st.sidebar.expander("🛠️ Diagnostics & Debug Info", expanded=False):
        st.write(f"**Patch Imported:** {_PATCH_STATUS['imported']}")
        st.write(f"**Patch Applied:** {_PATCH_STATUS['patched']}")
        if _PATCH_STATUS['import_err']:
            st.error(f"Import Error:\n{_PATCH_STATUS['import_err']}")
        
        st.write("**Request Errors:**")
        if _PATCH_STATUS['request_errs']:
            for err in _PATCH_STATUS['request_errs']:
                st.write(f"URL: {err['url']}")
                st.error(f"Error: {err['err']}\n\nTraceback:\n{err['traceback']}")
        else:
            st.write("None recorded.")
            
        if st.button("Run Connection Test"):
            with st.spinner("Testing connection..."):
                res = test_curl_cffi_request()
                st.code(res)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10px; opacity:0.5; letter-spacing:0.5px; text-align:center;'>"
        "Data © FastF1 / Ergast / F1<br>Educational use only"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "session" not in st.session_state:
    st.session_state["session"] = None
    st.session_state["sess_key"] = None
if "session2" not in st.session_state:
    st.session_state["session2"] = None
    st.session_state["sess_key2"] = None
if "year1" not in st.session_state:
    st.session_state["year1"] = _years[0] if _years else 2026
if "year2" not in st.session_state:
    st.session_state["year2"] = _years[0] if _years else 2026

sess_key = f"{year}_{gp}_{session_type}"
sess_key2 = f"{year2}_{gp2}_{session_type2}" if compare_sessions else None

if load_btn:
    if live_mode:
        with st.spinner(f"Loading Live Stream Data from '{live_filename}'…"):
            live_sess, err_msg = load_live_session(year, gp, session_type, live_filename)
            if err_msg or live_sess is None or not hasattr(live_sess, "laps") or live_sess.laps is None or live_sess.laps.empty:
                st.error(
                    f"**Live Timing Stream Error**\n\n"
                    f"{err_msg or 'No lap data found in live stream file.'}\n\n"
                    "Ensure you have started the SignalR recorder during an active session or selected a valid `.txt` stream recording."
                )
                _render_footer()
                st.stop()
            st.session_state["session"] = live_sess
            st.session_state["sess_key"] = f"LIVE_{live_filename}_{sess_key}"
            st.session_state["year1"] = year
    else:
        with st.spinner(f"Loading Session 1: {gp} {year} {session_label}…  (first load ~30 s)"):
            try:
                sess = load_session(year, gp, session_type)
                if not hasattr(sess, "laps") or sess.laps is None or sess.laps.empty:
                    raise ValueError("No lap data available for this session.")
                st.session_state["session"] = sess
                st.session_state["sess_key"] = sess_key
                st.session_state["year1"] = year
            except Exception as e:
                clear_session_cache(year, gp)
                st.session_state["session"] = None
                st.session_state["sess_key"] = None
                err_msg = str(e).rstrip(".") + "."
                st.error(
                    f"**Session Loading Error**\n\n"
                    f"FastF1 could not load the lap data: {err_msg}\n\n"
                    "We have cleared the cache for this session. Please try clicking **⬇️ Load Session(s)** again to reload."
                )
                _render_footer()
                st.stop()

    if compare_sessions and not live_mode:
        with st.spinner(f"Loading Session 2: {gp2} {year2} {session_label2}…  (first load ~30 s)"):
            try:
                sess2 = load_session(year2, gp2, session_type2)
                if not hasattr(sess2, "laps") or sess2.laps is None or sess2.laps.empty:
                    raise ValueError("No lap data available for this session.")
                st.session_state["session2"] = sess2
                st.session_state["sess_key2"] = sess_key2
                st.session_state["year2"] = year2
            except Exception as e:
                clear_session_cache(year2, gp2)
                st.session_state["session2"] = None
                st.session_state["sess_key2"] = None
                err_msg2 = str(e).rstrip(".") + "."
                st.error(
                    f"**Session Loading Error (Session 2)**\n\n"
                    f"FastF1 could not load the lap data: {err_msg2}\n\n"
                    "We have cleared the cache for this session. Please try clicking **⬇️ Load Session(s)** again to reload."
                )
                _render_footer()
                st.stop()
    else:
        st.session_state["session2"] = None
        st.session_state["sess_key2"] = None
        st.session_state["year2"] = None

sess = st.session_state.get("session")
sess2 = st.session_state.get("session2")
sess_key = st.session_state.get("sess_key")
sess_key2 = st.session_state.get("sess_key2")
year1 = st.session_state.get("year1")
year2 = st.session_state.get("year2")

if live_mode:
    live_status = get_live_recorder_status(live_filename)
    render_live_status_banner(live_status, auto_refresh_sec > 0, auto_refresh_sec)

# ── Landing ───────────────────────────────────────────────────────────────────
if sess is None:
    st.markdown(
        "<a href='http://rohanparekh.uk' target='_top' class='back-home-link main-back-home'>"
        "<span>👈</span>"
        "<span>rohanparekh.uk</span>"
        "</a>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='landing-container' style='max-width:560px; margin:80px auto; text-align:center;'>"
        "<div style='font-size:64px; margin-bottom:16px;'>🏎</div>"
        "<h1 style='font-size:36px; font-weight:800; color:var(--text-color); margin-bottom:8px;'>Pit Wall</h1>"
        "<p style='opacity:0.7; font-size:15px; line-height:1.6; margin-bottom:32px;'>"
        "Professional F1 lap telemetry explorer. Select a season, Grand Prix and session "
        "in the sidebar, then hit <strong style='color:var(--primary-color);'>Load Session</strong>."
        "</p>"
        "<div style='display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; text-align:left;'>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>📈</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Speed · Throttle · Brake<br>RPM · Gear · DRS</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>⏱</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Lap time &amp; sector splits<br>Tyre compound &amp; age</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>👥</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Head-to-head comparison<br>Overlapping or separate</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>🌤</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Weather conditions<br>Track status per lap</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    _render_footer()
    st.stop()

# ── Driver & lap controls ──────────────────────────────────────────────────────
try:
    all_drivers1 = sorted(sess.laps["Driver"].dropna().unique().tolist())
    if not all_drivers1:
        raise ValueError("Empty drivers list for Session 1")
    
    if sess2 is not None:
        all_drivers2 = sorted(sess2.laps["Driver"].dropna().unique().tolist())
        if not all_drivers2:
            raise ValueError("Empty drivers list for Session 2")
    else:
        all_drivers2 = None
except Exception as e:
    st.markdown("<br>", unsafe_allow_html=True)
    st.error(
        f"**Session Data Unavailable**\n\n"
        f"FastF1 could not load the lap data: {e}. This usually happens if "
        "the session is very recent and official telemetry hasn't been published yet, "
        "or if the session was cancelled."
    )
    # Clear cache to allow a clean retry next time
    try:
        clear_session_cache(year1, gp)
    except Exception:
        pass
    if sess2 is not None:
        try:
            clear_session_cache(year2, gp2)
        except Exception:
            pass
    # Clear invalid session states so we don't get stuck in a broken loop
    st.session_state["session"] = None
    st.session_state["session2"] = None
    st.session_state["sess_key"] = None
    st.session_state["sess_key2"] = None
    _render_footer()
    st.stop()

# ── Laps snapshot ─────────────────────────────────────────────────────────────
_all_laps1: pd.DataFrame = pd.DataFrame(sess.laps.copy())
_all_laps2: pd.DataFrame = pd.DataFrame(sess2.laps.copy()) if sess2 is not None else None

# ── Driver name labels (built once per session) ───────────────────────────────
_drv_labels1: dict = _build_driver_labels(sess)
_drv_labels2: dict = _build_driver_labels(sess2) if sess2 is not None else None









st.markdown(
    "<a href='http://rohanparekh.uk' target='_top' class='back-home-link main-back-home'>"
    "<span>👈</span>"
    "<span>rohanparekh.uk</span>"
    "</a>",
    unsafe_allow_html=True,
)

if sess2 is not None:
    col_hdr1, col_hdr2 = st.columns(2)
    with col_hdr1:
        st.caption("Session 1")
        _session_info_header(sess, session_type)
    with col_hdr2:
        st.caption("Session 2")
        _session_info_header(sess2, session_type2)
else:
    _session_info_header(sess, session_type)

# ── Driver Selection ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Driver Selection</div>", unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1])
with col_a:
    _p1_drv1 = _get_session_winner(sess, all_drivers1)
    _def_d1_idx = all_drivers1.index(_p1_drv1) if _p1_drv1 in all_drivers1 else 0
    driver1 = st.selectbox(
        "Driver 1", all_drivers1, index=_def_d1_idx, key="d1",
        format_func=_fmt_driver1,
    )
with col_b:
    if sess2 is not None:
        compare = True
        _def_d2_idx = all_drivers2.index(driver1) if driver1 in all_drivers2 else 0
        driver2 = st.selectbox(
            "Driver 2 (Session 2)", all_drivers2, index=_def_d2_idx, key="d2",
            format_func=_fmt_driver2,
        )
    else:
        compare = st.checkbox("Compare with Driver 2", value=False)
        driver2 = None
        if compare:
            remaining = [d for d in all_drivers1 if d != driver1]
            driver2 = st.selectbox(
                "Driver 2", remaining, key="d2",
                format_func=_fmt_driver1,
            )






col_c, col_d = st.columns([1, 1] if compare else [1, 2])
with col_c:
    lap1, laps1 = lap_selector(sess, driver1, "_1", _fmt_driver1)
with col_d:
    if compare and driver2:
        if sess2 is not None:
            lap2, laps2 = lap_selector(sess2, driver2, "_2", _fmt_driver2)
        else:
            lap2, laps2 = lap_selector(sess, driver2, "_2", _fmt_driver1)
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
tel2 = get_telemetry_cached(driver2, lap2, sess_key2) if (compare and driver2 and lap2 is not None) else None

colour1 = driver_colour(sess, driver1)
inject_styles(colour1)
colour2 = driver_colour(sess2 if sess2 is not None else sess, driver2) if driver2 else "#27F4D2"

matplotlib.rcParams.update(MATPLOTLIB_THEME)

# ── Lap Summary ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Lap Summary</div>", unsafe_allow_html=True)


def tyre_badge_html(compound: str, age_str: str, fresh: bool) -> str:
    raw    = str(compound).upper() if compound and compound != "?" else "UNKNOWN"
    pal    = COMPOUND_COLOURS.get(raw, COMPOUND_COLOURS["UNKNOWN"])
    col    = pal["fill"]
    letter = pal["letter"]
    text_col = pal["text"]
    worn_label = "fresh" if fresh else f"{age_str} laps"
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


def render_summary(lap, driver: str, colour: str = "#FF8700", session_obj=None, session_year=None):
    if lap is None:
        return
    try:
        lap_num_str = f"Lap {int(lap.get('LapNumber', '?'))}"
    except Exception:
        lap_num_str = ""

    active_sess = session_obj if session_obj is not None else sess
    active_year = session_year if session_year is not None else year

    try:
        driver_info = active_sess.get_driver(driver)
        raw_team    = driver_info.get("TeamName", "")
        logo_url    = _team_logo(raw_team, active_year)
        headshot_url = driver_info.get("HeadshotUrl", "") or ""
    except Exception:
        raw_team     = ""
        logo_url     = ""
        headshot_url = ""

    if logo_url and raw_team:
        team_badge_html = (
            f"<div class='team-badge'>"
            f"<img src='{logo_url}' class='team-logo'>"
            f"<span class='team-name-label'>{raw_team}</span>"
            f"</div>"
        )
    elif logo_url:
        team_badge_html = f"<div class='team-badge'><img src='{logo_url}' class='team-logo'></div>"
    elif raw_team:
        team_badge_html = f"<div class='team-badge'><span class='team-name-label'>{raw_team}</span></div>"
    else:
        team_badge_html = ""

    headshot_html = (
        f"<img src='{headshot_url}' class='driver-headshot' "
        f"onerror=\"this.style.display='none'\" alt='{driver}'>"
        if headshot_url else ""
    )

    st.markdown(
        f"<div class='driver-banner' style='--colour:{colour}; --colour-dim:{colour}18;'>"
        f"{headshot_html}"
        f"<div style='display:flex; flex-direction:column; gap:3px; min-width:0;'>"
        f"<div class='driver-code'>{driver}</div>"
        f"<div class='driver-meta'>{lap_num_str}</div>"
        f"</div>"
        f"{team_badge_html}"
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
        render_summary(lap1, driver1, colour1, sess, year1)
    with s2:
        render_summary(lap2, driver2, colour2, sess2 if sess2 is not None else sess, year2 if year2 is not None else year1)
else:
    render_summary(lap1, driver1, colour1, sess, year1)

# ── Session Statistics ────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Session Statistics</div>", unsafe_allow_html=True)

def render_session_stats(driver: str, colour: str, session_obj=None, all_laps=None):
    try:
        active_sess = session_obj if session_obj is not None else sess
        active_laps = all_laps if all_laps is not None else _all_laps1
        
        drv_info = active_sess.get_driver(driver)
        grid = drv_info.get("GridPosition", "N/A")
        pos = drv_info.get("Position", "N/A")
        status = str(drv_info.get("Status", "N/A"))
        try:
            grid_str = f"P{int(grid)}" if pd.notna(grid) else "N/A"
        except Exception:
            grid_str = str(grid)
        try:
            pos_str = f"P{int(pos)}" if pd.notna(pos) else "N/A"
        except Exception:
            pos_str = str(pos)

        dlaps = active_laps[active_laps["Driver"] == driver].copy()
        
        # Best Lap
        if not dlaps.empty and "LapTime" in dlaps.columns:
            best_lap = format_laptime(dlaps["LapTime"].min())
        else:
            best_lap = "N/A"
            
        # Top Speed
        if not dlaps.empty and "SpeedST" in dlaps.columns:
            max_speed = dlaps["SpeedST"].max()
            speed_str = f"{max_speed:.0f} km/h" if pd.notna(max_speed) else "N/A"
        else:
            speed_str = "N/A"
            
        # Avg Pace (Median of valid laps)
        if not dlaps.empty and "LapTime" in dlaps.columns:
            valid_laps = dlaps.dropna(subset=["LapTime"])
            if not valid_laps.empty:
                min_t = valid_laps["LapTime"].dt.total_seconds().min()
                valid_secs = valid_laps["LapTime"].dt.total_seconds()
                valid_secs = valid_secs[valid_secs < min_t * 1.07]
                avg_pace = pd.to_timedelta(valid_secs.median(), unit="s")
                avg_pace_str = format_laptime(avg_pace)
            else:
                avg_pace_str = "N/A"
        else:
            avg_pace_str = "N/A"

        c1, c2, c3 = st.columns(3)
        c4, c5, c6 = st.columns(3)

        def mc(col_obj, label, value):
            col_obj.markdown(
                f"<div class='metric-card' style='--accent:{colour}; margin-bottom: 14px;'>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value' style='font-size: clamp(16px, 2vw, 22px);'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        mc(c1, "Grid Position", grid_str)
        mc(c2, "Finish Position", pos_str)
        mc(c3, "Status", status)
        mc(c4, "Best Lap", best_lap)
        mc(c5, "Race Pace (Avg)", avg_pace_str)
        mc(c6, "Top Speed (ST)", speed_str)
    except Exception as e:
        st.warning(f"Session data unavailable for {driver}.")

if compare and driver2:
    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"<div style='text-align: center; font-size: 14px; font-weight: 600; letter-spacing: 1px; color: {colour1}; margin-bottom: 14px;'>{_fmt_driver1(driver1)}</div>", unsafe_allow_html=True)
        render_session_stats(driver1, colour1, sess, _all_laps1)
    with s2:
        st.markdown(f"<div style='text-align: center; font-size: 14px; font-weight: 600; letter-spacing: 1px; color: {colour2}; margin-bottom: 14px;'>{_fmt_driver2(driver2)}</div>", unsafe_allow_html=True)
        render_session_stats(driver2, colour2, sess2 if sess2 is not None else sess, _all_laps2 if _all_laps2 is not None else _all_laps1)
else:
    render_session_stats(driver1, colour1, sess, _all_laps1)

# ── Lap Time History ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Lap Time History</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_lap_history(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return cleaned lap DataFrame for a single driver."""
    try:
        # laps_df is a plain pd.DataFrame (not fastf1.core.Laps), so we
        # filter by the Driver column instead of using .pick_drivers().
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # filter out obvious outliers (safety car laps, pit laps > 3× median)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)
        return laps
    except Exception:
        return None


def _lap_history_fig(drivers_data: list, highlight_laps: list) -> go.Figure:
    """
    drivers_data : list of (driver, colour, laps_df)
    highlight_laps: list of selected LapNumber per driver (same order)
    """
    fig = go.Figure()

    for (driver, colour, laps), sel_lap in zip(drivers_data, highlight_laps):
        if laps is None or laps.empty:
            continue

        # ── Compound-coloured marker colours
        cmp_colours = {
            "SOFT": "#FF3333", "MEDIUM": "#FFD700", "HARD": "#CCCCCC",
            "INTERMEDIATE": "#39B54A", "WET": "#0067FF",
        }
        marker_colors = [
            cmp_colours.get(str(c).upper(), "#888888")
            for c in laps.get("Compound", ["?"] * len(laps))
        ]

        # ── Pit-out lap markers (first lap after a pit stop)
        pit_mask = laps["PitOutTime"].notna() if "PitOutTime" in laps.columns else pd.Series(False, index=laps.index)
        pit_laps  = laps[pit_mask]

        # ── Main line trace
        fig.add_trace(go.Scatter(
            x=laps["LapNumber"],
            y=laps["LapTimeSec"],
            mode="lines+markers",
            name=driver,
            line=dict(color=colour, width=2),
            marker=dict(
                color=marker_colors,
                size=7,
                line=dict(color=colour, width=1.2),
                symbol="circle",
            ),
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Lap %{x}<br>"
                "Time: %{customdata}<br>"
                "<extra></extra>"
            ),
            customdata=[
                f"{int(t//60)}:{t%60:06.3f}"
                for t in laps["LapTimeSec"]
            ],
        ))

        # ── Pit-stop triangles
        if not pit_laps.empty:
            fig.add_trace(go.Scatter(
                x=pit_laps["LapNumber"],
                y=pit_laps["LapTimeSec"],
                mode="markers",
                marker=dict(symbol="triangle-up", size=11, color=colour,
                            line=dict(color="white", width=1.2)),
                name=f"{driver} pit-out",
                hovertemplate=f"<b>{driver}</b> PIT OUT<br>Lap %{{x}}<extra></extra>",
                showlegend=True,
            ))

        # ── Highlight selected lap
        if sel_lap is not None:
            try:
                sel_row = laps[laps["LapNumber"] == int(sel_lap.get("LapNumber", -1))]
                if not sel_row.empty:
                    fig.add_vline(
                        x=int(sel_row["LapNumber"].iloc[0]),
                        line=dict(color=colour, width=1.5, dash="dot"),
                        opacity=0.6,
                        annotation_text=driver,
                        annotation_position="top",
                        annotation_font_size=10,
                    )
            except Exception:
                pass

    fig.update_layout(
        margin=dict(l=0, r=0, t=16, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            title="Lap Time (s)", gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
            tickformat=".1f",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        height=280,
    )
    return fig


if sess2 is not None:
    label1 = f"{driver1} ({year1})"
    label2 = f"{driver2} ({year2})"
else:
    label1 = driver1
    label2 = driver2

_hist_pairs = [(label1, colour1, _build_lap_history(driver1, sess_key, _all_laps1))]
_hist_laps  = [lap1]
if compare and driver2:
    _hist_pairs.append((label2, colour2, _build_lap_history(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1)))
    _hist_laps.append(lap2)

_all_none = all(p[2] is None or p[2].empty for p in _hist_pairs)
if _all_none:
    st.info("Lap time history not available for this session.")
else:
    # ── Compound filter ───────────────────────────────────────────────────────
    _all_compounds = sorted({
        str(c).upper()
        for _, _, _ldf in _hist_pairs if _ldf is not None and not _ldf.empty
        for c in _ldf["Compound"].dropna().unique()
        if str(c).upper() not in ("NAN", "NONE", "")
    })
    if _all_compounds:
        _selected_compounds = st.multiselect(
            "Filter by compound",
            options=_all_compounds,
            default=_all_compounds,
            format_func=lambda c: COMPOUND_COLOURS.get(c, {}).get("letter", c[0]) + f"  {c.title()}",
            key="lap_hist_compound_filter",
            label_visibility="collapsed",
        )
    else:
        _selected_compounds = _all_compounds

    # Apply compound filter to each driver's laps before plotting
    if _selected_compounds:
        _hist_pairs_filtered = [
            (drv, col,
             ldf[ldf["Compound"].str.upper().isin(_selected_compounds)].copy()
             if ldf is not None else None)
            for drv, col, ldf in _hist_pairs
        ]
    else:
        _hist_pairs_filtered = _hist_pairs

    st.plotly_chart(_lap_history_fig(_hist_pairs_filtered, _hist_laps), width="stretch", config={"displayModeBar": False})

# ── Fuel-Adjusted Pace Analysis ───────────────────────────────────────────────
st.markdown("<div class='section-title'>Fuel-Adjusted Pace</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:11px; opacity:0.55; margin:-6px 0 10px; letter-spacing:0.3px;'>"
    "Estimates each driver's true one-lap pace by removing the fuel-load penalty. "
    "Each lap of fuel adds roughly <strong>0.03 s</strong> to the lap time — "
    "correcting for this normalises all laps to equivalent <em>empty-tank</em> pace, "
    "making it easier to compare stints across different fuel levels."
    "</div>",
    unsafe_allow_html=True,
)

# ── Fuel effect tuner
_fuel_col, _ = st.columns([1, 3])
with _fuel_col:
    _fuel_effect = st.slider(
        "Fuel effect (s / lap of fuel)",
        min_value=0.01, max_value=0.06,
        value=0.03, step=0.005, format="%.3f",
        help="Industry standard is ~0.030 s per lap of fuel. Adjust to explore sensitivity.",
        key="fuel_effect_slider",
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _build_fuel_adjusted(driver: str, sess_k: str, fuel_effect: float,
                         laps_df: pd.DataFrame):
    """
    Return DataFrame with raw LapTimeSec and FuelAdjSec columns.
    Fuel correction: subtract (total_laps - lap_number) * fuel_effect
    → normalises all laps to empty-tank pace (equivalent to a flying Q-lap).
    Filters out in-laps and out-laps for accurate analysis.
    """
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        
        # Exclude in-laps and out-laps to focus on flying/pace laps
        if "PitOutTime" in laps.columns:
            laps = laps[laps["PitOutTime"].isna()]
        if "PitInTime" in laps.columns:
            laps = laps[laps["PitInTime"].isna()]
            
        if laps.empty:
            return None
            
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

        # Outlier filter — same as lap history (>2.5× median removed)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        # Total laps in the session (used to compute remaining fuel)
        total_laps = int(laps_df["LapNumber"].max())

        # Remaining fuel = laps left to run AFTER current lap
        laps["FuelLapsRemaining"] = (total_laps - laps["LapNumber"]).clip(lower=0)
        laps["FuelCorrection"]    = laps["FuelLapsRemaining"] * fuel_effect
        laps["FuelAdjSec"]        = laps["LapTimeSec"] - laps["FuelCorrection"]

        return laps[["LapNumber", "LapTimeSec", "FuelAdjSec",
                     "FuelCorrection", "Compound"]].copy()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def _build_fuel_sim_leaderboard(sess_k: str, fuel_effect: float, laps_df: pd.DataFrame):
    """
    Simulate qualifying order by calculating the median fuel-adjusted pace
    for each driver in the session. Filters out in-laps and out-laps.
    """
    try:
        results = []
        all_drvs = laps_df["Driver"].unique()
        total_laps = int(laps_df["LapNumber"].max())
        
        for drv in all_drvs:
            drv_laps = laps_df[laps_df["Driver"] == drv].copy()
            drv_laps = drv_laps.dropna(subset=["LapTime", "LapNumber"])
            if drv_laps.empty:
                continue
                
            # Exclude in-laps and out-laps to get true representative pace
            if "PitOutTime" in drv_laps.columns:
                drv_laps = drv_laps[drv_laps["PitOutTime"].isna()]
            if "PitInTime" in drv_laps.columns:
                drv_laps = drv_laps[drv_laps["PitInTime"].isna()]
                
            if drv_laps.empty:
                continue
                
            drv_laps["LapTimeSec"] = drv_laps["LapTime"].dt.total_seconds()
            
            # Outlier filter
            median_t = drv_laps["LapTimeSec"].median()
            drv_laps = drv_laps[drv_laps["LapTimeSec"] < median_t * 2.5].copy()
            if drv_laps.empty:
                continue
                
            drv_laps = drv_laps.sort_values("LapNumber").reset_index(drop=True)
            drv_laps["FuelLapsRemaining"] = (total_laps - drv_laps["LapNumber"]).clip(lower=0)
            drv_laps["FuelCorrection"]    = drv_laps["FuelLapsRemaining"] * fuel_effect
            drv_laps["FuelAdjSec"]        = drv_laps["LapTimeSec"] - drv_laps["FuelCorrection"]
            
            median_adj = drv_laps["FuelAdjSec"].median()
            best_adj   = drv_laps["FuelAdjSec"].min()
            laps_count = len(drv_laps)
            
            # Extract tyre compound used on the best fuel-adjusted lap
            best_idx = drv_laps["FuelAdjSec"].idxmin()
            best_compound = str(drv_laps.loc[best_idx, "Compound"]).upper() if "Compound" in drv_laps.columns else "UNKNOWN"
            if best_compound in ("NAN", "NONE", ""):
                best_compound = "UNKNOWN"
            
            results.append({
                "Driver": drv,
                "MedianAdjSec": median_adj,
                "BestAdjSec": best_adj,
                "BestCompound": best_compound,
                "Laps": laps_count
            })
            
        if not results:
            return None
            
        df = pd.DataFrame(results)
        df = df.sort_values("MedianAdjSec").reset_index(drop=True)
        df["Pos"] = df.index + 1
        
        p1_median = df.loc[0, "MedianAdjSec"]
        df["GapToLeader"] = df["MedianAdjSec"] - p1_median
        
        return df
    except Exception:
        return None


def _render_fuel_sim_leaderboard(sim_df, highlight_drivers: list, highlight_colours: list, fmt_func=None):
    """Render fuel-corrected simulated qualifying leaderboard as a styled HTML table."""
    colour_map = dict(zip(highlight_drivers, highlight_colours))
    rows_html = ""
    for _, row in sim_df.iterrows():
        drv        = str(row["Driver"])
        is_hl      = drv in colour_map
        accent     = colour_map.get(drv, "transparent")
        row_bg     = f"{accent}18" if is_hl else "transparent"
        border_css = f"border-left: 3px solid {accent};" if is_hl else "border-left: 3px solid transparent;"
        pos_col    = f"<span style='color:{accent}; font-weight:700;'>{row['Pos']}</span>" if is_hl else str(row["Pos"])
        
        med_time = row["MedianAdjSec"]
        med_time_str = f"{int(med_time//60)}:{med_time%60:06.3f}"
        
        best_time = row["BestAdjSec"]
        best_time_str = f"{int(best_time//60)}:{best_time%60:06.3f}"
        
        gap = row["GapToLeader"]
        gap_str = "—" if row["Pos"] == 1 else f"+{gap:.3f}s"
        
        # Compound color dot helper for best lap compound
        best_comp = str(row.get("BestCompound", "UNKNOWN")).upper()
        dot_col = COMPOUND_COLOURS.get(best_comp, COMPOUND_COLOURS["UNKNOWN"])["fill"]
        cmp_html = (
            f"<span style='display:inline-block; width:8px; height:8px; "
            f"border-radius:50%; background:{dot_col}; margin-right:5px; vertical-align:middle;'></span>"
            f"{best_comp.title()}"
        )
        
        rows_html += (
            f"<tr style='background:{row_bg}; {border_css}'>"
            f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
            f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{fmt_func(drv) if fmt_func else drv}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{med_time_str}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:12px; opacity:0.7;'>{gap_str}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{best_time_str}</td>"
            f"<td style='padding:7px 10px;'>{cmp_html}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{row['Laps']}</td>"
            "</tr>"
        )

    table_html = f"""
    <div style='overflow-x:auto; border-radius:12px; border:1px solid rgba(128,128,128,0.15); margin-bottom:8px;'>
    <table style='width:100%; border-collapse:collapse; font-size:13px;'>
      <thead>
        <tr style='border-bottom:1px solid rgba(128,128,128,0.2); opacity:0.6; font-size:10px;
                   letter-spacing:1.5px; text-transform:uppercase;'>
          <th style='padding:8px 10px;'>Pos</th>
          <th style='padding:8px 10px; text-align:left;'>Driver</th>
          <th style='padding:8px 10px; text-align:left;'>Median Fuel-Adj Time</th>
          <th style='padding:8px 10px; text-align:left;'>Gap</th>
          <th style='padding:8px 10px; text-align:left;'>Best Fuel-Adj Lap</th>
          <th style='padding:8px 10px; text-align:left;'>Tyre (Best)</th>
          <th style='padding:8px 10px;'>Laps Run</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def _fuel_pace_fig(drivers_data: list) -> go.Figure:
    """
    drivers_data: list of (driver, colour, df_with_raw_and_adj)
    Plots raw (solid) and fuel-adjusted (dashed) traces side-by-side.
    """
    fig = go.Figure()

    for driver, colour, df in drivers_data:
        if df is None or df.empty:
            continue

        marker_colors = [
            COMPOUND_COLOURS.get(str(c).upper(), COMPOUND_COLOURS["UNKNOWN"])["fill"]
            for c in df["Compound"]
        ]

        # ── Raw pace (solid line, semi-transparent)
        fig.add_trace(go.Scatter(
            x=df["LapNumber"], y=df["LapTimeSec"],
            mode="lines",
            name=f"{driver} raw",
            line=dict(color=colour, width=1.5, dash="dot"),
            opacity=0.45,
            hovertemplate=(
                f"<b>{driver} — Raw</b><br>Lap %{{x}}<br>"
                "Time: %{customdata}<extra></extra>"
            ),
            customdata=[f"{int(t//60)}:{t%60:06.3f}" for t in df["LapTimeSec"]],
        ))

        # ── Fuel-adjusted pace (solid, full opacity with compound markers)
        fig.add_trace(go.Scatter(
            x=df["LapNumber"], y=df["FuelAdjSec"],
            mode="lines+markers",
            name=f"{driver} fuel-adj",
            line=dict(color=colour, width=2.2),
            marker=dict(
                color=marker_colors, size=6,
                line=dict(color=colour, width=1),
            ),
            hovertemplate=(
                f"<b>{driver} — Fuel-Adj</b><br>Lap %{{x}}<br>"
                "Adj Time: %{customdata[0]}<br>"
                "Correction: −%{customdata[1]:.3f} s"
                "<extra></extra>"
            ),
            customdata=[
                [f"{int(t//60)}:{t%60:06.3f}", c]
                for t, c in zip(df["FuelAdjSec"], df["FuelCorrection"])
            ],
        ))

    # ── Annotation for how to read the chart
    fig.add_annotation(
        text="— · — Raw pace  ——  Fuel-adjusted pace",
        xref="paper", yref="paper", x=0.01, y=1.06,
        showarrow=False, font=dict(size=10), opacity=0.5,
        xanchor="left",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=32, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            title="Lap Time (s)", gridcolor="rgba(128,128,128,0.15)",
            zeroline=False, tickformat=".1f",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        height=300,
    )
    return fig


_fuel_pairs = [
    (
        label1, colour1,
        _build_fuel_adjusted(driver1, sess_key, _fuel_effect, _all_laps1)
    )
]
if compare and driver2:
    _fuel_pairs.append((
        label2, colour2,
        _build_fuel_adjusted(driver2, sess_key2 if sess_key2 else sess_key, _fuel_effect, _all_laps2 if _all_laps2 is not None else _all_laps1)
    ))

_fuel_all_none = all(p[2] is None or p[2].empty for p in _fuel_pairs)
if _fuel_all_none:
    st.info("Fuel-adjusted pace not available for this session.")
else:
    st.plotly_chart(_fuel_pace_fig(_fuel_pairs), width="stretch", config={"displayModeBar": False})

    # ── Pace summary stat cards
    _pace_cols = st.columns(len(_fuel_pairs))
    for _pc, (drv, col, df) in zip(_pace_cols, _fuel_pairs):
        if df is None or df.empty:
            continue
        _best_raw  = df["LapTimeSec"].min()
        _best_adj  = df["FuelAdjSec"].min()
        _avg_adj   = df["FuelAdjSec"].median()
        _pc.markdown(
            f"<div class='metric-card' style='--accent:{col};'>"
            f"<div class='metric-label'>{drv} — Fuel-Adj Pace</div>"
            f"<div class='metric-value'>{int(_best_adj//60)}:{_best_adj%60:06.3f}</div>"
            f"<div class='metric-sub'>"
            f"Best raw: {int(_best_raw//60)}:{_best_raw%60:06.3f} · "
            f"Median adj: {int(_avg_adj//60)}:{_avg_adj%60:06.3f}"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    # ── Simulated Qualifying Leaderboard
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    with st.expander("📋 View Simulated Qualifying Leaderboard (Fuel-Corrected)", expanded=False):
        st.markdown(
            "<div style='font-size:13px; margin-bottom:12px; opacity:0.8;'>"
            "This table simulates the overall qualification/race-pace order by ranking all drivers based on their "
            "<strong>median fuel-corrected pace</strong>. All laps are normalized to empty-tank equivalent pace."
            "</div>",
            unsafe_allow_html=True
        )
        if sess2 is not None:
            tab_l1, tab_l2 = st.tabs([f"Session 1 Leaderboard ({year1})", f"Session 2 Leaderboard ({year2})"])
            with tab_l1:
                _sim_df1 = _build_fuel_sim_leaderboard(sess_key, _fuel_effect, _all_laps1)
                if _sim_df1 is None or _sim_df1.empty:
                    st.info("No data available for Session 1.")
                else:
                    _render_fuel_sim_leaderboard(_sim_df1, [driver1], [colour1], _fmt_driver1)
            with tab_l2:
                _sim_df2 = _build_fuel_sim_leaderboard(sess_key2, _fuel_effect, _all_laps2)
                if _sim_df2 is None or _sim_df2.empty:
                    st.info("No data available for Session 2.")
                else:
                    _render_fuel_sim_leaderboard(_sim_df2, [driver2], [colour2], _fmt_driver2)
        else:
            _sim_df = _build_fuel_sim_leaderboard(sess_key, _fuel_effect, _all_laps1)
            if _sim_df is None or _sim_df.empty:
                st.info("No data available to simulate fuel-corrected qualifying order.")
            else:
                _hl_drivers = [driver1] + ([driver2] if compare and driver2 else [])
                _hl_colours = [colour1] + ([colour2] if compare and driver2 else [])
                _render_fuel_sim_leaderboard(_sim_df, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Tyre Stint Timeline ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Tyre Stint Timeline</div>", unsafe_allow_html=True)

# _CMP_PALETTE removed — use COMPOUND_COLOURS (defined in Constants block) directly.


@st.cache_data(show_spinner=False, ttl=3600)
def _build_stints(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return a list of stint dicts: {compound, start_lap, end_lap, laps, fresh}."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapNumber"]).sort_values("LapNumber")
        stints, current = [], None
        for _, row in laps.iterrows():
            cmp = str(row.get("Compound", "UNKNOWN")).upper()
            if cmp in ("NAN", "NONE", ""):
                cmp = "UNKNOWN"
            ln = int(row["LapNumber"])
            fresh = bool(row.get("FreshTyre", False))
            if current is None or cmp != current["compound"] or (
                "PitOutTime" in row and pd.notna(row.get("PitOutTime"))
            ):
                if current:
                    stints.append(current)
                current = {"compound": cmp, "start_lap": ln,
                           "end_lap": ln, "fresh": fresh}
            else:
                current["end_lap"] = ln
        if current:
            stints.append(current)
        for s in stints:
            s["laps"] = s["end_lap"] - s["start_lap"] + 1
        return stints
    except Exception:
        return []


def _stint_fig(drivers_stints: list) -> go.Figure:
    """
    drivers_stints: list of (driver_label, stints_list)
    Draws a horizontal Gantt-style bar per driver, coloured by compound.
    """
    fig = go.Figure()

    for driver, stints in drivers_stints:
        for s in stints:
            palette = COMPOUND_COLOURS.get(s["compound"], COMPOUND_COLOURS["UNKNOWN"])
            width   = s["end_lap"] - s["start_lap"] + 1
            fresh_marker = " ★" if s.get("fresh") else ""

            fig.add_trace(go.Bar(
                x=[width],
                y=[driver],
                base=[s["start_lap"] - 1],   # base = left-edge of bar
                orientation="h",
                name=s["compound"].title(),
                marker=dict(
                    color=palette["fill"],
                    line=dict(color="rgba(255,255,255,0.25)", width=1),
                ),
                text=f"{s['compound'].title()}{fresh_marker} · {s['laps']}L",
                textposition="inside",
                insidetextfont=dict(color=palette["text"], size=10),
                hovertemplate=(
                    f"<b>{driver}</b><br>"
                    f"Compound: {s['compound'].title()}{fresh_marker}<br>"
                    f"Laps {s['start_lap']}–{s['end_lap']} "
                    f"({s['laps']} laps)<extra></extra>"
                ),
                showlegend=False,
            ))

    # ── Compound legend swatches (manual)
    for cmp, pal in COMPOUND_COLOURS.items():
        if cmp == "UNKNOWN":
            continue
        fig.add_trace(go.Bar(
            x=[0], y=[""], orientation="h",
            marker=dict(color=pal["fill"]),
            name=cmp.title(),
            showlegend=True,
        ))

    fig.update_layout(
        barmode="stack",
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)", zeroline=False,
            categoryorder="array",
            categoryarray=[d for d, _ in reversed(drivers_stints)],
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
            title_text="Compound:",
        ),
        height=max(120, 100 + 70 * len(drivers_stints)),
    )
    return fig


_stint_data = [(label1, _build_stints(driver1, sess_key, _all_laps1))]
if compare and driver2:
    _stint_data.append((label2, _build_stints(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1)))

if all(not s for _, s in _stint_data):
    st.info("Stint data not available for this session.")
else:
    st.plotly_chart(_stint_fig(_stint_data), width="stretch", config={"displayModeBar": False})




# ── Pit Stop Summary ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Pit Stop Summary</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_pit_stops(driver: str, sess_k: str, laps_df: pd.DataFrame) -> list[dict] | None:
    """Return a list of pit stop dicts for one driver: lap, duration_s, old_cmp, new_cmp."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        stops = []
        for i, row in laps.iterrows():
            if pd.isna(row.get("PitInTime")) or pd.isna(row.get("PitOutTime")):
                continue
            try:
                duration_s = (row["PitOutTime"] - row["PitInTime"]).total_seconds()
            except Exception:
                duration_s = None

            # Compound before pit = this lap's compound
            old_cmp = str(row.get("Compound", "?")).title()

            # Compound after pit = next lap's compound
            new_cmp = "?"
            if i + 1 < len(laps):
                next_cmp = laps.iloc[i + 1].get("Compound", "?")
                if pd.notna(next_cmp):
                    new_cmp = str(next_cmp).title()

            stops.append({
                "lap":      int(row["LapNumber"]),
                "duration": round(duration_s, 1) if duration_s is not None else None,
                "old_cmp":  old_cmp,
                "new_cmp":  new_cmp,
            })
        return stops if stops else None
    except Exception:
        return None


def _render_pit_table(stops: list[dict], colour: str, driver_label: str) -> str:
    """Build an HTML pit stop table for one driver."""
    def _cmp_dot(cmp: str) -> str:
        pal = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])
        return (
            f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; "
            f"background:{pal['fill']}; margin-right:5px; vertical-align:middle;'></span>"
        )

    rows_html = ""
    for idx, s in enumerate(stops):
        row_bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        dur    = f"{s['duration']:.1f}s" if s["duration"] is not None else "—"
        rows_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:7px 10px; color:#aaa;'>#{idx+1}</td>"
            f"<td style='padding:7px 10px;'>Lap {s['lap']}</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{colour};'>{dur}</td>"
            f"<td style='padding:7px 10px;'>{_cmp_dot(s['old_cmp'])}{s['old_cmp']}</td>"
            f"<td style='padding:7px 10px;'>{_cmp_dot(s['new_cmp'])}{s['new_cmp']}</td>"
            f"</tr>"
        )

    return (
        f"<div style='margin-bottom:16px;'>"
        f"<div style='font-size:12px; font-weight:600; color:{colour}; "
        f"letter-spacing:0.5px; margin-bottom:6px;'>{driver_label}</div>"
        f"<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
        f"<thead><tr style='border-bottom:1px solid rgba(128,128,128,0.2); "
        f"font-size:11px; opacity:0.55; text-transform:uppercase; letter-spacing:0.5px;'>"
        f"<th style='padding:5px 10px; text-align:left;'>Stop</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Lap</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Duration</th>"
        f"<th style='padding:5px 10px; text-align:left;'>From</th>"
        f"<th style='padding:5px 10px; text-align:left;'>To</th>"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>"
    )


_pit_d1 = _build_pit_stops(driver1, sess_key, _all_laps1)
_pit_d2 = _build_pit_stops(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1) if compare and driver2 else None

if _pit_d1 is None and _pit_d2 is None:
    st.info("Pit stop data is not available for this session "
            "(Race and Sprint sessions only).")
else:
    _pit_html = ""
    if _pit_d1:
        _pit_html += _render_pit_table(_pit_d1, colour1, label1)
    if _pit_d2:
        _pit_html += _render_pit_table(_pit_d2, colour2, label2)
    if _pit_html:
        st.markdown(
            f"<div style='background:var(--secondary-background-color); "
            f"border:1px solid rgba(128,128,128,0.15); border-radius:12px; "
            f"padding:16px 20px;'>{_pit_html}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No pit stops recorded for the selected driver(s).")

# ── Pit Strategy & Undercut / Overcut Simulator ───────────────────────────────
if compare and driver2 and _pit_d1 and _pit_d2:
    st.markdown("<div class='section-title'>Pit Strategy & Undercut Analysis</div>", unsafe_allow_html=True)
    
    battles = []
    for p1 in _pit_d1:
        lap1 = p1['lap']
        for p2 in _pit_d2:
            lap2 = p2['lap']
            if abs(lap1 - lap2) <= 3:
                battles.append((p1, p2))
                break
                
    if not battles:
        st.info("The selected drivers were on divergent strategies and did not engage in a direct pit stop battle.")
    else:
        battle = battles[0]
        lap1 = battle[0]['lap']
        lap2 = battle[1]['lap']
        
        w_start = min(lap1, lap2) - 1
        w_end = max(lap1, lap2) + 2
        
        try:
            t1_start = _all_laps1[_all_laps1['LapNumber'] == w_start]['Time'].iloc[0]
            t2_start = _all_laps2[_all_laps2['LapNumber'] == w_start]['Time'].iloc[0]
            gap_start = (t1_start - t2_start).total_seconds()
            
            t1_end = _all_laps1[_all_laps1['LapNumber'] == w_end]['Time'].iloc[0]
            t2_end = _all_laps2[_all_laps2['LapNumber'] == w_end]['Time'].iloc[0]
            gap_end = (t1_end - t2_end).total_seconds()
            
            first_pitter = label1 if lap1 < lap2 else (label2 if lap2 < lap1 else "Simultaneous")
            
            net_change = gap_start - gap_end
            success = "Successful" if (lap1 < lap2 and net_change > 0) or (lap2 < lap1 and net_change < 0) else "Failed"
            success_color = "#52E252" if success == "Successful" else "#E8002D"
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Aggressor (Pitted First)", first_pitter)
            col2.metric(f"Gap at Lap {w_start}", f"{abs(gap_start):.2f}s", f"{'Behind' if gap_start > 0 else 'Ahead'}")
            col3.metric(f"Gap at Lap {w_end}", f"{abs(gap_end):.2f}s", f"{'Behind' if gap_end > 0 else 'Ahead'}")
            col4.markdown(f"<div style='text-align:center;'><div>Status</div><h3 style='color:{success_color}; margin-top:0;'>{success}</h3></div>", unsafe_allow_html=True)
            
            st.plotly_chart(build_undercut_chart(_all_laps1, _all_laps2, label1, label2, colour1, colour2, w_start, w_end, lap1, lap2), width="stretch", config={"displayModeBar": False})
            
        except Exception as e:
            st.warning("Could not calculate undercut gap due to missing telemetry on the battle laps.")


# ── Tyre Degradation Analysis ──────────────────────────────────────────────────
st.markdown("<div class='section-title'>Tyre Degradation Analysis</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:11px; opacity:0.55; margin:-6px 0 10px; letter-spacing:0.3px;'>"
    "Analyses tyre wear and pace drop-off by performing linear regression (OLS) on valid flyer laps. "
    "Out-laps, in-laps, and laps under Safety Car / VSC are excluded. "
    "Note: Fuel burn-off naturally masks tyre degradation by making the car lighter (~0.03 s per lap), "
    "which may result in flat or negative slopes on highly durable compounds."
    "</div>",
    unsafe_allow_html=True,
)

_deg_d1 = _build_tyre_deg_data(driver1, _all_laps1)
_deg_d2 = _build_tyre_deg_data(driver2, _all_laps2 if _all_laps2 is not None else _all_laps1) if compare and driver2 else None

if not _deg_d1 and not _deg_d2:
    st.info("Insufficient stint telemetry (minimum 4 consecutive green-flag laps per stint) to model tyre degradation.")
else:
    fig_deg, table_rows = build_tyre_deg_fig(_deg_d1, _deg_d2, driver1, driver2, colour1, colour2, compare)
    st.plotly_chart(fig_deg, width="stretch", config={"displayModeBar": False})

    # Summary Table
    table_html = ""
    for idx, row in enumerate(table_rows):
        row_bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        comp = row["compound"].title()
        comp_pal = COMPOUND_COLOURS.get(comp.upper(), COMPOUND_COLOURS["UNKNOWN"])
        comp_dot = (
            f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; "
            f"background:{comp_pal['fill']}; margin-right:5px; vertical-align:middle;'></span>"
        )
        
        deg_rate_str = f"{row['deg_rate']:+.3f} s/lap"
        deg_color = "#00e400" if row["deg_rate"] <= 0 else "#ff2200"
        
        fmt_name = _fmt_driver1(row["driver"]) if row["driver"] == driver1 else _fmt_driver2(row["driver"])
        
        table_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:7px 10px; font-weight:600; color:{row['colour']};'>{fmt_name}</td>"
            f"<td style='padding:7px 10px;'>Stint {row['stint']}</td>"
            f"<td style='padding:7px 10px;'>{comp_dot}{comp}</td>"
            f"<td style='padding:7px 10px;'>{row['laps']} laps</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{deg_color};'>{deg_rate_str}</td>"
            f"</tr>"
        )
        
    st.markdown(
        f"<div style='background:var(--secondary-background-color); "
        f"border:1px solid rgba(128,128,128,0.15); border-radius:12px; "
        f"padding:16px 20px; margin-top:16px;'>"
        f"<div style='font-size:12px; font-weight:600; letter-spacing:0.5px; margin-bottom:8px; opacity:0.8;'>Degradation Rates Summary</div>"
        f"<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
        f"<thead><tr style='border-bottom:1px solid rgba(128,128,128,0.2); "
        f"font-size:11px; opacity:0.55; text-transform:uppercase; letter-spacing:0.5px;'>"
        f"<th style='padding:5px 10px; text-align:left;'>Driver</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Stint</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Compound</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Sample Size</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Degradation Rate</th>"
        f"</tr></thead>"
        f"<tbody>{table_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True
    )
st.markdown("<div class='section-title'>Telemetry</div>", unsafe_allow_html=True)

if tel1 is None:
    st.warning("No telemetry available for the selected lap.")
    _render_footer()
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
    fig = plt.figure(figsize=(fig_width, 11), facecolor="none")
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
            ax.set_xlabel("Distance (m)", fontsize=11, labelpad=8)

    for ax_i, (label, _, _, _) in enumerate(CHANNELS):
        axes[ax_i].yaxis.set_label_position("left")
        axes[ax_i].text(1.002, 0.5, label, transform=axes[ax_i].transAxes,
                        fontsize=10, va="center", ha="left",
                        rotation=0, fontweight="600", alpha=0.6)

    fig.suptitle(title_str, fontsize=12, fontweight="bold", y=0.98)

    # Legend
    handles = [mpatches.Patch(color=c, label=d) for d, c, _ in drivers_telemetry]
    if len(handles) > 1:
        fig.legend(handles=handles, loc="upper right",
                   bbox_to_anchor=(0.97, 0.965), fontsize=9,
                   framealpha=0.9, handlelength=1.2, handleheight=0.8)
    return fig


# ── Overlapping ───────────────────────────────────────────────────────────────
if chart_mode == "Overlapping" or not compare:
    drv_list = [(label1, colour1, tel1)]
    if compare and tel2 is not None:
        drv_list.append((label2, colour2, tel2))

    if sess2 is not None:
        title = f"{year1} {gp} {session_label} ({driver1}) vs {year2} {gp2} {session_label2} ({driver2})"
    else:
        title = f"{gp} {year}  ·  {session_label}"
        if compare and driver2:
            title += f"  ·  {driver1} vs {driver2}"
        else:
            title += f"  ·  {driver1}"

    fig = build_chart(drv_list, title)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

# ── Separate ──────────────────────────────────────────────────────────────────
else:
    lc, rc = st.columns(2)
    for col_ctx, drv_lbl, driver, tel, colour, lap_obj in [
        (lc, label1, driver1, tel1, colour1, lap1),
        (rc, label2, driver2, tel2, colour2, lap2),
    ]:
        with col_ctx:
            if tel is None:
                st.warning(f"No telemetry for {drv_lbl}")
                continue
            try:
                lt = format_laptime(lap_obj.get("LapTime"))
            except Exception:
                lt = ""
            title = f"{drv_lbl}  ·  {lt}"
            fig = build_chart([(drv_lbl, colour, tel)], title, fig_width=7)
            st.pyplot(fig, width="stretch")
            plt.close(fig)


# ── Export Telemetry ──────────────────────────────────────────────────────────
with st.expander("⬇️  Export Telemetry Data", expanded=False):
    st.markdown(
        "<div style='font-size:12px; opacity:0.65; margin-bottom:10px;'>"
        "Download the raw telemetry for the selected lap(s) as a CSV file. "
        "Includes Distance, Speed, Throttle, Brake, RPM, Gear, DRS, "
        "Sector 1/2/3 times, and lap metadata."
        "</div>",
        unsafe_allow_html=True,
    )

    def _build_export_csv(driver: str, tel_df, lap_obj) -> bytes:
        """Merge lap metadata into the telemetry dataframe and return CSV bytes."""
        if tel_df is None or tel_df.empty:
            return b""
        export_cols = [c for c in
                       ["Distance", "Speed", "Throttle", "Brake", "RPM", "nGear", "DRS",
                        "X", "Y", "Z", "Time", "SessionTime"]
                       if c in tel_df.columns]
        df = tel_df[export_cols].copy()
        # Rename nGear → Gear for clarity
        df = df.rename(columns={"nGear": "Gear"})
        # Inject lap metadata as constant columns at the front
        df.insert(0, "Driver",    driver)
        df.insert(1, "LapNumber", int(lap_obj.get("LapNumber", 0)) if lap_obj is not None else "")
        df.insert(2, "LapTime",   format_laptime(lap_obj.get("LapTime")) if lap_obj is not None else "")
        df.insert(3, "Compound",  str(lap_obj.get("Compound", "?")).title() if lap_obj is not None else "")
        # Sector times — formatted as seconds (3 dp) for readability
        for _scol, _slabel in [
            ("Sector1Time", "Sector1Time_s"),
            ("Sector2Time", "Sector2Time_s"),
            ("Sector3Time", "Sector3Time_s"),
        ]:
            _sval = lap_obj.get(_scol) if lap_obj is not None else None
            try:
                _ssec = round(_sval.total_seconds(), 3) if _sval is not None and pd.notna(_sval) else ""
            except Exception:
                _ssec = ""
            df.insert(4, _slabel, _ssec)
        return df.to_csv(index=False).encode("utf-8")

    # ── Driver 1 download
    exp_cols = [st.columns(2)[0]]   # left half
    if compare and driver2 and tel2 is not None:
        exp_cols = list(st.columns(2))

    with exp_cols[0]:
        csv1 = _build_export_csv(driver1, tel1, lap1)
        fname1 = f"pitwall_{driver1}_lap{int(lap1.get('LapNumber', 0)) if lap1 is not None else 'X'}.csv"
        st.download_button(
            label=f"📥  {driver1} — Download CSV",
            data=csv1,
            file_name=fname1,
            mime="text/csv",
            disabled=(csv1 == b""),
            width="stretch",
        )

    # ── Driver 2 download (comparison mode only)
    if compare and driver2 and tel2 is not None and len(exp_cols) > 1:
        with exp_cols[1]:
            csv2 = _build_export_csv(driver2, tel2, lap2)
            fname2 = f"pitwall_{driver2}_lap{int(lap2.get('LapNumber', 0)) if lap2 is not None else 'X'}.csv"
            st.download_button(
                label=f"📥  {driver2} — Download CSV",
                data=csv2,
                file_name=fname2,
                mime="text/csv",
                disabled=(csv2 == b""),
                width="stretch",
            )

# ── Speed delta (overlapping + comparison) ────────────────────────────────────

if compare and chart_mode == "Overlapping" and tel1 is not None and tel2 is not None:
    if "Speed" in tel1.columns and "Speed" in tel2.columns:
        st.markdown("<div class='section-title'>Speed Delta</div>", unsafe_allow_html=True)

        fig_d = build_delta_chart(tel1, tel2, colour1, colour2, label1, label2)
        st.pyplot(fig_d, width='stretch')
        plt.close(fig_d)

if compare and chart_mode == "Overlapping" and lap1 is not None and lap2 is not None:
    st.markdown("<div class='section-title'>Time Delta (Continuous)</div>", unsafe_allow_html=True)
    fig_td = build_time_delta_chart(lap2, lap1, colour2, colour1, label2, label1)
    if fig_td:
        st.pyplot(fig_td, width='stretch')
        plt.close(fig_td)

# ── Fastest Laps Leaderboard ──────────────────────────────────────────────────
st.markdown("<div class='section-title'>Fastest Laps Leaderboard</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_leaderboard(sess_k: str, laps_df: pd.DataFrame):
    """Return a ranked DataFrame of all drivers' fastest laps."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapTime", "Driver"])
        # Get each driver's fastest lap
        idx = laps.groupby("Driver")["LapTime"].idxmin()
        best = laps.loc[idx].copy().reset_index(drop=True)
        best["LapTimeSec"] = best["LapTime"].dt.total_seconds()
        best = best.sort_values("LapTimeSec").reset_index(drop=True)

        # Gap to P1
        p1_time = best["LapTimeSec"].iloc[0]
        best["GapToP1"] = best["LapTimeSec"] - p1_time

        # Format columns
        best["Pos"]      = best.index + 1
        best["Time"]     = best["LapTime"].apply(format_laptime)
        best["Gap"]      = best["GapToP1"].apply(
            lambda g: "—" if g == 0 else f"+{g:.3f}s"
        )
        best["Lap"]      = best["LapNumber"].astype(int)
        best["Compound"] = best["Compound"].fillna("?").astype(str).str.title()
        best["Top Speed (km/h)"] = best["SpeedST"].apply(
            lambda s: f"{s:.0f}" if pd.notna(s) else "—"
        )

        return best[["Pos", "Driver", "Time", "Gap", "Compound", "Lap", "Top Speed (km/h)"]]
    except Exception:
        return None


def _render_leaderboard(lb_df, highlight_drivers: list, highlight_colours: list, fmt_func=None):
    """Render leaderboard as a styled HTML table."""
    colour_map = dict(zip(highlight_drivers, highlight_colours))
    rows_html = ""
    for _, row in lb_df.iterrows():
        drv        = str(row["Driver"])
        is_hl      = drv in colour_map
        accent     = colour_map.get(drv, "transparent")
        row_bg     = f"{accent}18" if is_hl else "transparent"
        border_css = f"border-left: 3px solid {accent};" if is_hl else "border-left: 3px solid transparent;"
        pos_col    = f"<span style='color:{accent}; font-weight:700;'>{row['Pos']}</span>" if is_hl else str(row["Pos"])

        # Compound colour dot — derived from canonical COMPOUND_COLOURS
        cmp     = str(row["Compound"])
        dot_col = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])["fill"]
        cmp_html = (
            f"<span style='display:inline-block; width:8px; height:8px; "
            f"border-radius:50%; background:{dot_col}; margin-right:5px; vertical-align:middle;'></span>"
            f"{cmp}"
        )

        rows_html += (
            f"<tr style='background:{row_bg}; {border_css}'>"
            f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
            f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{fmt_func(drv) if fmt_func else drv}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{row['Time']}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:12px; opacity:0.7;'>{row['Gap']}</td>"
            f"<td style='padding:7px 10px;'>{cmp_html}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{row['Lap']}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{row['Top Speed (km/h)']}</td>"
            "</tr>"
        )

    table_html = f"""
    <div style='overflow-x:auto; border-radius:12px; border:1px solid rgba(128,128,128,0.15); margin-bottom:8px;'>
    <table style='width:100%; border-collapse:collapse; font-size:13px;'>
      <thead>
        <tr style='border-bottom:1px solid rgba(128,128,128,0.2); opacity:0.6; font-size:10px;
                   letter-spacing:1.5px; text-transform:uppercase;'>
          <th style='padding:8px 10px;'>Pos</th>
          <th style='padding:8px 10px; text-align:left;'>Driver</th>
          <th style='padding:8px 10px; text-align:left;'>Time</th>
          <th style='padding:8px 10px; text-align:left;'>Gap</th>
          <th style='padding:8px 10px; text-align:left;'>Compound</th>
          <th style='padding:8px 10px;'>Lap</th>
          <th style='padding:8px 10px;'>Top Speed</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


if sess2 is not None:
    tab_lb1, tab_lb2 = st.tabs([f"Session 1 Leaderboard ({year1})", f"Session 2 Leaderboard ({year2})"])
    with tab_lb1:
        _lb1 = _build_leaderboard(sess_key, _all_laps1)
        if _lb1 is None or _lb1.empty:
            st.info("Leaderboard not available for Session 1.")
        else:
            _render_leaderboard(_lb1, [driver1], [colour1], _fmt_driver1)
    with tab_lb2:
        _lb2 = _build_leaderboard(sess_key2, _all_laps2)
        if _lb2 is None or _lb2.empty:
            st.info("Leaderboard not available for Session 2.")
        else:
            _render_leaderboard(_lb2, [driver2], [colour2], _fmt_driver2)
else:
    _lb = _build_leaderboard(sess_key, _all_laps1)
    if _lb is None or _lb.empty:
        st.info("Leaderboard not available for this session.")
    else:
        _hl_drivers  = [driver1] + ([driver2] if compare and driver2 else [])
        _hl_colours  = [colour1] + ([colour2] if compare and driver2 else [])
        _render_leaderboard(_lb, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Ideal Lap vs Actual Lap ───────────────────────────────────────────────────
st.markdown("<div class='section-title'>Ideal Lap vs Actual Lap</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_ideal_lap(sess_k: str, laps_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    For every driver, find best S1, best S2, best S3 across all valid laps.
    Returns a DataFrame with columns:
        Driver, BestS1, BestS2, BestS3, TheoreticalBest,
        ActualBest, Delta, BestS1Lap, BestS2Lap, BestS3Lap
    sorted by TheoreticalBest ascending.
    """
    try:
        laps = laps_df.copy()
        needed = ["Driver", "LapNumber", "Sector1Time", "Sector2Time",
                  "Sector3Time", "LapTime"]
        laps = laps.dropna(subset=["Driver", "LapTime"])

        # Check sector columns exist and have at least some data
        for col in ["Sector1Time", "Sector2Time", "Sector3Time"]:
            if col not in laps.columns or laps[col].dropna().empty:
                return None

        records = []
        for drv, grp in laps.groupby("Driver"):
            s1 = grp.dropna(subset=["Sector1Time"])
            s2 = grp.dropna(subset=["Sector2Time"])
            s3 = grp.dropna(subset=["Sector3Time"])
            lt = grp.dropna(subset=["LapTime"])
            if s1.empty or s2.empty or s3.empty or lt.empty:
                continue

            best_s1_row = s1.loc[s1["Sector1Time"].idxmin()]
            best_s2_row = s2.loc[s2["Sector2Time"].idxmin()]
            best_s3_row = s3.loc[s3["Sector3Time"].idxmin()]

            best_s1 = best_s1_row["Sector1Time"].total_seconds()
            best_s2 = best_s2_row["Sector2Time"].total_seconds()
            best_s3 = best_s3_row["Sector3Time"].total_seconds()

            theoretical = best_s1 + best_s2 + best_s3
            actual_best = lt["LapTime"].min().total_seconds()
            delta = actual_best - theoretical

            records.append({
                "Driver":          str(drv),
                "BestS1":          best_s1,
                "BestS2":          best_s2,
                "BestS3":          best_s3,
                "TheoreticalBest": theoretical,
                "ActualBest":      actual_best,
                "Delta":           delta,
                "BestS1Lap":       int(best_s1_row["LapNumber"]),
                "BestS2Lap":       int(best_s2_row["LapNumber"]),
                "BestS3Lap":       int(best_s3_row["LapNumber"]),
            })

        if not records:
            return None

        df = pd.DataFrame(records).sort_values("TheoreticalBest").reset_index(drop=True)
        df["Pos"] = df.index + 1

        # Gap to theoretical pole (best theoretical lap overall)
        pole_time = df["TheoreticalBest"].iloc[0]
        df["GapToPole"] = df["TheoreticalBest"] - pole_time

        return df
    except Exception:
        return None


def _fmt_sec(s: float) -> str:
    """Format seconds as M:SS.mmm lap-time string."""
    m = int(s // 60)
    return f"{m}:{s % 60:06.3f}"


def _render_ideal_lap_section(ideal_df, highlight_drivers: list, highlight_colours: list, fmt_func=None):
    if ideal_df is None or ideal_df.empty:
        st.info("Ideal lap analysis not available for this session.")
        return

    _delta_cards_html = ""
    for _cd, _cc in zip(highlight_drivers, highlight_colours):
        _row = ideal_df[ideal_df["Driver"] == _cd]
        if _row.empty:
            continue
        _r = _row.iloc[0]
        _sign = "+" if _r["Delta"] >= 0 else "-"
        _delta_str = f"{_sign}{abs(_r['Delta']):.3f}s"
        _delta_col  = "#ff6b6b" if _r["Delta"] > 0.05 else "#51cf66"
        _delta_cards_html += (
            f"<div style='background:var(--secondary-background-color);"
            f" border:1px solid rgba(128,128,128,0.15); border-radius:12px;"
            f" padding:14px 18px; flex:1; min-width:220px;'>"
            f"<div style='font-size:11px; font-weight:600; letter-spacing:1px;"
            f" text-transform:uppercase; color:{_cc}; margin-bottom:8px;'>"
            f"{fmt_func(_cd) if fmt_func else _cd}</div>"
            f"<div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px;"
            f" margin-bottom:10px;'>"
            f"<div style='font-size:11px; opacity:0.6;'>S1</div>"
            f"<div style='font-size:11px; opacity:0.6;'>S2</div>"
            f"<div style='font-size:11px; opacity:0.6;'>S3</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS1']:.3f}s</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS2']:.3f}s</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS3']:.3f}s</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {int(_r['BestS1Lap'])}</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {int(_r['BestS2Lap'])}</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {int(_r['BestS3Lap'])}</div>"
            f"</div>"
            f"<div style='border-top:1px solid rgba(128,128,128,0.15);"
            f" padding-top:8px; display:flex; justify-content:space-between;"
            f" align-items:center;'>"
            f"<div><div style='font-size:10px; opacity:0.5;'>Theoretical Best</div>"
            f"<div style='font-size:15px; font-weight:700;'>"
            f"{_fmt_sec(_r['TheoreticalBest'])}</div></div>"
            f"<div style='text-align:right;'>"
            f"<div style='font-size:10px; opacity:0.5;'>Time Left on Table</div>"
            f"<div style='font-size:15px; font-weight:700; color:{_delta_col};'>"
            f"{_delta_str}</div></div>"
            f"</div></div>"
        )

    if _delta_cards_html:
        st.markdown(
            f"<div style='display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px;'>"
            f"{_delta_cards_html}</div>",
            unsafe_allow_html=True,
        )

    # ── Full-field ideal lap table ─────────────────────────────────────────────
    _hl_set = set(highlight_drivers)
    _tbl_rows = ""
    for _, _r in ideal_df.iterrows():
        _is_hl  = _r["Driver"] in _hl_set
        _hl_col = highlight_colours[highlight_drivers.index(_r["Driver"])] if _is_hl else None
        _row_style = (
            f"border-left: 3px solid {_hl_col};"
            f" background: rgba({hex_to_rgb(_hl_col) if _hl_col else '0,0,0'},0.06);"
        ) if _is_hl and _hl_col else ""

        _gap_str  = "—" if _r["GapToPole"] < 0.001 else f"+{_r['GapToPole']:.3f}s"
        _sign     = "+" if _r["Delta"] >= 0 else "-"
        _d_str    = f"{_sign}{abs(_r['Delta']):.3f}s"
        _d_col    = "#ff6b6b" if _r["Delta"] > 0.05 else "#51cf66"
        _name     = fmt_func(_r["Driver"]) if fmt_func else _r["Driver"]

        _tbl_rows += (
            f"<tr style='{_row_style}'>"
            f"<td style='padding:7px 10px; opacity:0.5;'>{int(_r['Pos'])}</td>"
            f"<td style='padding:7px 10px; font-weight:{'700' if _is_hl else '400'};'>"
            f"{_name}</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS1']:.3f}s</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS2']:.3f}s</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS3']:.3f}s</td>"
            f"<td style='padding:7px 10px; font-weight:600;'>"
            f"{_fmt_sec(_r['TheoreticalBest'])}</td>"
            f"<td style='padding:7px 10px; opacity:0.6;'>{_gap_str}</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{_d_col};'>{_d_str}</td>"
            f"</tr>"
        )

    _ideal_tbl = f"""
    <div style='background:var(--secondary-background-color);
                border:1px solid rgba(128,128,128,0.15);
                border-radius:12px; padding:16px 20px; overflow-x:auto;'>
      <table style='width:100%; border-collapse:collapse; font-size:13px;'>
        <thead>
          <tr style='border-bottom:1px solid rgba(128,128,128,0.2);
                     font-size:11px; opacity:0.55; text-transform:uppercase;
                     letter-spacing:0.5px;'>
            <th style='padding:5px 10px; text-align:left;'>Pos</th>
            <th style='padding:5px 10px; text-align:left;'>Driver</th>
            <th style='padding:5px 10px; text-align:left;'>Best S1</th>
            <th style='padding:5px 10px; text-align:left;'>Best S2</th>
            <th style='padding:5px 10px; text-align:left;'>Best S3</th>
            <th style='padding:5px 10px; text-align:left;'>Theoretical Best</th>
            <th style='padding:5px 10px; text-align:left;'>Gap to Pole</th>
            <th style='padding:5px 10px; text-align:left;'>Time on Table</th>
          </tr>
        </thead>
        <tbody>{_tbl_rows}</tbody>
      </table>
    </div>
    """
    st.markdown(_ideal_tbl, unsafe_allow_html=True)


if sess2 is not None:
    tab_id1, tab_id2 = st.tabs([f"Session 1 Ideal Laps ({year1})", f"Session 2 Ideal Laps ({year2})"])
    with tab_id1:
        _ideal_df1 = _build_ideal_lap(sess_key, _all_laps1)
        _render_ideal_lap_section(_ideal_df1, [driver1], [colour1], _fmt_driver1)
    with tab_id2:
        _ideal_df2 = _build_ideal_lap(sess_key2, _all_laps2)
        _render_ideal_lap_section(_ideal_df2, [driver2], [colour2], _fmt_driver2)
else:
    _ideal_df = _build_ideal_lap(sess_key, _all_laps1)
    _render_ideal_lap_section(_ideal_df, [driver1] + ([driver2] if compare and driver2 else []),
                              [colour1] + ([colour2] if compare and driver2 else []), _fmt_driver1)



# ── Multi-Driver Grid Analysis & Heatmaps ───────────────────────────────────────
st.markdown("<div class='section-title'>Multi-Driver Grid Analysis & Heatmaps</div>", unsafe_allow_html=True)
_render_grid_heatmap_section(sess, _all_laps1, all_drivers1, sess_key)



# ── Gap to Leader ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Gap to Leader</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_gap_data(sess_k: str, laps_df: pd.DataFrame, _session_obj=None):
    """Return a dict {driver: pd.Series(gap_seconds, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        # Only use valid laps with a recorded LapTime
        laps = laps.dropna(subset=["LapTime", "LapNumber", "Driver"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # For each driver sort by lap number and compute cumulative race time
        gap_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber").copy()
            grp["CumTime"] = grp["LapTimeSec"].cumsum()
            gap_dict[drv] = grp.set_index("LapNumber")["CumTime"]
        if not gap_dict:
            return None, None
        # Build leader reference: at each lap, min cumulative time across drivers
        all_laps_idx = sorted({lap for s in gap_dict.values() for lap in s.index})
        leader_time = pd.Series(index=all_laps_idx, dtype=float)
        for lap in all_laps_idx:
            times_at_lap = [s.get(lap) for s in gap_dict.values() if lap in s.index]
            times_at_lap = [t for t in times_at_lap if t is not None]
            if times_at_lap:
                leader_time[lap] = min(times_at_lap)
        # Convert each driver's cumulative time to gap vs leader
        gap_to_leader = {}
        for drv, cum in gap_dict.items():
            gap = cum - leader_time.reindex(cum.index)
            gap_to_leader[drv] = gap
        # Also return track status by lap for shading
        try:
            ts = _session_obj.track_status.copy() if _session_obj is not None else None
            if ts is not None:
                ts["LapNumber"] = ts.index
        except Exception:
            ts = None
        return gap_to_leader, ts
    except Exception:
        return None, None

def _gap_chart_fig(gap_to_leader, highlight_drivers, highlight_colours, session_laps):
    """Build and return a Plotly figure of gap to leader."""
    fig = go.Figure()

    # Grey background traces for all other drivers
    for drv, gap in gap_to_leader.items():
        if drv in highlight_drivers:
            continue
        fig.add_trace(go.Scatter(
            x=list(gap.index), y=list(gap.values),
            mode="lines",
            line=dict(color="rgba(180,180,180,0.18)", width=1),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Mark pit laps for highlighted drivers
    try:
        pit_laps_all = session_laps[session_laps["PitOutTime"].notna()]["LapNumber"].tolist()
    except Exception:
        pit_laps_all = []

    # Highlighted driver traces
    for drv, col in zip(highlight_drivers, highlight_colours):
        if drv not in gap_to_leader:
            continue
        gap = gap_to_leader[drv]
        # Pit lap markers
        pit_x = [ln for ln in pit_laps_all
                 if ln in gap.index and
                 session_laps[(session_laps["Driver"] == drv) &
                              (session_laps["LapNumber"] == ln)].shape[0] > 0]
        fig.add_trace(go.Scatter(
            x=list(gap.index), y=list(gap.values),
            mode="lines",
            line=dict(color=col, width=2.5),
            name=drv,
            hovertemplate=f"<b>{drv}</b><br>Lap %{{x}}<br>Gap: +%{{y:.1f}} s<extra></extra>",
        ))
        if pit_x:
            fig.add_trace(go.Scatter(
                x=pit_x,
                y=[gap.get(ln) for ln in pit_x],
                mode="markers",
                marker=dict(symbol="triangle-down", size=10, color=col,
                            line=dict(color="white", width=1)),
                name=f"{drv} pit",
                hovertemplate=f"<b>{drv}</b> PIT<br>Lap %{{x}}<extra></extra>",
                showlegend=True,
            ))

    # Leader line at 0
    fig.add_hline(y=0, line=dict(color="rgba(255,135,0,0.5)", width=1.5, dash="dot"),
                  annotation_text="Leader", annotation_position="right")

    fig.update_layout(
        margin=dict(l=0, r=0, t=16, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Lap", gridcolor="rgba(128,128,128,0.15)",
                   tickmode="linear", dtick=5, zeroline=False),
        yaxis=dict(title="Gap to Leader (s)", gridcolor="rgba(128,128,128,0.15)",
                   zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        height=420,
    )
    return fig

def _render_gap_to_leader_section(sess_k, laps_df, session_obj, highlight_drivers, highlight_colours, fmt_func=None):
    gtl_data, ts_data = _build_gap_data(sess_k, laps_df, session_obj)
    if gtl_data is None:
        st.info("Gap to Leader data is not available for this session.")
        return

    # Check highlight drivers are actually in the dataset
    highlight = [d for d in highlight_drivers if d in gtl_data]
    colours = [highlight_colours[highlight_drivers.index(d)] for d in highlight]

    gtl_fig = _gap_chart_fig(gtl_data, highlight, colours, session_obj.laps)
    st.plotly_chart(gtl_fig, width="stretch", config={"displayModeBar": False})

    # Show quick stats below the chart
    stat_cols = st.columns(len(highlight))
    for col, drv, col_colour in zip(stat_cols, highlight, colours):
        gap_s = gtl_data[drv]
        final_gap = gap_s.iloc[-1]
        max_gap   = gap_s.max()
        drv_lbl = fmt_func(drv) if fmt_func else drv
        col.markdown(
            f"<div class='metric-card'>"
            f"<div class='metric-label'>{drv_lbl} — Final Gap</div>"
            f"<div class='metric-value' style='color:{col_colour};'>+{final_gap:.1f}s</div>"
            f"<div class='metric-sub'>Peak: +{max_gap:.1f} s behind leader</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

if sess2 is not None:
    tab_g1, tab_g2 = st.tabs([f"Session 1 ({year1})", f"Session 2 ({year2})"])
    with tab_g1:
        _render_gap_to_leader_section(sess_key, _all_laps1, sess, [driver1], [colour1], _fmt_driver1)
    with tab_g2:
        _render_gap_to_leader_section(sess_key2, _all_laps2, sess2, [driver2], [colour2], _fmt_driver2)
else:
    _render_gap_to_leader_section(sess_key, _all_laps1, sess,
                                  [driver1] + ([driver2] if compare and driver2 else []),
                                  [colour1] + ([colour2] if compare and driver2 else []), _fmt_driver1)


# ── Race Position Chart ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Race Position</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_position_data(sess_k: str, laps_df: pd.DataFrame):
    """Return a dict {driver: pd.Series(position, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapNumber", "Position", "Driver"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["Position"]  = laps["Position"].astype(int)
        pos_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber")
            pos_dict[str(drv)] = grp.set_index("LapNumber")["Position"]
        return pos_dict if pos_dict else None
    except Exception:
        return None


def _render_position_section(sess_k, laps_df, highlight_drivers, highlight_colours, fmt_func=None):
    pos_data = _build_position_data(sess_k, laps_df)
    if pos_data is None or not pos_data:
        st.info("Race position data is not available for this session type "
                "(only Race and Sprint sessions carry lap-by-lap position data).")
        return

    highlight = {}
    for drv, col in zip(highlight_drivers, highlight_colours):
        highlight[drv] = col

    pos_fig = go.Figure()

    # ── All drivers — faint grey background lines
    for _drv, _series in pos_data.items():
        if _drv in highlight:
            continue   # drawn as highlighted traces below
        drv_lbl = fmt_func(_drv) if fmt_func else _drv
        pos_fig.add_trace(go.Scatter(
            x=_series.index.tolist(),
            y=_series.tolist(),
            mode="lines",
            name=drv_lbl,
            line=dict(color="rgba(160,160,160,0.18)", width=1),
            hovertemplate=(
                f"<b>{drv_lbl}</b><br>"
                "Lap %{x}<br>P%{y}<extra></extra>"
            ),
            showlegend=False,
        ))

    # ── Selected driver(s) — vivid team-coloured lines with markers
    for _drv, _col in highlight.items():
        if _drv not in pos_data:
            continue
        _series = pos_data[_drv]
        drv_lbl = fmt_func(_drv) if fmt_func else _drv
        pos_fig.add_trace(go.Scatter(
            x=_series.index.tolist(),
            y=_series.tolist(),
            mode="lines+markers",
            name=drv_lbl,
            line=dict(color=_col, width=2.5),
            marker=dict(size=4, color=_col),
            hovertemplate=(
                f"<b>{drv_lbl}</b><br>"
                "Lap %{x}<br>P%{y}<extra></extra>"
            ),
            showlegend=True,
        ))

    # Max lap for x range
    _max_lap = max(
        (s.index.max() for s in pos_data.values() if not s.empty),
        default=1,
    )

    pos_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=12, b=0),
        height=360,
        xaxis=dict(
            title="Lap",
            range=[1, _max_lap],
            gridcolor="rgba(128,128,128,0.12)",
            zeroline=False,
        ),
        yaxis=dict(
            title="Position",
            autorange="reversed",   # P1 at top
            tickmode="linear",
            tick0=1,
            dtick=1,
            gridcolor="rgba(128,128,128,0.12)",
            zeroline=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            font=dict(size=11),
        ),
        font=dict(color="#888888", size=11),
        hoverlabel=dict(bgcolor="rgba(20,20,20,0.85)", font_size=12),
    )

    st.plotly_chart(pos_fig, width="stretch", config={"displayModeBar": False})


if sess2 is not None:
    tab_p1, tab_p2 = st.tabs([f"Session 1 ({year1})", f"Session 2 ({year2})"])
    with tab_p1:
        _render_position_section(sess_key, _all_laps1, [driver1], [colour1], _fmt_driver1)
    with tab_p2:
        _render_position_section(sess_key2, _all_laps2, [driver2], [colour2], _fmt_driver2)
else:
    _render_position_section(sess_key, _all_laps1,
                             [driver1] + ([driver2] if compare and driver2 else []),
                             [colour1] + ([colour2] if compare and driver2 else []), _fmt_driver1)

# ── Track Map ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Track Map</div>", unsafe_allow_html=True)

@st.cache_data(show_spinner=False, ttl=600)
def _get_telemetry_for_map(_lap, driver: str, sess_k: str):
    """Return merged position + car telemetry for a lap."""
    try:
        return _lap.get_telemetry()
    except Exception:
        return None

def render_maps_block(session_obj, sess_k, driver, colour, lap, key_suffix, other_driver=None, other_colour=None, other_lap=None, fmt_func=None):
    map_tab1, map_tab2, map_tab3, map_tab4 = st.tabs(["🎨  Track Map", "🕹️  Driver Inputs", "🎬  Race Replay", "🔍  Corner Analysis"])

    # ────────────────────────────────────────────────────────────────────────────
    # TAB 1 — Static speed-coloured track map
    # ────────────────────────────────────────────────────────────────────────────
    with map_tab1:
        def _speed_map_fig(l_obj, drv: str, col: str, l_obj2=None, drv2=None, col2=None):
            tel = _get_telemetry_for_map(l_obj, drv, sess_k)
            if tel is None or tel.empty:
                return None, "GPS position telemetry is not available for this lap."

            # We strictly need coordinate columns
            if not {"X", "Y"}.issubset(tel.columns) or tel["X"].dropna().empty or tel["Y"].dropna().empty:
                return None, "GPS position coordinates (X/Y) are not available for this lap."

            fig = go.Figure()
            has_speed = "Speed" in tel.columns and tel["Speed"].notna().any()
            warning_msg = None if has_speed else "Speed telemetry is not available; showing track outline only."

            if l_obj2 is not None and drv2:
                # ── Compare mode: AWS-Style Mini-Sector Speed Dominance Map
                tel2 = _get_telemetry_for_map(l_obj2, drv2, sess_k)
                has_speed2 = tel2 is not None and "Speed" in tel2.columns and tel2["Speed"].notna().any()
                has_distance = "Distance" in tel.columns and tel2 is not None and "Distance" in tel2.columns

                if has_speed and has_speed2 and has_distance:
                    NUM_MINISECTORS = 25
                    max_dist = max(tel["Distance"].max(), tel2["Distance"].max())
                    bin_edges = np.linspace(0, max_dist, NUM_MINISECTORS + 1)

                    for i in range(NUM_MINISECTORS):
                        d_start = bin_edges[i]
                        d_end = bin_edges[i+1]
                        
                        mask1 = (tel["Distance"] >= d_start) & (tel["Distance"] <= d_end)
                        mask2 = (tel2["Distance"] >= d_start) & (tel2["Distance"] <= d_end)
                        
                        if not mask1.any():
                            continue
                            
                        s1_mean = tel.loc[mask1, "Speed"].mean() if not tel.loc[mask1, "Speed"].empty else 0
                        s2_mean = tel2.loc[mask2, "Speed"].mean() if not tel2.loc[mask2, "Speed"].empty else 0
                        
                        fastest_color = col if s1_mean >= s2_mean else col2
                        fastest_drv = drv if s1_mean >= s2_mean else drv2
                        
                        # Grab the segment and include the next point to prevent visual gaps
                        idx = tel[mask1].index
                        if len(idx) > 0:
                            last_idx = idx[-1]
                            next_idx = last_idx + 1 if (last_idx + 1) in tel.index else last_idx
                            seg_indices = list(idx)
                            if next_idx not in seg_indices:
                                seg_indices.append(next_idx)
                                
                            seg = tel.loc[seg_indices]
                            
                            fig.add_trace(go.Scatter(
                                x=seg["X"], y=seg["Y"],
                                mode="lines",
                                line=dict(color=fastest_color, width=16),
                                name=f"Sector {i+1}",
                                hovertemplate=f"<b>Mini-Sector {i+1}</b><br>Fastest: {fastest_drv} ({max(s1_mean, s2_mean):.0f} km/h)<extra></extra>"
                            ))
                else:
                    # Fallback to gray if speed or distance is missing
                    fig.add_trace(go.Scatter(
                        x=tel["X"], y=tel["Y"], mode="lines",
                        line=dict(color="gray", width=16), showlegend=False, hoverinfo="skip"
                    ))
                    if not warning_msg:
                        warning_msg = "Speed/Distance telemetry is incomplete; showing single track outline."

                # Driver 2 path overlay
                if tel2 is not None and {"X", "Y"}.issubset(tel2.columns) and not tel2["X"].dropna().empty:
                    fig.add_trace(go.Scatter(
                        x=tel2["X"], y=tel2["Y"],
                        mode="markers",
                        marker=dict(color=col2, size=3, opacity=0.45),
                        name=f"{drv2} path",
                        hoverinfo="skip",
                    ))

            else:
                # ── Single driver mode: Speed map
                # Track outline
                fig.add_trace(go.Scatter(
                    x=tel["X"], y=tel["Y"], mode="lines",
                    line=dict(color="gray", width=16), showlegend=False, hoverinfo="skip"
                ))

                if has_speed:
                    # Driver 1 speed-coloured scatter
                    fig.add_trace(go.Scatter(
                        x=tel["X"], y=tel["Y"],
                        mode="markers",
                        marker=dict(
                            color=tel["Speed"],
                            colorscale=[[0.0, "#1a1aff"], [0.35, "#00c8ff"], [0.65, "#00e400"], [0.85, "#ffd700"], [1.0, "#ff2200"]],
                            size=4,
                            colorbar=dict(title=dict(text="Speed (km/h)"), thickness=10, len=0.7, bgcolor="rgba(0,0,0,0)", x=1.02),
                            showscale=True,
                        ),
                        name=drv,
                        hovertemplate=f"<b>{drv}</b><br>Speed: %{{marker.color:.0f}} km/h<br>X: %{{x:.0f}}  Y: %{{y:.0f}}<extra></extra>"
                    ))

            # ── Start / finish marker
            fig.add_trace(go.Scatter(
                x=[tel["X"].iloc[0]], y=[tel["Y"].iloc[0]],
                mode="markers",
                marker=dict(symbol="circle", size=14, color=col,
                            line=dict(color="white", width=2)),
                name="Start / Finish",
                hovertemplate="Start / Finish<extra></extra>",
            ))

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                yaxis=dict(visible=False),
                height=520,
                margin=dict(l=0, r=80, t=10, b=10),
            )
            return fig, warning_msg

        if lap is not None:
            res = _speed_map_fig(
                lap, driver, colour,
                l_obj2=other_lap,
                drv2=other_driver,
                col2=other_colour,
            )
            if res is not None:
                sm_fig, err_msg = res
                if sm_fig:
                    st.plotly_chart(sm_fig, width="stretch", config={"displayModeBar": False})
                    if err_msg:
                        st.info(err_msg)
                else:
                    st.info(err_msg)
            else:
                st.info("Position data not available for this lap.")
        else:
            st.info("Load a session and select a lap to view the speed map.")

    # ────────────────────────────────────────────────────────────────────────────
    # TAB 2 — Driver Inputs Map
    # ────────────────────────────────────────────────────────────────────────────
    with map_tab2:
        def _input_map_fig(l_obj, drv: str, col: str):
            tel = _get_telemetry_for_map(l_obj, drv, sess_k)
            if tel is None or tel.empty:
                return None, "GPS position telemetry is not available for this lap."

            # We strictly need coordinate columns
            if not {"X", "Y"}.issubset(tel.columns) or tel["X"].dropna().empty or tel["Y"].dropna().empty:
                return None, "GPS position coordinates (X/Y) are not available for this lap."

            fig = go.Figure()

            # Track outline
            fig.add_trace(go.Scatter(
                x=tel["X"], y=tel["Y"], mode="lines",
                line=dict(color="gray", width=16), showlegend=False, hoverinfo="skip"
            ))

            # Check if inputs exist (Throttle and Brake)
            has_inputs = {"Throttle", "Brake"}.issubset(tel.columns) and tel["Throttle"].notna().any() and tel["Brake"].notna().any()
            warning_msg = None if has_inputs else "Throttle/Brake inputs telemetry is not available; showing track outline only."

            if has_inputs:
                def get_input_color(row):
                    if row["Brake"] > 0:
                        return "#ff2200"  # Red for braking
                    elif row["Throttle"] >= 99:
                        return "#00e400"  # Green for full throttle
                    else:
                        return "#ffd700"  # Yellow for coasting/modulating

                colors = tel.apply(get_input_color, axis=1)

                fig.add_trace(go.Scatter(
                    x=tel["X"], y=tel["Y"],
                    mode="markers",
                    marker=dict(color=colors, size=4),
                    name=drv,
                    hovertemplate=(
                        f"<b>{drv}</b><br>"
                        "Throttle: %{customdata[0]:.0f}%<br>"
                        "Brake: %{customdata[1]}<br>"
                        "<extra></extra>"
                    ),
                    customdata=np.stack((tel["Throttle"], tel["Brake"]), axis=-1),
                    showlegend=False
                ))

            # Start / finish marker
            fig.add_trace(go.Scatter(
                x=[tel["X"].iloc[0]], y=[tel["Y"].iloc[0]],
                mode="markers",
                marker=dict(symbol="circle", size=14, color=col, line=dict(color="white", width=2)),
                name="Start / Finish", hovertemplate="Start / Finish<extra></extra>",
                showlegend=False
            ))

            # Dummy traces for legend
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color="#00e400", size=10), name="Full Throttle"))
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color="#ff2200", size=10), name="Braking"))
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(color="#ffd700", size=10), name="Coasting"))

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=True,
                xaxis=dict(visible=False, scaleanchor="y", scaleratio=1), yaxis=dict(visible=False),
                height=520, margin=dict(l=0, r=80, t=10, b=10),
            )
            return fig, warning_msg

        if lap is not None:
            if other_driver and other_lap is not None:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(
                        f"<div style='text-align:center; font-weight:bold; margin-bottom:8px; "
                        f"color:{colour};'>{fmt_func(driver) if fmt_func else driver}</div>",
                        unsafe_allow_html=True
                    )
                    res1 = _input_map_fig(lap, driver, colour)
                    if res1 is not None:
                        input_fig1, err_msg1 = res1
                        if input_fig1:
                            st.plotly_chart(input_fig1, width="stretch", config={"displayModeBar": False})
                            if err_msg1:
                                st.info(err_msg1)
                        else:
                            st.info(err_msg1)
                    else:
                        st.info(f"Input telemetry not available for {fmt_func(driver) if fmt_func else driver}.")
                with col2:
                    st.markdown(
                        f"<div style='text-align:center; font-weight:bold; margin-bottom:8px; "
                        f"color:{other_colour};'>{fmt_func(other_driver) if fmt_func else other_driver}</div>",
                        unsafe_allow_html=True
                    )
                    res2 = _input_map_fig(other_lap, other_driver, other_colour)
                    if res2 is not None:
                        input_fig2, err_msg2 = res2
                        if input_fig2:
                            st.plotly_chart(input_fig2, width="stretch", config={"displayModeBar": False})
                            if err_msg2:
                                st.info(err_msg2)
                        else:
                            st.info(err_msg2)
                    else:
                        st.info(f"Input telemetry not available for {fmt_func(other_driver) if fmt_func else other_driver}.")
            else:
                res = _input_map_fig(lap, driver, colour)
                if res is not None:
                    input_fig, err_msg = res
                    if input_fig:
                        st.plotly_chart(input_fig, width="stretch", config={"displayModeBar": False})
                        if err_msg:
                            st.info(err_msg)
                    else:
                        st.info(err_msg)
                else:
                    st.info("Input telemetry (Throttle/Brake) not available for this lap.")
        else:
            st.info("Load a session and select a lap to view driver inputs.")

    # ────────────────────────────────────────────────────────────────────────────
    # TAB 3 — Animated race replay with all cars
    # ────────────────────────────────────────────────────────────────────────────
    with map_tab3:
        replay_key = f"replay_{sess_k}"
        if replay_key not in st.session_state:
            st.session_state[replay_key] = None

        # ── Placeholder / button
        if st.session_state[replay_key] is None:
            st.markdown(
                "<div style='text-align:center; padding:56px 24px; border:1px dashed var(--text-color); "
                "border-radius:12px; margin:8px 0;'>"
                "<div style='font-size:52px; margin-bottom:14px;'>🎬</div>"
                "<div style='font-size:14px;'>Animated replay of all cars on track.</div>"
                "<div style='font-size:12px; margin-top:6px;'>"
                "Samples every 5 s · up to 500 frames · ~20 s to build"
                "</div></div>",
                unsafe_allow_html=True,
            )

        gen_col, _ = st.columns([1, 3])
        with gen_col:
            gen_btn = st.button("🎬  Generate Race Replay", key=f"gen_replay_{key_suffix}",
                                width="stretch")

        if gen_btn:
            st.session_state[replay_key] = None   # reset so we rebuild
            with st.spinner("Building animation — sampling all car positions…"):
                try:
                    # ── Build driver number → abbr + colour map
                    drv_meta = {}
                    for drv_num in session_obj.drivers:
                        try:
                            info = session_obj.get_driver(drv_num)
                            abbr   = info.get("Abbreviation", drv_num)
                            colour_val = _team_colour(info.get("TeamName", ""))
                            drv_meta[drv_num] = {"abbr": abbr, "colour": colour_val}
                        except Exception:
                            drv_meta[drv_num] = {"abbr": drv_num, "colour": "#888"}

                    # ── Extract position time series for each driver
                    T_STEP   = 5          # seconds between animation frames
                    MAX_SECS = 7200       # cap at 2 hours
                    MAX_FRAMES = 500

                    all_data = {}         # drv_num -> {t, x, y}
                    for drv_num in session_obj.drivers:
                        try:
                            pdf = session_obj.pos_data[drv_num]
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
                        _render_footer()
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
                        _render_footer()
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
                            line=dict(color="gray", width=14),
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
                                line=dict(color="black", width=1.5),
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

                    for f_i, t_sec in enumerate(t_grid):
                        label = _fmt(t_sec)
                        fdata = [
                            go.Scatter(
                                x=track_x, y=track_y, mode="lines",
                                line=dict(color="gray", width=14),
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
                                    line=dict(color="black", width=1.5),
                                ),
                                text=[meta["abbr"]],
                                textposition="top center",
                                textfont=dict(size=8, color=meta["colour"]),
                                name=meta["abbr"],
                                hovertemplate=f"<b>{meta['abbr']}</b><extra></extra>",
                            ))

                        frames.append(go.Frame(data=fdata, name=label))
                        # Add slider step only every ~12 frames to reduce clutter
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
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=True,
                        legend=dict(
                            bordercolor="gray", borderwidth=0.5,
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

            st.caption(
                f"⏱  {n_frames} frames · {session_secs // 60} min {session_secs % 60} s covered · "
                "5 s per frame · Click ▶ Play or drag the slider"
            )

    # ────────────────────────────────────────────────────────────────────────────
    # TAB 4 — Corner Analysis
    # ────────────────────────────────────────────────────────────────────────────
    with map_tab4:
        st.markdown("<h4 style='margin-top:0;'>Corner-by-Corner Performance Analysis</h4>", unsafe_allow_html=True)
        if lap is not None:
            circuit_info = None
            try:
                circuit_info = session_obj.get_circuit_info()
            except Exception:
                pass

            if circuit_info is None or not hasattr(circuit_info, "corners") or circuit_info.corners is None or circuit_info.corners.empty:
                st.warning("Track layout or corner data is not available for this session.")
            else:
                corners_df = circuit_info.corners.copy()
                corners_df["Number_str"] = corners_df["Number"].astype(str)
                corner_list = corners_df["Number_str"].tolist()
                
                sel_col, _ = st.columns([2, 3])
                with sel_col:
                    selected_corner = st.selectbox(
                        "Select Corner",
                        corner_list,
                        key=f"corner_sel_{key_suffix}",
                    )

                corner_row = corners_df[corners_df["Number_str"] == selected_corner].iloc[0]
                apex_dist = corner_row["Distance"]
                corner_letter = corner_row.get("Letter", "")
                corner_label = f"Turn {selected_corner}{corner_letter}" if pd.notna(corner_letter) and corner_letter else f"Turn {selected_corner}"

                tel1 = _get_telemetry_for_map(lap, driver, sess_k)
                tel2 = None
                if other_driver and other_lap is not None:
                    tel2 = _get_telemetry_for_map(other_lap, other_driver, sess_k)

                has_tel1 = tel1 is not None and not tel1.empty and {"X", "Y", "Distance", "Speed"}.issubset(tel1.columns)
                
                if not has_tel1:
                    st.warning(f"Telemetry data is not available for {fmt_func(driver) if fmt_func else driver} to perform corner analysis.")
                else:
                    WINDOW_BEFORE = 200
                    WINDOW_AFTER = 100
                    
                    win1 = tel1[(tel1["Distance"] >= apex_dist - WINDOW_BEFORE) & (tel1["Distance"] <= apex_dist + WINDOW_AFTER)]
                    win2 = None
                    if tel2 is not None and not tel2.empty and {"X", "Y", "Distance", "Speed"}.issubset(tel2.columns):
                        win2 = tel2[(tel2["Distance"] >= apex_dist - WINDOW_BEFORE) & (tel2["Distance"] <= apex_dist + WINDOW_AFTER)]

                    def compute_stats(df):
                        if df is None or df.empty:
                            return None
                        
                        apex_speed = df["Speed"].min()
                        apex_rows = df[df["Speed"] == apex_speed]
                        if apex_rows.empty:
                            return None
                        
                        apex_row_data = apex_rows.iloc[0]
                        apex_d = apex_row_data["Distance"]
                        apex_x = apex_row_data["X"]
                        apex_y = apex_row_data["Y"]
                        
                        braking_d = None
                        braking_x = None
                        braking_y = None
                        
                        pre_apex_df = df[df["Distance"] <= apex_d]
                        
                        if "Brake" in df.columns and (pre_apex_df["Brake"] > 0).any():
                            brk_row = pre_apex_df[pre_apex_df["Brake"] > 0].iloc[0]
                            braking_d = brk_row["Distance"]
                            braking_x = brk_row["X"]
                            braking_y = brk_row["Y"]
                        else:
                            if len(pre_apex_df) > 1:
                                ds = pre_apex_df["Speed"].diff()
                                decel_mask = ds < -1
                                if decel_mask.any():
                                    brk_row = pre_apex_df[decel_mask].iloc[0]
                                    braking_d = brk_row["Distance"]
                                    braking_x = brk_row["X"]
                                    braking_y = brk_row["Y"]
                        
                        dist_to_apex = None
                        if braking_d is not None:
                            dist_to_apex = apex_d - braking_d
                            
                        return {
                            "apex_speed": apex_speed,
                            "apex_dist": apex_d,
                            "apex_x": apex_x,
                            "apex_y": apex_y,
                            "braking_dist": braking_d,
                            "braking_x": braking_x,
                            "braking_y": braking_y,
                            "dist_to_apex": dist_to_apex
                        }

                    stats1 = compute_stats(win1)
                    stats2 = compute_stats(win2) if win2 is not None else None

                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(
                            f"<div style='border-left: 4px solid {colour}; padding-left: 12px; margin-bottom: 16px;'>"
                            f"<div style='font-size: 13px; opacity: 0.7;'>Driver 1</div>"
                            f"<div style='font-size: 18px; font-weight: bold; color: {colour};'>{fmt_func(driver) if fmt_func else driver}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        if stats1:
                            m1, m2 = st.columns(2)
                            m1.metric("Apex Speed", f"{stats1['apex_speed']:.0f} km/h")
                            if stats1['dist_to_apex'] is not None:
                                m2.metric("Braking Distance", f"{stats1['dist_to_apex']:.0f} m before apex")
                            else:
                                m2.metric("Braking Distance", "No braking detected")
                        else:
                            st.caption("No corner telemetry available.")
                            
                    with col2:
                        if other_driver and other_lap is not None:
                            st.markdown(
                                f"<div style='border-left: 4px solid {other_colour}; padding-left: 12px; margin-bottom: 16px;'>"
                                f"<div style='font-size: 13px; opacity: 0.7;'>Driver 2</div>"
                                f"<div style='font-size: 18px; font-weight: bold; color: {other_colour};'>{fmt_func(other_driver) if fmt_func else other_driver}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if stats2:
                                m1, m2 = st.columns(2)
                                m1.metric("Apex Speed", f"{stats2['apex_speed']:.0f} km/h")
                                if stats2['dist_to_apex'] is not None:
                                    m2.metric("Braking Distance", f"{stats2['dist_to_apex']:.0f} m before apex")
                                else:
                                    m2.metric("Braking Distance", "No braking detected")
                            else:
                                st.caption("No corner telemetry available.")

                    from plotly.subplots import make_subplots
                    fig = make_subplots(
                        rows=2, cols=1,
                        shared_xaxes=False,
                        vertical_spacing=0.15,
                        subplot_titles=(f"Racing Line Overlay ({corner_label})", "Speed Profile (km/h vs Distance)")
                    )

                    fig.add_trace(go.Scatter(
                        x=win1["X"], y=win1["Y"],
                        mode="lines",
                        line=dict(color=colour, width=4),
                        name=driver,
                        legendgroup=driver,
                        hovertemplate=f"<b>{driver}</b><br>X: %{{x:.0f}}<br>Y: %{{y:.0f}}<extra></extra>"
                    ), row=1, col=1)

                    if win2 is not None:
                        fig.add_trace(go.Scatter(
                            x=win2["X"], y=win2["Y"],
                            mode="lines",
                            line=dict(color=other_colour, width=4),
                            name=other_driver,
                            legendgroup=other_driver,
                            hovertemplate=f"<b>{other_driver}</b><br>X: %{{x:.0f}}<br>Y: %{{y:.0f}}<extra></extra>"
                        ), row=1, col=1)

                    if stats1:
                        fig.add_trace(go.Scatter(
                            x=[stats1["apex_x"]], y=[stats1["apex_y"]],
                            mode="markers",
                            marker=dict(symbol="star", size=12, color=colour, line=dict(color="white", width=1)),
                            name=f"{driver} Apex",
                            legendgroup=driver,
                            hovertemplate=f"<b>{driver} Apex</b><br>Speed: {stats1['apex_speed']:.0f} km/h<extra></extra>",
                            showlegend=False
                        ), row=1, col=1)
                    if stats2:
                        fig.add_trace(go.Scatter(
                            x=[stats2["apex_x"]], y=[stats2["apex_y"]],
                            mode="markers",
                            marker=dict(symbol="star", size=12, color=other_colour, line=dict(color="white", width=1)),
                            name=f"{other_driver} Apex",
                            legendgroup=other_driver,
                            hovertemplate=f"<b>{other_driver} Apex</b><br>Speed: {stats2['apex_speed']:.0f} km/h<extra></extra>",
                            showlegend=False
                        ), row=1, col=1)

                    if stats1 and stats1["braking_x"] is not None:
                        fig.add_trace(go.Scatter(
                            x=[stats1["braking_x"]], y=[stats1["braking_y"]],
                            mode="markers",
                            marker=dict(symbol="x", size=10, color=colour, line=dict(color="white", width=1)),
                            name=f"{driver} Braking Point",
                            legendgroup=driver,
                            hovertemplate=f"<b>{driver} Braking</b><br>Dist to Apex: {stats1['dist_to_apex']:.0f} m<extra></extra>",
                            showlegend=False
                        ), row=1, col=1)
                    if stats2 and stats2["braking_x"] is not None:
                        fig.add_trace(go.Scatter(
                            x=[stats2["braking_x"]], y=[stats2["braking_y"]],
                            mode="markers",
                            marker=dict(symbol="x", size=10, color=other_colour, line=dict(color="white", width=1)),
                            name=f"{other_driver} Braking Point",
                            legendgroup=other_driver,
                            hovertemplate=f"<b>{other_driver} Braking</b><br>Dist to Apex: {stats2['dist_to_apex']:.0f} m<extra></extra>",
                            showlegend=False
                        ), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=win1["Distance"] - apex_dist, y=win1["Speed"],
                        mode="lines",
                        line=dict(color=colour, width=3),
                        name=driver,
                        legendgroup=driver,
                        showlegend=False,
                        hovertemplate=f"<b>{driver}</b><br>Dist: %{{x:.1f}} m from apex<br>Speed: %{{y:.0f}} km/h<extra></extra>"
                    ), row=2, col=1)

                    if win2 is not None:
                        fig.add_trace(go.Scatter(
                            x=win2["Distance"] - apex_dist, y=win2["Speed"],
                            mode="lines",
                            line=dict(color=other_colour, width=3),
                            name=other_driver,
                            legendgroup=other_driver,
                            showlegend=False,
                            hovertemplate=f"<b>{other_driver}</b><br>Dist: %{{x:.1f}} m from apex<br>Speed: %{{y:.0f}} km/h<extra></extra>"
                        ), row=2, col=1)

                    fig.update_xaxes(title_text="Distance relative to apex (m)", row=2, col=1)
                    fig.update_yaxes(title_text="Speed (km/h)", row=2, col=1)
                    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1, row=1, col=1)
                    fig.update_yaxes(visible=False, row=1, col=1)

                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=640,
                        margin=dict(l=0, r=40, t=40, b=10),
                        showlegend=True,
                    )
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Load a session and select a lap to view corner analysis.")

if sess2 is not None:
    session_map_tabs = st.tabs([f"Session 1 ({year1})", f"Session 2 ({year2})"])
    with session_map_tabs[0]:
        render_maps_block(sess, sess_key, driver1, colour1, lap1, "sess1", fmt_func=_fmt_driver1)
    with session_map_tabs[1]:
        render_maps_block(sess2, sess_key2, driver2, colour2, lap2, "sess2", fmt_func=_fmt_driver2)
else:
    render_maps_block(sess, sess_key, driver1, colour1, lap1, "single",
                      other_driver=(driver2 if compare else None),
                      other_colour=(colour2 if compare else None),
                      other_lap=(lap2 if compare else None),
                      fmt_func=_fmt_driver1)


# ── Championship Standings & Classification ───────────────────────────────────
st.markdown("<hr style='margin:24px 0 16px; border-style: solid; opacity:0.15;'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Championship Standings & Classification</div>", unsafe_allow_html=True)


def _get_round(session):
    try:
        ev = session.event
        if ev is not None and "RoundNumber" in ev:
            val = ev["RoundNumber"]
            if pd.notna(val):
                return int(val)
    except Exception:
        pass
    return None


if sess2 is not None:
    tab_cls1, tab_cls2 = st.tabs([f"Session 1 Standings & Results ({year1})", f"Session 2 Standings & Results ({year2})"])
    with tab_cls1:
        # Session 1 Constructors Standings
        r1 = _get_round(sess)
        standings1 = _build_constructor_standings(year1, r1)
        team1 = sess.get_driver(driver1).get("TeamName", "") if driver1 else ""
        st.markdown("<div style='font-size: 15px; font-weight: 700; margin-bottom: 8px; opacity: 0.85;'>🏆 Constructors' Championship Standings</div>", unsafe_allow_html=True)
        _render_constructor_standings(standings1, [team1], [colour1])
        
        # Session 1 Classification
        st.markdown("<div style='font-size: 15px; font-weight: 700; margin-top: 18px; margin-bottom: 8px; opacity: 0.85;'>🏁 Official Session Classification</div>", unsafe_allow_html=True)
        _cls1 = _build_final_classification(sess_key, sess.results)
        standings_d1 = _build_driver_standings(year1, r1)
        _render_final_classification(_cls1, [driver1], [colour1], _fmt_driver1, standings_d1, laps_df=_all_laps1)
        
    with tab_cls2:
        # Session 2 Constructors Standings
        r2 = _get_round(sess2)
        standings2 = _build_constructor_standings(year2, r2)
        team2 = sess2.get_driver(driver2).get("TeamName", "") if driver2 else ""
        st.markdown("<div style='font-size: 15px; font-weight: 700; margin-bottom: 8px; opacity: 0.85;'>🏆 Constructors' Championship Standings</div>", unsafe_allow_html=True)
        _render_constructor_standings(standings2, [team2], [colour2])
        
        # Session 2 Classification
        st.markdown("<div style='font-size: 15px; font-weight: 700; margin-top: 18px; margin-bottom: 8px; opacity: 0.85;'>🏁 Official Session Classification</div>", unsafe_allow_html=True)
        _cls2 = _build_final_classification(sess_key2, sess2.results)
        standings_d2 = _build_driver_standings(year2, r2)
        _render_final_classification(_cls2, [driver2], [colour2], _fmt_driver2, standings_d2, laps_df=_all_laps2)
else:
    # Single Session constructors standings
    r = _get_round(sess)
    standings = _build_constructor_standings(year, r)
    team1 = sess.get_driver(driver1).get("TeamName", "") if driver1 else ""
    team2 = (sess.get_driver(driver2).get("TeamName", "") if (compare and driver2) else "")
    _hl_teams = [team1] + ([team2] if team2 else [])
    _hl_colours = [colour1] + ([colour2] if compare and driver2 else [])
    
    st.markdown("<div style='font-size: 15px; font-weight: 700; margin-bottom: 8px; opacity: 0.85;'>🏆 Constructors' Championship Standings</div>", unsafe_allow_html=True)
    _render_constructor_standings(standings, _hl_teams, _hl_colours)
    
    # Single Session classification
    st.markdown("<div style='font-size: 15px; font-weight: 700; margin-top: 18px; margin-bottom: 8px; opacity: 0.85;'>🏁 Official Session Classification</div>", unsafe_allow_html=True)
    _cls = _build_final_classification(sess_key, sess.results)
    _hl_drivers = [driver1] + ([driver2] if compare and driver2 else [])
    _hl_colours = [colour1] + ([colour2] if compare and driver2 else [])
    standings_d = _build_driver_standings(year, r)
    _render_final_classification(_cls, _hl_drivers, _hl_colours, _fmt_driver1, standings_d, laps_df=_all_laps1)


_render_footer()


