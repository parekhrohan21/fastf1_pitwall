import pandas as pd
import numpy as np
def build_undercut_chart_str():
    return """
def build_undercut_chart(l1_df, l2_df, d1_label, d2_label, color1, color2, start_lap, end_lap, p1_lap, p2_lap):
    \"\"\"
    Plots the gap (Driver 1 - Driver 2) over a specific pit window.
    \"\"\"
    # Align laps
    laps_range = list(range(start_lap, end_lap + 1))
    
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
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(title="Lap Number", tickmode="linear", tick0=start_lap, dtick=1, showgrid=False, zeroline=False),
        yaxis=dict(title="Gap (s) [Negative means D1 is ahead]", zeroline=True, zerolinecolor="rgba(255,255,255,0.2)", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        showlegend=False,
        height=300
    )
    return fig
"""
print("OK")
