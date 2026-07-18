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
    _fmt_driver1, _fmt_driver2
)
from src.charts.plotly import (
    _lap_history_fig, _fuel_pace_fig, _stint_fig, _gap_chart_fig,
    _speed_map_fig, _input_map_fig, build_replay_fig, build_corner_fig
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
            with col_st2:
                if compare and stats2:
                    st.markdown(f"<div style='border-left: 4px solid {other_colour}; padding-left: 12px; margin-bottom: 16px;'><div style='font-size: 13px; opacity: 0.7;'>Driver 2</div><div style='font-size: 18px; font-weight: bold; color: {other_colour};'>{fmt_func(other_driver) if fmt_func else other_driver}</div></div>", unsafe_allow_html=True)
                    st.write(f"Apex Speed: **{stats2['apex_speed']:.1f} km/h**")
                    st.write(f"Braking Distance to Apex: **{stats2['dist_to_apex']:.1f} m**" if stats2["braking_dist"] is not None else "Braking Distance to Apex: **—**")

            st.plotly_chart(fig_corner, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Load a session to view corner analysis.")
