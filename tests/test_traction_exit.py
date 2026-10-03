import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.data.loader import _calculate_traction_metrics
from src.charts.plotly import build_traction_exit_fig


def _create_synthetic_traction_telemetry(
    apex_dist: float = 1200.0,
    initial_pick_up_m: float = 10.0,
    full_throttle_m: float = 60.0,
    hesitations: bool = False,
    oversteer: bool = False
) -> pd.DataFrame:
    """
    Create synthetic corner exit telemetry from apex - 60m to apex + 250m.
    apex_dist: distance of apex in meters.
    initial_pick_up_m: meters post-apex where throttle > 5%.
    full_throttle_m: meters post-apex where throttle reaches 100%.
    hesitations: whether to inject throttle drops during acceleration phase.
    oversteer: whether to inject counter-steering movements.
    """
    distances = np.arange(apex_dist - 60.0, apex_dist + 260.0, 5.0)
    n = len(distances)
    times = pd.to_timedelta(np.arange(0, n * 0.05, 0.05), unit="s")

    speeds = []
    throttles = []
    steerings = []

    init_d = apex_dist + initial_pick_up_m
    full_d = apex_dist + full_throttle_m

    for d in distances:
        # Speed: decelerates down to 85 km/h at apex, accelerates up to 240 km/h
        if d <= apex_dist:
            spd = 85.0 + 80.0 * ((apex_dist - d) / 60.0) ** 1.2
        else:
            spd = 85.0 + (240.0 - 85.0) * min(1.0, ((d - apex_dist) / 250.0) ** 0.9)
        speeds.append(spd)

        # Throttle: 0% before initial pick-up, ramps to 100% at full_d, stays at 100%
        if d < init_d:
            th = 0.0
        elif d >= full_d:
            th = 100.0
        else:
            progress = (d - init_d) / max(1.0, (full_d - init_d))
            th = 5.0 + 95.0 * progress
        throttles.append(th)

        # Steering: right-hand turn (+25 degrees at apex, unwinds to 0)
        if d < apex_dist:
            st_ang = 25.0 * (1.0 - (apex_dist - d) / 100.0)
        else:
            st_ang = max(0.0, 25.0 * (1.0 - (d - apex_dist) / 120.0))
        steerings.append(st_ang)

    df = pd.DataFrame({
        "Distance": distances,
        "Speed": np.array(speeds, dtype=float),
        "Time": times,
        "Throttle": np.array(throttles, dtype=float),
        "Steering": np.array(steerings, dtype=float),
    })

    if hesitations:
        # Inject two distinct throttle drops during acceleration
        mask1 = (df["Distance"] >= init_d + 15.0) & (df["Distance"] <= init_d + 25.0)
        df.loc[mask1, "Throttle"] = df.loc[mask1, "Throttle"] - 20.0
        mask2 = (df["Distance"] >= init_d + 35.0) & (df["Distance"] <= init_d + 45.0)
        df.loc[mask2, "Throttle"] = df.loc[mask2, "Throttle"] - 15.0

    if oversteer:
        # Inject counter-steering reversals during exit
        mask_ov = (df["Distance"] >= apex_dist + 20.0) & (df["Distance"] <= apex_dist + 30.0)
        df.loc[mask_ov, "Steering"] = -8.0

    return df


def test_calculate_traction_metrics_valid_smooth():
    """Test traction metrics for a smooth progressive throttle exit."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(
        apex_dist=apex_dist, initial_pick_up_m=10.0, full_throttle_m=60.0
    )
    metrics = _calculate_traction_metrics(df, apex_dist)

    assert metrics["apex_dist"] == 1200.0
    assert metrics["apex_speed"] is not None
    assert abs(metrics["apex_speed"] - 85.0) < 5.0

    assert metrics["dist_to_initial_throttle"] is not None
    assert abs(metrics["dist_to_initial_throttle"] - 10.0) <= 5.0

    assert metrics["dist_to_full_throttle"] is not None
    assert abs(metrics["dist_to_full_throttle"] - 60.0) <= 5.0

    assert metrics["throttle_application_dist"] is not None
    assert abs(metrics["throttle_application_dist"] - 50.0) <= 5.0

    assert metrics["throttle_ramp_rate"] is not None
    assert metrics["throttle_ramp_rate"] > 1.0  # Approx 95% over 50m = ~1.9 %/m

    assert metrics["hesitation_count"] == 0
    assert len(metrics["hesitations"]) == 0

    assert metrics["traction_aggression_score"] is not None
    assert metrics["traction_aggression_score"] >= 70.0

    assert metrics["exit_speed_100m"] is not None
    assert metrics["exit_speed_100m"] > metrics["apex_speed"]

    assert metrics["df_processed"] is not None
    assert "DistToApex" in metrics["df_processed"].columns
    assert "G_Force" in metrics["df_processed"].columns
    assert "Throttle_Pct" in metrics["df_processed"].columns


def test_calculate_traction_metrics_with_hesitations():
    """Test detection of throttle hesitation/lift modulations."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(
        apex_dist=apex_dist, initial_pick_up_m=10.0, full_throttle_m=70.0, hesitations=True
    )
    metrics = _calculate_traction_metrics(df, apex_dist)

    assert metrics["hesitation_count"] >= 1
    assert len(metrics["hesitations"]) >= 1

    # Score should be penalized compared to smooth run
    smooth_df = _create_synthetic_traction_telemetry(
        apex_dist=apex_dist, initial_pick_up_m=10.0, full_throttle_m=70.0, hesitations=False
    )
    smooth_metrics = _calculate_traction_metrics(smooth_df, apex_dist)
    assert metrics["traction_aggression_score"] < smooth_metrics["traction_aggression_score"]


def test_calculate_traction_metrics_with_oversteer():
    """Test oversteer counter-steer correction detection."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(
        apex_dist=apex_dist, oversteer=True
    )
    metrics = _calculate_traction_metrics(df, apex_dist)

    assert metrics["oversteer_corrections_count"] is not None
    assert metrics["oversteer_corrections_count"] >= 1


def test_calculate_traction_metrics_normalized_throttle():
    """Test handling of 0.0 to 1.0 normalized throttle telemetry."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(apex_dist=apex_dist)
    df["Throttle"] = df["Throttle"] / 100.0  # normalize to 0..1

    metrics = _calculate_traction_metrics(df, apex_dist)
    assert metrics["dist_to_initial_throttle"] is not None
    assert metrics["dist_to_full_throttle"] is not None
    assert metrics["throttle_ramp_rate"] is not None
    assert metrics["throttle_ramp_rate"] > 0.5


def test_calculate_traction_metrics_edge_cases():
    """Test edge cases: None, empty DataFrame, missing columns, constant zero throttle."""
    apex_dist = 1000.0

    # None input
    m_none = _calculate_traction_metrics(None, apex_dist)
    assert m_none["apex_speed"] is None
    assert m_none["hesitation_count"] == 0

    # Empty DataFrame
    m_empty = _calculate_traction_metrics(pd.DataFrame(), apex_dist)
    assert m_empty["apex_speed"] is None

    # Missing Throttle column
    df_no_th = pd.DataFrame({
        "Distance": [950, 1000, 1050],
        "Speed": [100, 90, 120],
        "Time": [0.0, 1.0, 2.0]
    })
    m_no_th = _calculate_traction_metrics(df_no_th, apex_dist)
    assert m_no_th["apex_speed"] is not None
    assert m_no_th["dist_to_initial_throttle"] is None

    # Constant zero throttle
    df_zero_th = df_no_th.copy()
    df_zero_th["Throttle"] = [0.0, 0.0, 0.0]
    m_zero = _calculate_traction_metrics(df_zero_th, apex_dist)
    assert m_zero["dist_to_initial_throttle"] is None
    assert m_zero["dist_to_full_throttle"] is None


def test_calculate_traction_metrics_flat_out_corner():
    """A corner taken at full throttle has no pick-up: flagged flat out, no ramp or score."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(apex_dist=apex_dist)
    df["Throttle"] = 100.0

    metrics = _calculate_traction_metrics(df, apex_dist)
    assert metrics["flat_out"] is True
    assert metrics["dist_to_initial_throttle"] is None
    assert metrics["throttle_ramp_rate"] is None
    assert metrics["traction_aggression_score"] is None
    assert metrics["hesitation_count"] == 0
    # Exit metrics do not depend on a pick-up and are still reported
    assert metrics["exit_speed_100m"] is not None
    assert metrics["peak_exit_accel_g"] is not None

    assert build_traction_exit_fig(df, None, "VER", None, "#3671C6", None, apex_dist) is not None


def test_calculate_traction_metrics_flat_out_threshold():
    """A small breath above the threshold is flat out; a real lift below it is not."""
    apex_dist = 1200.0

    breath = _create_synthetic_traction_telemetry(apex_dist=apex_dist)
    breath["Throttle"] = 100.0
    near_apex = (breath["Distance"] >= apex_dist - 10) & (breath["Distance"] <= apex_dist + 10)
    breath.loc[near_apex, "Throttle"] = 90.0
    assert _calculate_traction_metrics(breath, apex_dist)["flat_out"] is True

    lift = breath.copy()
    lift.loc[near_apex, "Throttle"] = 60.0
    m_lift = _calculate_traction_metrics(lift, apex_dist)
    assert m_lift["flat_out"] is False
    assert m_lift["traction_aggression_score"] is not None


def test_calculate_traction_metrics_snap_pick_up():
    """Closed-to-full between two samples must give a steep ramp, not 0 %/m."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(
        apex_dist=apex_dist, initial_pick_up_m=10.0, full_throttle_m=10.0
    )
    metrics = _calculate_traction_metrics(df, apex_dist)

    assert metrics["flat_out"] is False
    assert metrics["dist_to_initial_throttle"] == metrics["dist_to_full_throttle"]
    # 0 -> 100% across one 5m sample
    assert metrics["throttle_application_dist"] == pytest.approx(5.0)
    assert metrics["throttle_ramp_rate"] == pytest.approx(20.0)
    assert metrics["throttle_gradient"] > 0


def test_build_traction_exit_fig_single_driver():
    """Test Plotly figure generation for a single driver."""
    apex_dist = 1200.0
    df = _create_synthetic_traction_telemetry(apex_dist=apex_dist, hesitations=True)
    fig = build_traction_exit_fig(
        win1=df, win2=None,
        driver1="VER", driver2=None,
        colour1="#3671C6", colour2=None,
        apex_dist=apex_dist
    )

    assert fig is not None
    assert isinstance(fig, go.Figure)
    # Check trace count (throttle, initial marker, full marker, hesitation marker, speed, accel)
    assert len(fig.data) >= 4
    # Check layout
    assert fig.layout.height == 620


def test_build_traction_exit_fig_two_drivers():
    """Test Plotly figure generation comparing two drivers."""
    apex_dist = 1200.0
    df1 = _create_synthetic_traction_telemetry(apex_dist=apex_dist, full_throttle_m=50.0)
    df2 = _create_synthetic_traction_telemetry(apex_dist=apex_dist, full_throttle_m=80.0, hesitations=True)

    fig = build_traction_exit_fig(
        win1=df1, win2=df2,
        driver1="VER", driver2="HAM",
        colour1="#3671C6", colour2="#27F4D2",
        apex_dist=apex_dist,
        fmt_func1=lambda d: f"Max {d}", fmt_func2=lambda d: f"Lewis {d}"
    )

    assert fig is not None
    assert isinstance(fig, go.Figure)
    # Both drivers should have traces
    trace_names = [t.name for t in fig.data if t.name is not None]
    assert any("VER" in name or "Max" in name for name in trace_names)
    assert any("HAM" in name or "Lewis" in name for name in trace_names)


def test_build_traction_exit_fig_invalid_input():
    """Test figure builder handles None and empty data gracefully."""
    assert build_traction_exit_fig(None, None, "VER", None, "#fff", None, 1000.0) is None
    assert build_traction_exit_fig(pd.DataFrame(), None, "VER", None, "#fff", None, 1000.0) is None
