import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.data.loader import _calculate_gear_shift_metrics
from src.charts.plotly import build_gear_shift_fig


def _create_synthetic_gear_telemetry(include_short_shift: bool = True) -> pd.DataFrame:
    """Create a realistic synthetic lap telemetry dataset with RPM, Gear, Speed, Throttle, Distance."""
    # 500 points covering 0 to 5000m (10m step)
    distances = np.arange(0, 5000, 10)
    n = len(distances)

    gears = []
    rpms = []
    speeds = []
    throttles = []

    current_gear = 1
    current_rpm = 4000.0

    for i, d in enumerate(distances):
        # Progress through gears 1 to 8, then downshift to 3, etc.
        if i == 30:
            # Upshift 1 -> 2 at 11,500 RPM
            current_gear = 2
            current_rpm = 9000.0
        elif i == 70:
            # Upshift 2 -> 3: short shift at 10,500 RPM with 100% throttle
            current_gear = 3
            current_rpm = 8200.0 if include_short_shift else 11500.0
        elif i == 120:
            # Upshift 3 -> 4 at redline 11,900 RPM
            current_gear = 4
            current_rpm = 9200.0
        elif i == 180:
            # Upshift 4 -> 5 at 11,600 RPM
            current_gear = 5
            current_rpm = 9500.0
        elif i == 250:
            # Downshift 5 -> 4
            current_gear = 4
            current_rpm = 11000.0
        elif i == 270:
            # Downshift 4 -> 3
            current_gear = 3
            current_rpm = 11200.0
        elif i == 330:
            # Upshift 3 -> 4 at 11,600 RPM
            current_gear = 4
            current_rpm = 9400.0
        elif i == 400:
            # Upshift 4 -> 5 at 11,700 RPM
            current_gear = 5
            current_rpm = 9600.0
        else:
            # Rising RPM in gear
            current_rpm = min(12000.0, current_rpm + 40.0)

        speed = 80.0 + (current_gear * 30.0) + (current_rpm / 300.0)
        throttle = 100.0 if (i % 80 > 15) else 20.0

        gears.append(current_gear)
        # Pre-shift RPM simulation: set RPM just before the shift
        rpms.append(current_rpm)
        speeds.append(speed)
        throttles.append(throttle)

    # Explicitly set pre-shift RPM values to ensure test repeatability
    # Index 69 is just before upshift 2->3
    if include_short_shift:
        rpms[69] = 10500.0  # < 11000 -> short shift
        throttles[69] = 95.0
    else:
        rpms[69] = 11500.0
        throttles[69] = 95.0

    # Index 119 is just before upshift 3->4
    rpms[119] = 11950.0  # >= 11800 -> redline shift
    throttles[119] = 100.0

    return pd.DataFrame({
        "Distance": distances,
        "Gear": gears,
        "RPM": rpms,
        "Speed": speeds,
        "Throttle": throttles
    })


def test_calculate_gear_shift_metrics_valid():
    df = _create_synthetic_gear_telemetry(include_short_shift=True)
    metrics = _calculate_gear_shift_metrics(df)

    assert metrics["avg_rpm"] is not None
    assert metrics["avg_rpm"] > 4000.0
    assert metrics["max_rpm"] is not None
    assert metrics["max_rpm"] >= 11950.0

    assert metrics["total_upshifts"] > 0
    assert metrics["total_downshifts"] > 0
    assert metrics["total_shifts"] == metrics["total_upshifts"] + metrics["total_downshifts"]

    assert metrics["short_shifts_count"] >= 1
    assert metrics["redline_shifts_count"] >= 1
    assert metrics["upshift_rpm_mean"] is not None
    assert 10000.0 <= metrics["upshift_rpm_mean"] <= 12500.0

    # Gear distribution
    gear_dist = metrics["gear_distribution"]
    assert len(gear_dist) == 8
    total_pct = sum(gear_dist.values())
    assert 99.0 <= total_pct <= 101.0  # close to 100% accounting for rounding

    # Shifts DataFrame
    shifts_df = metrics["shifts_df"]
    assert not shifts_df.empty
    assert set(["Distance", "Speed", "RPM", "RPM_Post", "from_gear", "to_gear", "type", "is_short_shift", "is_redline"]).issubset(shifts_df.columns)


def test_calculate_gear_shift_metrics_ngar_alias():
    """Verify that FastF1 'nGear' column is supported identically to 'Gear'."""
    df = _create_synthetic_gear_telemetry()
    df["nGear"] = df.pop("Gear")
    metrics = _calculate_gear_shift_metrics(df)

    assert metrics["total_shifts"] > 0
    assert metrics["avg_rpm"] is not None
    assert sum(metrics["gear_distribution"].values()) > 0


def test_calculate_gear_shift_metrics_no_short_shifts():
    df = _create_synthetic_gear_telemetry(include_short_shift=False)
    metrics = _calculate_gear_shift_metrics(df)
    assert metrics["short_shifts_count"] == 0


def test_calculate_gear_shift_metrics_edge_cases():
    # 1. None dataframe
    m_none = _calculate_gear_shift_metrics(None)
    assert m_none["total_shifts"] == 0
    assert m_none["avg_rpm"] is None
    assert m_none["shifts_df"].empty

    # 2. Empty dataframe
    m_empty = _calculate_gear_shift_metrics(pd.DataFrame())
    assert m_empty["total_shifts"] == 0
    assert m_empty["avg_rpm"] is None

    # 3. Missing essential columns
    df_missing = pd.DataFrame({"Distance": [1, 2, 3], "Speed": [100, 110, 120]})
    m_missing = _calculate_gear_shift_metrics(df_missing)
    assert m_missing["total_shifts"] == 0

    # 4. Telemetry with 0 gears / neutral
    df_neutral = pd.DataFrame({
        "Distance": [10, 20, 30],
        "RPM": [4000, 4200, 4100],
        "Gear": [0, 0, 0]
    })
    m_neutral = _calculate_gear_shift_metrics(df_neutral)
    assert m_neutral["total_shifts"] == 0
    assert m_neutral["short_shifts_count"] == 0


def test_build_gear_shift_fig_single_driver():
    df = _create_synthetic_gear_telemetry()
    data1 = _calculate_gear_shift_metrics(df)

    fig = build_gear_shift_fig(
        gear_data1=data1,
        gear_data2=None,
        driver1="VER",
        driver2=None,
        colour1="#3671C6",
        colour2=None,
        fmt_func1=lambda d: f"Max Verstappen ({d})"
    )

    assert isinstance(fig, go.Figure)
    # Check that traces exist for RPM line, upshifts, and gear distribution
    trace_names = [t.name for t in fig.data if t.name]
    assert any("VER" in name for name in trace_names)
    assert any("RPM" in name for name in trace_names)


def test_build_gear_shift_fig_comparison():
    df1 = _create_synthetic_gear_telemetry(include_short_shift=True)
    df2 = _create_synthetic_gear_telemetry(include_short_shift=False)

    data1 = _calculate_gear_shift_metrics(df1)
    data2 = _calculate_gear_shift_metrics(df2)

    fig = build_gear_shift_fig(
        gear_data1=data1,
        gear_data2=data2,
        driver1="VER",
        driver2="NOR",
        colour1="#3671C6",
        colour2="#FF8000",
        fmt_func1=lambda d: f"Verstappen ({d})",
        fmt_func2=lambda d: f"Norris ({d})"
    )

    assert isinstance(fig, go.Figure)
    trace_names = [t.name for t in fig.data if t.name]
    assert any("Verstappen" in name for name in trace_names)
    assert any("Norris" in name for name in trace_names)
    # Both drivers should have traces in the layout
    assert len(fig.data) >= 4
