import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def mock_race_results():
    """Return a mock pandas DataFrame mimicking Race results."""
    return pd.DataFrame({
        "Position": [1.0, 2.0, 3.0],
        "FullName": ["Max Verstappen", "Lando Norris", "Lewis Hamilton"],
        "TeamName": ["Red Bull Racing", "McLaren", "Mercedes"],
        "GridPosition": [1.0, 3.0, 2.0],
        "Laps": [56.0, 56.0, 56.0],
        "Points": [25.0, 18.0, 15.0],
        "Status": ["Finished", "Finished", "Finished"],
        "Time": [
            pd.to_timedelta("5400s"),
            pd.to_timedelta("5405.5s"),
            pd.to_timedelta("5412.3s")
        ]
    })

@pytest.fixture
def mock_qualifying_results():
    """Return a mock pandas DataFrame mimicking Qualifying results."""
    return pd.DataFrame({
        "Position": [1.0, 2.0, 3.0],
        "FullName": ["Lando Norris", "Max Verstappen", "Lewis Hamilton"],
        "TeamName": ["McLaren", "Red Bull Racing", "Mercedes"],
        "GridPosition": [0.0, 0.0, 0.0],
        "Laps": [15.0, 14.0, 16.0],
        "Points": [0.0, 0.0, 0.0],
        "Q1": [
            pd.to_timedelta("89.5s"),
            pd.to_timedelta("89.7s"),
            pd.to_timedelta("90.1s")
        ],
        "Q2": [
            pd.to_timedelta("88.8s"),
            pd.to_timedelta("88.9s"),
            pd.to_timedelta("89.3s")
        ],
        "Q3": [
            pd.to_timedelta("88.1s"),
            pd.to_timedelta("88.3s"),
            pd.to_timedelta("88.6s")
        ]
    })

@pytest.fixture
def mock_practice_results():
    """Return a mock pandas DataFrame mimicking Practice results (where Position is NaN)."""
    return pd.DataFrame({
        "Position": [np.nan, np.nan, np.nan],
        "FullName": ["Lando Norris", "Max Verstappen", "Lewis Hamilton"],
        "TeamName": ["McLaren", "Red Bull Racing", "Mercedes"],
        "GridPosition": [0.0, 0.0, 0.0],
        "Laps": [25.0, 24.0, 22.0],
        "Points": [0.0, 0.0, 0.0]
    })

@pytest.fixture
def mock_laps_data():
    """Return a mock laps DataFrame with mixed lap profiles (standard, in-lap, out-lap, outlier)."""
    return pd.DataFrame({
        "Driver": ["4", "4", "4", "4", "4", "4", "44", "44"],
        "LapNumber": [1, 2, 3, 4, 5, 6, 1, 2],
        "LapTime": [
            pd.to_timedelta("95s"),    # Outlier (very slow)
            pd.to_timedelta("81.2s"),  # Standard flyer
            pd.to_timedelta("81.0s"),  # Standard flyer
            pd.to_timedelta("81.5s"),  # Standard flyer
            pd.to_timedelta("83.0s"),  # Standard flyer
            pd.to_timedelta("120s"),   # Pit-in lap
            pd.to_timedelta("81.8s"),  # Driver 44 flyer
            pd.to_timedelta("81.6s")   # Driver 44 flyer
        ],
        "PitOutTime": [
            pd.to_timedelta("0s"),     # Out-lap
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT
        ],
        "PitInTime": [
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.NaT,
            pd.to_timedelta("115s"),   # In-lap
            pd.NaT,
            pd.NaT
        ],
        "Compound": ["SOFT", "SOFT", "SOFT", "SOFT", "SOFT", "SOFT", "MEDIUM", "MEDIUM"],
        "TyreLife": [1, 2, 3, 4, 5, 6, 1, 2]
    })
