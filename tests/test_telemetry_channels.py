import pytest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.charts.matplotlib import (
    CHANNEL_CONFIG,
    AVAILABLE_CHANNELS,
    build_chart,
    build_delta_chart,
    build_time_delta_chart,
)


@pytest.fixture
def mock_telemetry_df():
    """Create a realistic mock telemetry dataframe for testing."""
    distance = np.linspace(0, 5000, 100)
    return pd.DataFrame({
        "Distance": distance,
        "Speed": 100 + 150 * np.sin(distance / 500),
        "Throttle": np.clip(50 + 50 * np.sin(distance / 400), 0, 100),
        "Brake": (np.sin(distance / 600) > 0.5).astype(int),
        "RPM": 10000 + 2000 * np.sin(distance / 300),
        "nGear": np.random.randint(1, 9, size=len(distance)),
        "DRS": (np.sin(distance / 1000) > 0.3).astype(int) * 12,
    })


@pytest.fixture
def mock_telemetry_df2():
    """Create a second mock telemetry dataframe for driver comparison."""
    distance = np.linspace(0, 5000, 100)
    return pd.DataFrame({
        "Distance": distance,
        "Speed": 95 + 155 * np.sin(distance / 500),
        "Throttle": np.clip(45 + 55 * np.sin(distance / 400), 0, 100),
        "Brake": (np.sin(distance / 550) > 0.5).astype(int),
        "RPM": 9800 + 2200 * np.sin(distance / 300),
        "nGear": np.random.randint(1, 9, size=len(distance)),
        "DRS": (np.sin(distance / 1000) > 0.4).astype(int) * 12,
    })


def test_available_channels_definition():
    """Test that all 6 standard telemetry channels are defined in configuration."""
    assert "Speed" in AVAILABLE_CHANNELS
    assert "Throttle" in AVAILABLE_CHANNELS
    assert "Brake" in AVAILABLE_CHANNELS
    assert "RPM" in AVAILABLE_CHANNELS
    assert "Gear" in AVAILABLE_CHANNELS
    assert "DRS" in AVAILABLE_CHANNELS
    assert len(AVAILABLE_CHANNELS) == 6


def test_build_chart_default_all_channels(mock_telemetry_df):
    """Test building chart with default channel selection (all 6 channels)."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    fig = build_chart(drivers, "Test Lap Telemetry")
    assert fig is not None
    assert len(fig.axes) == 6
    plt.close(fig)


def test_build_chart_comparison_drivers(mock_telemetry_df, mock_telemetry_df2):
    """Test building chart with 2 drivers in comparison mode."""
    drivers = [
        ("4 · NOR", "#FF8000", mock_telemetry_df),
        ("1 · VER", "#3671C6", mock_telemetry_df2),
    ]
    fig = build_chart(drivers, "NOR vs VER Comparison")
    assert fig is not None
    assert len(fig.axes) == 6
    plt.close(fig)


def test_build_chart_subset_channels(mock_telemetry_df):
    """Test building chart with custom subset of telemetry channels."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    subset = ["Speed", "Throttle"]
    fig = build_chart(drivers, "Speed & Throttle", selected_channels=subset)
    assert fig is not None
    assert len(fig.axes) == 2
    # Verify bottom subplot has x label
    assert fig.axes[-1].get_xlabel() == "Distance (m)"
    plt.close(fig)


def test_build_chart_single_channel_scaling(mock_telemetry_df):
    """Test building chart with single channel and verify dynamic height."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    fig_single = build_chart(drivers, "Speed Only", selected_channels=["Speed"])
    assert fig_single is not None
    assert len(fig_single.axes) == 1
    # Check that single-channel figure height is scaled down appropriately
    w, h = fig_single.get_size_inches()
    assert h < 6.0
    plt.close(fig_single)


def test_build_chart_empty_selection(mock_telemetry_df):
    """Test building chart with empty list returns None."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    fig = build_chart(drivers, "Empty", selected_channels=[])
    assert fig is None


def test_build_chart_invalid_channels(mock_telemetry_df):
    """Test that invalid channel names are filtered out safely."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    fig = build_chart(drivers, "Invalid", selected_channels=["NonExistentChannel", "Invalid"])
    assert fig is None

    # Mixed valid and invalid
    fig_mixed = build_chart(drivers, "Mixed", selected_channels=["Speed", "FakeChannel", "DRS"])
    assert fig_mixed is not None
    assert len(fig_mixed.axes) == 2
    plt.close(fig_mixed)


def test_build_chart_special_flags(mock_telemetry_df):
    """Test that special channel flags like gear, brake, and drs configure axes properly."""
    drivers = [("4 · NOR", "#FF8000", mock_telemetry_df)]
    fig = build_chart(drivers, "Inputs & Gear", selected_channels=["Brake", "Gear", "DRS"])
    assert fig is not None
    assert len(fig.axes) == 3
    # Gear axis y-ticks
    gear_ax = fig.axes[1]
    assert gear_ax.get_ylim() == (0.5, 8.5)
    plt.close(fig)


def test_build_delta_chart(mock_telemetry_df, mock_telemetry_df2):
    """Test building speed delta chart."""
    fig = build_delta_chart(mock_telemetry_df, mock_telemetry_df2, "#FF8000", "#3671C6", "NOR", "VER")
    assert fig is not None
    assert len(fig.axes) == 1
    assert fig.axes[0].get_ylabel() == "Δ Speed (km/h)"
    plt.close(fig)

