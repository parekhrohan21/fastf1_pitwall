"""Unit tests for Issue #197: Driver Driving Style DNA & Apex Aggression Spider Radar."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.data.loader import (
    DNA_AXES,
    _build_dna_benchmark_envelope,
    _calculate_driving_style_dna,
    _classify_driving_style,
    _detect_corner_apexes,
)
from src.charts.plotly import build_driving_style_dna_fig


def _make_synthetic_lap(
    *,
    trail_brake_depth_m: float = 45.0,
    throttle_ramp_rate: float = 1.4,
    steering_noise: float = 2.0,
    upshift_rpm_peak: float = 12100.0,
    apex_speed_kmh: float = 145.0,
    high_speed_apex_kmh: float = 225.0,
    include_steering: bool = True,
    include_xy: bool = True,
) -> pd.DataFrame:
    """Build a realistic 4000 m synthetic lap with 4 corners (including a high-speed corner)."""
    n = 800
    dist = np.linspace(0.0, 4000.0, n)
    t_sec = np.linspace(0.0, 82.0, n)

    # Base straight-line speed 305 km/h with 4 corner dips at 700, 1600, 2500, 3400 m
    speed = np.full(n, 305.0, dtype=float)
    throttle = np.full(n, 100.0, dtype=float)
    brake = np.zeros(n, dtype=float)
    rpm = np.full(n, 11200.0, dtype=float)
    gear = np.full(n, 8, dtype=int)

    corners = [
        (700.0, apex_speed_kmh),
        (1600.0, apex_speed_kmh - 15.0),
        (2500.0, high_speed_apex_kmh),
        (3400.0, apex_speed_kmh + 10.0),
    ]

    for c_dist, c_vmin in corners:
        rel = dist - c_dist
        # Gaussian-like speed dip around the apex
        dip_mask = np.abs(rel) <= 160.0
        profile = np.exp(-0.5 * (rel[dip_mask] / 52.0) ** 2)
        speed[dip_mask] = 305.0 - (305.0 - c_vmin) * profile

        # Entry braking window: [-130 m, -release_offset]
        release_offset = max(2.0, 65.0 - trail_brake_depth_m)
        b_mask = (rel >= -130.0) & (rel <= -release_offset)
        if np.any(b_mask):
            # Progressive brake taper when trail_brake_depth_m is deep
            b_rel = (rel[b_mask] - (-130.0)) / max(130.0 - release_offset, 1.0)
            brake[b_mask] = np.clip(100.0 * (1.0 - 0.75 * b_rel), 10.0, 100.0)
            throttle[b_mask] = 0.0

        # Mid-corner coasting/trail zone
        mid_mask = (rel > -release_offset) & (rel <= 5.0)
        throttle[mid_mask] = 10.0

        # Exit throttle ramp
        exit_mask = (rel > 5.0) & (rel <= 140.0)
        exit_d = rel[exit_mask] - 5.0
        throttle[exit_mask] = np.clip(15.0 + throttle_ramp_rate * exit_d, 15.0, 100.0)

        # Gear & RPM progression on exit
        g_seq = np.clip(3 + (exit_d // 25.0).astype(int), 3, 8)
        gear[exit_mask] = g_seq
        # Sawtooth RPM peaking at upshift_rpm_peak before each shift
        frac_in_gear = (exit_d % 25.0) / 25.0
        rpm[exit_mask] = (upshift_rpm_peak - 1600.0) + 1600.0 * frac_in_gear

    data: dict[str, np.ndarray] = {
        "Distance": dist,
        "Time": pd.to_timedelta(t_sec, unit="s"),
        "Speed": speed,
        "Throttle": throttle,
        "Brake": brake,
        "RPM": rpm,
        "nGear": gear,
    }

    if include_steering:
        rng = np.random.default_rng(42)
        base_steer = 18.0 * np.sin(dist / 220.0)
        jitter = rng.normal(0.0, steering_noise, size=n)
        data["Steering"] = base_steer + jitter

    if include_xy:
        # Smooth parametric closed-loop track with curvature spikes at corners
        theta = (dist / 4000.0) * 2.0 * np.pi + 0.15 * np.sin(4.0 * (dist / 4000.0) * 2.0 * np.pi)
        if not include_steering and steering_noise > 5.0:
            rng = np.random.default_rng(99)
            theta = theta + rng.normal(0.0, 0.025, size=n)
        dx = np.cos(theta) * np.gradient(dist)
        dy = np.sin(theta) * np.gradient(dist)
        data["X"] = np.cumsum(dx)
        data["Y"] = np.cumsum(dy)

    return pd.DataFrame(data)


def test_dna_axes_structure():
    """Verify the 6 canonical DNA axes are defined in order."""
    assert len(DNA_AXES) == 6
    keys = [k for k, _ in DNA_AXES]
    assert keys == [
        "trail_braking",
        "throttle_aggression",
        "steering_smoothness",
        "rpm_exploitation",
        "apex_commitment",
        "aero_confidence",
    ]


def test_detect_corner_apexes_auto_and_explicit():
    """Verify corner apex detection works both with explicit circuit_info distances and auto-detection."""
    df = _make_synthetic_lap()
    auto_corners = _detect_corner_apexes(df)
    assert len(auto_corners) == 4
    for expected in (700.0, 1600.0, 2500.0, 3400.0):
        assert any(abs(c - expected) < 35.0 for c in auto_corners)

    explicit = _detect_corner_apexes(df, [705.0, 1595.0, 2505.0])
    assert explicit == [705.0, 1595.0, 2505.0]


def test_calculate_dna_with_steering_channel():
    """Verify 6-axis DNA calculation when direct Steering channel is present."""
    df = _make_synthetic_lap(include_steering=True)
    res = _calculate_driving_style_dna(df)
    assert res is not None
    assert len(res["scores"]) == 6
    assert len(res["axis_labels"]) == 6
    assert all(0.0 <= s <= 100.0 for s in res["scores"])
    assert 0.0 <= res["overall_dna_score"] <= 100.0
    assert res["raw_metrics"]["steering_source"] == "steering"
    assert res["raw_metrics"]["corners_analysed"] == 4
    assert isinstance(res["archetype"], str) and len(res["archetype"]) > 0


def test_calculate_dna_trajectory_fallback_without_steering():
    """Verify Axis 3 falls back cleanly to X/Y trajectory yaw smoothness when Steering is absent."""
    df = _make_synthetic_lap(include_steering=False, include_xy=True)
    assert "Steering" not in df.columns
    res = _calculate_driving_style_dna(df)
    assert res is not None
    assert res["raw_metrics"]["steering_source"] == "trajectory"
    assert all(0.0 <= s <= 100.0 for s in res["scores"])


def test_calculate_dna_minimal_columns_fallback():
    """Verify DNA computation still succeeds with only Distance and Speed columns."""
    df = _make_synthetic_lap(include_steering=False, include_xy=False)[["Distance", "Speed"]]
    res = _calculate_driving_style_dna(df)
    assert res is not None
    assert len(res["scores"]) == 6
    assert all(0.0 <= s <= 100.0 for s in res["scores"])


def test_calculate_dna_differentiates_driving_styles():
    """Verify aggressive vs conservative/smooth telemetry profiles produce distinct axis scores."""
    df_aggressive = _make_synthetic_lap(
        trail_brake_depth_m=60.0,
        throttle_ramp_rate=2.0,
        steering_noise=9.5,
        upshift_rpm_peak=12250.0,
        apex_speed_kmh=162.0,
        high_speed_apex_kmh=242.0,
    )
    df_conservative = _make_synthetic_lap(
        trail_brake_depth_m=10.0,
        throttle_ramp_rate=0.45,
        steering_noise=0.4,
        upshift_rpm_peak=10650.0,
        apex_speed_kmh=112.0,
        high_speed_apex_kmh=178.0,
    )

    dna_agg = _calculate_driving_style_dna(df_aggressive)
    dna_con = _calculate_driving_style_dna(df_conservative)
    assert dna_agg is not None and dna_con is not None

    assert dna_agg["axes"]["trail_braking"] > dna_con["axes"]["trail_braking"]
    assert dna_agg["axes"]["throttle_aggression"] > dna_con["axes"]["throttle_aggression"]
    assert dna_con["axes"]["steering_smoothness"] > dna_agg["axes"]["steering_smoothness"]
    assert dna_agg["axes"]["rpm_exploitation"] > dna_con["axes"]["rpm_exploitation"]
    assert dna_agg["axes"]["apex_commitment"] > dna_con["axes"]["apex_commitment"]
    assert dna_agg["axes"]["aero_confidence"] > dna_con["axes"]["aero_confidence"]


@pytest.mark.parametrize(
    "axes,expected_archetype",
    [
        (
            {
                "trail_braking": 88.0,
                "throttle_aggression": 55.0,
                "steering_smoothness": 50.0,
                "rpm_exploitation": 55.0,
                "apex_commitment": 68.0,
                "aero_confidence": 55.0,
            },
            "Aggressive Trail-Braker",
        ),
        (
            {
                "trail_braking": 48.0,
                "throttle_aggression": 89.0,
                "steering_smoothness": 55.0,
                "rpm_exploitation": 68.0,
                "apex_commitment": 52.0,
                "aero_confidence": 54.0,
            },
            "Early Throttle Committer",
        ),
        (
            {
                "trail_braking": 50.0,
                "throttle_aggression": 48.0,
                "steering_smoothness": 90.0,
                "rpm_exploitation": 50.0,
                "apex_commitment": 86.0,
                "aero_confidence": 58.0,
            },
            "Smooth Momentum Driver",
        ),
        (
            {
                "trail_braking": 50.0,
                "throttle_aggression": 52.0,
                "steering_smoothness": 58.0,
                "rpm_exploitation": 52.0,
                "apex_commitment": 68.0,
                "aero_confidence": 92.0,
            },
            "High-Speed Aero Specialist",
        ),
        (
            {
                "trail_braking": 48.0,
                "throttle_aggression": 56.0,
                "steering_smoothness": 52.0,
                "rpm_exploitation": 91.0,
                "apex_commitment": 50.0,
                "aero_confidence": 50.0,
            },
            "Rev-Band Exploiter",
        ),
        (
            {
                "trail_braking": 62.0,
                "throttle_aggression": 60.0,
                "steering_smoothness": 63.0,
                "rpm_exploitation": 61.0,
                "apex_commitment": 64.0,
                "aero_confidence": 60.0,
            },
            "Balanced All-Rounder",
        ),
    ],
)
def test_classify_driving_style_archetypes(axes, expected_archetype):
    """Verify each archetype badge is selected when its signature traits dominate."""
    arch, desc = _classify_driving_style(axes)
    assert arch == expected_archetype
    assert isinstance(desc, str) and len(desc) > 15


def test_build_driving_style_dna_fig_single_and_compare():
    """Verify spider radar figure builder produces valid Scatterpolar traces in single and compare modes."""
    df1 = _make_synthetic_lap(trail_brake_depth_m=55.0)
    df2 = _make_synthetic_lap(trail_brake_depth_m=20.0, throttle_ramp_rate=1.9)
    dna1 = _calculate_driving_style_dna(df1)
    dna2 = _calculate_driving_style_dna(df2)

    fig_single = build_driving_style_dna_fig(dna1, driver1="VER", colour1="#3671C6")
    assert isinstance(fig_single, go.Figure)
    # Benchmark trace + Driver 1 trace
    assert len(fig_single.data) == 2
    assert all(isinstance(t, go.Scatterpolar) for t in fig_single.data)
    assert len(fig_single.data[1].r) == 7  # 6 axes + closed loop

    fig_comp = build_driving_style_dna_fig(
        dna1,
        dna2=dna2,
        driver1="VER",
        driver2="NOR",
        colour1="#3671C6",
        colour2="#FF8000",
        fmt_func1=lambda d: f"{d} · Red Bull",
        fmt_func2=lambda d: f"{d} · McLaren",
    )
    assert isinstance(fig_comp, go.Figure)
    # Benchmark trace + Driver 1 + Driver 2
    assert len(fig_comp.data) == 3
    assert "VER · Red Bull" in fig_comp.data[1].name
    assert "NOR · McLaren" in fig_comp.data[2].name


def test_null_and_empty_handling():
    """Verify graceful None returns on empty or invalid inputs."""
    assert _calculate_driving_style_dna(None) is None
    assert _calculate_driving_style_dna(pd.DataFrame()) is None
    assert _calculate_driving_style_dna(pd.DataFrame({"Distance": [1, 2], "Speed": [100, 110]})) is None
    assert build_driving_style_dna_fig(None) is None
    assert build_driving_style_dna_fig({}) is None
    env = _build_dna_benchmark_envelope(None)
    assert len(env) == 6
