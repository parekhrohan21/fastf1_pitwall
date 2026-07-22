import pytest
import pandas as pd
import numpy as np
from src.data.loader import _build_final_classification, _build_fuel_adjusted

def test_build_final_classification_race(mock_race_results):
    """Test classification builder under Race conditions."""
    df = _build_final_classification("2024_China_R", mock_race_results)
    assert df is not None
    assert "Pos" in df.columns
    assert list(df["Pos"]) == [1, 2, 3]
    assert df.loc[0, "FullName"] == "Max Verstappen"

def test_build_final_classification_qualifying(mock_qualifying_results):
    """Test classification builder under Qualifying conditions."""
    df = _build_final_classification("2024_China_Q", mock_qualifying_results)
    assert df is not None
    assert "Pos" in df.columns
    assert "Q3" in df.columns
    assert df.loc[0, "FullName"] == "Lando Norris"

def test_build_final_classification_practice(mock_practice_results):
    """Test that practice sessions with NaN positions return 'PRACTICE' info code."""
    res = _build_final_classification("2024_China_FP1", mock_practice_results)
    assert res == "PRACTICE"

def test_build_final_classification_empty():
    """Test that empty results dataframe returns None safely."""
    df = pd.DataFrame()
    res = _build_final_classification("2024_China_R", df)
    assert res is None

def test_build_fuel_adjusted_basic(mock_laps_data):
    """Test that fuel adjusted pace calculates correct subtraction values."""
    fuel_effect = 0.03
    df = _build_fuel_adjusted("4", "2024_China_R", fuel_effect, mock_laps_data)
    
    assert df is not None
    assert len(df) == 4  # Should filter out out-lap (lap 1), outlier (lap 1), and pit-in (lap 6)
    
    # Max lap number in mock_laps_data is 6
    # Let's inspect Lap 2
    # FuelRemaining = 6 - 2 = 4 laps
    # FuelCorrection = 4 * 0.03 = 0.12 s
    # LapTimeSec = 81.2
    # FuelAdjSec = 81.2 - 0.12 = 81.08
    lap2 = df[df["LapNumber"] == 2].iloc[0]
    assert pytest.approx(lap2["FuelCorrection"]) == 0.12
    assert pytest.approx(lap2["FuelAdjSec"]) == 81.08

def test_build_fuel_adjusted_pit_filtering(mock_laps_data):
    """Test that pit-in and pit-out laps are successfully excluded."""
    df = _build_fuel_adjusted("4", "2024_China_R", 0.03, mock_laps_data)
    
    # Lap 1 has PitOutTime != NaT -> should be excluded
    # Lap 6 has PitInTime != NaT -> should be excluded
    assert 1 not in df["LapNumber"].values
    assert 6 not in df["LapNumber"].values

def test_build_fuel_adjusted_outliers(mock_laps_data):
    """Test that extreme outlier laps (> 2.5x median) are filtered out."""
    df = _build_fuel_adjusted("4", "2024_China_R", 0.03, mock_laps_data)
    
    # Median flyer lap time is around 81.2s.
    # Lap 1 in mock is 95s (but it is also a pit-out lap).
    # If we had a flyer lap that was > 200s, it would be excluded.
    
    # Let's add a test with an explicit slow flyer to verify outlier logic
    slow_laps = pd.DataFrame({
        "Driver": ["4", "4", "4"],
        "LapNumber": [1, 2, 3],
        "LapTime": [
            pd.to_timedelta("80s"),
            pd.to_timedelta("81s"),
            pd.to_timedelta("300s")  # Outlier > 2.5 * median
        ],
        "PitOutTime": [pd.NaT, pd.NaT, pd.NaT],
        "PitInTime": [pd.NaT, pd.NaT, pd.NaT],
        "Compound": ["SOFT", "SOFT", "SOFT"],
        "TyreLife": [1, 2, 3]
    })
    
    res = _build_fuel_adjusted("4", "2024_China_R", 0.03, slow_laps)
    assert res is not None
    assert 3 not in res["LapNumber"].values
    assert len(res) == 2
