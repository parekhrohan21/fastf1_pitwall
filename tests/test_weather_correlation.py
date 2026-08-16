import pandas as pd
import numpy as np
import pytest
from src.data.loader import _build_weather_correlation_data
from src.charts.plotly import build_weather_correlation_fig


def test_build_weather_correlation_data_basic():
    # Build synthetic laps DataFrame with TrackTemp and LapTime
    laps_data = {
        "Driver": ["NOR"] * 10 + ["VER"] * 10,
        "LapNumber": list(range(1, 11)) * 2,
        "LapTime": [pd.Timedelta(seconds=90 + i * 0.1) for i in range(10)] + [pd.Timedelta(seconds=89.5 + i * 0.15) for i in range(10)],
        "IsAccurate": [True] * 20,
        "TrackTemp": [35.0 + i * 0.5 for i in range(10)] + [35.0 + i * 0.5 for i in range(10)],
        "AirTemp": [22.0] * 20,
        "Rainfall": [False] * 20,
        "Compound": ["SOFT"] * 10 + ["SOFT"] * 10,
        "Time": [pd.Timedelta(seconds=100 * i) for i in range(1, 11)] * 2
    }
    laps_df = pd.DataFrame(laps_data)

    res = _build_weather_correlation_data("2024_Test_Race", laps_df, drivers=["NOR", "VER"])
    assert res is not None
    assert "stats" in res
    assert "laps_weather_df" in res
    assert "driver_laps" in res

    stats = res["stats"]
    assert stats["track_temp_min"] == 35.0
    assert stats["track_temp_max"] == 39.5
    assert stats["temp_correlation"] is not None
    assert stats["rainfall_detected"] is False


def test_build_weather_correlation_crossover_and_figure():
    # Test slick to wet crossover transition
    laps_data = {
        "Driver": ["NOR"] * 6,
        "LapNumber": [1, 2, 3, 4, 5, 6],
        "LapTime": [pd.Timedelta(seconds=90.0 + i) for i in range(6)],
        "IsAccurate": [True] * 6,
        "TrackTemp": [32.0, 31.5, 30.0, 28.0, 27.5, 27.0],
        "AirTemp": [20.0] * 6,
        "Rainfall": [False, False, True, True, True, True],
        "Compound": ["MEDIUM", "MEDIUM", "INTERMEDIATE", "INTERMEDIATE", "WET", "WET"],
        "Time": [pd.Timedelta(seconds=100 * i) for i in range(1, 7)]
    }
    laps_df = pd.DataFrame(laps_data)

    res = _build_weather_correlation_data("2024_Wet_Race", laps_df, drivers=["NOR"])
    assert res is not None
    assert res["stats"]["rainfall_detected"] is True
    assert res["stats"]["wet_laps_count"] == 4

    # Build figure
    fig = build_weather_correlation_fig(res, driver_colors={"NOR": "#FF8000"}, driver_labels={"NOR": "NOR · Norris"})
    assert fig is not None
