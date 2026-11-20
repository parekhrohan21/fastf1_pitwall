"""Pit Wall — F1 Telemetry Dashboard: Streamlit entry point.

Architecture
------------
This file is orchestration only: it owns the widget layout and the order in
which sections render. All computation lives in the ``src/`` package:

- ``src/data/loader.py``       FastF1 loading, ``@st.cache_data`` builders
                               (``_build_*``), live timing, proxy patch
- ``src/charts/plotly.py``     interactive Plotly figure builders
- ``src/charts/matplotlib.py`` static telemetry figures (channels, deltas)
- ``src/ui/styles.py``         CSS design system, team/compound colours, theme
- ``src/ui/components.py``     self-contained section renderers (``_render_*``)

Execution model
---------------
Streamlit re-runs this script top to bottom on every widget interaction; there
are no callbacks driving the page. Two mechanisms make that affordable:

- ``st.session_state`` holds the loaded FastF1 session(s) and their cache keys,
  so a session survives reruns and is only fetched when Load is pressed.
- ``@st.cache_data`` builders in the loader are keyed on ``sess_key``
  (``"{year}_{gp}_{session}"``) plus plain-DataFrame lap snapshots, so each
  section's data is computed once per session.

Render flow
-----------
 1. Page config & imports   ``set_page_config`` must be the first Streamlit call.
 2. Sidebar                 season / GP / session pickers, optional Session 2,
                            theme toggle, live timing controls, Load button.
 3. Session state & loading fetch on Load; on failure clear cache and stop.
 4. Landing                 nothing loaded yet: show landing page and stop.
 5. Per-session prep        driver lists, lap snapshots, race control, labels.
 6. Driver & lap selection  Driver 1/2, lap pickers, chart view mode.
 7. Telemetry fetch         car data for the selected laps.
 8. Driver analysis         summaries, pace, tyres, pit stops, consistency,
                            weather, track evolution, braking, gears, eras.
 9. Telemetry charts        channel filter, overlapping/separate, export, deltas.
                            The run stops before this if the lap has no telemetry.
10. Field-wide analysis     leaderboards, speed traps, weekend progression (#156),
                            ideal lap, teammates, heatmaps, gap, race control, positions, map, standings.
11. PDF export & footer     sidebar debrief export of figures collected above.

Review notes (#177)
-------------------
Merged from the former code_review_issue_177.md. The 46 section notes in this file were
written after reading the code they describe, and the change was comment-only: the AST of
this module was identical to ``main`` apart from the docstring. Streamlit "magic" can render
a bare top-level string, so ``AppTest`` was used to confirm this docstring never appears on
the page and ``set_page_config`` still runs first.

Four defects were found while reading every section. None was introduced by #177; all four
have since been fixed in later work:

1. ``lap1`` / ``lap2`` were overwritten by the undercut simulator's pairing loop (integer lap
   numbers replacing the selected lap objects, breaking six downstream sections). The loop now
   uses ``_u_lap1`` / ``_u_lap2``.
2. The Pit Lane Transit Loss section never rendered: ``_build_pit_transit_data`` received raw
   ``fastf1.core.Laps`` and an un-prefixed session (``UnhashableParamError``) while a bare
   ``except Exception: pass`` hid it. It now receives ``_all_laps1`` and ``_sess_obj`` (#189).
3. The undercut gap read ``_all_laps1[LapNumber == w_start]["Time"].iloc[0]`` with no driver
   filter. It now reads from the per-driver frames ``_laps_driver1`` / ``_laps_driver2``.
4. ``dark_mode`` was initialised only at module import time, which runs once per Python
   process rather than once per browser session; ``inject_styles()`` and ``_toggle_theme()``
   now also guard it on every run.

Comparison modes
----------------
- Driver compare: two drivers from one session. ``sess2`` is ``None``.
- Session compare: Session 2 is loaded alongside Session 1 (any year, GP or
  session), and ``compare`` is forced on with Driver 2 taken from Session 2.

Session-2 inputs fall back to Session 1 (``_all_laps2 if _all_laps2 is not None
else _all_laps1``), so both modes share one code path. Field-wide sections
render one tab per session in session-compare mode.
"""
import streamlit as st              # web UI framework: every widget, chart and layout call
import pandas as pd                 # tables of laps, results and telemetry
import numpy as np                  # numeric helpers used by a few inline calculations
import plotly.graph_objects as go   # interactive charts (most figures are built in src/charts/plotly.py)
# CHANGE (#203): Defer importing matplotlib and src.charts.matplotlib until the
# Telemetry Charts section so cold-start / landing renders skip font-cache & mpl setup.

# Streamlit Page Config MUST be run first before any other Streamlit widgets!
# It sets the browser tab title and icon, uses the full screen width, and opens
# the sidebar by default.
st.set_page_config(
    page_title="Pitwall · F1 Live Telemetry & Insights",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modular imports. app.py only arranges the page; the real work is imported:
#   styles      -> CSS theme, team and tyre colours
#   loader      -> downloading sessions and the cached data builders (_build_*)
#   components  -> ready-made page sections (_render_*)
#   plotly      -> chart builders used directly in this file
from src.ui.styles import inject_styles, _toggle_theme, TEAM_COLOURS, COMPOUND_COLOURS, TRACK_STATUS_MAP, MATPLOTLIB_THEME
from src.data.loader import (
    load_schedule, load_session, ensure_session_telemetry, clear_session_cache, livetiming_rejects_requests, f1_sign_in_error, format_laptime, driver_colour, hex_to_rgb,
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
    _render_braking_analysis_section, _render_traction_exit_section, _render_gear_analysis_section,
    _render_speed_trap_section, _render_teammate_battle_section,
    _render_pit_loss_section, _render_weekend_progression_section,
    _render_dirty_air_section, _render_brag_video_section, _render_strategy_simulator_section,
    _render_driving_style_dna_section, _render_corner_geometry_section,
    _render_microsector_section, _render_launch_analysis_section
)
from src.charts.plotly import (
    _lap_history_fig, _fuel_pace_fig, _stint_fig, _gap_chart_fig,
    _speed_map_fig, _input_map_fig, build_tyre_deg_fig, build_undercut_chart, _add_flag_zones
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
# Every user control lives here. Values are re-read on each rerun, but nothing
# is fetched until Load is pressed. Session names come from the event schedule
# (Session1–Session5), so sprint weekends list their real session formats.
# Inject design system & dark/light theme CSS early on every render.
# Orange (#FF8700) is the default accent until a driver is picked, after which
# inject_styles runs again with that driver's team colour.
inject_styles("#FF8700")

with st.sidebar:
    # "Back to rohanparekh.uk" link and the Pit Wall title block
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

    # Seasons 2026 down to 2018 (newest first); 2018 is the oldest season with
    # usable lap timing data.
    _years = list(range(2026, 2017, -1))
    year = st.selectbox("Season", _years, index=0, label_visibility="visible")

    # Download (or read from cache) that season's race calendar. Without it no
    # Grand Prix can be picked, so a failure stops the page here.
    with st.spinner("Loading calendar…"):
        try:
            schedule = load_schedule(year)
            gp_names = schedule["EventName"].tolist()
        except Exception as e:
            st.error(f"Could not load {year} schedule: {e}")
            _render_footer()
            st.stop()

    # Pre-select the most recent Grand Prix that has already happened
    _def_gp_idx = _get_default_gp_index(schedule, gp_names)
    gp = st.selectbox("Grand Prix", gp_names, index=_def_gp_idx)

    # Session names shown in the menu -> the short codes FastF1 expects
    _session_code_map = {
        "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
        "Qualifying": "Q", "Sprint Qualifying": "SQ", "Sprint Shootout": "SS",
        "Sprint": "S", "Race": "R"
    }

    # Determine dynamic sessions for primary session selection: read the event's
    # Session1..Session5 columns so sprint weekends list Sprint / Sprint
    # Qualifying instead of FP2 / FP3. A standard weekend is the fallback.
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

    # Default to the Race (or the last session of the weekend if there is none)
    _def_sess_idx = primary_sessions.index("Race") if "Race" in primary_sessions else len(primary_sessions) - 1
    session_label = st.selectbox("Session", primary_sessions, index=_def_sess_idx)
    session_type = _session_code_map.get(session_label, session_label)  # e.g. "Race" -> "R"

    # --- Session 2 Selector ---
    # Optional second session (any season / GP / session) for cross-session
    # comparison. The variables stay None when the box is unticked.
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

        # Default Session 2 to the same session type as Session 1 when it exists
        if session_label in secondary_sessions:
            _def_sess_idx2 = secondary_sessions.index(session_label)
        else:
            _def_sess_idx2 = secondary_sessions.index("Race") if "Race" in secondary_sessions else len(secondary_sessions) - 1

        session_label2 = st.selectbox("Session 2", secondary_sessions, index=_def_sess_idx2, key="session2")
        session_type2 = _session_code_map.get(session_label2, session_label2)

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    # Theme button: the label names the mode you would switch TO; clicking runs
    # _toggle_theme, which flips st.session_state["dark_mode"].
    mode_label = "☀️  Light Mode" if st.session_state.get("dark_mode", True) else "🌙  Dark Mode"
    st.button(mode_label, key="theme_toggle", on_click=_toggle_theme, use_container_width=True)

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    # Live timing mode: instead of downloading a finished session, read a file
    # that a background recorder fills with F1's live SignalR feed.
    live_mode = st.toggle("🔴 Real-Time Live Timing Mode", value=False, key="live_mode_toggle")

    live_filename = "live_timing.txt"   # where the recorder writes the live feed
    auto_refresh_sec = 0                # 0 = never auto-refresh the page

    if live_mode:
        with st.expander("📡 Live Streamer Controls", expanded=True):
            live_filename = st.text_input("Live Timing File", value="live_timing.txt", key="live_filename_input")
            # Start / Stop buttons control the background recorder process
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

            # How often the page reloads itself to pick up new live data
            auto_refresh_choice = st.selectbox("Auto-Refresh Rate", ["OFF", "5s", "10s", "15s", "30s"], index=0, key="auto_refresh_choice")
            if auto_refresh_choice != "OFF":
                auto_refresh_sec = int(auto_refresh_choice.replace("s", ""))

            # Recorder health: running or idle, packets received, file size
            live_status = get_live_recorder_status(live_filename)
            st.caption(f"Status: {'Active Stream' if live_status['active'] else 'Idle'} | Packets: {live_status['line_count']:,} | Size: {live_status['size_bytes']/1024:.1f} KB")

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    # Nothing is downloaded until this is clicked; load_btn is True only on the
    # rerun triggered by the click.
    load_btn = st.button("⬇️  Load Session(s)", use_container_width=True)

    # ── Diagnostics expander ──────────────────────────────────────────────────
    # Shows whether loader.py's curl_cffi HTTP patch imported and applied, plus
    # any recorded request failures — for debugging FastF1 downloads on hosts
    # that block the default HTTP client.
    with st.sidebar.expander("🛠️ Diagnostics & Debug Info", expanded=False):
        st.write(f"**Data Source:** {_PATCH_STATUS.get('last_data_source', 'Auto (OpenF1 / Jolpica / FastF1)')}")
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
            
        # Pings OpenF1, Jolpica-F1, MultiViewer and F1 live timing, and prints
        # each HTTP status so you can see which data source is reachable.
        if st.button("Run Connection Test"):
            with st.spinner("Testing connection..."):
                res = test_curl_cffi_request()
                st.code(res)

    # Data credits at the bottom of the sidebar
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10px; opacity:0.5; letter-spacing:0.5px; text-align:center;'>"
        "Data © OpenF1 / Jolpica-F1 / MultiViewer / FastF1<br>Educational use only"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
# Loaded sessions persist in st.session_state; the sidebar widgets only describe
# what *would* be loaded. On Load, live mode reads a recorded SignalR stream
# file, otherwise load_session() fetches via local cache, OpenF1 + MultiViewer
# + Jolpica-F1 (free, no sign-in required), or FastF1.
# A failed load clears incomplete cache entries so the next click is a clean retry,
# then st.stop() ends the run. Session 2 loads only in session-compare mode and never
# in live mode. sess / sess2 / sess_key / sess_key2 are then read back from
# state — they are the source of truth for everything below.
# First visit in this browser tab: create empty slots so the reads below never
# raise KeyError. They survive every later rerun.
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

# Cache keys such as "2026_British Grand Prix_R". Cached builders use them to
# tell sessions apart, so each session's results are computed once.
sess_key = f"{year}_{gp}_{session_type}"
sess_key2 = f"{year2}_{gp2}_{session_type2}" if compare_sessions else None

if load_btn:
    if live_mode:
        # Live mode: build a session from the recorded live-timing file. The key
        # is prefixed "LIVE_" so cached results never mix with a finished session.
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
        with st.spinner(f"Loading Session 1: {gp} {year} {session_label}…  (first load ~15–30 s)"):
            try:
                # load_session tries the local cache, then the free APIs (and F1
                # live timing if signed in); an empty lap table counts as a failure
                # CHANGE (#203): Load laps-first (load_telemetry=False); heavy car/pos
                # telemetry is fetched lazily by ensure_session_telemetry() below.
                sess = load_session(year, gp, session_type, load_telemetry=False)
                if not hasattr(sess, "laps") or sess.laps is None or sess.laps.empty:
                    raise ValueError("No lap data available for this session.")
                st.session_state["session"] = sess
                st.session_state["sess_key"] = sess_key
                st.session_state["year1"] = year
            except Exception as e:
                # Remove half-downloaded cache files and forget the session, so
                # the next click retries cleanly instead of reloading bad data.
                clear_session_cache(year, gp)
                st.session_state["session"] = None
                st.session_state["sess_key"] = None
                err_msg = str(e).rstrip(".") + "."
                # Network-wide failure (free APIs and F1 both down) gets its own
                # message; otherwise it is a problem with this session's data.
                if livetiming_rejects_requests():
                    st.error(
                        "**Upstream F1 data servers are unreachable**\n\n"
                        "Both the free OpenF1/Jolpica APIs and F1's live-timing server failed to respond. "
                        "Check your network connection and click **⬇️ Load Session(s)** to retry."
                    )
                else:
                    st.error(
                        f"**Session Loading Error**\n\n"
                        f"Could not load lap data for this session: {err_msg}\n\n"
                        "This session may not have taken place yet, or temporary rate limiting occurred. "
                        "Please try clicking **⬇️ Load Session(s)** again."
                    )
                _render_footer()
                st.stop()

    # Session 2 is loaded the same way, only in session-compare mode
    if compare_sessions and not live_mode:
        with st.spinner(f"Loading Session 2: {gp2} {year2} {session_label2}…  (first load ~15–30 s)"):
            try:
                sess2 = load_session(year2, gp2, session_type2, load_telemetry=False)
                if not hasattr(sess2, "laps") or sess2.laps is None or sess2.laps.empty:
                    raise ValueError("No lap data available for this session.")
                st.session_state["session2"] = sess2
                st.session_state["sess_key2"] = sess_key2
                st.session_state["year2"] = year2
            except Exception as e:
                # same recovery as Session 1, for the second compared session
                clear_session_cache(year2, gp2)
                st.session_state["session2"] = None
                st.session_state["sess_key2"] = None
                err_msg2 = str(e).rstrip(".") + "."
                if livetiming_rejects_requests():
                    st.error(
                        "**Upstream F1 data servers are unreachable**\n\n"
                        "Both the free OpenF1/Jolpica APIs and F1's live-timing server failed to respond. "
                        "Check your network connection and click **⬇️ Load Session(s)** to retry."
                    )
                else:
                    st.error(
                        f"**Session Loading Error (Session 2)**\n\n"
                        f"FastF1 could not load the lap data: {err_msg2}\n\n"
                        "We have cleared the cache for this session. Please try clicking **⬇️ Load Session(s)** again to reload."
                    )
                _render_footer()
                st.stop()
    else:
        # Compare box unticked: forget any Session 2 from an earlier load
        st.session_state["session2"] = None
        st.session_state["sess_key2"] = None
        st.session_state["year2"] = None

# Read the loaded session(s) back from state. These, not the sidebar widgets,
# decide what the rest of the page shows (the sidebar may have been changed
# without pressing Load again).
sess = st.session_state.get("session")
sess2 = st.session_state.get("session2")
sess_key = st.session_state.get("sess_key")
sess_key2 = st.session_state.get("sess_key2")
year1 = st.session_state.get("year1")
year2 = st.session_state.get("year2")

# Live mode banner at the top of the page (recorder status and refresh timer)
if live_mode:
    live_status = get_live_recorder_status(live_filename)
    render_live_status_banner(live_status, auto_refresh_sec > 0, auto_refresh_sec)

# ── Landing ───────────────────────────────────────────────────────────────────
# Nothing loaded yet: show the landing page and stop. Every section below can
# assume `sess` is a loaded session.
if sess is None:
    # Back link, then a welcome card with four feature tiles
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
# Guard: a session can load with no lap data (very recent or cancelled events).
# In that case clear both the FastF1 cache and session state, so the user is not
# stuck re-running against a broken session.
try:
    # Three-letter driver codes (e.g. "VER") that set a lap in each session
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
# Plain pandas copies of the lap tables. @st.cache_data cannot hash
# fastf1.core.Laps, so cached builders take these instead of sess.laps
# (AGENT.md coding standard). _all_laps2 is None outside session-compare mode.
_all_laps1: pd.DataFrame = pd.DataFrame(sess.laps.copy())
_all_laps2: pd.DataFrame = pd.DataFrame(sess2.laps.copy()) if sess2 is not None else None

# ── Race Control Messages ──────────────────────────────────────────────────────
# Built once and shared: flag and safety car periods are shaded on Lap Time
# History and Gap to Leader, and the full log renders in Race Control Feed.
_rc_messages = _build_race_control_messages(sess_key, sess)  # table: lap, flag type, message

# ── Driver name labels (built once per session) ───────────────────────────────
# 'VER · Verstappen'-style display labels for selectbox format_func and legends.
_drv_labels1: dict = _build_driver_labels(sess)
_drv_labels2: dict = _build_driver_labels(sess2) if sess2 is not None else None

# Build closures that capture the labels dicts — avoids NameError from loader.py globals
# _fmt_driver1("VER") -> "VER · Verstappen". Driver 2's formatter falls back to
# Session 1's names when there is no second session.
_fmt_driver1 = _make_fmt_driver(_drv_labels1)
_fmt_driver2 = _make_fmt_driver(_drv_labels2 or _drv_labels1, fallback=_drv_labels1)

# ── Export Figures Collection ──────────────────────────────────────────────────
# Plotly figures are registered here as their sections render (Lap Time History,
# Tyre Stints, Gap to Leader, Position History) and bundled into the sidebar PDF
# debrief at the very end of the script.
_export_figs = {}  # {"Lap Time History": figure, ...}, filled in as sections render


# ── Session header ────────────────────────────────────────────────────────────
# Back link, then the event banner (circuit, flag, round, session, date). In
# session-compare mode both sessions' banners sit side by side.
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
# Driver 1 defaults to the session winner. In session-compare mode Driver 2 is
# picked from Session 2 and `compare` is forced on; otherwise Driver 2 is
# optional and drawn from the same session. `compare` and `driver2` gate every
# head-to-head element below. Each driver then gets a lap picker, and with two
# drivers the user chooses Overlapping or Separate telemetry charts.
st.markdown("<div class='section-title'>Driver Selection</div>", unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1])
with col_a:
    # Winner (or fastest driver in practice) is pre-selected as Driver 1
    _p1_drv1 = _get_session_winner(sess, all_drivers1)
    _def_d1_idx = all_drivers1.index(_p1_drv1) if _p1_drv1 in all_drivers1 else 0
    driver1 = st.selectbox(
        "Driver 1", all_drivers1, index=_def_d1_idx, key="d1",
        format_func=_fmt_driver1,
    )
with col_b:
    if sess2 is not None:
        # Session compare: always comparing; default to the same driver in
        # Session 2 (e.g. VER 2025 vs VER 2026) when they took part.
        compare = True
        _def_d2_idx = all_drivers2.index(driver1) if driver1 in all_drivers2 else 0
        driver2 = st.selectbox(
            "Driver 2 (Session 2)", all_drivers2, index=_def_d2_idx, key="d2",
            format_func=_fmt_driver2,
        )
    else:
        # Driver compare within one session is optional
        compare = st.checkbox("Compare with Driver 2", value=False)
        driver2 = None
        if compare:
            remaining = [d for d in all_drivers1 if d != driver1]  # can't compare a driver with themselves
            driver2 = st.selectbox(
                "Driver 2", remaining, key="d2",
                format_func=_fmt_driver1,
            )


# Lap pickers ("Fastest" or a lap number). lap1 / lap2 are the chosen lap rows
# that most sections below analyse; laps1 / laps2 are all of that driver's laps.
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

# Chart mode toggle: only offered with two drivers; one driver always uses the
# Overlapping layout.
chart_mode = "Overlapping"
if compare and driver2:
    chart_mode = st.radio(
        "Chart View", ["Overlapping", "Separate"], horizontal=True, index=0,
        help="Overlapping: both drivers on same axes | Separate: individual side-by-side charts",
    )


# ── Telemetry ─────────────────────────────────────────────────────────────────
# Car data (speed, throttle, brake, RPM, gear, DRS) for the selected lap(s),
# used by braking, gears, era comparison and the telemetry charts. inject_styles
# runs again so the page accent colour follows Driver 1's team.
# CHANGE (#203): Lazily populate car & position telemetry onto the shared session
# object(s) only when telemetry sections are reached.
with st.spinner("Loading car & position telemetry…"):
    ensure_session_telemetry(sess)
    if sess2 is not None:
        ensure_session_telemetry(sess2)

# Car data for the chosen laps (None if unavailable); Driver 2 only when comparing
tel1 = get_telemetry_cached(driver1, lap1, sess_key)
tel2 = get_telemetry_cached(driver2, lap2, sess_key2) if (compare and driver2 and lap2 is not None) else None

# Team colour for each driver, used by every chart and card. The page accent is
# re-themed to Driver 1's team; teal is a placeholder when there is no Driver 2.
colour1 = driver_colour(sess, driver1)
inject_styles(colour1)
colour2 = driver_colour(sess2 if sess2 is not None else sess, driver2) if driver2 else "#27F4D2"

# ── Lap Summary ───────────────────────────────────────────────────────────────
# Headline cards for each selected lap.
st.markdown("<div class='section-title'>Lap Summary</div>", unsafe_allow_html=True)


# Two drivers -> two cards side by side; one driver -> a single card. Each card
# shows headshot, team, lap time, sectors, tyre and weather for that lap.
if compare and lap2 is not None:
    s1, s2 = st.columns(2)
    with s1:
        render_summary(lap1, driver1, colour1, sess, year1)
    with s2:
        render_summary(lap2, driver2, colour2, sess2 if sess2 is not None else sess, year2 if year2 is not None else year1)
else:
    render_summary(lap1, driver1, colour1, sess, year1)

# ── Session Statistics ────────────────────────────────────────────────────────
# Per-driver aggregates across the whole session, not just the selected lap.
st.markdown("<div class='section-title'>Session Statistics</div>", unsafe_allow_html=True)


# Grid, finish, status, best lap, race pace and top speed for each driver; with
# two drivers each column gets a coloured name heading.
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
# Every lap for each driver, with the selected lap highlighted and race control
# periods shaded. Labels carry the year in session-compare mode so the legend
# stays unambiguous across seasons.
st.markdown("<div class='section-title'>Lap Time History</div>", unsafe_allow_html=True)


# Legend labels reused by many sections below: "VER" normally, "VER (2026)"
# when comparing two sessions.
if sess2 is not None:
    label1 = f"{driver1} ({year1})"
    label2 = f"{driver2} ({year2})"
else:
    label1 = driver1
    label2 = driver2

# (label, colour, lap-history table) per driver, plus the selected lap of each
# so the chart can highlight it.
_hist_pairs = [(label1, colour1, _build_lap_history(driver1, sess_key, _all_laps1))]
_hist_laps  = [lap1]
if compare and driver2:
    _hist_pairs.append((label2, colour2, _build_lap_history(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1)))
    _hist_laps.append(lap2)

# No lap times for anyone (e.g. a session with no timed laps): show a note
_all_none = all(p[2] is None or p[2].empty for p in _hist_pairs)
if _all_none:
    st.info("Lap time history not available for this session.")
else:
    # ── Compound filter ───────────────────────────────────────────────────────
    # Options are the union of compounds either driver used; the filter is
    # applied to each driver's laps before plotting.
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

    # Draw the chart (flag periods shaded) and keep it for the PDF export
    _lap_hist_fig_obj = _lap_history_fig(_hist_pairs_filtered, _hist_laps, rc_messages=_rc_messages)
    _export_figs["Lap Time History"] = _lap_hist_fig_obj
    st.plotly_chart(_lap_hist_fig_obj, width="stretch", config={"displayModeBar": False})

# ── Fuel-Adjusted Pace Analysis ───────────────────────────────────────────────
# Normalises lap times to empty-tank pace so stints on different fuel loads
# can be compared directly.
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
# One slider value drives both the pace chart and the simulated leaderboard.
_fuel_col, _ = st.columns([1, 3])
with _fuel_col:
    _fuel_effect = st.slider(
        "Fuel effect (s / lap of fuel)",
        min_value=0.01, max_value=0.06,
        value=0.03, step=0.005, format="%.3f",
        help="Industry standard is ~0.030 s per lap of fuel. Adjust to explore sensitivity.",
        key="fuel_effect_slider",
    )


# Each lap's time minus the fuel effect x laps of fuel still on board, per driver
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
    # Best fuel-adjusted lap per driver, with best raw and median adjusted pace.
    _pace_cols = st.columns(len(_fuel_pairs))
    for _pc, (drv, col, df) in zip(_pace_cols, _fuel_pairs):
        if df is None or df.empty:
            continue
        _best_raw  = df["LapTimeSec"].min()      # fastest lap as timed
        _best_adj  = df["FuelAdjSec"].min()      # fastest lap after fuel correction
        _avg_adj   = df["FuelAdjSec"].median()   # typical corrected pace (median ignores outliers)
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
    # Ranks the whole field by median fuel-corrected pace; one tab per session
    # in session-compare mode.
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    with st.expander("📋 View Simulated Qualifying Leaderboard (Fuel-Corrected)", expanded=False):
        st.markdown(
            "<div style='font-size:13px; margin-bottom:12px; opacity:0.8;'>"
            "This table simulates the overall qualification/race-pace order by ranking all drivers based on their "
            "<strong>median fuel-corrected pace</strong>. All laps are normalized to empty-tank equivalent pace."
            "</div>",
            unsafe_allow_html=True
        )
        # Session compare: one tab per session; otherwise one table with the
        # selected driver(s) highlighted
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
# Compound and length of each stint per driver.
st.markdown("<div class='section-title'>Tyre Stint Timeline</div>", unsafe_allow_html=True)


# Per driver: list of stints (compound, first lap, last lap)
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
# Derived from lap PitIn/PitOut times, so only Race and Sprint sessions produce
# data. _pit_d1 / _pit_d2 are reused by the undercut simulator below.
st.markdown("<div class='section-title'>Pit Stop Summary</div>", unsafe_allow_html=True)


# Per driver: list of stops (lap, stop duration, tyres before/after), or None
_pit_d1 = _build_pit_stops(driver1, sess_key, _all_laps1)
_pit_d2 = _build_pit_stops(driver2, sess_key2 if sess_key2 else sess_key, _all_laps2 if _all_laps2 is not None else _all_laps1) if compare and driver2 else None

if _pit_d1 is None and _pit_d2 is None:
    st.info("Pit stop data is not available for this session "
            "(Race and Sprint sessions only).")
else:
    # One HTML table per driver, wrapped together in a single card
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
# Runs only when two compared drivers both pitted. Pairs the first stops made
# within 3 laps of each other, then compares the on-track gap one lap before
# the earlier stop with the gap two laps after the later one: the stop is
# 'Successful' if whoever pitted first gained time across that window.
if compare and driver2 and _pit_d1 and _pit_d2:
    st.markdown("<div class='section-title'>Pit Strategy & Undercut Analysis</div>", unsafe_allow_html=True)
    
    # Filter laps specifically for each compared driver to ensure gap lookups
    # compute the true on-track distance between them, and gracefully handle
    # single-session compare mode where _all_laps2 is None.
    _laps_driver1 = _all_laps1[_all_laps1['Driver'] == driver1]
    _laps_source2 = _all_laps2 if _all_laps2 is not None else _all_laps1
    _laps_driver2 = _laps_source2[_laps_source2['Driver'] == driver2]

    # Pair each of Driver 1's stops with Driver 2's first stop within 3 laps:
    # those are stops made in response to each other.
    battles = []
    for p1 in _pit_d1:
        _u_lap1 = p1['lap']
        for p2 in _pit_d2:
            _u_lap2 = p2['lap']
            if abs(_u_lap1 - _u_lap2) <= 3:
                battles.append((p1, p2))
                break
                
    if not battles:
        st.info("The selected drivers were on divergent strategies and did not engage in a direct pit stop battle.")
    else:
        battle = battles[0]
        # Use prefixed variables (_u_lap1, _u_lap2) to prevent shadowing outer lap1 / lap2 objects
        _u_lap1 = battle[0]['lap']
        _u_lap2 = battle[1]['lap']
        
        # Compare the gap one lap before the first stop with the gap two laps
        # after the second, once both cars are back up to speed
        w_start = min(_u_lap1, _u_lap2) - 1
        w_end = max(_u_lap1, _u_lap2) + 2
        
        try:
            # "Time" = session clock when each driver finished that lap, so the
            # difference is the on-track gap (positive = Driver 1 behind)
            t1_start = _laps_driver1[_laps_driver1['LapNumber'] == w_start]['Time'].iloc[0]
            t2_start = _laps_driver2[_laps_driver2['LapNumber'] == w_start]['Time'].iloc[0]
            gap_start = (t1_start - t2_start).total_seconds()
            
            t1_end = _laps_driver1[_laps_driver1['LapNumber'] == w_end]['Time'].iloc[0]
            t2_end = _laps_driver2[_laps_driver2['LapNumber'] == w_end]['Time'].iloc[0]
            gap_end = (t1_end - t2_end).total_seconds()
            
            first_pitter = label1 if _u_lap1 < _u_lap2 else (label2 if _u_lap2 < _u_lap1 else "Simultaneous")
            
            # Undercut works if whoever stopped first gained time over the window
            net_change = gap_start - gap_end
            success = "Successful" if (_u_lap1 < _u_lap2 and net_change > 0) or (_u_lap2 < _u_lap1 and net_change < 0) else "Failed"
            success_color = "#52E252" if success == "Successful" else "#E8002D"
            
            # Result cards, then a chart of the gap through the pit window
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Aggressor (Pitted First)", first_pitter)
            col2.metric(f"Gap at Lap {w_start}", f"{abs(gap_start):.2f}s", f"{'Behind' if gap_start > 0 else 'Ahead'}")
            col3.metric(f"Gap at Lap {w_end}", f"{abs(gap_end):.2f}s", f"{'Behind' if gap_end > 0 else 'Ahead'}")
            col4.markdown(f"<div style='text-align:center;'><div>Status</div><h3 style='color:{success_color}; margin-top:0;'>{success}</h3></div>", unsafe_allow_html=True)
            
            st.plotly_chart(build_undercut_chart(_laps_driver1, _laps_driver2, label1, label2, colour1, colour2, w_start, w_end, _u_lap1, _u_lap2), width="stretch", config={"displayModeBar": False})
            
        except Exception as e:
            # a lap in the window is missing (e.g. retirement or red flag)
            st.warning("Could not calculate undercut gap due to missing telemetry on the battle laps.")


# ── Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown ───────────
# Field-wide pit loss breakdown: in-lap push, pit lane transit, out-lap warm-up.
# The whole block sits in a try/except that swallows errors, so a failure here
# renders nothing rather than taking down the rest of the page.
try:
    # Use _all_laps1 (DataFrame) and _sess_obj (prefixed with _ to bypass Streamlit cache hashing)
    _transit_laps = _all_laps1
    _transit_data = _build_pit_transit_data(sess_key, _transit_laps, _sess_obj=sess, driver=driver1)
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
            fmt_func=_fmt_driver1,
        )
except Exception:
    pass


# ── Tyre Degradation Analysis ──────────────────────────────────────────────────
# Per-stint regression of lap time against tyre age on green-flag flyer laps.
# With the fuel decoupler on (default), the fuel-burn gain is removed before
# fitting so the slope reflects mechanical wear. The rates table and the
# crossover matrix below both reuse `table_rows` from build_tyre_deg_fig.
st.markdown("<div class='section-title'>Tyre Degradation Analysis</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:11px; opacity:0.55; margin:-6px 0 10px; letter-spacing:0.3px;'>"
    "Analyses tyre wear and pace drop-off by performing linear regression (OLS) and quadratic thermal modeling on valid flyer laps. "
    "Out-laps, in-laps, and laps under Safety Car / VSC are excluded. "
    "Fuel decoupling removes artificial lap time gains from fuel mass burn (~0.3 kg/lap) to reveal true mechanical tyre degradation."
    "</div>",
    unsafe_allow_html=True,
)

# Fuel Decoupler Controls: a toggle, and (when on) a slider for how much faster
# the car gets per lap as fuel burns off. Off = fit raw lap times.
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

# Per-stint degradation fits for each driver: fuel-corrected or raw
if decouple_fuel:
    _deg_d1 = _build_fuel_decoupled_tyre_deg(driver1, _all_laps1, fuel_effect=fuel_burn_rate)
    _deg_d2 = _build_fuel_decoupled_tyre_deg(driver2, _all_laps2 if _all_laps2 is not None else _all_laps1, fuel_effect=fuel_burn_rate) if compare and driver2 else None
else:
    _deg_d1 = _build_tyre_deg_data(driver1, _all_laps1)
    _deg_d2 = _build_tyre_deg_data(driver2, _all_laps2 if _all_laps2 is not None else _all_laps1) if compare and driver2 else None

if not _deg_d1 and not _deg_d2:
    st.info("Insufficient stint telemetry (minimum 4 consecutive green-flag laps per stint) to model tyre degradation.")
else:
    # Chart of lap time vs tyre age with fitted lines; table_rows holds one row
    # per stint (driver, compound, laps, seconds lost per lap)
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

    # Summary Table: one row per stint with a coloured compound dot. Green rate
    # = lap times got quicker over the stint; red = they got slower.
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
    # Projects each stint's cliff lap and pit window from the same fitted rows.
    render_tyre_crossover_matrix(
        table_rows=table_rows,
        fmt_driver1=_fmt_driver1,
        fmt_driver2=_fmt_driver2,
        driver1=driver1,
        driver2=driver2 if compare else None,
        colour1=colour1,
        colour2=colour2,
    )

# ── Tyre Stint Pace Degradation Matrix & Pit Window Simulator (#196) ────────
# Race / Sprint only (gate lives in the renderer). Reuses the fuel decoupler
# setting above and seeds pit loss from the circuit's measured grid median net
# pit loss computed by the Pit Lane Transit Loss section.
try:
    # Typical time lost by a pit stop at this circuit, measured by the Pit Lane
    # Transit section above. NameError: that section failed before setting
    # _transit_data, so the simulator uses its own default.
    _strat_pit_loss = None
    try:
        _strat_pit_loss = (_transit_data or {}).get("summary", {}).get("grid_median_pit_loss")
    except NameError:
        _strat_pit_loss = None
    # Session type from the loaded session ("Race"), not the sidebar, which may
    # have been changed without reloading
    try:
        _strat_session_type = str(sess.name)
    except Exception:
        _strat_session_type = session_type
    _render_strategy_simulator_section(
        sess_key, _all_laps1, _strat_session_type, driver1,
        colour=colour1, fmt_func=_fmt_driver1,
        default_pit_loss=_strat_pit_loss,
        fuel_effect=fuel_burn_rate,
    )
except Exception:
    st.warning("Strategy simulator could not be rendered for this session.")

# ── Driver Consistency & Stint Pace Distribution ───────────────────────────
# Lap time spread per driver and stint. _hl_drivers / _hl_colours set here are
# reused by the next two sections.
st.markdown("<div class='section-title'>Driver Consistency & Stint Pace Distribution</div>", unsafe_allow_html=True)
_hl_drivers = [driver1] + ([driver2] if compare and driver2 else [])
_hl_colours = [colour1] + ([colour2] if compare and driver2 else [])
_render_consistency_section(_all_laps1, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Track Temperature & Weather Impact Correlation ─────────────────────────
# Lap pace against track temperature, read from the session's weather data.
_render_weather_correlation_section(sess_key, _all_laps1, sess, _hl_drivers, _hl_colours, _fmt_driver1)

# ── Track Evolution & Grip Improvement Ramp (Practice / Qualifying only) ───
# Practice and Qualifying only. The session gate lives inside the renderer,
# which is why session_type is passed; other sessions render nothing.
_render_track_evolution_section(
    sess_key, _all_laps1, sess, session_type, _hl_drivers, _hl_colours, _fmt_driver1
)

# ── Braking Efficiency & Trail-Braking Zone Analysis ───────────────────────
# Needs Driver 1 telemetry; adds Driver 2 when comparing.
st.markdown("<div class='section-title'>Braking Efficiency & Trail-Braking Zone Analysis</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_braking_analysis_section(
        sess_key, sess, lap1, lap2, driver1, driver2, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Corner Exit Traction & Throttle Pick-Up Analysis ───────────────────────
# Measures throttle application aggression, hesitation lifts, and traction drive.
st.markdown("<div class='section-title'>Corner Exit Traction & Throttle Pick-Up Analysis</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_traction_exit_section(
        sess_key, sess, lap1, lap2, driver1, driver2, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Gear Shift Strategy & RPM Power Band Optimization ──────────────────────
# Gear usage, shift points and RPM bands from the fetched telemetry.
st.markdown("<div class='section-title'>Gear Shift Strategy & RPM Power Band Optimization</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_gear_analysis_section(
        sess_key, tel1, tel2 if (compare and driver2) else None,
        driver1, driver2, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Driver Driving Style DNA & Apex Aggression Spider Radar (#197) ──────────
# Scores six driving traits (0-100) from the lap's telemetry and draws them on
# a radar chart with a driving-style label; needs Driver 1 telemetry.
st.markdown("<div class='section-title'>🧬 Driver Driving Style DNA & Apex Aggression Spider Radar</div>", unsafe_allow_html=True)
if tel1 is not None:
    _render_driving_style_dna_section(
        sess_key, sess, tel1, tel2 if (compare and driver2) else None,
        driver1, driver2 if compare else None, colour1, colour2, compare,
        fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Corner Geometry & Minimum-Radius Apex Trajectory Curvature (#198) ────────
# Line deltas only make sense on one circuit, so a session compare against a
# different Grand Prix shows Driver 1 alone.
st.markdown("<div class='section-title'>📐 Corner Geometry & Minimum-Radius Apex Analysis</div>", unsafe_allow_html=True)
# True when there is one session, or both sessions are at the same Grand Prix
try:
    _same_circuit = sess2 is None or sess2.event["EventName"] == sess.event["EventName"]
except Exception:
    _same_circuit = False
_render_corner_geometry_section(
    sess_key, sess, lap1, lap2 if (compare and driver2) else None,
    driver1, driver2 if compare else None, colour1, colour2, compare,
    same_circuit=_same_circuit, fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
)

# ── Start Line Reaction Time & Launch Telemetry Acceleration Analyzer (#200) ──
# Standing-start launch analysis on Lap 1 (0–100 km/h, 0–200 km/h, reaction time,
# clutch bite-point RPM drop, wheelspin & Turn 1 braking). Race / Sprint only;
# reads sess.name from the loaded session (not the sidebar) and passes sess2 /
# _all_laps2 so cross-session Race/Sprint comparisons work seamlessly.
try:
    _launch_session_type = str(sess.name)
except Exception:
    _launch_session_type = session_type
_render_launch_analysis_section(
    sess_key, sess, _all_laps1, _launch_session_type,
    driver1, driver2 if compare else None, colour1, colour2, compare,
    fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2,
    session_obj2=sess2, laps_df2=_all_laps2, sess_k2=sess_key2
)


# ── Multi-Year Historical Lap Comparison ─────────────────────────────────
# Only when both compared laps have telemetry — built for session-compare
# across seasons. Both laps are aligned on a shared distance grid.
if compare and tel1 is not None and tel2 is not None:
    # Labels like "2025 VER · Verstappen", and each lap time in seconds (None
    # when the lap has no official time)
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

# No car data for Driver 1's lap: nothing below can be drawn, so end the page
if tel1 is None:
    st.warning("No telemetry available for the selected lap.")
    _render_footer()
    st.stop()

# ── Telemetry Channel Filter ──────────────────────────────────────────────────
# CHANGE (#203): Lazy-import matplotlib & src.charts.matplotlib only when
# Telemetry Charts render so cold-start / landing skips Matplotlib setup.
import matplotlib
import matplotlib.pyplot as plt
from src.charts.matplotlib import style_ax, build_chart, build_delta_chart, build_time_delta_chart, AVAILABLE_CHANNELS
matplotlib.rcParams.update(MATPLOTLIB_THEME)  # dark/light colours for the static charts

# Note the stop just above: without Driver 1 telemetry the run ends there, so
# every section below (including the field-wide ones) is skipped.
selected_channels = st.multiselect(
    "Telemetry Channels",
    options=AVAILABLE_CHANNELS,
    default=AVAILABLE_CHANNELS,
    help="Toggle and select which telemetry channels to display on the chart.",
)

# ── Overlapping ───────────────────────────────────────────────────────────────
# All drivers on shared axes. Also the single-driver view.
if chart_mode == "Overlapping" or not compare:
    # (label, colour, telemetry) for each driver to draw on the shared axes
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

    # Static Matplotlib chart, one row per selected channel. plt.close frees
    # the figure's memory, which would otherwise build up on every rerun.
    fig = build_chart(drv_list, title, selected_channels=selected_channels)
    if fig is not None:
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    else:
        st.info("Select at least one telemetry channel above to display the chart.")

# ── Separate ──────────────────────────────────────────────────────────────────
# Side-by-side charts, one per driver.
else:
    # Left column = Driver 1, right column = Driver 2; each chart's title is
    # that driver's label and lap time
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
# Download the selected laps' telemetry as CSV, Parquet or JSON.
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
# Overlapping mode only. Speed Delta compares the two telemetry traces; Time
# Delta runs fastf1.utils.delta_time on the two lap objects to show where time
# is gained or lost along the lap.

if compare and chart_mode == "Overlapping" and tel1 is not None and tel2 is not None:
    if "Speed" in tel1.columns and "Speed" in tel2.columns:
        st.markdown("<div class='section-title'>Speed Delta</div>", unsafe_allow_html=True)

        # Speed difference along the lap, shaded by whichever driver is faster
        fig_d = build_delta_chart(tel1, tel2, colour1, colour2, label1, label2)
        st.pyplot(fig_d, width='stretch')
        plt.close(fig_d)

if compare and chart_mode == "Overlapping" and lap1 is not None and lap2 is not None:
    st.markdown("<div class='section-title'>Time Delta (Continuous)</div>", unsafe_allow_html=True)
    # Running time gap along the lap (laps passed Driver 2 first so the line
    # reads as Driver 2 relative to Driver 1)
    fig_td = build_time_delta_chart(lap2, lap1, colour2, colour1, label2, label1)
    if fig_td:
        st.pyplot(fig_td, width='stretch')
        plt.close(fig_td)

# ── Micro-Sector Speed Delta & Dominance Streamgraph (#199) ────────────────
# Compare Mode only, in both chart modes. Session compare across different
# Grands Prix is refused inside the renderer.
if compare and driver2:
    st.markdown("<div class='section-title'>🧩 Micro-Sector Speed Delta & Dominance Timeline</div>", unsafe_allow_html=True)
    # same check as Corner Geometry: one session, or both at the same Grand Prix
    try:
        _same_circuit_ms = sess2 is None or sess2.event["EventName"] == sess.event["EventName"]
    except Exception:
        _same_circuit_ms = False
    _render_microsector_section(
        sess_key, sess, lap1, lap2, tel1, tel2, driver1, driver2, colour1, colour2,
        same_circuit=_same_circuit_ms, fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
    )

# ── Fastest Laps Leaderboard ──────────────────────────────────────────────────
# From here on, sections are field-wide: they read the whole lap table rather
# than the selected laps, and render one tab per session in session-compare mode.
st.markdown("<div class='section-title'>Fastest Laps Leaderboard</div>", unsafe_allow_html=True)


# Every driver's fastest lap, ranked; selected drivers highlighted
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
# Official speed trap sensors (ST, I1, I2, FL), Session 1 only.
st.markdown("<div class='section-title'>Speed Trap & Intermediate Velocity Radar Breakdown</div>", unsafe_allow_html=True)
_render_speed_trap_section(
    sess_key, _all_laps1, driver1, driver2 if compare else None,
    colour1, colour2 if compare else None, compare,
    fmt_func1=_fmt_driver1, fmt_func2=_fmt_driver2
)

# ── Clean Air vs Dirty Air Pace Impact & Overtaking (Issue #157) ───────────
# Race / Sprint only — the renderer gates on session_type and draws nothing otherwise.
# Reuses the highlighted drivers, colours and label formatter from the sections above.
# The session type comes from the loaded session (not the sidebar, which may have changed
# since loading); a Driver 2 taken from a second session is skipped inside the renderer.
try:
    _da_session_type = str(sess.name)
except Exception:
    _da_session_type = session_type
_render_dirty_air_section(
    sess_key, _all_laps1, _da_session_type, _hl_drivers, _hl_colours, _fmt_driver1
)

# ── Automated Session Brag Video (Issue #171) ──────────────────────────────
# CHANGE (#203): Isolate Brag Video controls inside @st.fragment so changing
# mode/resolution/FPS or generating a clip does not rerun the whole page.
@st.fragment
def _frag_brag_video():
    # Builds a shareable highlight clip of Driver 1's lap. A Driver 2 from the
    # same session can join (e.g. pole duel); one from another session cannot.
    try:
        _brag_lap_no = int(lap1["LapNumber"]) if lap1 is not None else None
    except Exception:
        _brag_lap_no = None
    _render_brag_video_section(
        sess, _all_laps1, driver1, _brag_lap_no, sess_key, colour1, _fmt_driver1,
        driver2 if compare and sess2 is None else None, colour2, _fmt_driver2
    )

_frag_brag_video()  # draw the section now; later clicks inside it rerun only this function

# ── Weekend Multi-Session Progression Tracker (Issue #156) ─────────────────
# CHANGE (#203): Isolate Weekend Progression inside @st.fragment so clicking the
# on-demand load button only updates this section.
@st.fragment
def _frag_weekend_progression():
    # Loads every session of this Grand Prix for Driver 1 (on button press) to
    # show pace and mileage across the weekend. Lap length in km comes from
    # Driver 1's telemetry and is used to convert laps into distance.
    try:
        _wk_event = str(sess.event["EventName"])
        _wk_len_km = float(tel1["Distance"].max()) / 1000.0 if tel1 is not None and "Distance" in tel1.columns else None
    except Exception:
        _wk_event, _wk_len_km = None, None
    if _wk_event:
        _render_weekend_progression_section(year1, _wk_event, driver1, colour1, _fmt_driver1, _wk_len_km)

_frag_weekend_progression()

# ── Ideal Lap vs Actual Lap ───────────────────────────────────────────────────
# Each driver's best sectors combined into a theoretical lap, against their
# actual best.
st.markdown("<div class='section-title'>Ideal Lap vs Actual Lap</div>", unsafe_allow_html=True)


# Session compare: one tab per session; otherwise one view with both drivers
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
# CHANGE (#203): Isolate interactive Qualifying/Race toggle inside @st.fragment.
@st.fragment
def _frag_teammate_battle():
    # Each team's two drivers compared (qualifying or race pace), with the
    # selected drivers highlighted; one tab per session in session compare
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

_frag_teammate_battle()


# ── Multi-Driver Grid Analysis & Heatmaps ───────────────────────────────────────
# CHANGE (#203): Isolate heatmap mode/driver multiselect inside @st.fragment.
@st.fragment
def _frag_grid_heatmap():
    # Pick 3-20 drivers to compare sector times, lap-by-lap pace or top speed
    # as colour-coded heatmaps
    st.markdown("<div class='section-title'>Multi-Driver Grid Analysis & Heatmaps</div>", unsafe_allow_html=True)
    _render_grid_heatmap_section(sess, _all_laps1, all_drivers1, sess_key, fmt_func=_fmt_driver1)

_frag_grid_heatmap()


# ── Gap to Leader ─────────────────────────────────────────────────────────────
# Gap to the leader per lap, with race control periods shaded. Only the
# Session 1 figure is registered for PDF export.
st.markdown("<div class='section-title'>Gap to Leader</div>", unsafe_allow_html=True)

# The renderer returns the figure so it can be added to the PDF export
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
# CHANGE (#203): Isolate Race Control filter inside @st.fragment.
@st.fragment
def _frag_race_control():
    st.markdown("<div class='section-title'>Race Control Feed</div>", unsafe_allow_html=True)

    if _rc_messages is None or _rc_messages.empty:
        st.info("Race control messages are not available for this session.")
    else:
        # Flag type colour badge map: (emoji, colour) for each kind of message
        _FLAG_BADGE = {
            "SAFETY CAR":         ("🟠", "#FF8C00"),
            "VIRTUAL SAFETY CAR": ("🟡", "#FFD700"),
            "RED FLAG":           ("🔴", "#DC0000"),
            "YELLOW FLAG":        ("🟡", "#FFC800"),
            "CLEAR":              ("🟢", "#39B54A"),
            "INVESTIGATION":      ("🔵", "#5B8DEF"),
            "INFO":               ("⚪", "#888888"),
        }
        # Searchable filter: "All" or one message type
        _rc_filter_options = ["All"] + sorted(_rc_messages["FlagType"].unique().tolist())
        _rc_filter = st.selectbox("Filter by event type", _rc_filter_options, key="rc_filter")
        _rc_display = _rc_messages if _rc_filter == "All" else _rc_messages[_rc_messages["FlagType"] == _rc_filter]

        # Build display columns: keep the useful ones, show "Lap 12" instead of
        # 12, and put the emoji badge in front of each flag type
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

_frag_race_control()


# ── Race Position Chart ───────────────────────────────────────────────────────
# Running order lap by lap.
st.markdown("<div class='section-title'>Race Position</div>", unsafe_allow_html=True)

# Running order chart; the Session 1 figure is kept for the PDF export
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
# CHANGE (#203): Isolate Track Map tabs, corner selectors & race replay inside
# @st.fragment so map interactions never rerun the full 29-section page.
@st.fragment
def _frag_track_map():
    # Speed map, mini-sector dominance, pedal inputs, corner analysis and the
    # animated race replay, in tabs. Each session gets its own key prefix
    # ("sess1", "sess2", "single") so Streamlit widget IDs never clash.
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

_frag_track_map()


# ── Championship Standings & Classification ───────────────────────────────────
# Constructors' standings up to this round and the official session
# classification, with the selected drivers and their teams highlighted.
st.markdown("<hr style='margin:24px 0 16px; border-style: solid; opacity:0.15;'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Championship Standings & Classification</div>", unsafe_allow_html=True)


if sess2 is not None:
    tab_cls1, tab_cls2 = st.tabs([f"Session 1 Standings & Results ({year1})", f"Session 2 Standings & Results ({year2})"])
    with tab_cls1:
        # Session 1 Constructors Standings: championship table after this round,
        # with Driver 1's team highlighted
        r1 = _get_round(sess)
        standings1 = _build_constructor_standings(year1, r1)
        team1 = sess.get_driver(driver1).get("TeamName", "") if driver1 else ""
        st.markdown("<div style='font-size: 15px; font-weight: 700; margin-bottom: 8px; opacity: 0.85;'>🏆 Constructors' Championship Standings</div>", unsafe_allow_html=True)
        _render_constructor_standings(standings1, [team1], [colour1])
        
        # Session 1 Classification: official results, plus each driver's
        # championship points so far
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
    # Single Session constructors standings: both selected drivers' teams are
    # highlighted (one team if they are teammates)
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

# ── PDF Debrief Export & Footer ───────────────────────────────────────────────
# Added last, once the sections above have populated _export_figs.
# The sidebar "Generate PDF Report" button bundles the figures in _export_figs.
# Not offered in live mode, where the data is still changing.
with st.sidebar:
    if not live_mode and "driver1" in locals() and "driver2" in locals():
        render_export_section(f"{year} {gp} {session_label}", driver1, driver2 if compare else None, _export_figs)

_render_footer()  # credits and links at the bottom of the page
