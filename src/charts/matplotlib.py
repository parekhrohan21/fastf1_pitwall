import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import streamlit as st

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
