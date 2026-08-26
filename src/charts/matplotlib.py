import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st
import fastf1.utils

# ── Telemetry Channel Configurations ──────────────────────────────────────────
# Mapping of channel name -> (subplot_title, df_column, y_label, special_flag, height_ratio)
CHANNEL_CONFIG = {
    "Speed":    ("Speed",    "Speed",    "km/h",  "",      3.0),
    "Throttle": ("Throttle", "Throttle", "%",     "",      2.0),
    "Brake":    ("Brake",    "Brake",    "",      "brake", 1.0),
    "RPM":      ("RPM",      "RPM",      "RPM",   "",      2.0),
    "Gear":     ("Gear",     "nGear",    "Gear",  "gear",  1.5),
    "DRS":      ("DRS",      "DRS",      "DRS",   "drs",   1.0),
}
AVAILABLE_CHANNELS = list(CHANNEL_CONFIG.keys())


def style_ax(ax, ylabel: str, special: str = ""):
    ax.set_ylabel(ylabel, fontsize=11, labelpad=8)
    ax.grid(True, linestyle=":", linewidth=0.3, alpha=0.8, color="#888888")
    ax.tick_params(axis="both", length=3, labelsize=10, colors="#888888")
    for spine in ax.spines.values():
        spine.set_edgecolor("#888888")
        spine.set_alpha(0.3)
    if special == "brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"], fontsize=10)
    elif special == "drs":
        ax.set_ylim(-1, 15)
        ax.set_yticks([0, 8, 12])
        ax.set_yticklabels(["Off", "On", "On"], fontsize=9)
    else:
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))


def build_chart(
    drivers_telemetry: list,
    title_str: str,
    fig_width: float = 14,
    selected_channels: list[str] | None = None,
) -> plt.Figure | None:
    """Build multi-channel telemetry comparison chart with dynamic channel filtering and height scaling."""
    if selected_channels is None:
        active_channel_keys = AVAILABLE_CHANNELS
    else:
        # Preserve user selection order while filtering only known valid channels
        active_channel_keys = [ch for ch in selected_channels if ch in CHANNEL_CONFIG]

    if not active_channel_keys:
        return None

    active_channels = [CHANNEL_CONFIG[k] for k in active_channel_keys]
    num_channels = len(active_channels)
    h_ratios = [cfg[4] for cfg in active_channels]

    # Dynamically scale figure height based on selected channels and their height ratios
    fig_height = max(2.8, sum(h_ratios) * 1.05 + 0.5)

    fig = plt.figure(figsize=(fig_width, fig_height), facecolor="none")
    gs = gridspec.GridSpec(
        num_channels,
        1,
        figure=fig,
        hspace=0.04,
        height_ratios=h_ratios,
        top=0.94 if num_channels > 1 else 0.90,
        bottom=0.06 if num_channels > 1 else 0.15,
        left=0.07,
        right=0.97,
    )
    axes = [fig.add_subplot(gs[i]) for i in range(num_channels)]

    for ax_i, (_, col, ylabel, special, _) in enumerate(active_channels):
        ax = axes[ax_i]
        for drv_label, colour, tel in drivers_telemetry:
            if tel is not None and col in tel.columns:
                lw = 1.7 if drv_label == drivers_telemetry[0][0] else 1.5
                ls = "-" if drv_label == drivers_telemetry[0][0] else "--"
                al = 0.95 if drv_label == drivers_telemetry[0][0] else 0.80
                ax.plot(
                    tel["Distance"],
                    tel[col],
                    color=colour,
                    linewidth=lw,
                    linestyle=ls,
                    alpha=al,
                    label=drv_label,
                    solid_capstyle="round",
                )
                if col == "Speed" and drv_label == drivers_telemetry[0][0]:
                    ax.fill_between(tel["Distance"], tel[col], alpha=0.05, color=colour)

        unit = f" ({ylabel})" if ylabel else ""
        style_ax(
            ax,
            col if not ylabel else ylabel + unit if special not in ("brake", "drs", "gear") else col,
            special,
        )

        # gear: integer y ticks
        if special == "gear":
            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))
            ax.set_ylim(0.5, 8.5)
            ax.set_yticks(range(1, 9))

        if ax_i < num_channels - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Distance (m)", fontsize=11, labelpad=8)

    for ax_i, (label, _, _, _, _) in enumerate(active_channels):
        axes[ax_i].yaxis.set_label_position("left")
        axes[ax_i].text(
            1.002,
            0.5,
            label,
            transform=axes[ax_i].transAxes,
            fontsize=10,
            va="center",
            ha="left",
            rotation=0,
            fontweight="600",
            alpha=0.6,
        )

    fig.suptitle(title_str, fontsize=12, fontweight="bold", y=0.98)

    # Legend
    handles = [mpatches.Patch(color=c, label=d) for d, c, _ in drivers_telemetry]
    if len(handles) > 1:
        fig.legend(
            handles=handles,
            loc="upper right",
            bbox_to_anchor=(0.97, 0.965),
            fontsize=9,
            framealpha=0.9,
            handlelength=1.2,
            handleheight=0.8,
        )
    return fig


def build_delta_chart(tel1, tel2, colour1, colour2, label1, label2):
    speed2_i = np.interp(tel1["Distance"], tel2["Distance"], tel2["Speed"])
    delta = tel1["Speed"].values - speed2_i

    fig_d, ax_d = plt.subplots(figsize=(14, 2.8), facecolor="none")
    ax_d.set_facecolor("none")
    ax_d.axhline(0, color="gray", alpha=0.5, linewidth=0.8)
    ax_d.fill_between(tel1["Distance"], delta,
                      where=(delta >= 0), color=colour1, alpha=0.6,
                      label=f"{label1} faster", interpolate=True)
    ax_d.fill_between(tel1["Distance"], delta,
                      where=(delta < 0),  color=colour2, alpha=0.6,
                      label=f"{label2} faster", interpolate=True)
    ax_d.set_ylabel("Δ Speed (km/h)", fontsize=11)
    ax_d.set_xlabel("Distance (m)", fontsize=11)
    ax_d.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
    for spine in ax_d.spines.values():
        spine.set_edgecolor("gray")
        spine.set_alpha(0.3)
    ax_d.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
    ax_d.tick_params(labelsize=10)
    ax_d.legend(fontsize=10, framealpha=0.9)
    fig_d.tight_layout()
    return fig_d


def build_time_delta_chart(lap_comp, lap_ref, colour_comp, colour_ref, label_comp, label_ref):
    """
    Plots the continuous time delta between two laps over distance.
    delta_time returns a pd.Series representing the time delta.
    A positive delta means lap_comp is slower than lap_ref.
    A negative delta means lap_comp is faster than lap_ref.
    """
    try:
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(lap_ref, lap_comp)
        
        fig_td, ax_td = plt.subplots(figsize=(14, 2.8), facecolor="none")
        ax_td.set_facecolor("none")
        ax_td.axhline(0, color="gray", alpha=0.5, linewidth=0.8)
        
        # Fill where comp is slower than ref (positive delta)
        ax_td.fill_between(ref_tel["Distance"], delta_time,
                           where=(delta_time >= 0), color=colour_comp, alpha=0.6,
                           label=f"{label_ref} faster", interpolate=True)
        # Fill where comp is faster than ref (negative delta)
        ax_td.fill_between(ref_tel["Distance"], delta_time,
                           where=(delta_time < 0),  color=colour_ref, alpha=0.6,
                           label=f"{label_comp} faster", interpolate=True)
                           
        ax_td.set_ylabel("Δ Time (s)", fontsize=11)
        ax_td.set_xlabel("Distance (m)", fontsize=11)
        ax_td.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
        
        for spine in ax_td.spines.values():
            spine.set_edgecolor("gray")
            spine.set_alpha(0.3)
        ax_td.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
        ax_td.tick_params(labelsize=10)
        ax_td.legend(fontsize=10, framealpha=0.9)
        fig_td.tight_layout()
        return fig_td
    except Exception as e:
        import logging
        logging.error(f"Error building time delta chart: {e}")
        return None

