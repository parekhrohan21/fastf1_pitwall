import plotly.graph_objects as go
import numpy as np
import pandas as pd
import streamlit as st
from plotly.subplots import make_subplots
from src.ui.styles import COMPOUND_COLOURS
from src.data.loader import _get_telemetry_for_map, _team_colour

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

    # Built figure layout
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Racing Line Overlay", "Speed Profile"),
        vertical_spacing=0.08
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
    return fig, stats1, stats2


def build_tyre_deg_fig(_deg_d1, _deg_d2, driver1, driver2, colour1, colour2, compare):
    fig_deg = go.Figure()
    table_rows = []

    def process_driver_deg(deg_data, drv_name, drv_colour, is_primary):
        if not deg_data:
            return
        marker_symbol = "circle" if is_primary else "square"
        line_dash = "solid" if is_primary else "dash"

        for s in deg_data:
            stint_num = s["stint"]
            compound = s["compound"]
            laps_list = s["laps"]

            x_vals = np.array([l["TyreLife"] for l in laps_list])
            y_vals = np.array([l["LapTime_s"] for l in laps_list])

            # Fit linear regression
            slope, intercept = np.polyfit(x_vals, y_vals, 1)
            label_str = f"{drv_name} - Stint {stint_num} ({compound})"

            # Scatter points
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
                hovertemplate=(
                    f"<b>{drv_name}</b> (Stint {stint_num} - {compound})<br>"
                    "Tyre Age: %{x} laps<br>"
                    "Lap Time: %{customdata:.3f} s<br>"
                    f"Deg Rate: {slope:+.3f} s/lap<extra></extra>"
                ),
                customdata=y_vals
            ))

            # Regression Line
            x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
            y_line = slope * x_line + intercept
            fig_deg.add_trace(go.Scatter(
                x=x_line, y=y_line,
                mode="lines",
                line=dict(color=drv_colour, width=2, dash=line_dash),
                name=f"{label_str} Trend",
                legendgroup=label_str,
                showlegend=False,
                hoverinfo="skip"
            ))

            # Store stats for the table
            table_rows.append({
                "driver": drv_name,
                "colour": drv_colour,
                "stint": stint_num,
                "compound": compound,
                "laps": len(x_vals),
                "deg_rate": slope,
                "base_pace": intercept
            })

    process_driver_deg(_deg_d1, driver1, colour1, is_primary=True)
    if compare and _deg_d2:
        process_driver_deg(_deg_d2, driver2, colour2, is_primary=False)

    fig_deg.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Tyre Age (Laps)",
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
        ),
        yaxis=dict(
            title="Lap Time (Seconds)",
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

