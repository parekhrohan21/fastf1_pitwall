import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import matplotlib
import matplotlib.pyplot as plt

# Streamlit Page Config MUST be run first before any other Streamlit widgets!
st.set_page_config(
    page_title="Pitwall · F1 Live Telemetry & Insights",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modular imports
from src.ui.styles import inject_styles, _toggle_theme, TEAM_COLOURS, COMPOUND_COLOURS, TRACK_STATUS_MAP, MATPLOTLIB_THEME
from src.data.loader import (
    load_schedule, load_session, clear_session_cache, format_laptime, driver_colour, hex_to_rgb,
    _build_driver_labels, get_telemetry_cached, _format_classification_time,
    _map_driver_id_to_number, _get_session_winner, _get_default_gp_index,
    get_constructor_colour, is_same_team, _build_constructor_standings,
    get_driver_standings_points, _build_driver_standings, _build_final_classification,
    _make_fmt_driver, _build_lap_history, _build_fuel_adjusted,
    _build_fuel_sim_leaderboard, _build_stints, _build_pit_stops, _build_tyre_deg_data,
    _build_fuel_decoupled_tyre_deg,
    _build_leaderboard, _build_ideal_lap, _build_gap_data, _build_position_data,
    _get_telemetry_for_map, _get_round, start_live_recorder, stop_live_recorder,
    get_live_recorder_status, load_live_session, _PATCH_STATUS, test_curl_cffi_request,
    _build_race_control_messages, _build_export_csv, _build_export_parquet, _build_export_json,
    _build_teammate_battle_data, _build_pit_transit_data
)
from src.ui.components import (
    _render_constructor_standings, _render_final_classification, _render_footer,
    _session_info_header, lap_selector, tyre_badge_html, weather_strip_html,
    render_summary, render_session_stats, _render_fuel_sim_leaderboard,
    _render_pit_table, _render_leaderboard, _render_ideal_lap_section,
    _render_gap_to_leader_section, _render_position_section, render_maps_block,
    render_live_status_banner, _render_grid_heatmap_section, render_export_section,
    render_telemetry_export_panel, _render_consistency_section, _render_weather_correlation_section,
    _render_track_evolution_section,
    _render_multi_year_comparison_section, render_tyre_crossover_matrix, render_fuel_decoupled_deg_metrics,
    _render_braking_analysis_section, _render_gear_analysis_section,
    _render_speed_trap_section, _render_teammate_battle_section,
    _render_pit_loss_section
)
from src.charts.plotly import (
    _lap_history_fig, _fuel_pace_fig, _stint_fig, _gap_chart_fig,
    build_tyre_deg_fig, build_undercut_chart, _add_flag_zones
)
from src.charts.matplotlib import style_ax, build_chart, build_delta_chart, build_time_delta_chart, AVAILABLE_CHANNELS

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

# ── Race Control Messages ──────────────────────────────────────────────────────
_rc_messages = _build_race_control_messages(sess_key, sess)

# ── Driver name labels (built once per session) ───────────────────────────────
_drv_labels1: dict = _build_driver_labels(sess)
_drv_labels2: dict = _build_driver_labels(sess2) if sess2 is not None else None

# Build closures that capture the labels dicts — avoids NameError from loader.py globals
_fmt_driver1 = _make_fmt_driver(_drv_labels1)
_fmt_driver2 = _make_fmt_driver(_drv_labels2 or _drv_labels1, fallback=_drv_labels1)

# ── Export Figures Collection ──────────────────────────────────────────────────
_export_figs = {}









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

    _lap_hist_fig_obj = _lap_history_fig(_hist_pairs_filtered, _hist_laps, rc_messages=_rc_messages)
    _export_figs["Lap Time History"] = _lap_hist_fig_obj
    st.plotly_chart(_lap_hist_fig_obj, width="stretch", config={"displayModeBar": False})

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




_stint_data = [(label1, _build_stints(driver1, sess_key, _all_laps1))]
if compare and driver2:
    _stint_data.append((label2, _build_stints(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1)))

if all(not s for _, s in _stint_data):
    st.info("Stint data not available for this session.")
else:
    _stint_fig_obj = _stint_fig(_stint_data)
    _export_figs["Tyre Stints"] = _stint_fig_obj
    st.plotly_chart(_stint_fig_obj, width="stretch", config={"displayModeBar": False})




# ── Pit Stop Summary ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Pit Stop Summary</div>", unsafe_allow_html=True)




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


# ── Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown ───────────
try:
    _transit_laps = sess.laps if hasattr(sess, "laps") and sess.laps is not None else _all_laps1
    _transit_data = _build_pit_transit_data(sess_key, _transit_laps, sess_obj=sess, driver=driver1)
    if _transit_data and _transit_data.get("has_data") and _transit_data.get("all_stops"):
        _render_pit_loss_section(
            _transit_data,
            driver1=driver1,
            driver2=driver2 if compare else None,
            compare=compare,
            colour1=colour1,
            colour2=colour2,
            label1=label1,
            label2=label2,
        )
except Exception:
    pass


# ── Tyre Degradation Analysis ──────────────────────────────────────────────────
st.markdown("<div class='section-title'>Tyre Degradation Analysis</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:11px; opacity:0.55; margin:-6px 0 10px; letter-spacing:0.3px;'>"
    "Analyses tyre wear and pace drop-off by performing linear regression (OLS) and quadratic thermal modeling on valid flyer laps. "
    "Out-laps, in-laps, and laps under Safety Car / VSC are excluded. "
    "Fuel decoupling removes artificial lap time gains from fuel mass burn (~0.3 kg/lap) to reveal true mechanical tyre degradation."
    "</div>",
    unsafe_allow_html=True,
)

# Fuel Decoupler Controls
col_fuel1, col_fuel2 = st.columns([1.8, 2.2])
with col_fuel1:
    decouple_fuel = st.toggle(
        "⛽ Decouple Fuel Burn (True Tyre Wear)",
        value=True,
        help="Removes fuel burn mass gain (~0.035 s/lap) so tyre degradation rates reflect true mechanical wear rather than being masked by car weight loss."
    )
with col_fuel2:
    if decouple_fuel:
        fuel_burn_rate = st.slider(
            "Fuel Burn Sensitivity (s/lap)",
            min_value=0.010,
            max_value=0.070,
            value=0.035,
            step=0.005,
            format="%.3f s/lap",
            help="Customizable pace gain per lap from burning race fuel. Standard Grand Prix average is ~0.035 s/lap."
        )
    else:
        fuel_burn_rate = 0.0

if decouple_fuel:
    _deg_d1 = _build_fuel_decoupled_tyre_deg(driver1, _all_laps1, fuel_effect=fuel_burn_rate)
    _deg_d2 = _build_fuel_decoupled_tyre_deg(driver2, _all_laps2 if _all_laps2 is not None else _all_laps1, fuel_effect=fuel_burn_rate) if compare and driver2 else None
else:
    _deg_d1 = _build_tyre_deg_data(driver1, _all_laps1)
    _deg_d2 = _build_tyre_deg_data(driver2, _all_laps2 if _all_laps2 is not None else _all_laps1) if compare and driver2 else None

if not _deg_d1 and not _deg_d2:
    st.info("Insufficient stint telemetry (minimum 4 consecutive green-flag laps per stint) to model tyre degradation.")
else:
    fig_deg, table_rows = build_tyre_deg_fig(
        _deg_d1, _deg_d2, driver1, driver2, colour1, colour2, compare,
        show_fuel_corrected=decouple_fuel
    )

    if decouple_fuel:
        render_fuel_decoupled_deg_metrics(
            table_rows=table_rows,
            fuel_effect=fuel_burn_rate,
            driver1=driver1,
            driver2=driver2 if compare else None,
            fmt_driver1=_fmt_driver1,
            fmt_driver2=_fmt_driver2,
            colour1=colour1,
            colour2=colour2,
        )

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

        deg_color = "#00e400" if row["deg_rate"] <= 0 else "#ff2200"
        if decouple_fuel and row.get("is_fuel_decoupled"):
            deg_rate_str = (
                f"<span style='color:{deg_color}; font-weight:600;'>{row['deg_rate']:+.3f} s/lap</span> "
                f"<span style='font-size:11px; opacity:0.6;'>(Raw: {row.get('raw_deg_rate', row['deg_rate']):+.3f})</span>"
            )
        else:
            deg_rate_str = f"<span style='color:{deg_color}; font-weight:600;'>{row['deg_rate']:+.3f} s/lap</span>"

        fmt_name = _fmt_driver1(row["driver"]) if row["driver"] == driver1 else _fmt_driver2(row["driver"])

        table_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:7px 10px; font-weight:600; color:{row['colour']};'>{fmt_name}</td>"
            f"<td style='padding:7px 10px;'>Stint {row['stint']}</td>"
            f"<td style='padding:7px 10px;'>{comp_dot}{comp}</td>"
            f"<td style='padding:7px 10px;'>{row['laps']} laps</td>"
            f"<td style='padding:7px 10px;'>{deg_rate_str}</td>"
            f"</tr>"
        )

    rate_col_header = "Degradation Rate (True vs Raw)" if decouple_fuel else "Degradation Rate"
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
        f"<th style='padding:5px 10px; text-align:left;'>{rate_col_header}</th>"
        f"</tr></thead>"
        f"<tbody>{table_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True
    )

    # ── Tyre Life & Crossover Prediction Matrix ──────────────────────────────
    render_tyre_crossover_matrix(
        table_rows=table_rows,
        fmt_driver1=_fmt_driver1,
        fmt_driver2=_fmt_driver2,
        driver1=driver1,
        driver2=driver2 if compare else None,
        colour1=colour1,
        colour2=colour2,
    )

# ── Driver Consistency & Stint Pace Distribution ───────────────────────────
st.markdown("<div class='section-title'>Driver Consistency & Stint Pace Distribution</div>", unsafe_allow_html=True)
_hl_drivers = [driver1] + ([driver2] if compare and driver2 else [])
_hl_colours = [colour1] + ([colour2] if compare and driver2 else [])
_render_consistency_section(_all_laps1, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Track Temperature & Weather Impact Correlation ─────────────────────────
_render_weather_correlation_section(sess_key, _all_laps1, sess, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Track Evolution & Grip Improvement Ramp (Practice / Qualifying only) ───
_render_track_evolution_section(
    sess_key, _all_laps1, sess, session_type, _hl_drivers, _hl_colours, _fmt_driver1
)

# ── Braking Efficiency & Trail-Braking Zone Analysis ───────────────────────
st.markdown("<div class='section-title'>Braking Efficiency & Trail-Braking Zone Analysis</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_braking_analysis_section(
        sess_key, sess, lap1, lap2, driver1, driver2, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Gear Shift Strategy & RPM Power Band Optimization ──────────────────────
st.markdown("<div class='section-title'>Gear Shift Strategy & RPM Power Band Optimization</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_gear_analysis_section(
        sess_key, tel1, tel2 if (compare and driver2) else None,
        driver1, driver2, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )



# ── Multi-Year Historical Lap Comparison ─────────────────────────────────
if compare and tel1 is not None and tel2 is not None:
    _era_label1 = f"{year1} {_fmt_driver1(driver1)}"
    _era_label2 = f"{year2} {_fmt_driver2(driver2)}"
    _lap1_sec = lap1["LapTime"].total_seconds() if lap1 is not None and hasattr(lap1, "LapTime") and pd.notna(lap1["LapTime"]) else None
    _lap2_sec = lap2["LapTime"].total_seconds() if lap2 is not None and hasattr(lap2, "LapTime") and pd.notna(lap2["LapTime"]) else None
    _render_multi_year_comparison_section(
        tel1, tel2,
        label1=_era_label1, label2=_era_label2,
        lap1_sec=_lap1_sec, lap2_sec=_lap2_sec,
        color1=colour1, color2=colour2
    )

st.markdown("<div class='section-title'>Telemetry</div>", unsafe_allow_html=True)

if tel1 is None:
    st.warning("No telemetry available for the selected lap.")
    _render_footer()
    st.stop()

# ── Telemetry Channel Filter ──────────────────────────────────────────────────
selected_channels = st.multiselect(
    "Telemetry Channels",
    options=AVAILABLE_CHANNELS,
    default=AVAILABLE_CHANNELS,
    help="Toggle and select which telemetry channels to display on the chart.",
)

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

    fig = build_chart(drv_list, title, selected_channels=selected_channels)
    if fig is not None:
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    else:
        st.info("Select at least one telemetry channel above to display the chart.")

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
            fig = build_chart([(drv_lbl, colour, tel)], title, fig_width=7, selected_channels=selected_channels)
            if fig is not None:
                st.pyplot(fig, width="stretch")
                plt.close(fig)
            else:
                st.info("Select at least one telemetry channel to display.")



# ── Export Telemetry ──────────────────────────────────────────────────────────
render_telemetry_export_panel(
    driver1,
    tel1,
    lap1,
    driver2=driver2 if compare else None,
    tel2=tel2 if compare else None,
    lap2=lap2 if compare else None,
    compare=compare,
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

# ── Speed Trap & Intermediate Velocity Radar Breakdown ─────────────────────
st.markdown("<div class='section-title'>Speed Trap & Intermediate Velocity Radar Breakdown</div>", unsafe_allow_html=True)
_render_speed_trap_section(
    sess_key, _all_laps1, driver1, driver2 if compare else None,
    colour1, colour2 if compare else None, compare,
    fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
)

# ── Ideal Lap vs Actual Lap ───────────────────────────────────────────────────
st.markdown("<div class='section-title'>Ideal Lap vs Actual Lap</div>", unsafe_allow_html=True)




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

# ── Intra-Team Teammate Battle & Qualifying Delta Matrix ───────────────────
st.markdown("<div class='section-title'>Intra-Team Teammate Battle & Qualifying Delta Matrix</div>", unsafe_allow_html=True)
if sess2 is not None:
    tab_tb1, tab_tb2 = st.tabs([f"Session 1 Teammate Battles ({year1})", f"Session 2 Teammate Battles ({year2})"])
    with tab_tb1:
        _render_teammate_battle_section(
            sess_key, _all_laps1, _sess_obj=sess,
            highlight_driver1=driver1, highlight_driver2=driver2 if compare else None,
            colour1=colour1, colour2=colour2 if compare else None,
            compare=compare, fmt_func=_fmt_driver1
        )
    with tab_tb2:
        _render_teammate_battle_section(
            sess_key2, _all_laps2, _sess_obj=sess2,
            highlight_driver1=driver2, highlight_driver2=None,
            colour1=colour2, colour2=None,
            compare=False, fmt_func=_fmt_driver2
        )
else:
    _render_teammate_battle_section(
        sess_key, _all_laps1, _sess_obj=sess,
        highlight_driver1=driver1, highlight_driver2=driver2 if compare else None,
        colour1=colour1, colour2=colour2 if compare else None,
        compare=compare, fmt_func=_fmt_driver1
    )



# ── Multi-Driver Grid Analysis & Heatmaps ───────────────────────────────────────
st.markdown("<div class='section-title'>Multi-Driver Grid Analysis & Heatmaps</div>", unsafe_allow_html=True)
_render_grid_heatmap_section(sess, _all_laps1, all_drivers1, sess_key, fmt_func=_fmt_driver1)



# ── Gap to Leader ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Gap to Leader</div>", unsafe_allow_html=True)

if sess2 is not None:
    tab_g1, tab_g2 = st.tabs([f"Session 1 ({year1})", f"Session 2 ({year2})"])
    with tab_g1:
        _gtl_fig = _render_gap_to_leader_section(sess_key, _all_laps1, sess, [driver1], [colour1], _fmt_driver1, rc_messages=_rc_messages)
        if _gtl_fig:
            _export_figs["Gap to Leader"] = _gtl_fig
    with tab_g2:
        _render_gap_to_leader_section(sess_key2, _all_laps2, sess2, [driver2], [colour2], _fmt_driver2)
else:
    _gtl_fig = _render_gap_to_leader_section(sess_key, _all_laps1, sess,
                                  [driver1] + ([driver2] if compare and driver2 else []),
                                  [colour1] + ([colour2] if compare and driver2 else []), _fmt_driver1,
                                  rc_messages=_rc_messages)
    if _gtl_fig:
        _export_figs["Gap to Leader"] = _gtl_fig

# ── Race Control Feed ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Race Control Feed</div>", unsafe_allow_html=True)

if _rc_messages is None or _rc_messages.empty:
    st.info("Race control messages are not available for this session.")
else:
    # Flag type colour badge map
    _FLAG_BADGE = {
        "SAFETY CAR":         ("🟠", "#FF8C00"),
        "VIRTUAL SAFETY CAR": ("🟡", "#FFD700"),
        "RED FLAG":           ("🔴", "#DC0000"),
        "YELLOW FLAG":        ("🟡", "#FFC800"),
        "CLEAR":              ("🟢", "#39B54A"),
        "INVESTIGATION":      ("🔵", "#5B8DEF"),
        "INFO":               ("⚪", "#888888"),
    }
    # Searchable filter
    _rc_filter_options = ["All"] + sorted(_rc_messages["FlagType"].unique().tolist())
    _rc_filter = st.selectbox("Filter by event type", _rc_filter_options, key="rc_filter")
    _rc_display = _rc_messages if _rc_filter == "All" else _rc_messages[_rc_messages["FlagType"] == _rc_filter]

    # Build display columns
    _rc_cols = [c for c in ["LapNumber", "FlagType", "Message", "Category", "Scope", "Sector"] if c in _rc_display.columns]
    _rc_df = _rc_display[_rc_cols].copy()
    if "LapNumber" in _rc_df.columns:
        _rc_df["LapNumber"] = _rc_df["LapNumber"].apply(lambda x: f"Lap {int(x)}" if pd.notna(x) else "—")
    if "FlagType" in _rc_df.columns:
        _rc_df["FlagType"] = _rc_df["FlagType"].apply(
            lambda ft: f"{_FLAG_BADGE.get(ft, ('⚪', '#888888'))[0]} {ft}"
        )
    st.dataframe(
        _rc_df,
        width="stretch",
        hide_index=True,
    )


# ── Race Position Chart ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Race Position</div>", unsafe_allow_html=True)

if sess2 is not None:
    tab_p1, tab_p2 = st.tabs([f"Session 1 ({year1})", f"Session 2 ({year2})"])
    with tab_p1:
        _pos_fig = _render_position_section(sess_key, _all_laps1, [driver1], [colour1], _fmt_driver1)
        if _pos_fig:
            _export_figs["Position History"] = _pos_fig
    with tab_p2:
        _render_position_section(sess_key2, _all_laps2, [driver2], [colour2], _fmt_driver2)
else:
    _pos_fig = _render_position_section(sess_key, _all_laps1,
                             [driver1] + ([driver2] if compare and driver2 else []),
                             [colour1] + ([colour2] if compare and driver2 else []), _fmt_driver1)
    if _pos_fig:
        _export_figs["Position History"] = _pos_fig

# ── Track Map ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Track Map</div>", unsafe_allow_html=True)


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

with st.sidebar:
    if not live_mode and "driver1" in locals() and "driver2" in locals():
        render_export_section(f"{year} {gp} {session_label}", driver1, driver2 if compare else None, _export_figs)

_render_footer()


