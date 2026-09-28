import plotly.graph_objects as go
import numpy as np
import pandas as pd
import streamlit as st
from plotly.subplots import make_subplots
from src.ui.styles import COMPOUND_COLOURS
from src.data.loader import _get_telemetry_for_map, _team_colour

# ── Flag zone colour map ──────────────────────────────────────────────────────
_FLAG_COLOURS = {
    "SAFETY CAR":         "rgba(255,140,0,0.15)",
    "VIRTUAL SAFETY CAR": "rgba(255,223,0,0.12)",
    "RED FLAG":           "rgba(220,0,0,0.15)",
    "YELLOW FLAG":        "rgba(255,200,0,0.10)",
}


def _add_flag_zones(fig: go.Figure, rc_messages, max_lap: int = 70) -> None:
    """Add semi-transparent flag zone rectangles to a Plotly figure that uses LapNumber on x-axis."""
    if rc_messages is None or rc_messages.empty:
        return
    if "LapNumber" not in rc_messages.columns or "FlagType" not in rc_messages.columns:
        return

    df = rc_messages.dropna(subset=["LapNumber"]).copy()
    df["LapNumber"] = df["LapNumber"].astype(int)

    flag_types = ["SAFETY CAR", "VIRTUAL SAFETY CAR", "RED FLAG", "YELLOW FLAG"]
    for _, row in df.iterrows():
        ftype = row["FlagType"]
        if ftype not in flag_types:
            continue
        start_lap = int(row["LapNumber"])
        # Find next CLEAR after this flag
        clears = df[(df["FlagType"] == "CLEAR") & (df["LapNumber"] > start_lap)]
        end_lap = int(clears["LapNumber"].iloc[0]) if not clears.empty else start_lap + 4
        end_lap = min(end_lap, max_lap)
        fig.add_vrect(
            x0=start_lap - 0.5, x1=end_lap + 0.5,
            fillcolor=_FLAG_COLOURS[ftype],
            layer="below", line_width=0,
            annotation_text=ftype.replace(" FLAG", ""),
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color="rgba(255,255,255,0.6)",
        )


def _lap_history_fig(drivers_data: list, highlight_laps: list, rc_messages=None) -> go.Figure:
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
    # Overlay flag zones
    if rc_messages is not None:
        try:
            all_laps = []
            for _, _, laps in drivers_data:
                if laps is not None and not laps.empty and "LapNumber" in laps.columns:
                    all_laps.extend(laps["LapNumber"].tolist())
            max_lap = int(max(all_laps)) if all_laps else 70
        except Exception:
            max_lap = 70
        _add_flag_zones(fig, rc_messages, max_lap)
    return fig


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



def _speed_map_fig(l_obj, drv: str, col: str, sess_key: str, l_obj2=None, drv2=None, col2=None):
    tel = _get_telemetry_for_map(l_obj, drv, sess_key)
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
        tel2 = _get_telemetry_for_map(l_obj2, drv2, sess_key)
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
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=10, b=10),
                height=560,
                showlegend=False
            )
            return fig, warning_msg
            
    # Fallback to single driver outline or outline-only
    fig.add_trace(go.Scatter(
        x=tel["X"], y=tel["Y"],
        mode="lines",
        line=dict(color=col, width=16),
        name=drv,
        hovertemplate=f"<b>{drv}</b><extra></extra>"
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=10, b=10),
        height=560,
        showlegend=False
    )
    return fig, warning_msg


def _input_map_fig(l_obj, drv: str, col: str, sess_key: str):
    tel = _get_telemetry_for_map(l_obj, drv, sess_key)
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
                f"<b>{drv} Inputs</b><br>"
                "Throttle: %{customdata[0]:.0f}%<br>"
                "Brake: %{customdata[1]}<extra></extra>"
            ),
            customdata=np.column_stack((tel["Throttle"], tel["Brake"]))
        ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=10, b=10),
        height=560,
        showlegend=False
    )
    return fig, warning_msg


def build_replay_fig(session_obj):
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
        return None, "No position data available for this session."

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
        xi = np.interp(t_grid, d["t"], d["x"], left=np.nan, right=np.nan)
        yi = np.interp(t_grid, d["t"], d["y"], left=np.nan, right=np.nan)
        retired_at = d["t"][-1]
        xi[t_grid > retired_at + T_STEP] = np.nan
        yi[t_grid > retired_at + T_STEP] = np.nan
        grids[drv_num] = (xi, yi)
        valid_drvs.append(drv_num)

    if not valid_drvs:
        return None, "Insufficient position data for animation."

    # ── Track outline from the driver with most data points
    longest = max(all_data, key=lambda k: len(all_data[k]["t"]))
    track_x = all_data[longest]["x"]
    track_y = all_data[longest]["y"]

    # Thin track to ~1000 pts for display
    thin = max(1, len(track_x) // 1000)
    track_x = track_x[::thin]
    track_y = track_y[::thin]

    def _fmt(sec: float) -> str:
        m, s = int(sec // 60), int(sec % 60)
        return f"{m:02d}:{s:02d}"

    # ── Build initial traces
    init_traces = [
        go.Scatter(
            x=track_x, y=track_y,
            mode="lines",
            line=dict(color="gray", width=14),
            showlegend=False, hoverinfo="skip",
        )
    ]
    for drv_num in valid_drvs:
        meta  = drv_meta.get(drv_num, {"abbr": drv_num, "colour": "#888"})
        xi, yi = grids[drv_num]
        px, py = xi[0], yi[0]
        init_traces.append(go.Scatter(
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

    # ── Build animation frames
    frames = []
    slider_steps = []
    for f_i, t_val in enumerate(t_grid):
        label = _fmt(t_val)
        fdata = [
            go.Scatter(
                x=track_x, y=track_y,
                mode="lines",
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
        hoverlabel=dict(bgcolor="#111", font_color="#eee", bordercolor="#333"),
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

    replay_fig = go.Figure(data=init_traces, layout=layout, frames=frames)
    return replay_fig, None


def build_corner_fig(win1, win2, driver, other_driver, colour, other_colour, apex_dist, fmt_func=None):
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

        max_steering = None
        if "Steering" in df.columns and pd.notna(df["Steering"]).any():
            steering_num = pd.to_numeric(df["Steering"], errors="coerce")
            if not steering_num.isna().all():
                max_steering = float(steering_num.abs().max())

        drs_active = False
        if "DRS" in df.columns and pd.notna(df["DRS"]).any():
            drs_num = pd.to_numeric(df["DRS"], errors="coerce")
            drs_active = bool((drs_num > 0).any())

        return {
            "apex_speed": apex_speed,
            "apex_dist": apex_d,
            "apex_x": apex_x,
            "apex_y": apex_y,
            "braking_dist": braking_d,
            "braking_x": braking_x,
            "braking_y": braking_y,
            "dist_to_apex": dist_to_apex,
            "max_steering": max_steering,
            "drs_active": drs_active
        }

    stats1 = compute_stats(win1)
    stats2 = compute_stats(win2) if win2 is not None else None

    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=(
            "<b>Racing Line Overlay</b>",
            "<b>Speed Profile</b>",
            "<b>Steering Angle (° degrees)</b>",
            "<b>DRS Activation Status</b>"
        ),
        vertical_spacing=0.06,
        row_heights=[0.34, 0.24, 0.22, 0.20]
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

    if "Steering" in win1.columns:
        fig.add_trace(go.Scatter(
            x=win1["Distance"] - apex_dist, y=pd.to_numeric(win1["Steering"], errors="coerce"),
            mode="lines",
            line=dict(color=colour, width=2.5),
            name=driver,
            legendgroup=driver,
            showlegend=False,
            hovertemplate=f"<b>{driver}</b><br>Dist: %{{x:.1f}} m from apex<br>Steering: %{{y:.1f}}°<extra></extra>"
        ), row=3, col=1)

    if win2 is not None and "Steering" in win2.columns:
        fig.add_trace(go.Scatter(
            x=win2["Distance"] - apex_dist, y=pd.to_numeric(win2["Steering"], errors="coerce"),
            mode="lines",
            line=dict(color=other_colour, width=2.5, dash="dash"),
            name=other_driver,
            legendgroup=other_driver,
            showlegend=False,
            hovertemplate=f"<b>{other_driver}</b><br>Dist: %{{x:.1f}} m from apex<br>Steering: %{{y:.1f}}°<extra></extra>"
        ), row=3, col=1)

    if "DRS" in win1.columns:
        drs1_val = (pd.to_numeric(win1["DRS"], errors="coerce") > 0).astype(int)
        fig.add_trace(go.Scatter(
            x=win1["Distance"] - apex_dist, y=drs1_val,
            mode="lines",
            line=dict(color=colour, width=2.5),
            name=driver,
            legendgroup=driver,
            showlegend=False,
            hovertemplate=f"<b>{driver}</b><br>Dist: %{{x:.1f}} m from apex<br>DRS: %{{y}}<extra></extra>"
        ), row=4, col=1)

    if win2 is not None and "DRS" in win2.columns:
        drs2_val = (pd.to_numeric(win2["DRS"], errors="coerce") > 0).astype(int)
        fig.add_trace(go.Scatter(
            x=win2["Distance"] - apex_dist, y=drs2_val,
            mode="lines",
            line=dict(color=other_colour, width=2.5, dash="dash"),
            name=other_driver,
            legendgroup=other_driver,
            showlegend=False,
            hovertemplate=f"<b>{other_driver}</b><br>Dist: %{{x:.1f}} m from apex<br>DRS: %{{y}}<extra></extra>"
        ), row=4, col=1)

    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1, row=1, col=1)
    fig.update_yaxes(visible=False, row=1, col=1)

    fig.update_xaxes(gridcolor="rgba(128,128,128,0.2)", row=2, col=1)
    fig.update_yaxes(title_text="Speed (km/h)", gridcolor="rgba(128,128,128,0.2)", row=2, col=1)

    fig.update_xaxes(gridcolor="rgba(128,128,128,0.2)", row=3, col=1)
    fig.update_yaxes(title_text="Steering (°)", gridcolor="rgba(128,128,128,0.2)", row=3, col=1)

    fig.update_xaxes(title_text="Distance relative to apex (m)", gridcolor="rgba(128,128,128,0.2)", row=4, col=1)
    fig.update_yaxes(title_text="DRS Active", tickvals=[0, 1], ticktext=["OFF", "ON"], gridcolor="rgba(128,128,128,0.2)", row=4, col=1)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,20,0.6)",
        font=dict(color="#e8e8e8", family="Inter, sans-serif"),
        height=820,
        margin=dict(l=60, r=40, t=40, b=40),
        showlegend=True,
    )
    return fig, stats1, stats2


def build_tyre_deg_fig(
    _deg_d1,
    _deg_d2,
    driver1: str,
    driver2: str | None,
    colour1: str,
    colour2: str | None,
    compare: bool,
    show_fuel_corrected: bool = True
):
    fig_deg = go.Figure()
    table_rows = []
    has_decoupled = False

    def process_driver_deg(deg_data, drv_name, drv_colour, is_primary):
        nonlocal has_decoupled
        if not deg_data:
            return
        marker_symbol = "circle" if is_primary else "square"
        line_dash = "solid" if is_primary else "dash"

        for s in deg_data:
            stint_num = s["stint"]
            compound = s["compound"]
            laps_list = s["laps"]
            is_decoupled = s.get("is_fuel_decoupled", False) and show_fuel_corrected
            if is_decoupled:
                has_decoupled = True

            x_vals = np.array([l["TyreLife"] for l in laps_list], dtype=float)
            if is_decoupled and "LapTime_s_fuel_corr" in laps_list[0]:
                y_vals = np.array([l["LapTime_s_fuel_corr"] for l in laps_list], dtype=float)
                y_raw = np.array([l.get("LapTime_s_raw", l.get("LapTime_s")) for l in laps_list], dtype=float)
            else:
                y_vals = np.array([l.get("LapTime_s_raw", l["LapTime_s"]) for l in laps_list], dtype=float)
                y_raw = y_vals

            # Regression slope and intercept
            if is_decoupled:
                slope = s.get("fuel_corrected_slope", s.get("slope"))
                intercept = s.get("fuel_corrected_base_pace", s.get("base_pace"))
            else:
                slope = s.get("raw_slope", s.get("slope"))
                intercept = s.get("raw_base_pace", s.get("base_pace"))

            if slope is None:
                slope = float(np.polyfit(x_vals, y_vals, 1)[0])
            if intercept is None:
                intercept = float(np.polyfit(x_vals, y_vals, 1)[1])

            raw_slope = s.get("raw_slope", slope)
            fuel_effect = s.get("fuel_effect", 0.0)

            label_str = f"{drv_name} - Stint {stint_num} ({compound})"
            if is_decoupled:
                label_str += " [Fuel Decoupled]"

            # ── Scatter points ──────────────────────────────────────────────
            if is_decoupled:
                custom_data = np.stack((y_vals, y_raw), axis=-1)
                hover_template = (
                    f"<b>{drv_name}</b> (Stint {stint_num} - {compound})<br>"
                    "Tyre Age: %{x} laps<br>"
                    "True Pace: %{customdata[0]:.3f} s<br>"
                    "Raw Lap Time: %{customdata[1]:.3f} s<br>"
                    f"True Deg Rate: {slope:+.3f} s/lap<br>"
                    f"Raw Timing Deg: {raw_slope:+.3f} s/lap<br>"
                    f"Fuel Offset: -{fuel_effect:.3f} s/lap<extra></extra>"
                )
            else:
                custom_data = y_vals
                hover_template = (
                    f"<b>{drv_name}</b> (Stint {stint_num} - {compound})<br>"
                    "Tyre Age: %{x} laps<br>"
                    "Lap Time: %{customdata:.3f} s<br>"
                    f"Deg Rate: {slope:+.3f} s/lap<extra></extra>"
                )

            fig_deg.add_trace(go.Scatter(
                x=x_vals, y=y_vals,
                mode="markers",
                marker=dict(
                    color=drv_colour,
                    symbol=marker_symbol,
                    size=8,
                    line=dict(color="rgba(255,255,255,0.4)", width=1)
                ),
                name=label_str,
                legendgroup=label_str,
                hovertemplate=hover_template,
                customdata=custom_data
            ))

            # ── Linear regression trendline ─────────────────────────────────
            x_extend = np.linspace(x_vals.min(), x_vals.max() + 5, 150)
            y_line = slope * x_extend + intercept
            fig_deg.add_trace(go.Scatter(
                x=x_extend, y=y_line,
                mode="lines",
                line=dict(color=drv_colour, width=1.5, dash=line_dash),
                name=f"{label_str} Linear Trend",
                legendgroup=label_str,
                showlegend=False,
                hoverinfo="skip"
            ))

            # ── Quadratic degradation curve overlay ─────────────────────────
            quad_coeffs = s.get("quad_coeffs") if is_decoupled else s.get("raw_quad_coeffs", s.get("quad_coeffs"))
            if quad_coeffs is not None:
                a, b, c = quad_coeffs
                x_quad = np.linspace(x_vals.min(), x_vals.max() + 8, 200)
                y_quad = np.polyval([a, b, c], x_quad)
                fig_deg.add_trace(go.Scatter(
                    x=x_quad, y=y_quad,
                    mode="lines",
                    line=dict(
                        color=drv_colour,
                        width=2.5,
                        dash="solid" if is_primary else "longdash"
                    ),
                    name=f"{label_str} Thermal Curve",
                    legendgroup=label_str,
                    showlegend=False,
                    opacity=0.55,
                    hoverinfo="skip"
                ))

            # ── Cliff lap vertical marker ────────────────────────────────────
            cliff_lap = s.get("cliff_lap") if is_decoupled else s.get("raw_cliff_lap", s.get("cliff_lap"))
            if cliff_lap is not None:
                fig_deg.add_vline(
                    x=cliff_lap,
                    line_width=1.5,
                    line_dash="dot",
                    line_color=drv_colour,
                    annotation_text=f"⚠ Cliff ~Lap {cliff_lap}" + (" (True)" if is_decoupled else ""),
                    annotation_position="top right",
                    annotation_font_size=10,
                    annotation_font_color=drv_colour,
                )

            # ── Store stats for summary table ────────────────────────────────
            table_rows.append({
                "driver": drv_name,
                "colour": drv_colour,
                "stint": stint_num,
                "compound": compound,
                "laps": len(x_vals),
                "deg_rate": slope,
                "raw_deg_rate": raw_slope,
                "true_deg_rate": s.get("true_deg_rate", slope),
                "base_pace": intercept,
                "fuel_effect": fuel_effect,
                "is_fuel_decoupled": is_decoupled,
                "cliff_lap": cliff_lap,
                "raw_cliff_lap": s.get("raw_cliff_lap"),
                "remaining_laps": s.get("remaining_laps"),
                "pit_window_low": s.get("pit_window_low"),
                "pit_window_high": s.get("pit_window_high"),
                "last_tyre_life": s.get("last_tyre_life"),
            })

    process_driver_deg(_deg_d1, driver1, colour1, is_primary=True)
    if compare and _deg_d2:
        process_driver_deg(_deg_d2, driver2, colour2, is_primary=False)

    y_title = "Fuel-Corrected Pace (s) [0-Fuel Ref]" if has_decoupled else "Lap Time (Seconds)"

    fig_deg.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Tyre Age (Laps)",
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
        ),
        yaxis=dict(
            title=y_title,
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=False
        ),
        height=450,
        margin=dict(l=0, r=40, t=20, b=10),
        showlegend=True,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    return fig_deg, table_rows


def build_grid_heatmap_fig(heatmap_data: dict, mode: str = "Sectors") -> go.Figure | None:
    """Build an interactive Plotly Heatmap for multi-driver grid analysis."""
    if not heatmap_data or "deltas" not in heatmap_data or "drivers" not in heatmap_data:
        return None

    drivers = heatmap_data["drivers"]
    columns = heatmap_data["columns"]
    deltas = heatmap_data["deltas"]
    values = heatmap_data.get("values", [])

    if mode == "Speed":
        # Deficit in km/h: 0 (top speed) -> Emerald Green, larger deficit -> Dark Red
        colorscale = [
            [0.0, "#00E676"],   # Top speed (0 km/h deficit)
            [0.2, "#66BB6A"],
            [0.5, "#FFD54F"],   # Moderate deficit
            [0.8, "#FF7043"],
            [1.0, "#FF5252"],   # Highest speed deficit
        ]
        unit_label = "km/h deficit"
        hover_fmt = "<b>%{y} · %{x}</b><br>Value: %{customdata}<br>Deficit: -%{z:.1f} km/h<extra></extra>"
    else:
        # Time delta in seconds: 0s (P1) -> Emerald Green, larger delta -> Coral Red
        colorscale = [
            [0.0, "#00E676"],   # 0.000s delta (P1 / Best)
            [0.15, "#81C784"],  # +0.1s - +0.3s
            [0.4, "#FFD54F"],   # +0.5s
            [0.7, "#FF7043"],   # +1.0s
            [1.0, "#FF5252"],   # +2.0s+ deficit
        ]
        unit_label = "seconds delta"
        hover_fmt = "<b>%{y} · %{x}</b><br>Lap/Split: %{customdata}<br>Delta: +%{z:.3f}s<extra></extra>"

    fig = go.Figure(data=go.Heatmap(
        z=deltas,
        x=columns,
        y=drivers,
        customdata=values,
        colorscale=colorscale,
        colorbar=dict(
            title=dict(text=unit_label, font=dict(size=12)),
            thickness=14,
            len=0.85,
        ),
        hovertemplate=hover_fmt,
        showscale=True,
    ))

    calc_height = max(420, len(drivers) * 32 + 100)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Sector / Lap / Speed Metric",
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
            side="top" if len(columns) > 15 else "bottom",
        ),
        yaxis=dict(
            title="Driver",
            autorange="reversed",  # P1 at top
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
        ),
        height=calc_height,
        margin=dict(l=60, r=40, t=40, b=40),
    )

    return fig

def build_undercut_chart(l1_df, l2_df, d1_label, d2_label, color1, color2, start_lap, end_lap, p1_lap, p2_lap):
    """
    Plots the gap (Driver 1 - Driver 2) over a specific pit window.
    """
    laps_range = list(range(int(start_lap), int(end_lap) + 1))
    
    gaps = []
    plot_laps = []
    
    for l in laps_range:
        try:
            t1 = l1_df[l1_df['LapNumber'] == l]['Time'].iloc[0]
            t2 = l2_df[l2_df['LapNumber'] == l]['Time'].iloc[0]
            if pd.notna(t1) and pd.notna(t2):
                gaps.append((t1 - t2).total_seconds())
                plot_laps.append(l)
        except Exception:
            continue
            
    fig = go.Figure()
    if not plot_laps:
        return fig
        
    fig.add_trace(go.Scatter(
        x=plot_laps, y=gaps, mode="lines+markers",
        line=dict(color="#ffffff", width=2),
        marker=dict(size=8, color="#ffffff"),
        name="Time Gap (D1 - D2)"
    ))
    
    # Add vertical lines for pit laps
    if p1_lap in plot_laps:
        fig.add_vline(x=p1_lap, line_width=1, line_dash="dash", line_color=color1,
                      annotation_text=f"{d1_label} Pits", annotation_position="top right")
    if p2_lap in plot_laps:
        fig.add_vline(x=p2_lap, line_width=1, line_dash="dash", line_color=color2,
                      annotation_text=f"{d2_label} Pits", annotation_position="top left")
                      
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=30, b=40),
        xaxis=dict(title="Lap Number", tickmode="linear", tick0=start_lap, dtick=1, showgrid=False, zeroline=False),
        yaxis=dict(title="Gap (s) [Negative: D1 Ahead]", zeroline=True, zerolinecolor="rgba(255,255,255,0.2)", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        showlegend=False,
        height=350
    )
    return fig


def build_stint_consistency_fig(consistency_data: dict, highlight_drivers: list, highlight_colours: list) -> go.Figure | None:
    """
    Build Plotly Violin/Boxplot chart comparing driver pace distributions per stint.
    """
    if not consistency_data or "drivers" not in consistency_data:
        return None

    drivers_dict = consistency_data["drivers"]
    fig = go.Figure()

    driver_color_map = {}
    for drv, col in zip(highlight_drivers, highlight_colours):
        if drv:
            driver_color_map[drv] = col

    has_traces = False
    for drv in highlight_drivers:
        if drv not in drivers_dict:
            continue
        drv_info = drivers_dict[drv]
        colour = driver_color_map.get(drv, "#FF8700")

        for s_info in drv_info["stints"]:
            stint_num = s_info["stint"]
            compound = s_info["compound"]
            laps_df = s_info["laps_df"]
            if laps_df.empty:
                continue

            trace_name = f"{drv} - Stint {stint_num} ({compound})"

            hover_text = [
                f"<b>{drv}</b> (Stint {stint_num} - {compound})<br>"
                f"Lap {row['LapNumber']}<br>"
                f"Lap Time: {int(row['LapTime_s']//60)}:{row['LapTime_s']%60:06.3f}<br>"
                f"Tyre Age: {row.get('TyreLife', 'N/A')}"
                for _, row in laps_df.iterrows()
            ]

            fig.add_trace(go.Violin(
                y=laps_df["LapTime_s"],
                x=[trace_name] * len(laps_df),
                name=trace_name,
                box_visible=True,
                meanline_visible=True,
                points="all",
                jitter=0.25,
                marker=dict(size=5, color=colour),
                line=dict(color=colour, width=1.5),
                text=hover_text,
                hoverinfo="text",
            ))
            has_traces = True

    if not has_traces:
        return None

    fig.update_layout(
        title=dict(
            text="Stint Pace Distribution & Driver Consistency (Violin / Boxplot)",
            font=dict(size=15, color="#e8e8e8")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e8e8e8", family="Inter, sans-serif"),
        yaxis=dict(
            title="Lap Time (seconds)",
            gridcolor="rgba(128,128,128,0.2)",
            zerolinecolor="rgba(128,128,128,0.2)",
            autorange="reversed",
        ),
        xaxis=dict(
            title="Driver & Stint",
            gridcolor="rgba(128,128,128,0.2)",
            tickangle=-15,
        ),
        margin=dict(l=50, r=40, t=60, b=60),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def build_weather_correlation_fig(
    weather_data: dict,
    driver_colors: dict[str, str] = None,
    driver_labels: dict[str, str] = None
) -> go.Figure | None:
    """
    Build dual-axis Plotly chart overlaying Track Temperature (°C) and Driver Lap Times.
    Highlights rain crossover windows and rain intensity.
    """
    if not weather_data or "laps_weather_df" not in weather_data:
        return None

    laps_w_df = weather_data["laps_weather_df"]
    driver_laps = weather_data.get("driver_laps", {})
    stats = weather_data.get("stats", {})

    if laps_w_df is None or laps_w_df.empty:
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. Plot Track Temperature on Secondary Y-axis
    if "TrackTemp" in laps_w_df.columns and not laps_w_df["TrackTemp"].isna().all():
        fig.add_trace(
            go.Scatter(
                x=laps_w_df["LapNumber"],
                y=laps_w_df["TrackTemp"],
                mode="lines",
                name="Track Temp (°C)",
                line=dict(color="#FF5722", width=3),
                fill="tozeroy",
                fillcolor="rgba(255, 87, 34, 0.08)",
                hovertemplate="<b>Lap %{x}</b><br>Track Temp: %{y:.1f}°C<extra></extra>",
            ),
            secondary_y=True,
        )

    # 2. Plot Driver Lap Times on Primary Y-axis
    colors = driver_colors or {}
    labels = driver_labels or {}

    for drv, df_drv in driver_laps.items():
        if df_drv.empty:
            continue

        clr = colors.get(drv, "#00E5FF")
        lbl = labels.get(drv, drv)

        fig.add_trace(
            go.Scatter(
                x=df_drv["LapNumber"],
                y=df_drv["LapTime_s"],
                mode="lines+markers",
                name=f"{lbl} Pace",
                line=dict(color=clr, width=2),
                marker=dict(size=6, color=clr),
                hovertemplate=f"<b>{lbl}</b><br>Lap %{{x}}<br>Lap Time: %{{y:.3f}}s<extra></extra>",
            ),
            secondary_y=False,
        )

    # 3. Add Rain Crossover Vlines
    crossover_laps = stats.get("crossover_laps", [])
    for lap_crossover in crossover_laps:
        fig.add_vline(
            x=lap_crossover,
            line=dict(color="#00E5FF", width=2, dash="dash"),
            annotation_text=f"☔ Rain Crossover L{lap_crossover}",
            annotation_position="top left",
            annotation_font=dict(color="#00E5FF", size=11),
        )

    # 4. Highlight wet laps shading if rainfall was detected
    if "Rainfall" in laps_w_df.columns:
        wet_df = laps_w_df[laps_w_df["Rainfall"] == True]
        if not wet_df.empty:
            for _, r_row in wet_df.iterrows():
                l_num = r_row["LapNumber"]
                fig.add_vrect(
                    x0=l_num - 0.5,
                    x1=l_num + 0.5,
                    fillcolor="rgba(0, 191, 255, 0.12)",
                    layer="below",
                    line_width=0,
                )

    fig.update_layout(
        title=dict(
            text="<b>Track Temperature & Weather Impact Correlation</b>",
            font=dict(size=16, color="#ffffff", family="Inter, sans-serif"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,20,0.6)",
        font=dict(color="#e8e8e8", family="Inter, sans-serif"),
        margin=dict(l=60, r=60, t=60, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0.5)",
        ),
        hovermode="x unified",
    )

    fig.update_xaxes(
        title_text="Lap Number",
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
    )

    fig.update_yaxes(
        title_text="Lap Time (seconds)",
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
        secondary_y=False,
    )

    fig.update_yaxes(
        title_text="Track Temperature (°C)",
        gridcolor="rgba(255, 87, 34, 0.15)",
        secondary_y=True,
    )

    return fig


def build_multi_year_comparison_fig(
    multi_year_data: dict,
    color1: str = "#FF8700",
    color2: str = "#00E5FF"
) -> go.Figure | None:
    """
    Build dual-subplot Plotly figure comparing speed profiles (km/h) and continuous time delta (s)
    across two different seasons / technical regulation eras.
    """
    if not multi_year_data or "grid" not in multi_year_data:
        return None

    grid = multi_year_data["grid"]
    speed1 = multi_year_data["speed1"]
    speed2 = multi_year_data["speed2"]
    time_delta = multi_year_data.get("time_delta")
    stats = multi_year_data.get("stats", {})

    lbl1 = stats.get("label1", "Era 1")
    lbl2 = stats.get("label2", "Era 2")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(
            f"<b>Speed Telemetry Profile ({lbl1} vs {lbl2})</b>",
            f"<b>Continuous Time Delta (Δ s per meter)</b>"
        )
    )

    # 1. Speed Traces (Subplot 1)
    fig.add_trace(
        go.Scatter(
            x=grid,
            y=speed1,
            mode="lines",
            name=lbl1,
            line=dict(color=color1, width=2.5),
            hovertemplate=f"<b>{lbl1}</b><br>Dist: %{{x:.0f}}m<br>Speed: %{{y:.1f}} km/h<extra></extra>",
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=grid,
            y=speed2,
            mode="lines",
            name=lbl2,
            line=dict(color=color2, width=2.5, dash="dash"),
            hovertemplate=f"<b>{lbl2}</b><br>Dist: %{{x:.0f}}m<br>Speed: %{{y:.1f}} km/h<extra></extra>",
        ),
        row=1, col=1
    )

    # 2. Time Delta Trace (Subplot 2)
    if time_delta is not None:
        fig.add_trace(
            go.Scatter(
                x=grid,
                y=time_delta,
                mode="lines",
                name=f"Δ Time ({lbl1} - {lbl2})",
                line=dict(color="#00E676", width=2),
                fill="tozeroy",
                fillcolor="rgba(0, 230, 118, 0.12)",
                hovertemplate=f"<b>Δ Time</b><br>Dist: %{{x:.0f}}m<br>Delta: %{{y:+.3f}}s<extra></extra>",
            ),
            row=2, col=1
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,20,0.6)",
        font=dict(color="#e8e8e8", family="Inter, sans-serif"),
        margin=dict(l=60, r=40, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0.5)",
        ),
        hovermode="x unified",
        height=520,
    )

    fig.update_xaxes(
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
        row=1, col=1
    )
    fig.update_xaxes(
        title_text="Track Distance (meters)",
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
        row=2, col=1
    )

    fig.update_yaxes(
        title_text="Speed (km/h)",
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
        row=1, col=1
    )
    fig.update_yaxes(
        title_text="Delta (seconds)",
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.2)",
        row=2, col=1
    )

    return fig


def build_braking_efficiency_fig(
    win1, win2, driver1: str, driver2: str | None, colour1: str, colour2: str | None,
    apex_dist: float, fmt_func1=None, fmt_func2=None
):
    """
    Build a 3-row Plotly figure comparing braking efficiency:
    1. Speed vs Distance to Apex
    2. Brake % vs Distance to Apex
    3. Longitudinal Deceleration (G) vs Distance to Apex
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("<b>Speed (km/h)</b>", "<b>Brake Pressure (%)</b>", "<b>Longitudinal Deceleration (G)</b>")
    )

    def _add_traces(df, drv: str, col: str, drv_label: str):
        if df is None or df.empty or not {"Distance", "Speed", "Time"}.issubset(df.columns):
            return
        
        df = df.copy()
        df["DistToApex"] = df["Distance"] - apex_dist
        
        # Calculate deceleration (G)
        if pd.api.types.is_timedelta64_dtype(df["Time"]):
            dt = df["Time"].dt.total_seconds().diff()
        else:
            dt = pd.to_numeric(df["Time"], errors="coerce").diff()
            
        dv = df["Speed"].diff() / 3.6
        dt = dt.replace(0, np.nan)
        accel_ms2 = dv / dt
        df["G_Force"] = (accel_ms2 / 9.81).rolling(window=3, min_periods=1, center=True).mean().clip(-6.0, 2.5)

        # 1. Speed
        fig.add_trace(go.Scatter(
            x=df["DistToApex"], y=df["Speed"],
            mode="lines", line=dict(color=col, width=2.5),
            name=drv_label, legendgroup=drv,
            hovertemplate=f"<b>{drv_label}</b><br>Dist to Apex: %{{x:.0f}} m<br>Speed: %{{y:.0f}} km/h<extra></extra>"
        ), row=1, col=1)

        # 2. Brake %
        if "Brake" in df.columns:
            brake_thresh = 0 if df["Brake"].max() <= 1.0 else 5
            brake_vals = df["Brake"] * 100 if df["Brake"].max() <= 1.0 else df["Brake"]
                
            fig.add_trace(go.Scatter(
                x=df["DistToApex"], y=brake_vals,
                mode="lines", line=dict(color=col, width=2.5),
                name=drv_label, legendgroup=drv, showlegend=False,
                hovertemplate=f"<b>{drv_label}</b><br>Dist to Apex: %{{x:.0f}} m<br>Brake: %{{y:.0f}}%<extra></extra>"
            ), row=2, col=1)

            # Initial braking point marker on brake chart
            pre_apex = df[df["DistToApex"] <= 0]
            brake_active = pre_apex[pre_apex["Brake"] > brake_thresh]
            if not brake_active.empty:
                init_pt = brake_active.iloc[0]
                init_val = init_pt["Brake"] * 100 if df["Brake"].max() <= 1.0 else init_pt["Brake"]
                fig.add_trace(go.Scatter(
                    x=[init_pt["DistToApex"]], y=[init_val],
                    mode="markers", marker=dict(symbol="x", size=9, color=col, line=dict(color="white", width=1)),
                    name=f"{drv_label} Brake Point", legendgroup=drv, showlegend=False,
                    hovertemplate=f"<b>{drv_label} Initial Brake</b><br>Dist to Apex: %{{x:.0f}} m<extra></extra>"
                ), row=2, col=1)

        # 3. Deceleration
        fig.add_trace(go.Scatter(
            x=df["DistToApex"], y=df["G_Force"],
            mode="lines", line=dict(color=col, width=2.5),
            name=drv_label, legendgroup=drv, showlegend=False,
            hovertemplate=f"<b>{drv_label}</b><br>Dist to Apex: %{{x:.0f}} m<br>Decel: %{{y:.2f}} G<extra></extra>"
        ), row=3, col=1)

    label1 = fmt_func1(driver1) if fmt_func1 else driver1
    _add_traces(win1, driver1, colour1, label1)

    if win2 is not None and driver2 and colour2:
        label2 = fmt_func2(driver2) if fmt_func2 else driver2
        _add_traces(win2, driver2, colour2, label2)

    fig.update_layout(
        height=620,
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
    )

    # Add a vertical line at apex (DistToApex = 0)
    for i in range(1, 4):
        fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.4)", row=i, col=1)
        fig.update_xaxes(
            gridcolor="rgba(128,128,128,0.2)",
            zerolinecolor="rgba(128,128,128,0.4)",
            row=i, col=1
        )
        if i == 3:
            fig.update_xaxes(title_text="Distance relative to Apex (m)", row=i, col=1)

    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", row=1, col=1)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", range=[0, 105], row=2, col=1)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.4)", range=[-6, 2.5], row=3, col=1)

    return fig


def build_gear_shift_fig(
    gear_data1: dict, gear_data2: dict | None,
    driver1: str, driver2: str | None,
    colour1: str, colour2: str | None,
    fmt_func1=None, fmt_func2=None
) -> go.Figure:
    """
    Build a 2-row Plotly figure comparing gear shift strategies:
    1. Engine RPM vs Track Distance with Shift Event Markers
    2. Gear Usage Distribution (% of Lap Distance in Gears 1-8)
    """
    label1 = fmt_func1(driver1) if fmt_func1 else driver1
    label2 = fmt_func2(driver2) if (fmt_func2 and driver2) else (driver2 if driver2 else "")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.14,
        subplot_titles=(
            "<b>Engine RPM Operating Curve & Shift Points</b>",
            "<b>Gear Usage Distribution (% of Lap Distance)</b>"
        ),
        row_heights=[0.58, 0.42]
    )

    # 1. RPM traces on Row 1
    df1 = gear_data1.get("df_processed") if gear_data1 else None
    if df1 is not None and not df1.empty and {"Distance", "RPM"}.issubset(df1.columns):
        fig.add_trace(go.Scatter(
            x=df1["Distance"], y=df1["RPM"],
            mode="lines", line=dict(color=colour1, width=2.2),
            name=f"{label1} RPM", legendgroup=driver1,
            hovertemplate=f"<b>{label1}</b><br>Distance: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<extra></extra>"
        ), row=1, col=1)

        # Upshift markers
        shifts1 = gear_data1.get("shifts_df")
        if shifts1 is not None and not shifts1.empty:
            upshifts1 = shifts1[shifts1["type"] == "upshift"]
            if not upshifts1.empty:
                normal1 = upshifts1[~upshifts1["is_short_shift"]]
                if not normal1.empty:
                    fig.add_trace(go.Scatter(
                        x=normal1["Distance"], y=normal1["RPM"],
                        mode="markers",
                        marker=dict(symbol="circle", size=6, color=colour1, line=dict(color="#ffffff", width=1)),
                        name=f"{label1} Upshifts", legendgroup=driver1,
                        hovertemplate=f"<b>{label1} Upshift</b><br>Dist: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<br>Gear: %{{customdata[0]}} ➔ %{{customdata[1]}}<extra></extra>",
                        customdata=np.stack((normal1["from_gear"], normal1["to_gear"]), axis=-1)
                    ), row=1, col=1)

                short1 = upshifts1[upshifts1["is_short_shift"]]
                if not short1.empty:
                    fig.add_trace(go.Scatter(
                        x=short1["Distance"], y=short1["RPM"],
                        mode="markers",
                        marker=dict(symbol="diamond", size=9, color="#ffd700", line=dict(color=colour1, width=1.5)),
                        name=f"{label1} Short-Shift", legendgroup=driver1,
                        hovertemplate=f"<b>{label1} Short-Shift (Traction)</b><br>Dist: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<br>Gear: %{{customdata[0]}} ➔ %{{customdata[1]}}<extra></extra>",
                        customdata=np.stack((short1["from_gear"], short1["to_gear"]), axis=-1)
                    ), row=1, col=1)

    # Driver 2 on Row 1
    if gear_data2 is not None and driver2 and colour2:
        df2 = gear_data2.get("df_processed")
        if df2 is not None and not df2.empty and {"Distance", "RPM"}.issubset(df2.columns):
            fig.add_trace(go.Scatter(
                x=df2["Distance"], y=df2["RPM"],
                mode="lines", line=dict(color=colour2, width=2.2),
                name=f"{label2} RPM", legendgroup=driver2,
                hovertemplate=f"<b>{label2}</b><br>Distance: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<extra></extra>"
            ), row=1, col=1)

            shifts2 = gear_data2.get("shifts_df")
            if shifts2 is not None and not shifts2.empty:
                upshifts2 = shifts2[shifts2["type"] == "upshift"]
                if not upshifts2.empty:
                    normal2 = upshifts2[~upshifts2["is_short_shift"]]
                    if not normal2.empty:
                        fig.add_trace(go.Scatter(
                            x=normal2["Distance"], y=normal2["RPM"],
                            mode="markers",
                            marker=dict(symbol="circle", size=6, color=colour2, line=dict(color="#ffffff", width=1)),
                            name=f"{label2} Upshifts", legendgroup=driver2,
                            hovertemplate=f"<b>{label2} Upshift</b><br>Dist: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<br>Gear: %{{customdata[0]}} ➔ %{{customdata[1]}}<extra></extra>",
                            customdata=np.stack((normal2["from_gear"], normal2["to_gear"]), axis=-1)
                        ), row=1, col=1)

                    short2 = upshifts2[upshifts2["is_short_shift"]]
                    if not short2.empty:
                        fig.add_trace(go.Scatter(
                            x=short2["Distance"], y=short2["RPM"],
                            mode="markers",
                            marker=dict(symbol="diamond", size=9, color="#ffd700", line=dict(color=colour2, width=1.5)),
                            name=f"{label2} Short-Shift", legendgroup=driver2,
                            hovertemplate=f"<b>{label2} Short-Shift (Traction)</b><br>Dist: %{{x:.0f}} m<br>RPM: %{{y:.0f}}<br>Gear: %{{customdata[0]}} ➔ %{{customdata[1]}}<extra></extra>",
                            customdata=np.stack((short2["from_gear"], short2["to_gear"]), axis=-1)
                        ), row=1, col=1)

    # 2. Gear Usage Distribution on Row 2 (Gears 1 to 8)
    gears = [f"Gear {g}" for g in range(1, 9)]
    dist1 = [gear_data1.get("gear_distribution", {}).get(g, 0.0) for g in range(1, 9)] if gear_data1 else [0.0] * 8
    
    fig.add_trace(go.Bar(
        y=gears, x=dist1,
        orientation="h",
        name=label1,
        marker=dict(color=colour1),
        legendgroup=driver1,
        showlegend=False,
        hovertemplate=f"<b>{label1}</b><br>%{{y}}: %{{x:.1f}}% of lap<extra></extra>"
    ), row=2, col=1)

    if gear_data2 is not None and driver2 and colour2:
        dist2 = [gear_data2.get("gear_distribution", {}).get(g, 0.0) for g in range(1, 9)]
        fig.add_trace(go.Bar(
            y=gears, x=dist2,
            orientation="h",
            name=label2,
            marker=dict(color=colour2),
            legendgroup=driver2,
            showlegend=False,
            hovertemplate=f"<b>{label2}</b><br>%{{y}}: %{{x:.1f}}% of lap<extra></extra>"
        ), row=2, col=1)

    fig.update_layout(
        height=680,
        barmode="group",
        margin=dict(l=50, r=40, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1)
    )

    fig.update_xaxes(title_text="Track Distance (m)", gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", row=1, col=1)
    fig.update_yaxes(title_text="Engine RPM", gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", row=1, col=1)

    fig.update_xaxes(title_text="% of Lap Distance", gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="Gear Ratio", gridcolor="rgba(128,128,128,0.2)", zerolinecolor="rgba(128,128,128,0.2)", row=2, col=1)

    return fig


# ── Speed Trap & Intermediate Velocity Radar Breakdown ─────────────────────

def build_speed_trap_radar_fig(
    speed_data: dict,
    selected_drivers: list[str],
    driver_colours: list[str] | dict[str, str],
    fmt_func=None,
    include_grid_max: bool = True
) -> go.Figure | None:
    """
    Construct a 4-axis polar radar chart comparing drivers across SpeedST, SpeedI1, SpeedI2, and SpeedFL.
    """
    if not speed_data or not speed_data.get("has_data"):
        return None

    df = speed_data.get("drivers_df")
    if df is None or df.empty:
        return None

    sensor_keys = ["SpeedST", "SpeedI1", "SpeedI2", "SpeedFL"]
    sensor_labels = ["Speed Trap (ST)", "Intermediate 1 (I1)", "Intermediate 2 (I2)", "Finish Line (FL)"]
    categories = sensor_labels + [sensor_labels[0]]

    fig = go.Figure()

    all_speeds = []
    for s in sensor_keys:
        if s in df.columns:
            vals = df[s].dropna()
            if not vals.empty:
                all_speeds.extend(vals.tolist())

    if not all_speeds:
        return None

    min_speed = max(0, float(np.floor(min(all_speeds) / 10) * 10) - 10)
    max_speed = float(np.ceil(max(all_speeds) / 10) * 10) + 10

    # Grid max benchmark
    if include_grid_max:
        grid_max_vals = []
        for s in sensor_keys:
            if s in df.columns and df[s].notna().any():
                grid_max_vals.append(float(df[s].max()))
            else:
                grid_max_vals.append(min_speed)
        grid_max_closed = grid_max_vals + [grid_max_vals[0]]

        fig.add_trace(go.Scatterpolar(
            r=grid_max_closed,
            theta=categories,
            fill="none",
            name="Grid Maximum",
            line=dict(color="rgba(255,215,0,0.5)", width=2, dash="dash"),
            hovertemplate="<b>Grid Maximum</b><br>%{theta}: %{r:.1f} km/h<extra></extra>",
        ))

    # Convert colours to dict if list
    if isinstance(driver_colours, list):
        col_map = dict(zip(selected_drivers, driver_colours))
    else:
        col_map = driver_colours or {}

    for drv in selected_drivers:
        drv_str = str(drv)
        drv_row = df[df["Driver"] == drv_str]
        if drv_row.empty:
            continue

        row = drv_row.iloc[0]
        speeds = []
        for s in sensor_keys:
            val = row[s] if s in row and pd.notna(row[s]) else min_speed
            speeds.append(float(val))

        speeds_closed = speeds + [speeds[0]]
        drv_col = col_map.get(drv_str, "#00E5FF")
        drv_label = fmt_func(drv_str) if fmt_func else drv_str

        # Hex to rgba fill
        fill_col = drv_col
        if fill_col.startswith("#") and len(fill_col) == 7:
            r_c = int(fill_col[1:3], 16)
            g_c = int(fill_col[3:5], 16)
            b_c = int(fill_col[5:7], 16)
            fill_col = f"rgba({r_c},{g_c},{b_c},0.2)"

        fig.add_trace(go.Scatterpolar(
            r=speeds_closed,
            theta=categories,
            fill="toself",
            fillcolor=fill_col,
            name=drv_label,
            line=dict(color=drv_col, width=2.5),
            hovertemplate=f"<b>{drv_label}</b><br>%{{theta}}: %{{r:.1f}} km/h<extra></extra>",
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[min_speed, max_speed],
                gridcolor="rgba(128,128,128,0.2)",
                linecolor="rgba(128,128,128,0.2)",
                tickfont=dict(size=10, color="rgba(255,255,255,0.6)"),
                angle=45,
            ),
            angularaxis=dict(
                gridcolor="rgba(128,128,128,0.2)",
                linecolor="rgba(128,128,128,0.2)",
                tickfont=dict(size=12, color="rgba(255,255,255,0.85)"),
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=480,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ),
    )

    return fig


def build_speed_trap_bar_fig(
    speed_data: dict,
    group_by: str = "Constructor",
    metric_type: str = "Max"
) -> go.Figure | None:
    """
    Construct a grouped bar chart comparing timing trap velocities across constructors or power units.
    """
    if not speed_data or not speed_data.get("has_data"):
        return None

    if group_by == "PowerUnit":
        df = speed_data.get("power_unit_summary")
        x_col = "PowerUnit"
        title_text = "Power Unit Speed Trap Comparison"
    else:
        df = speed_data.get("constructor_summary")
        x_col = "Team"
        title_text = "Constructor Speed Trap Comparison"

    if df is None or df.empty or x_col not in df.columns:
        return None

    sensor_map = [
        ("SpeedST", "Speed Trap (ST)", "#FF1744"),
        ("SpeedI1", "Intermediate 1 (I1)", "#00E5FF"),
        ("SpeedI2", "Intermediate 2 (I2)", "#76FF03"),
        ("SpeedFL", "Finish Line (FL)", "#FFD600"),
    ]

    suffix = "_Max" if metric_type == "Max" else "_Mean"
    fig = go.Figure()

    all_vals = []
    for s_key, s_label, col in sensor_map:
        col_name = f"{s_key}{suffix}"
        if col_name in df.columns and df[col_name].notna().any():
            vals = df[col_name].dropna().tolist()
            all_vals.extend(vals)
            fig.add_trace(go.Bar(
                x=df[x_col],
                y=df[col_name],
                name=s_label,
                marker=dict(color=col),
                hovertemplate=f"<b>%{{x}}</b><br>{s_label} ({metric_type}): %{{y:.1f}} km/h<extra></extra>",
            ))

    if not all_vals:
        return None

    y_min = max(0, float(np.floor(min(all_vals) / 10) * 10) - 20)
    y_max = float(np.ceil(max(all_vals) / 10) * 10) + 10

    fig.update_layout(
        barmode="group",
        height=450,
        margin=dict(l=50, r=30, t=50, b=50),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor="rgba(128,128,128,0.2)",
            tickangle=-25 if len(df) > 5 else 0,
        ),
        yaxis=dict(
            title_text=f"Velocity ({metric_type} km/h)",
            range=[y_min, y_max],
            gridcolor="rgba(128,128,128,0.2)",
            zerolinecolor="rgba(128,128,128,0.2)",
        ),
    )

    return fig


# ── Intra-Team Teammate Battle & Qualifying Delta Matrix ───────────────────

def build_teammate_matrix_fig(
    teammate_data: dict,
    mode: str = "Qualifying"
) -> go.Figure | None:
    """
    Construct a horizontal diverging bar chart of intra-team teammate deltas across constructors.
    Supports mode='Qualifying' (single-lap gap) and mode='Race Pace' (median clean-air pace delta).
    """
    if not teammate_data or not teammate_data.get("has_data"):
        return None

    pairs = teammate_data.get("pairs", [])
    if not pairs:
        return None

    teams = []
    deltas = []
    colours = []
    text_labels = []
    customdata = []

    for p in pairs:
        t_name = p.get("team", "Unknown")
        t_col = p.get("team_colour", "#00E5FF")
        d1 = p.get("driver1", {})
        d2 = p.get("driver2", {})

        if mode == "Race Pace":
            val = p.get("race_pace_delta_s")
            if val is None:
                continue
            faster_drv = d1.get("code") if val >= 0 else d2.get("code")
            trailing_drv = d2.get("code") if val >= 0 else d1.get("code")
            val_abs = abs(val)
            pct_str = "—"
            bar_text = f"{faster_drv} (-{val_abs:.3f} s/lap)"
        else:
            val = p.get("qual_delta_s")
            if val is None:
                continue
            faster_drv = p.get("faster_driver", d1.get("code", "D1"))
            trailing_drv = p.get("trailing_driver", d2.get("code", "D2"))
            val_abs = abs(val)
            pct = p.get("qual_delta_pct")
            pct_str = f"{pct:.2f}" if pct is not None else "0.0"
            bar_text = f"{faster_drv} (-{val_abs:.3f}s | -{pct_str}%)"

        teams.append(t_name)
        deltas.append(val_abs)
        colours.append(t_col)
        text_labels.append(bar_text)

        customdata.append([
            faster_drv,
            trailing_drv,
            pct_str,
            f"{p.get('s1_advantage')} (+{p.get('s1_delta', 0.0):.3f}s)",
            f"{p.get('s2_advantage')} (+{p.get('s2_delta', 0.0):.3f}s)",
            f"{p.get('s3_advantage')} (+{p.get('s3_delta', 0.0):.3f}s)",
            p.get("sector_dominance", "—"),
            d1.get("median_race_pace_str", "—"),
            d2.get("median_race_pace_str", "—"),
            d1.get("pos", "—"),
            d2.get("pos", "—"),
            d1.get("best_lap_str", "—"),
            d2.get("best_lap_str", "—"),
        ])

    if not teams:
        return None

    # Reverse list so top constructor appears at top of Y axis
    teams.reverse()
    deltas.reverse()
    colours.reverse()
    text_labels.reverse()
    customdata.reverse()

    fig = go.Figure()

    if mode == "Race Pace":
        htemplate = (
            "<b>%{y}</b><br>"
            "Faster Race Pace: <b>%{customdata[0]}</b> (%{customdata[7]})<br>"
            "Trailing Pace: %{customdata[1]} (%{customdata[8]})<br>"
            "Pace Advantage: <b>-%{x:.3f} s/lap</b><br>"
            "Race Positions: P%{customdata[9]} vs P%{customdata[10]}<extra></extra>"
        )
        x_title = "Median Race Pace Advantage (s/lap)"
    else:
        htemplate = (
            "<b>%{y}</b><br>"
            "Faster Teammate: <b>%{customdata[0]}</b> (%{customdata[11]})<br>"
            "Trailing Teammate: %{customdata[1]} (%{customdata[12]})<br>"
            "Qualifying Gap: <b>-%{x:.3f}s</b> (-%{customdata[2]}%)<br>"
            "Sector Dominance: %{customdata[6]}<br>"
            "S1: %{customdata[3]} | S2: %{customdata[4]} | S3: %{customdata[5]}<extra></extra>"
        )
        x_title = "Qualifying Lap Time Advantage (Seconds)"

    fig.add_trace(go.Bar(
        y=teams,
        x=deltas,
        orientation="h",
        marker=dict(
            color=colours,
            line=dict(color="rgba(255,255,255,0.2)", width=1),
        ),
        text=text_labels,
        textposition="outside",
        textfont=dict(size=11, color="#ffffff"),
        cliponaxis=False,
        customdata=customdata,
        hovertemplate=htemplate,
    ))

    max_delta = max(deltas) if deltas else 1.0
    x_max = max_delta * 1.35 if max_delta > 0 else 1.0

    chart_height = max(360, len(teams) * 40 + 60)

    fig.update_layout(
        height=chart_height,
        margin=dict(l=140, r=90, t=30, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title_text=x_title,
            range=[0, x_max],
            gridcolor="rgba(128,128,128,0.2)",
            zeroline=True,
            zerolinecolor="rgba(128,128,128,0.5)",
            zerolinewidth=1.5,
        ),
        yaxis=dict(
            tickfont=dict(size=12, color="#ffffff"),
            gridcolor="rgba(128,128,128,0.1)",
        ),
        showlegend=False,
    )

    return fig


def build_pit_loss_fig(
    transit_data: dict,
    driver1: str | None = None,
    driver2: str | None = None,
    compare: bool = False,
) -> go.Figure | None:
    """
    Construct an interactive stacked horizontal bar chart visualising the breakdown
    of pit loss into:
      1. In-Lap Push Delta (Amber)
      2. Pit Lane Transit Duration (Cyan)
      3. Out-Lap Cold Tyre Warm-up Delta (Purple)
    Supports driver comparison or full-grid pit stop analysis.
    """
    if not transit_data or not transit_data.get("has_data"):
        return None

    all_stops = transit_data.get("all_stops", [])
    if not all_stops:
        return None

    if compare and (driver1 or driver2):
        active_drivers = {d for d in [driver1, driver2] if d}
        stops = [s for s in all_stops if s.get("driver") in active_drivers]
        if not stops:
            stops = all_stops
    else:
        stops = all_stops

    if not stops:
        return None

    # Sort stops so the most efficient / lowest net pit loss is at the top
    sorted_stops = sorted(
        stops,
        key=lambda s: (
            s["net_pit_loss_s"] if s.get("net_pit_loss_s") is not None else 999.0,
            s["pit_lane_time_s"] if s.get("pit_lane_time_s") is not None else 999.0,
        )
    )

    labels = []
    in_deltas = []
    transit_times = []
    out_deltas = []
    custom_in = []
    custom_transit = []
    custom_out = []

    for s in sorted_stops:
        drv = s.get("driver", "UNK")
        stop_num = s.get("stop_num", 1)
        in_lap = s.get("in_lap", 0)
        out_lap = s.get("out_lap", in_lap + 1)
        lbl = f"{drv} S{stop_num} (L{in_lap})"
        labels.append(lbl)

        in_delta = max(0.0, s["in_lap_delta_s"]) if s.get("in_lap_delta_s") is not None else 0.0
        transit = max(0.0, s["pit_lane_time_s"]) if s.get("pit_lane_time_s") is not None else (s.get("pit_duration_s") or 0.0)
        out_delta = max(0.0, s["out_lap_delta_s"]) if s.get("out_lap_delta_s") is not None else 0.0

        in_deltas.append(in_delta)
        transit_times.append(transit)
        out_deltas.append(out_delta)

        in_time_str = f"{s['in_lap_time_s']:.2f}s" if s.get("in_lap_time_s") is not None else "N/A"
        base_time_str = f"{s['baseline_lap_s']:.2f}s" if s.get("baseline_lap_s") is not None else "N/A"
        old_cmp = s.get("old_compound", "?")
        new_cmp = s.get("new_compound", "?")
        pit_dur_str = f"{s['pit_duration_s']:.2f}s" if s.get("pit_duration_s") is not None else "N/A"
        out_time_str = f"{s['out_lap_time_s']:.2f}s" if s.get("out_lap_time_s") is not None else "N/A"
        s1_str = f"{s['out_lap_s1_delta_s']:+.2f}s" if s.get("out_lap_s1_delta_s") is not None else "N/A"
        s2_str = f"{s['out_lap_s2_delta_s']:+.2f}s" if s.get("out_lap_s2_delta_s") is not None else "N/A"
        s3_str = f"{s['out_lap_s3_delta_s']:+.2f}s" if s.get("out_lap_s3_delta_s") is not None else "N/A"
        net_loss_str = f"{s['net_pit_loss_s']:.2f}s" if s.get("net_pit_loss_s") is not None else "N/A"

        custom_in.append([in_time_str, base_time_str, old_cmp, new_cmp])
        custom_transit.append([pit_dur_str, f"L{in_lap}", f"L{out_lap}"])
        custom_out.append([out_time_str, base_time_str, s1_str, s2_str, s3_str, net_loss_str])

    fig = go.Figure()

    # 1. In-Lap Push Delta (Amber)
    fig.add_trace(go.Bar(
        y=labels,
        x=in_deltas,
        name="In-Lap Push Delta",
        orientation="h",
        marker=dict(
            color="#F59E0B",
            line=dict(color="rgba(255,255,255,0.15)", width=1),
        ),
        customdata=custom_in,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Phase: In-Lap Push / Entry Delta<br>"
            "In-Lap Time: %{customdata[0]}<br>"
            "Baseline Pace: %{customdata[1]}<br>"
            "In-Lap Push Delta: <b>+%{x:.2f}s</b><br>"
            "Compound Change: %{customdata[2]} → %{customdata[3]}<extra></extra>"
        ),
    ))

    # 2. Pit Lane Transit Duration (Cyan)
    fig.add_trace(go.Bar(
        y=labels,
        x=transit_times,
        name="Pit Lane Transit",
        orientation="h",
        marker=dict(
            color="#06B6D4",
            line=dict(color="rgba(255,255,255,0.15)", width=1),
        ),
        customdata=custom_transit,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Phase: Pit Lane Transit Duration<br>"
            "Transit Time (In→Out): <b>%{x:.2f}s</b><br>"
            "Stationary Stop Duration: %{customdata[0]}<br>"
            "Laps: %{customdata[1]} → %{customdata[2]}<extra></extra>"
        ),
    ))

    # 3. Out-Lap Cold Tyre Warm-up Delta (Purple)
    fig.add_trace(go.Bar(
        y=labels,
        x=out_deltas,
        name="Out-Lap Warm-up Delta",
        orientation="h",
        marker=dict(
            color="#8B5CF6",
            line=dict(color="rgba(255,255,255,0.15)", width=1),
        ),
        customdata=custom_out,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Phase: Out-Lap Cold Tyre Warm-up Delta<br>"
            "Out-Lap Time: %{customdata[0]}<br>"
            "Baseline Pace: %{customdata[1]}<br>"
            "Warm-up Delta: <b>+%{x:.2f}s</b><br>"
            "Sector Deltas: S1 %{customdata[2]} | S2 %{customdata[3]} | S3 %{customdata[4]}<br>"
            "Net Total Pit Loss: <b>%{customdata[5]}</b><extra></extra>"
        ),
    ))

    chart_height = max(380, len(labels) * 38 + 90)

    fig.update_layout(
        barmode="stack",
        height=chart_height,
        margin=dict(l=140, r=40, t=50, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title_text="Cumulative Pit Loss Duration (Seconds)",
            gridcolor="rgba(128,128,128,0.2)",
            zeroline=True,
            zerolinecolor="rgba(128,128,128,0.5)",
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=12, color="#ffffff"),
            gridcolor="rgba(128,128,128,0.1)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#ffffff", size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
    )

    return fig




