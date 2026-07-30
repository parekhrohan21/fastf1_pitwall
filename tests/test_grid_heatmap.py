import pytest
import pandas as pd
import numpy as np
from src.data.loader import _build_grid_heatmap_data


@pytest.fixture
def mock_sector_laps_data():
    """Return a mock laps DataFrame populated with sector split times."""
    return pd.DataFrame({
        "Driver": ["NOR", "NOR", "VER", "VER", "HAM", "HAM"],
        "LapNumber": [1, 2, 1, 2, 1, 2],
        "Sector1Time": [
            pd.to_timedelta("25.1s"), pd.to_timedelta("25.0s"),
            pd.to_timedelta("25.3s"), pd.to_timedelta("25.2s"),
            pd.to_timedelta("25.5s"), pd.to_timedelta("25.4s")
        ],
        "Sector2Time": [
            pd.to_timedelta("30.2s"), pd.to_timedelta("30.1s"),
            pd.to_timedelta("30.0s"), pd.to_timedelta("29.9s"),
            pd.to_timedelta("30.4s"), pd.to_timedelta("30.3s")
        ],
        "Sector3Time": [
            pd.to_timedelta("26.0s"), pd.to_timedelta("25.9s"),
            pd.to_timedelta("26.1s"), pd.to_timedelta("26.0s"),
            pd.to_timedelta("26.3s"), pd.to_timedelta("26.2s")
        ],
        "LapTime": [
            pd.to_timedelta("81.3s"), pd.to_timedelta("81.0s"),
            pd.to_timedelta("81.4s"), pd.to_timedelta("81.1s"),
            pd.to_timedelta("82.2s"), pd.to_timedelta("81.9s")
        ],
        "SpeedST": [325.0, 326.0, 328.0, 329.0, 322.0, 323.0],
        "SpeedI1": [280.0, 281.0, 285.0, 286.0, 278.0, 279.0],
        "SpeedI2": [290.0, 291.0, 294.0, 295.0, 288.0, 289.0],
        "SpeedFL": [240.0, 241.0, 243.0, 244.0, 238.0, 239.0],
    })


def test_build_grid_heatmap_data_sectors(mock_sector_laps_data):
    res = _build_grid_heatmap_data("2024_Test_R", mock_sector_laps_data, mode="Sectors")
    assert res is not None
    assert "drivers" in res
    assert "columns" in res
    assert "deltas" in res
    assert len(res["drivers"]) == 3
    assert res["columns"] == ["Sector 1", "Sector 2", "Sector 3", "Theoretical Best", "Actual Best"]
    assert res["deltas"].shape == (3, 5)
    # Minimum delta should be 0.0s for the fastest sector drivers
    assert np.min(res["deltas"]) == 0.0


def test_build_grid_heatmap_data_laps(mock_sector_laps_data):
    res = _build_grid_heatmap_data("2024_Test_R", mock_sector_laps_data, mode="Laps")
    assert res is not None
    assert len(res["columns"]) == 2  # Lap 1, Lap 2
    assert res["deltas"].shape == (3, 2)


def test_build_grid_heatmap_data_speed(mock_sector_laps_data):
    res = _build_grid_heatmap_data("2024_Test_R", mock_sector_laps_data, mode="Speed")
    assert res is not None
    assert len(res["columns"]) == 4  # ST, I1, I2, FL Speed
    assert res["deltas"].shape == (3, 4)
    # Deficit vs top speed (VER is fastest, deficit for VER ST speed should be 0)
    assert np.min(res["deltas"]) == 0.0


def test_build_grid_heatmap_data_empty():
    res = _build_grid_heatmap_data("2024_Test_R", pd.DataFrame(), mode="Sectors")
    assert res is None

    res_none = _build_grid_heatmap_data("2024_Test_R", None, mode="Sectors")
    assert res_none is None
