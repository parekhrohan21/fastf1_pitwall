import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.data.loader import _calculate_braking_metrics
from src.charts.plotly import build_braking_efficiency_fig


def _create_synthetic_braking_telemetry(apex_dist: float = 1300.0) -> pd.DataFrame:
    """Create a realistic synthetic corner telemetry dataset around an apex."""
    # Distance from 1000m to 1400m with 10m step
    distances = np.arange(1000.0, 1410.0, 10.0)
    n = len(distances)

    # Time series in 0.1s increments
    times = pd.to_timedelta(np.arange(0, n * 0.1, 0.1), unit="s")

    # Speed: 320 km/h on straight, decelerates to 90 km/h at apex (1300m), accelerates to 180 km/h
    speeds = []
    for d in distances:
        if d < 1150.0:
            speeds.append(320.0)
        elif d <= apex_dist:
            # Linear decel from 320 to 90
            speeds.append(320.0 - (320.0 - 90.0) * ((d - 1150.0) / (apex_dist - 1150.0)))
        else:
            # Accel from 90 to 180
            speeds.append(90.0 + (180.0 - 90.0) * ((d - apex_dist) / (1400.0 - apex_dist)))

    # Brake: 0 before 1150, 100% at 1150-1220, trails to 0 at 1280
    brakes = []
    for d in distances:
        if d < 1150.0:
            brakes.append(0.0)
        elif d <= 1220.0:
            brakes.append(100.0)
        elif d <= 1280.0:
            brakes.append(100.0 * (1.0 - (d - 1220.0) / 60.0))
        else:
            brakes.append(0.0)

    # Throttle: 100% on straight, 0% during braking, picks up after 1290m
    throttles = []
    for d in distances:
        if d < 1150.0:
            throttles.append(100.0)
        elif d < 1290.0:
            throttles.append(0.0)
        else:
            throttles.append(min(100.0, (d - 1290.0) * 1.0))

    return pd.DataFrame({
        "Distance": distances,
        "Speed": np.array(speeds, dtype=float),
        "Time": times,
        "Brake": np.array(brakes, dtype=float),
        "Throttle": np.array(throttles, dtype=float),
    })


def test_calculate_braking_metrics_valid_data():
    apex_dist = 1300.0
    df = _create_synthetic_braking_telemetry(apex_dist=apex_dist)
    metrics = _calculate_braking_metrics(df, apex_dist)

    assert metrics["initial_brake_dist"] is not None
    # Initial brake applied at 1150m, apex at 1300m -> 150m before apex
    assert abs(metrics["initial_brake_dist"] - 150.0) < 15.0

    # Peak deceleration should be negative and around -3 to -6 G
    assert metrics["peak_decel"] is not None
    assert metrics["peak_decel"] < -1.0

    # Trail brake release should be before apex (~20m to apex)
    assert metrics["trail_brake_release"] is not None
    assert metrics["trail_brake_release"] > 0

    # Trail braking distance
    assert metrics["trail_braking_dist"] is not None
    assert metrics["trail_braking_dist"] > 0

    # Apex speed should be minimum speed (approx 90 km/h)
    assert metrics["apex_speed"] is not None
    assert abs(metrics["apex_speed"] - 90.0) < 5.0

    # Processed DataFrame should contain DistToApex and G_Force
    assert metrics["df_processed"] is not None
    assert "DistToApex" in metrics["df_processed"].columns
    assert "G_Force" in metrics["df_processed"].columns


def test_calculate_braking_metrics_boolean_brake():
    apex_dist = 1300.0
    df = _create_synthetic_braking_telemetry(apex_dist=apex_dist)
    # Convert Brake to boolean 0/1
    df["Brake"] = (df["Brake"] > 0).astype(int)

    metrics = _calculate_braking_metrics(df, apex_dist)
    assert metrics["initial_brake_dist"] is not None
    assert abs(metrics["initial_brake_dist"] - 150.0) < 15.0
    assert metrics["peak_decel"] is not None


def test_calculate_braking_metrics_edge_cases():
    apex_dist = 1300.0

    # None DataFrame
    assert _calculate_braking_metrics(None, apex_dist)["initial_brake_dist"] is None

    # Empty DataFrame
    assert _calculate_braking_metrics(pd.DataFrame(), apex_dist)["initial_brake_dist"] is None

    # Missing Brake column
    df_no_brake = pd.DataFrame({
        "Distance": [1000.0, 1100.0, 1200.0],
        "Speed": [300.0, 250.0, 200.0],
        "Time": pd.to_timedelta([0, 1, 2], unit="s")
    })
    res_no_brake = _calculate_braking_metrics(df_no_brake, apex_dist)
    assert res_no_brake["initial_brake_dist"] is None
    assert res_no_brake["apex_speed"] == 200.0

    # Identical timestamps (zero dt)
    df_zero_dt = pd.DataFrame({
        "Distance": [1000.0, 1000.0, 1000.0],
        "Speed": [300.0, 300.0, 300.0],
        "Time": pd.to_timedelta([1, 1, 1], unit="s"),
        "Brake": [0.0, 0.0, 0.0],
        "Throttle": [100.0, 100.0, 100.0],
    })
    res_zero_dt = _calculate_braking_metrics(df_zero_dt, apex_dist)
    assert res_zero_dt["initial_brake_dist"] is None


def test_build_braking_efficiency_fig_single_driver():
    apex_dist = 1300.0
    win1 = _create_synthetic_braking_telemetry(apex_dist=apex_dist)
    fig = build_braking_efficiency_fig(
        win1=win1, win2=None,
        driver1="4", driver2=None,
        colour1="#FF8000", colour2=None,
        apex_dist=apex_dist,
        fmt_func1=lambda d: f"NOR ({d})"
    )

    assert isinstance(fig, go.Figure)
    # Check that traces exist
    assert len(fig.data) >= 3
    # Check that driver label was applied
    trace_names = [t.name for t in fig.data if t.name]
    assert any("NOR (4)" in name for name in trace_names)


def test_build_braking_efficiency_fig_compare_mode():
    apex_dist = 1300.0
    win1 = _create_synthetic_braking_telemetry(apex_dist=apex_dist)
    win2 = _create_synthetic_braking_telemetry(apex_dist=apex_dist)
    # Give driver 2 slightly earlier braking (at 1120m instead of 1150m)
    win2["Speed"] = win2["Speed"] * 0.98

    fig = build_braking_efficiency_fig(
        win1=win1, win2=win2,
        driver1="4", driver2="1",
        colour1="#FF8000", colour2="#3671C6",
        apex_dist=apex_dist,
        fmt_func1=lambda d: f"NOR ({d})",
        fmt_func2=lambda d: f"VER ({d})"
    )

    assert isinstance(fig, go.Figure)
    trace_names = [t.name for t in fig.data if t.name]
    assert any("NOR (4)" in name for name in trace_names)
    assert any("VER (1)" in name for name in trace_names)


def test_build_braking_efficiency_fig_empty_inputs():
    fig = build_braking_efficiency_fig(
        win1=None, win2=None,
        driver1="4", driver2=None,
        colour1="#FF8000", colour2=None,
        apex_dist=1000.0
    )
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
