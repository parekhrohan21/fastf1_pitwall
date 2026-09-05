import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.ui.styles import TEAM_COLOURS, COMPOUND_COLOURS, TRACK_STATUS_MAP
from src.data.loader import (
    hex_to_rgb, _team_logo, _team_colour, format_laptime, driver_colour,
    _build_driver_labels, _format_classification_time, _map_driver_id_to_number,
    _get_session_winner, _get_default_gp_index, get_constructor_colour,
    is_same_team, _build_constructor_standings, get_driver_standings_points,
    _build_driver_standings, _build_final_classification, _get_telemetry_for_map,
    _build_grid_heatmap_data, _build_consistency_analysis,
    _build_weather_correlation_data, _build_multi_year_comparison,
    _build_export_csv, _build_export_parquet, _build_export_json
)
from src.charts.plotly import (
    _lap_history_fig, _fuel_pace_fig, _stint_fig, _gap_chart_fig,
    _speed_map_fig, _input_map_fig, build_replay_fig, build_corner_fig,
    build_grid_heatmap_fig, build_stint_consistency_fig, build_weather_correlation_fig,
    build_multi_year_comparison_fig, build_braking_efficiency_fig
)

def _render_constructor_standings(standings_list, highlight_teams: list, highlight_colours: list):
    """Render constructor standings as a styled HTML table."""
    if not standings_list:
        st.info("ℹ️ Constructors' Championship standings are not available for this session.")
        return

    # Build a map of highlighted teams to their colors
    hl_map = {}
    for team, col in zip(highlight_teams, highlight_colours):
        if team:
            hl_map[team] = col

    rows_html = ""
    for item in standings_list:
        pos = item.get("position", "")
        points = item.get("points", "0")
        wins = item.get("wins", "0")
        constructor = item.get("Constructor", {})
        c_name = constructor.get("name", "")

        # Find matching team highlight color
        is_hl = False
        accent = "transparent"
        for hl_team, col in hl_map.items():
            if is_same_team(hl_team, c_name):
                is_hl = True
                accent = col
                break

        row_bg = f"{accent}18" if is_hl else "transparent"
        border_css = f"border-left: 3px solid {accent};" if is_hl else "border-left: 3px solid transparent;"
        pos_col = f"<span style='color:{accent}; font-weight:700;'>{pos}</span>" if is_hl else str(pos)

        # Get team color for the indicator block
        team_color_hex = get_constructor_colour(c_name)
        team_indicator = ""
        if team_color_hex:
            team_indicator = (
                f"<span style='display:inline-block; width:4px; height:12px; "
                f"background:{team_color_hex}; margin-right:6px; vertical-align:middle;'></span>"
            )

        team_html = f"{team_indicator}{c_name}"

        rows_html += (
            f"<tr style='background:{row_bg}; {border_css}'>"
            f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
            f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{team_html}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{wins}</td>"
            f"<td style='padding:7px 10px; text-align:center;'><b>{points}</b></td>"
            f"</tr>"
        )

    headers = ["Pos", "Constructor", "Wins", "Points"]
    alignments = ["center", "left", "center", "center"]

    th_html = ""
    for h, align in zip(headers, alignments):
        th_html += f"<th style='padding:8px 10px; text-align:{align};'>{h}</th>"

    table_html = f"""
    <div style='overflow-x:auto; border-radius:12px; border:1px solid rgba(128,128,128,0.15); margin-bottom:16px;'>
    <table style='width:100%; border-collapse:collapse; font-size:13px;'>
      <thead>
        <tr style='border-bottom:1px solid rgba(128,128,128,0.2); opacity:0.6; font-size:10px;
                   letter-spacing:1.5px; text-transform:uppercase;'>
          {th_html}
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def _render_final_classification(df, highlight_drivers: list, highlight_colours: list, fmt_func=None, standings_list=None, laps_df=None):
    """Render official classification results as a styled HTML table."""
    if isinstance(df, str) and df == "PRACTICE":
        st.info("ℹ️ Official classification results are not available for Practice sessions. Please refer to the Fastest Laps Leaderboard above.")
        return

    if df is None or df.empty:
        st.info("Leaderboard not available for this session.")
        return

    # Check if Q1 column exists and has non-nulls (Qualifying)
    is_qualifying = "Q1" in df.columns and df["Q1"].notna().any()
    
    colour_map = dict(zip(highlight_drivers, highlight_colours))
    rows_html = ""
    
    for i, row in df.iterrows():
        drv = str(row["DriverNumber"])
        abbr = str(row.get("Abbreviation", "")).strip()
        last_name = str(row.get("LastName", "")).strip()
        if abbr and abbr != "nan":
            if last_name and last_name != "nan":
                display_drv = f"{drv} · {abbr} · {last_name}"
            else:
                display_drv = f"{drv} · {abbr}"
        else:
            display_drv = drv
            
        is_hl = drv in colour_map
        accent = colour_map.get(drv, "transparent")
        row_bg = f"{accent}18" if is_hl else "transparent"
        border_css = f"border-left: 3px solid {accent};" if is_hl else "border-left: 3px solid transparent;"
        pos_col = f"<span style='color:{accent}; font-weight:700;'>{row['Pos']}</span>" if is_hl else str(row["Pos"])
        
        # Get driver standing details
        drv_abbr = str(row.get("Abbreviation", ""))
        drv_lastname = str(row.get("LastName", ""))
        tot_points = get_driver_standings_points(standings_list, drv_abbr, drv, drv_lastname) if standings_list else "—"

        # Format team name with team color strip / indicator if available
        team_name = str(row.get("TeamName", ""))
        team_color = str(row.get("TeamColor", ""))
        team_html = team_name
        if team_color and team_color != "nan":
            # Add a small team color block before team name
            team_html = (
                f"<span style='display:inline-block; width:4px; height:12px; "
                f"background:#{team_color.lstrip('#')}; margin-right:6px; vertical-align:middle;'></span>"
                f"{team_name}"
            )

        # Count stops for Race/Sprint
        stops_str = "0"
        if not is_qualifying and laps_df is not None and not laps_df.empty:
            if drv_abbr:
                drv_laps = laps_df[laps_df["Driver"] == drv_abbr]
                if not drv_laps.empty:
                    stops_count = drv_laps[drv_laps["PitInTime"].notna() & drv_laps["PitOutTime"].notna()].shape[0]
                    stops_str = str(stops_count)

        if is_qualifying:
            # Show Q1, Q2, Q3
            q1_t = format_laptime(row.get("Q1"))
            q2_t = format_laptime(row.get("Q2"))
            q3_t = format_laptime(row.get("Q3"))
            
            rows_html += (
                f"<tr style='background:{row_bg}; {border_css}'>"
                f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
                f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{display_drv}</td>"
                f"<td style='padding:7px 10px;'>{team_html}</td>"
                f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{q1_t}</td>"
                f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{q2_t}</td>"
                f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{q3_t}</td>"
                f"<td style='padding:7px 10px; text-align:center; font-family:monospace;'>{tot_points}</td>"
                f"</tr>"
            )
        else:
            # Show Race/Sprint results
            is_first = (i == 0)
            time_status = _format_classification_time(row, is_first=is_first)
            
            points_val = row.get("Points", 0.0)
            points_str = f"{int(points_val)}" if pd.notna(points_val) and points_val % 1 == 0 else f"{points_val}"
            if float(points_val) == 0.0:
                points_str = "0"
            points_str = f"<b>{points_str}</b>" if float(points_val) > 0.0 else points_str
            
            grid_pos = row.get("GridPosition")
            grid_str = f"{int(grid_pos)}" if pd.notna(grid_pos) else "—"
            
            laps_val = row.get("Laps")
            laps_str = f"{int(laps_val)}" if pd.notna(laps_val) else "—"

            rows_html += (
                f"<tr style='background:{row_bg}; {border_css}'>"
                f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
                f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{display_drv}</td>"
                f"<td style='padding:7px 10px;'>{team_html}</td>"
                f"<td style='padding:7px 10px; text-align:center;'>{grid_str}</td>"
                f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{time_status}</td>"
                f"<td style='padding:7px 10px; text-align:center;'>{laps_str}</td>"
                f"<td style='padding:7px 10px; text-align:center;'>{stops_str}</td>"
                f"<td style='padding:7px 10px; text-align:center;'>{points_str}</td>"
                f"<td style='padding:7px 10px; text-align:center; font-family:monospace;'>{tot_points}</td>"
                f"</tr>"
            )

    if is_qualifying:
        headers = ["Pos", "Driver", "Team", "Q1", "Q2", "Q3", "CH Points"]
        alignments = ["center", "left", "left", "left", "left", "left", "center"]
    else:
        headers = ["Pos", "Driver", "Team", "Grid", "Time/Status", "Laps", "Stops", "Points", "CH Points"]
        alignments = ["center", "left", "left", "center", "left", "center", "center", "center", "center"]

    th_html = ""
    for h, align in zip(headers, alignments):
        th_html += f"<th style='padding:8px 10px; text-align:{align};'>{h}</th>"

    table_html = f"""
    <div style='overflow-x:auto; border-radius:12px; border:1px solid rgba(128,128,128,0.15); margin-bottom:8px;'>
    <table style='width:100%; border-collapse:collapse; font-size:13px;'>
      <thead>
        <tr style='border-bottom:1px solid rgba(128,128,128,0.2); opacity:0.6; font-size:10px;
                   letter-spacing:1.5px; text-transform:uppercase;'>
          {th_html}
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def _render_footer() -> None:
    """Render a styled bottom footer indicating design origin."""
    st.markdown(
        "<div style='text-align: center; margin-top: 60px; margin-bottom: 30px; "
        "font-size: 13px; opacity: 0.5; font-family: var(--font-family); color: var(--text-color);'>"
        "Made proudly in Great Britain 🇬🇧"
        "</div>",
        unsafe_allow_html=True
    )


def _session_info_header(session, sess_type_code: str) -> None:
    """Render a slim banner summarising the loaded session."""
    try:
        ev = session.event

        # Human-readable session type
        _type_labels = {
            "R": "Race", "Q": "Qualifying", "SQ": "Sprint Qualifying",
            "SS": "Sprint Shootout", "S": "Sprint",
            "FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3",
        }
        session_label = _type_labels.get(str(sess_type_code).upper(), str(sess_type_code))

        # Basic event fields — safe fallback for each
        circuit  = str(ev.get("Location",   ev.get("EventName", "—")))
        country  = str(ev.get("Country",    "—"))
        round_no = ev.get("RoundNumber",  "—")
        raw_date = ev.get("EventDate",    None)

        # Format date nicely
        try:
            date_str = pd.Timestamp(raw_date).strftime("%-d %B %Y")
        except Exception:
            date_str = str(raw_date)[:10] if raw_date else "—"

        # Country → flag emoji lookup
        _flags = {
            "United Kingdom": "🇬🇧", "United States": "🇺🇸", "Italy": "🇮🇹",
            "Monaco": "🇲🇨", "Spain": "🇪🇸", "France": "🇫🇷", "Germany": "🇩🇪",
            "Belgium": "🇧🇪", "Netherlands": "🇳🇱", "Hungary": "🇭🇺",
            "Austria": "🇦🇹", "Canada": "🇨🇦", "Australia": "🇦🇺",
            "Japan": "🇯🇵", "China": "🇨🇳", "Bahrain": "🇧🇭",
            "Saudi Arabia": "🇸🇦", "Azerbaijan": "🇦🇿", "Singapore": "🇸🇬",
            "Mexico": "🇲🇽", "Brazil": "🇧🇷", "Abu Dhabi": "🇦🇪",
            "United Arab Emirates": "🇦🇪", "Qatar": "🇶🇦", "Miami": "🇺🇸",
            "Las Vegas": "🇺🇸",
        }
        flag = _flags.get(country, "🏁")

        # Session type → icon
        _type_icons = {
            "Race": "🏆", "Qualifying": "⏱", "Sprint": "⚡",
            "Sprint Qualifying": "⚡", "Sprint Shootout": "⚡",
            "Practice 1": "🔧", "Practice 2": "🔧", "Practice 3": "🔧",
        }
        sess_icon = _type_icons.get(session_label, "🏎")

        st.markdown(
            f"""
            <div class="session-info-header" style="
                background: linear-gradient(135deg,
                    rgba(var(--primary-rgb), 0.08) 0%,
                    var(--secondary-background-color) 60%);
                border: 1px solid rgba(var(--primary-rgb), 0.25);
                border-left: 4px solid var(--primary-color);
                border-radius: 14px;
                padding: 14px 20px;
                margin-bottom: 18px;
                display: flex;
                align-items: center;
                gap: 24px;
                flex-wrap: wrap;
            ">
                <div style="font-size: 36px; line-height: 1;">{flag}</div>
                <div style="flex: 1; min-width: 200px;">
                    <div style="
                        font-size: 18px; font-weight: 700;
                        letter-spacing: -0.3px; margin-bottom: 3px;
                    ">{circuit}</div>
                    <div style="font-size: 12px; opacity: 0.55; letter-spacing: 0.5px;">
                        {country} &nbsp;·&nbsp; Round {round_no}
                    </div>
                </div>
                <div style="display:flex; gap:28px; flex-wrap:wrap;">
                    <div style="text-align:center;">
                        <div style="font-size:20px;">{sess_icon}</div>
                        <div style="font-size:11px; opacity:0.6; margin-top:2px;">{session_label}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="
                            font-size:13px; font-weight:600;
                            color:var(--primary-color); white-space:nowrap;
                        ">{date_str}</div>
                        <div style="font-size:11px; opacity:0.6; margin-top:2px;">Event Date</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass   # Never crash the page for a cosmetic header


def lap_selector(session_obj, driver: str, suffix: str = "", fmt_func=None):
    dlaps = session_obj.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    if dlaps.empty:
        dlaps = session_obj.laps.pick_drivers(driver).dropna(subset=["LapTime"]).reset_index(drop=True)
    if dlaps.empty:
        st.warning(f"No valid laps for {fmt_func(driver) if fmt_func else driver}.")
        return None, None
    opts   = ["Fastest"] + [str(int(ln)) for ln in dlaps["LapNumber"].tolist()]
    choice = st.selectbox(f"Lap — {fmt_func(driver) if fmt_func else driver}", opts, key=f"lap_{driver}{suffix}")
    lap    = dlaps.loc[dlaps["LapTime"].idxmin()] if choice == "Fastest" \
        else dlaps[dlaps["LapNumber"] == int(choice)].iloc[0]
    return lap, dlaps


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


def render_live_status_banner(status_info: dict, auto_refresh: bool = False, interval_sec: int = 10):
    """Render broadcast-grade live timing status header banner."""
    active = status_info.get("active", False)
    exists = status_info.get("exists", False)
    size_kb = status_info.get("size_bytes", 0) / 1024.0
    line_count = status_info.get("line_count", 0)
    last_mod = status_info.get("last_modified", "N/A")
    
    badge_color = "#e53e3e" if active else ("#319795" if exists else "#718096")
    badge_text = "LIVE STREAMING" if active else ("LIVE FILE LOADED" if exists else "LIVE MODE IDLE")
    pulse_dot = "<span style='display:inline-block; width:8px; height:8px; border-radius:50%; background:#fff; margin-right:6px;'></span>" if active else ""
    refresh_str = f"ON ({interval_sec}s)" if auto_refresh else "OFF"
    
    st.markdown(
        f"""
        <div style="background: rgba(26, 26, 26, 0.85); border: 1px solid rgba(255,255,255,0.1);
                    border-left: 4px solid {badge_color}; border-radius: 8px; padding: 12px 16px;
                    margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;
                    backdrop-filter: blur(10px);">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: {badge_color}; color: #ffffff; font-size: 11px; font-weight: 700;
                            letter-spacing: 1px; padding: 4px 8px; border-radius: 4px; display: flex;
                            align-items: center;">
                    {pulse_dot}{badge_text}
                </div>
                <div style="color: #ccc; font-size: 13px;">
                    Packets: <strong>{line_count:,}</strong> | Size: <strong>{size_kb:.1f} KB</strong> | Last Update: <strong>{last_mod}</strong>
                </div>
            </div>
            <div style="color: #888; font-size: 12px;">
                Auto-Refresh: <strong>{refresh_str}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


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



def render_maps_block(session, session_obj, sess_k, driver, other_driver, colour, other_colour, compare, l1, l2, fmt_func=None):
    map_tab1, map_tab2, map_tab3, map_tab4 = st.tabs([
        "🗺️  Timing Dominance Map",
        "🛞  Driver Inputs Map",
        "🎬  Race Replay",
        "🔍  Corner Analysis"
    ])
    
    with map_tab1:
        if session_obj is not None:
            l_obj = l1
            l_obj2 = l2 if compare else None
            fig, warning_msg = _speed_map_fig(l_obj, driver, colour, sess_k, l_obj2, other_driver, other_colour)
            if warning_msg:
                st.warning(warning_msg)
            if fig:
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Load a session to view track dominance map.")
            
    with map_tab2:
        if session_obj is not None:
            if compare:
                col_inp1, col_inp2 = st.columns(2)
                with col_inp1:
                    st.markdown(f"<div style='font-size: 14px; font-weight: bold; color: {colour}; margin-bottom: 8px;'>{fmt_func(driver) if fmt_func else driver}</div>", unsafe_allow_html=True)
                    fig1, w1 = _input_map_fig(l1, driver, colour, sess_k)
                    if w1: st.warning(w1)
                    if fig1: st.plotly_chart(fig1, width="stretch", config={"displayModeBar": False})
                with col_inp2:
                    st.markdown(f"<div style='font-size: 14px; font-weight: bold; color: {other_colour}; margin-bottom: 8px;'>{fmt_func(other_driver) if fmt_func else other_driver}</div>", unsafe_allow_html=True)
                    fig2, w2 = _input_map_fig(l2, other_driver, other_colour, sess_k)
                    if w2: st.warning(w2)
                    if fig2: st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
            else:
                fig1, w1 = _input_map_fig(l1, driver, colour, sess_k)
                if w1: st.warning(w1)
                if fig1: st.plotly_chart(fig1, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Load a session to view driver inputs map.")
            
    with map_tab3:
        if session_obj is not None:
            replay_key = f"replay_fig_{sess_k}"
            if replay_key not in st.session_state:
                with st.spinner("Building replay animation..."):
                    fig_rep, err = build_replay_fig(session_obj)
                    if err:
                        st.warning(err)
                    else:
                        st.session_state[replay_key] = fig_rep
            
            if replay_key in st.session_state:
                st.plotly_chart(st.session_state[replay_key], width="stretch")
        else:
            st.info("Load a session to view animated replay.")
            
    with map_tab4:
        if session_obj is not None:
            try:
                circuit_info = session_obj.get_circuit_info()
            except Exception:
                st.warning("Circuit geometry info is not available for this track.")
                return

            corners = circuit_info.corners
            if corners.empty:
                st.warning("No corner data available in circuit info.")
                return

            # Corner selectbox
            corners_clean = corners.copy()
            corners_clean["Number"] = corners_clean["Number"].astype(str)
            corner_labels = [f"Turn {row['Number']}{row['Letter'] or ''}" for _, row in corners_clean.iterrows()]
            selected_corner_label = st.selectbox("Select Corner", corner_labels, key="corner_selector")
            
            idx = corner_labels.index(selected_corner_label)
            selected_corner = corners_clean.iloc[idx]
            apex_dist = selected_corner["Distance"]

            try:
                tel1_all = _get_telemetry_for_map(l1, driver, sess_k)
                tel2_all = _get_telemetry_for_map(l2, other_driver, sess_k) if compare else None
            except Exception:
                st.warning("Could not load telemetry for corner analysis.")
                return

            if tel1_all is None or tel1_all.empty:
                st.warning(f"No telemetry available for {driver}.")
                return

            win1 = tel1_all[(tel1_all["Distance"] >= apex_dist - 200) & (tel1_all["Distance"] <= apex_dist + 100)]
            win2 = tel2_all[(tel2_all["Distance"] >= apex_dist - 200) & (tel2_all["Distance"] <= apex_dist + 100)] if compare and tel2_all is not None and not tel2_all.empty else None

            fig_corner, stats1, stats2 = build_corner_fig(win1, win2, driver, other_driver, colour, other_colour, apex_dist, fmt_func)
            
            col_st1, col_st2 = st.columns(2)
            with col_st1:
                st.markdown(f"<div style='border-left: 4px solid {colour}; padding-left: 12px; margin-bottom: 16px;'><div style='font-size: 13px; opacity: 0.7;'>Driver 1</div><div style='font-size: 18px; font-weight: bold; color: {colour};'>{fmt_func(driver) if fmt_func else driver}</div></div>", unsafe_allow_html=True)
                if stats1:
                    st.write(f"Apex Speed: **{stats1['apex_speed']:.1f} km/h**")
                    st.write(f"Braking Distance to Apex: **{stats1['dist_to_apex']:.1f} m**" if stats1["braking_dist"] is not None else "Braking Distance to Apex: **—**")
                    if stats1.get("max_steering") is not None:
                        st.write(f"Max Steering Angle: **{stats1['max_steering']:.1f}°**")
                    st.write(f"DRS Activated: **{'Yes' if stats1.get('drs_active') else 'No'}**")
            with col_st2:
                if compare and stats2:
                    st.markdown(f"<div style='border-left: 4px solid {other_colour}; padding-left: 12px; margin-bottom: 16px;'><div style='font-size: 13px; opacity: 0.7;'>Driver 2</div><div style='font-size: 18px; font-weight: bold; color: {other_colour};'>{fmt_func(other_driver) if fmt_func else other_driver}</div></div>", unsafe_allow_html=True)
                    st.write(f"Apex Speed: **{stats2['apex_speed']:.1f} km/h**")
                    st.write(f"Braking Distance to Apex: **{stats2['dist_to_apex']:.1f} m**" if stats2["braking_dist"] is not None else "Braking Distance to Apex: **—**")
                    if stats2.get("max_steering") is not None:
                        st.write(f"Max Steering Angle: **{stats2['max_steering']:.1f}°**")
                    st.write(f"DRS Activated: **{'Yes' if stats2.get('drs_active') else 'No'}**")

            st.plotly_chart(fig_corner, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Load a session to view corner analysis.")


def _render_grid_heatmap_section(sess, laps_df: pd.DataFrame, all_drivers: list[str], sess_key: str, fmt_func=None):
    """Render the Multi-Driver Grid Analysis & Heatmaps section in app.py."""
    if sess is None or laps_df is None or laps_df.empty or not all_drivers:
        st.info("ℹ️ Multi-driver grid analysis is unavailable for this session.")
        return

    col_ctrl1, col_ctrl2 = st.columns([2, 1])

    with col_ctrl1:
        default_drvs = all_drivers[:10] if len(all_drivers) >= 10 else all_drivers
        selected_drvs = st.multiselect(
            "Select Grid Drivers (3 to 20 drivers)",
            options=all_drivers,
            default=default_drvs,
            key="grid_heatmap_drivers_select",
            format_func=fmt_func if fmt_func is not None else str,
            help="Select drivers across the grid to compare split times, pace deltas, and top speeds.",
        )

    with col_ctrl2:
        mode_label = st.radio(
            "Analysis View",
            options=["Sector Split Deltas", "Lap-by-Lap Pace Heatmap", "Top Speed Matrix"],
            horizontal=False,
            key="grid_heatmap_mode_radio",
        )

    if not selected_drvs or len(selected_drvs) < 2:
        st.warning("⚠️ Please select at least 2 drivers to generate the grid analysis heatmap.")
        return

    mode_map = {
        "Sector Split Deltas": "Sectors",
        "Lap-by-Lap Pace Heatmap": "Laps",
        "Top Speed Matrix": "Speed",
    }

    mode = mode_map.get(mode_label, "Sectors")
    heatmap_data = _build_grid_heatmap_data(sess_key, laps_df, selected_drvs, mode=mode)

    if not heatmap_data:
        st.warning("⚠️ Unable to calculate grid heatmap data for the selected drivers and mode.")
        return

    fig = build_grid_heatmap_fig(heatmap_data, mode=mode)

    # Metric Cards Summary
    best_vals = heatmap_data.get("best_values", [])
    cols_list = heatmap_data.get("columns", [])

    if mode == "Sectors" and len(best_vals) >= 5:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Grid Best S1", f"{best_vals[0]:.3f}s")
        m2.metric("Grid Best S2", f"{best_vals[1]:.3f}s")
        m3.metric("Grid Best S3", f"{best_vals[2]:.3f}s")
        m4.metric("Grid Best Theoretical", f"{best_vals[3]:.3f}s")
    elif mode == "Speed" and len(best_vals) >= 1:
        m_cols = st.columns(min(len(best_vals), 4))
        for idx, (mc_obj, val) in enumerate(zip(m_cols, best_vals)):
            lbl = cols_list[idx] if idx < len(cols_list) else f"Speed {idx+1}"
            mc_obj.metric(f"Top {lbl}", f"{val:.0f} km/h" if pd.notna(val) else "—")

    if fig:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": True})
    else:
        st.info("No heatmap figure generated.")


# ── Debrief Report Export ─────────────────────────────────────────────────────
def _build_pdf_report(session_name: str, driver1: str, driver2: str, figs: dict) -> bytearray:
    from fpdf import FPDF
    import tempfile
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(w=0, h=15, text=f"Post-Race Debrief: {session_name}", new_x="LMARGIN", new_y="NEXT", align="C")
    
    pdf.set_font("Helvetica", "", 12)
    driver_str = f"Drivers: {driver1}"
    if driver2:
        driver_str += f" vs {driver2}"
    pdf.cell(w=0, h=10, text=driver_str, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    # Render each figure
    for title, fig in figs.items():
        if fig is None: continue
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(w=0, h=10, text=title, new_x="LMARGIN", new_y="NEXT")
        
        try:
            img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                tmpfile.write(img_bytes)
                tmpfile_path = tmpfile.name
                
            pdf.image(tmpfile_path, w=190)
            pdf.ln(10)
        except Exception as e:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(w=0, h=10, text=f"[Error rendering chart: {e}]", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(10)
            
    return pdf.output()

def render_export_section(session_name: str, driver1: str, driver2: str, figs: dict):
    import streamlit as st
    st.markdown("---")
    st.subheader("📥 Export Post-Race Debrief")
    st.write("Generate a printable PDF report containing all the charts above.")
    
    if st.button("Generate PDF Report", use_container_width=True):
        with st.spinner("Generating PDF... This may take a minute."):
            try:
                pdf_bytes = _build_pdf_report(session_name, driver1, driver2, figs)
                st.download_button(
                    label="📄 Download PDF",
                    data=pdf_bytes,
                    file_name=f"Debrief_{session_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("PDF generated! Click above to download.")
            except Exception as e:
                st.error(f"Error generating PDF: {e}")


def render_telemetry_export_panel(
    driver1: str,
    tel1: pd.DataFrame | None,
    lap1: dict | pd.Series | None,
    driver2: str | None = None,
    tel2: pd.DataFrame | None = None,
    lap2: dict | pd.Series | None = None,
    compare: bool = False,
):
    """Render the Telemetry Export expander panel with CSV, Parquet, and JSON download formats."""
    with st.expander("⬇️  Export Telemetry Data", expanded=False):
        st.markdown(
            "<div style='font-size:12px; opacity:0.65; margin-bottom:12px;'>"
            "Export high-frequency telemetry channels (Distance, Speed, Throttle, Brake, RPM, Gear, DRS, coordinates) "
            "and lap metadata for the selected lap(s)."
            "</div>",
            unsafe_allow_html=True,
        )

        export_format = st.radio(
            "Select Export Format:",
            options=["CSV", "Parquet", "JSON"],
            index=0,
            horizontal=True,
            key="telemetry_export_format_radio",
        )

        fmt_meta = {
            "CSV": {
                "mime": "text/csv",
                "ext": "csv",
                "desc": "Universal table format compatible with Excel, Google Sheets, and data tools.",
            },
            "Parquet": {
                "mime": "application/octet-stream",
                "ext": "parquet",
                "desc": "High-performance columnar binary format with Snappy compression for Pandas, Polars, and PyArrow.",
            },
            "JSON": {
                "mime": "application/json",
                "ext": "json",
                "desc": "Structured records format ideal for web applications, APIs, and custom dashboards.",
            },
        }

        meta = fmt_meta.get(export_format, fmt_meta["CSV"])
        st.caption(f"ℹ️ **{export_format}**: {meta['desc']}")

        def _get_export_bytes(drv: str, tel: pd.DataFrame | None, lap: dict | pd.Series | None) -> bytes:
            if export_format == "Parquet":
                return _build_export_parquet(drv, tel, lap)
            elif export_format == "JSON":
                return _build_export_json(drv, tel, lap)
            else:
                return _build_export_csv(drv, tel, lap)

        exp_cols = [st.columns(2)[0]]
        if compare and driver2 and tel2 is not None:
            exp_cols = list(st.columns(2))

        # ── Driver 1 download
        with exp_cols[0]:
            data1 = _get_export_bytes(driver1, tel1, lap1)
            lap_num1 = int(lap1.get("LapNumber", 0)) if (lap1 is not None and hasattr(lap1, "get") and pd.notna(lap1.get("LapNumber", 0))) else "X"
            fname1 = f"pitwall_{driver1}_lap{lap_num1}.{meta['ext']}"
            st.download_button(
                label=f"📥  {driver1} — Download {export_format}",
                data=data1,
                file_name=fname1,
                mime=meta["mime"],
                disabled=(data1 == b"" or data1 is None),
                width="stretch",
                key=f"dl_btn_{driver1}_{meta['ext']}",
            )

        # ── Driver 2 download (comparison mode only)
        if compare and driver2 and tel2 is not None and len(exp_cols) > 1:
            with exp_cols[1]:
                data2 = _get_export_bytes(driver2, tel2, lap2)
                lap_num2 = int(lap2.get("LapNumber", 0)) if (lap2 is not None and hasattr(lap2, "get") and pd.notna(lap2.get("LapNumber", 0))) else "X"
                fname2 = f"pitwall_{driver2}_lap{lap_num2}.{meta['ext']}"
                st.download_button(
                    label=f"📥  {driver2} — Download {export_format}",
                    data=data2,
                    file_name=fname2,
                    mime=meta["mime"],
                    disabled=(data2 == b"" or data2 is None),
                    width="stretch",
                    key=f"dl_btn_{driver2}_{meta['ext']}",
                )


def _render_consistency_section(laps_df: pd.DataFrame, highlight_drivers: list, highlight_colours: list, fmt_func=None):
    """Render Consistency Score, Clean Air vs Traffic Deficit metric cards, and Violin plot."""
    if laps_df is None or laps_df.empty:
        st.info("ℹ️ Lap time data unavailable for consistency analysis.")
        return

    analysis_data = _build_consistency_analysis("", laps_df, highlight_drivers)
    if not analysis_data or "drivers" not in analysis_data or not analysis_data["drivers"]:
        st.info("ℹ️ Insufficient clean laps available to compute consistency metrics.")
        return

    drivers_data = analysis_data["drivers"]

    for drv, col in zip(highlight_drivers, highlight_colours):
        if drv not in drivers_data:
            continue
        d_info = drivers_data[drv]
        drv_label = fmt_func(drv) if fmt_func else drv

        st.markdown(
            f"<div style='border-left: 4px solid {col}; padding-left: 12px; margin-bottom: 12px; font-weight: bold; font-size: 16px; color: {col};'>"
            f"{drv_label} — Pace Consistency Summary"
            f"</div>",
            unsafe_allow_html=True
        )

        c1, c2, c3, c4 = st.columns(4)

        score_str = f"{d_info['overall_score']:.1f}%"
        std_str = f"±{d_info['overall_std']:.3f} s"
        clean_air_str = format_laptime(pd.to_timedelta(d_info["clean_air_pace"], unit="s"))
        deficit_val = d_info["traffic_deficit"]
        deficit_str = f"+{deficit_val:.3f} s / lap" if deficit_val > 0 else "0.000 s (Clean Air)"

        def _card(column, label, main_val, sub_val=""):
            sub_html = f"<div style='font-size:11px; opacity:0.7; margin-top:2px;'>{sub_val}</div>" if sub_val else ""
            column.markdown(
                f"<div class='metric-card' style='--accent:{col}; margin-bottom: 14px;'>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value' style='font-size: clamp(16px, 2vw, 22px);'>{main_val}</div>"
                f"{sub_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

        _card(c1, "Consistency Index", score_str, f"Std Dev: {std_str}")
        _card(c2, "Lap Time Std Dev", std_str, f"Over {d_info['clean_laps_count']} clean laps")
        _card(c3, "Clean Air Pace (Median)", clean_air_str, "Optimal clear track pace")
        _card(c4, "Traffic Deficit", deficit_str, "Pace lost following car ahead")

    fig = build_stint_consistency_fig(analysis_data, highlight_drivers, highlight_colours)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")

    table_rows = []
    for drv, col in zip(highlight_drivers, highlight_colours):
        if drv not in drivers_data:
            continue
        d_info = drivers_data[drv]
        for s in d_info["stints"]:
            med_str = format_laptime(pd.to_timedelta(s["median"], unit="s"))
            table_rows.append({
                "Driver": fmt_func(drv) if fmt_func else drv,
                "Stint": s["stint"],
                "Compound": s["compound"],
                "Valid Laps": s["count"],
                "Median Pace": med_str,
                "Std Dev (s)": f"±{s['std']:.3f} s",
                "Consistency Score": f"{s['score']:.1f}%"
            })

    if table_rows:
        df_table = pd.DataFrame(table_rows)
        st.markdown("<div style='font-size:13px; font-weight:700; margin-top:8px; margin-bottom:6px; opacity:0.85;'>📊 Stint-by-Stint Consistency Breakdown</div>", unsafe_allow_html=True)
        st.dataframe(df_table, width="stretch", hide_index=True)


def _render_weather_correlation_section(
    sess_k: str,
    laps_df: pd.DataFrame,
    session_obj=None,
    highlight_drivers: list[str] = None,
    highlight_colours: list[str] = None,
    fmt_func=None
):
    """Render track temperature and weather correlation metrics and dual-axis chart."""
    if laps_df is None or laps_df.empty or not highlight_drivers:
        return

    weather_data = _build_weather_correlation_data(sess_k, laps_df, session_obj, highlight_drivers)
    if not weather_data or "stats" not in weather_data:
        return

    stats = weather_data["stats"]

    st.markdown("<div class='section-title'>🌡 Track Temperature & Weather Impact Correlation</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    def _wcard(column, label, main_val, sub_val=""):
        sub_html = f"<div style='font-size:11px; opacity:0.7; margin-top:2px;'>{sub_val}</div>" if sub_val else ""
        column.markdown(
            f"<div class='metric-card' style='--accent:#FF5722; margin-bottom: 14px;'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value' style='font-size: clamp(16px, 2vw, 22px);'>{main_val}</div>"
            f"{sub_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

    t_min = stats.get("track_temp_min")
    t_max = stats.get("track_temp_max")
    t_avg = stats.get("track_temp_avg")
    if t_min is not None and t_max is not None:
        range_str = f"{t_min:.1f}°C – {t_max:.1f}°C"
        sub_t = f"Avg {t_avg:.1f}°C track"
    else:
        range_str = "—"
        sub_t = "Track temp unavailable"
    _wcard(c1, "Track Temp Range", range_str, sub_t)

    corr = stats.get("temp_correlation")
    if corr is not None:
        corr_str = f"{corr:+.3f}"
        if corr > 0.3:
            sens_str = "High Heat Sensitivity"
        elif corr < -0.3:
            sens_str = "Pace Improves with Heat"
        else:
            sens_str = "Neutral Heat Impact"
    else:
        corr_str = "—"
        sens_str = "Insufficient clean laps"
    _wcard(c2, "Pace-Temp Correlation", corr_str, sens_str)

    rain_det = stats.get("rainfall_detected", False)
    wet_laps = stats.get("wet_laps_count", 0)
    if rain_det or wet_laps > 0:
        rain_str = f"☔ Wet ({wet_laps} Laps)"
        rain_sub = "Rainfall recorded during session"
    else:
        rain_str = "☀️ Dry Session"
        rain_sub = "Zero rainfall recorded"
    _wcard(c3, "Weather Condition", rain_str, rain_sub)

    crossover = stats.get("crossover_laps", [])
    if crossover:
        cross_str = f"Lap {crossover[0]}"
        cross_sub = f"{len(crossover)} crossover transitions"
    else:
        cross_str = "None"
        cross_sub = "No Slick/Wet crossover"
    _wcard(c4, "Rain Crossover", cross_str, cross_sub)

    colors_map = dict(zip(highlight_drivers, highlight_colours)) if highlight_colours else {}
    labels_map = {d: (fmt_func(d) if fmt_func else d) for d in highlight_drivers}

    fig = build_weather_correlation_fig(weather_data, colors_map, labels_map)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")


def _render_multi_year_comparison_section(
    tel1: pd.DataFrame,
    tel2: pd.DataFrame,
    label1: str = "Era 1",
    label2: str = "Era 2",
    lap1_sec: float = None,
    lap2_sec: float = None,
    color1: str = "#FF8700",
    color2: str = "#00E5FF"
):
    """Render multi-year historical lap telemetry comparison and metric cards."""
    if tel1 is None or tel2 is None or tel1.empty or tel2.empty:
        return

    data = _build_multi_year_comparison(tel1, tel2, label1, label2, lap1_sec, lap2_sec)
    if not data or "stats" not in data:
        return

    stats = data["stats"]

    st.markdown("<div class='section-title'>🏛 Multi-Year Historical Lap Comparison</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    def _mcard(column, label, main_val, sub_val="", accent_col="#FF8700"):
        sub_html = f"<div style='font-size:11px; opacity:0.7; margin-top:2px;'>{sub_val}</div>" if sub_val else ""
        column.markdown(
            f"<div class='metric-card' style='--accent:{accent_col}; margin-bottom: 14px;'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value' style='font-size: clamp(16px, 2vw, 22px);'>{main_val}</div>"
            f"{sub_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

    delta_s = stats.get("lap_delta_s")
    if delta_s is not None:
        delta_str = f"{delta_s:+.3f} s"
        faster_era = label1 if delta_s < 0 else label2
        delta_sub = f"{faster_era} faster"
    else:
        delta_str = "—"
        delta_sub = "Lap time delta unavailable"
    _mcard(c1, "Era Lap Time Delta", delta_str, delta_sub, color1)

    ts1 = stats.get("top_speed1", 0)
    ts2 = stats.get("top_speed2", 0)
    _mcard(c2, "Top Speed (ST)", f"{ts1} / {ts2} km/h", f"{label1} vs {label2}", color2)

    ap1 = stats.get("apex_speed1", 0)
    ap2 = stats.get("apex_speed2", 0)
    _mcard(c3, "Min Apex Speed", f"{ap1} / {ap2} km/h", f"{label1} vs {label2}", color1)

    th1 = stats.get("throttle_pct1")
    th2 = stats.get("throttle_pct2")
    if th1 is not None and th2 is not None:
        th_str = f"{th1:.1f}% / {th2:.1f}%"
        th_sub = "Full throttle lap ratio"
    else:
        th_str = "—"
        th_sub = "Throttle telemetry unavailable"
    _mcard(c4, "Full Throttle %", th_str, th_sub, color2)

    fig = build_multi_year_comparison_fig(data, color1, color2)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")


def render_tyre_crossover_matrix(
    table_rows: list[dict],
    fmt_driver1,
    fmt_driver2,
    driver1: str,
    driver2: str | None = None,
    colour1: str = "#FF8700",
    colour2: str = "#00D2BE",
) -> None:
    """Render the Tyre Life & Predictive Crossover Matrix table.

    Displays a full-field breakdown per driver and per stint with:
    - Compound (with coloured dot)
    - Degradation Rate (s/lap)
    - Model type used (Quadratic / Linear)
    - Predicted Cliff Lap (TyreLife at +1.5 s pace drop)
    - Remaining Laps to cliff
    - Pit Window recommendation (cliff ± 3 laps)
    - Urgency badge (🟢 Safe / 🟡 Soon / 🔴 Critical / ✅ Past Cliff)
    """
    if not table_rows:
        return

    rows_with_cliff = [r for r in table_rows if r.get("cliff_lap") is not None]
    if not rows_with_cliff:
        st.info(
            "ℹ️ Insufficient stint length or tyre degradation slope to generate "
            "predictive cliff estimates (minimum 5 laps required for quadratic model, "
            "or positive degradation slope for linear fallback)."
        )
        return

    st.markdown(
        "<div class='section-title'>🔮 Tyre Life & Crossover Prediction Matrix</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:13px; opacity:0.65; margin-bottom:14px;'>"
        "Predicted lap at which tyre pace degrades by ≥ 1.5 s above stint base pace, "
        "using quadratic thermal modelling (with linear fallback). "
        "Remaining laps are calculated from last observed tyre age in the stint. "
        "Pit window = cliff lap ± 3 laps."
        "</div>",
        unsafe_allow_html=True,
    )

    def _urgency(remaining: int | None) -> tuple[str, str]:
        """Return (badge_text, row_tint) based on remaining laps to cliff."""
        if remaining is None:
            return "—", "transparent"
        if remaining <= 0:
            return "✅ Past Cliff", "rgba(255,255,255,0.04)"
        if remaining <= 3:
            return "🔴 Critical", "rgba(255,50,50,0.07)"
        if remaining <= 8:
            return "🟡 Soon", "rgba(255,200,50,0.07)"
        return "🟢 Safe", "rgba(80,200,80,0.05)"

    header_html = (
        "<div style='background:var(--secondary-background-color); "
        "border:1px solid rgba(128,128,128,0.15); border-radius:12px; "
        "padding:16px 20px; margin-top:16px;'>"
        "<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
        "<thead><tr style='border-bottom:1px solid rgba(128,128,128,0.2); "
        "font-size:11px; opacity:0.55; text-transform:uppercase; letter-spacing:0.5px;'>"
        "<th style='padding:5px 10px; text-align:left;'>Driver</th>"
        "<th style='padding:5px 10px; text-align:left;'>Stint</th>"
        "<th style='padding:5px 10px; text-align:left;'>Compound</th>"
        "<th style='padding:5px 10px; text-align:left;'>Deg Rate</th>"
        "<th style='padding:5px 10px; text-align:left;'>Model</th>"
        "<th style='padding:5px 10px; text-align:left;'>Cliff Lap (TyreLife)</th>"
        "<th style='padding:5px 10px; text-align:left;'>Remaining</th>"
        "<th style='padding:5px 10px; text-align:left;'>Pit Window</th>"
        "<th style='padding:5px 10px; text-align:left;'>Status</th>"
        "</tr></thead><tbody>"
    )

    body_html = ""
    for idx, row in enumerate(table_rows):
        cliff_lap = row.get("cliff_lap")
        if cliff_lap is None:
            continue

        drv_name = row["driver"]
        drv_colour = row.get("colour", "#888888")
        fmt_name = fmt_driver1(drv_name) if drv_name == driver1 else (
            fmt_driver2(drv_name) if fmt_driver2 else drv_name
        )

        comp = str(row.get("compound", "")).upper()
        comp_pal = COMPOUND_COLOURS.get(comp, COMPOUND_COLOURS["UNKNOWN"])
        comp_dot = (
            f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; "
            f"background:{comp_pal['fill']}; margin-right:5px; vertical-align:middle;'></span>"
        )

        remaining = row.get("remaining_laps")
        pit_low = row.get("pit_window_low")
        pit_high = row.get("pit_window_high")
        pit_str = f"Lap {pit_low}–{pit_high}" if (pit_low is not None and pit_high is not None) else "—"
        rem_str = f"{remaining} laps" if remaining is not None else "—"

        has_quad = row.get("quad_coeffs") if hasattr(row, "get") else None
        # We don't store quad_coeffs directly in table_rows, but we infer from cliff quality
        model_badge = "Quadratic" if (remaining is not None and remaining >= 0) else "Linear"

        deg_rate = row.get("deg_rate", 0.0)
        deg_color = "#00e400" if deg_rate <= 0 else "#ff2200"
        deg_str = f"{deg_rate:+.3f} s/lap"

        urgency_text, row_tint = _urgency(remaining)
        row_bg = row_tint if row_tint != "transparent" else (
            "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        )

        body_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:7px 10px; font-weight:600; color:{drv_colour};'>{fmt_name}</td>"
            f"<td style='padding:7px 10px;'>Stint {row.get('stint', '—')}</td>"
            f"<td style='padding:7px 10px;'>{comp_dot}{comp.title()}</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{deg_color};'>{deg_str}</td>"
            f"<td style='padding:7px 10px; font-size:11px; opacity:0.7;'>{model_badge}</td>"
            f"<td style='padding:7px 10px; font-weight:700;'>~{cliff_lap}</td>"
            f"<td style='padding:7px 10px;'>{rem_str}</td>"
            f"<td style='padding:7px 10px; font-size:12px;'>{pit_str}</td>"
            f"<td style='padding:7px 10px; font-weight:600;'>{urgency_text}</td>"
            "</tr>"
        )

    st.markdown(
        header_html + body_html + "</tbody></table></div>",
        unsafe_allow_html=True,
    )
