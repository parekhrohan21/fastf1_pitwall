import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.data.loader import _build_teammate_battle_data
from src.charts.plotly import build_teammate_matrix_fig


class MockSession:
    """Mock FastF1 session object with results DataFrame."""
    def __init__(self, results_df: pd.DataFrame):
        self.results = results_df


@pytest.fixture
def sample_teammate_laps_and_results():
    """Build mock laps and results for two teams: McLaren (NOR, PIA) and Red Bull (VER, PER)."""
    results_df = pd.DataFrame({
        "DriverNumber": ["4", "81", "1", "11"],
        "Abbreviation": ["NOR", "PIA", "VER", "PER"],
        "FullName": ["Lando Norris", "Oscar Piastri", "Max Verstappen", "Sergio Perez"],
        "TeamName": ["McLaren", "McLaren", "Red Bull Racing", "Red Bull Racing"],
        "Position": [1.0, 2.0, 3.0, 6.0],
        "GridPosition": [1.0, 2.0, 3.0, 5.0],
        "Q1": [pd.to_timedelta("89.0s"), pd.to_timedelta("89.2s"), pd.to_timedelta("89.1s"), pd.to_timedelta("89.5s")],
        "Q2": [pd.to_timedelta("88.4s"), pd.to_timedelta("88.5s"), pd.to_timedelta("88.3s"), pd.to_timedelta("88.8s")],
        "Q3": [pd.to_timedelta("87.8s"), pd.to_timedelta("87.95s"), pd.to_timedelta("88.0s"), pd.to_timedelta("88.45s")],
    })

    laps_records = []
    # McLaren: NOR (best 87.8s, S1: 28.1s, S2: 29.3s, S3: 30.4s)
    #          PIA (best 87.95s, S1: 28.2s, S2: 29.25s, S3: 30.5s)
    # Red Bull: VER (best 88.0s, S1: 28.0s, S2: 29.5s, S3: 30.5s)
    #           PER (best 88.45s, S1: 28.3s, S2: 29.6s, S3: 30.55s)

    # 5 race laps per driver
    drivers_data = [
        ("NOR", "McLaren", [88.5, 88.6, 88.4, 88.7, 88.5], 28.1, 29.3, 30.4),
        ("PIA", "McLaren", [88.7, 88.8, 88.6, 88.9, 88.7], 28.2, 29.25, 30.5),
        ("VER", "Red Bull Racing", [88.6, 88.5, 88.7, 88.6, 88.5], 28.0, 29.5, 30.5),
        ("PER", "Red Bull Racing", [89.2, 89.1, 89.3, 89.4, 89.2], 28.3, 29.6, 30.55),
    ]

    for drv, team, lap_times, s1, s2, s3 in drivers_data:
        for idx, lt in enumerate(lap_times, start=1):
            laps_records.append({
                "Driver": drv,
                "Team": team,
                "LapNumber": idx,
                "LapTime": pd.to_timedelta(f"{lt}s"),
                "Sector1Time": pd.to_timedelta(f"{s1 + (idx * 0.05)}s"),
                "Sector2Time": pd.to_timedelta(f"{s2 + (idx * 0.05)}s"),
                "Sector3Time": pd.to_timedelta(f"{s3 + (idx * 0.05)}s"),
                "PitInTime": pd.NaT,
                "PitOutTime": pd.NaT,
                "TrackStatus": "1",
                "IsAccurate": True,
            })

    laps_df = pd.DataFrame(laps_records)
    session_obj = MockSession(results_df)

    return laps_df, session_obj


def test_build_teammate_battle_data_qualifying(sample_teammate_laps_and_results):
    """Verify teammate pairing, qualifying gap in seconds and percentage, and ranking."""
    laps_df, session_obj = sample_teammate_laps_and_results
    data = _build_teammate_battle_data("2024_Test_Q", laps_df, _session_obj=session_obj)

    assert data is not None
    assert data["has_data"] is True
    assert len(data["pairs"]) == 2

    # Check McLaren pair
    mclaren = next(p for p in data["pairs"] if p["team"] == "McLaren")
    assert mclaren["faster_driver"] == "NOR"
    assert mclaren["trailing_driver"] == "PIA"
    # Q3 delta: 87.95 - 87.80 = 0.15s
    assert pytest.approx(mclaren["qual_delta_s"], 0.001) == 0.150
    assert mclaren["qual_delta_pct"] > 0
    assert mclaren["driver1"]["pos"] == 1
    assert mclaren["driver2"]["pos"] == 2

    # Check Red Bull pair
    rb = next(p for p in data["pairs"] if p["team"] == "Red Bull Racing")
    assert rb["faster_driver"] == "VER"
    assert rb["trailing_driver"] == "PER"
    # Q3 delta: 88.45 - 88.00 = 0.45s
    assert pytest.approx(rb["qual_delta_s"], 0.001) == 0.450


def test_build_teammate_battle_data_race(sample_teammate_laps_and_results):
    """Verify median clean-air race pace calculation and race gap deltas."""
    laps_df, session_obj = sample_teammate_laps_and_results
    data = _build_teammate_battle_data("2024_Test_R", laps_df, _session_obj=session_obj)

    assert data["has_data"] is True
    mclaren = next(p for p in data["pairs"] if p["team"] == "McLaren")
    assert mclaren["has_race_data"] is True
    # NOR race pace median: 88.5s, PIA race pace median: 88.7s -> delta 0.20s
    assert pytest.approx(mclaren["race_pace_delta_s"], 0.01) == 0.20
    assert mclaren["pos_delta"] == 1  # P2 - P1 = 1


def test_sector_dominance_resolution(sample_teammate_laps_and_results):
    """Verify sector breakdown advantages for S1, S2, and S3."""
    laps_df, session_obj = sample_teammate_laps_and_results
    data = _build_teammate_battle_data("2024_Test_Q", laps_df, _session_obj=session_obj)

    mclaren = next(p for p in data["pairs"] if p["team"] == "McLaren")
    # NOR had better S1 (28.15 vs 28.25) and S3 (30.45 vs 30.55), PIA had better S2 (29.30 vs 29.35)
    assert mclaren["s1_advantage"] == "NOR"
    assert mclaren["s2_advantage"] == "PIA"
    assert mclaren["s3_advantage"] == "NOR"
    assert mclaren["d1_sector_wins"] == 2
    assert mclaren["d2_sector_wins"] == 1
    assert "NOR (2–1)" in mclaren["sector_dominance"]


def test_summary_kpis(sample_teammate_laps_and_results):
    """Verify summary metrics: closest battle, largest delta, and grid median."""
    laps_df, session_obj = sample_teammate_laps_and_results
    data = _build_teammate_battle_data("2024_Test_Q", laps_df, _session_obj=session_obj)
    summary = data["summary"]

    assert summary["closest_battle"]["team"] == "McLaren"  # 0.15s
    assert summary["largest_delta"]["team"] == "Red Bull Racing"  # 0.45s
    # Median of [0.15, 0.45] is 0.30
    assert pytest.approx(summary["median_delta_s"], 0.01) == 0.30
    assert summary["total_teams"] == 2


def test_single_driver_team_and_odd_pairings():
    """Verify graceful handling when a team has only 1 driver or 3 drivers."""
    results_df = pd.DataFrame({
        "DriverNumber": ["4", "81", "20", "27", "77"],
        "Abbreviation": ["NOR", "PIA", "MAG", "HUL", "BOT"],
        "TeamName": ["McLaren", "McLaren", "Haas", "Haas", "Sauber"],  # Sauber has only 1 driver (BOT)
        "Position": [1.0, 2.0, 11.0, 12.0, 15.0],
    })

    laps_df = pd.DataFrame({
        "Driver": ["NOR", "PIA", "MAG", "HUL", "BOT"],
        "Team": ["McLaren", "McLaren", "Haas", "Haas", "Sauber"],
        "LapNumber": [1, 1, 1, 1, 1],
        "LapTime": [pd.to_timedelta("80s"), pd.to_timedelta("80.2s"), pd.to_timedelta("81s"), pd.to_timedelta("81.3s"), pd.to_timedelta("82s")],
        "Sector1Time": [pd.to_timedelta("25s")] * 5,
        "Sector2Time": [pd.to_timedelta("25s")] * 5,
        "Sector3Time": [pd.to_timedelta("30s")] * 5,
    })

    data = _build_teammate_battle_data("2024_Sauber_Single", laps_df, _session_obj=MockSession(results_df))
    assert data["has_data"] is True
    # Only McLaren and Haas have 2 drivers
    teams = [p["team"] for p in data["pairs"]]
    assert "McLaren" in teams
    assert "Haas" in teams
    assert "Sauber" not in teams


def test_edge_cases_and_graceful_failures():
    """Verify empty laps and missing data return safe fallbacks."""
    assert _build_teammate_battle_data("2024_Empty", pd.DataFrame())["has_data"] is False
    assert _build_teammate_battle_data("2024_None", None)["has_data"] is False


def test_build_teammate_matrix_fig(sample_teammate_laps_and_results):
    """Verify build_teammate_matrix_fig renders a valid Plotly Figure for Qualifying and Race Pace."""
    laps_df, session_obj = sample_teammate_laps_and_results
    data = _build_teammate_battle_data("2024_Test_Q", laps_df, _session_obj=session_obj)

    fig_qual = build_teammate_matrix_fig(data, mode="Qualifying")
    assert isinstance(fig_qual, go.Figure)
    assert len(fig_qual.data) == 1
    assert fig_qual.data[0].orientation == "h"
    assert len(fig_qual.data[0].x) == 2

    fig_race = build_teammate_matrix_fig(data, mode="Race Pace")
    assert isinstance(fig_race, go.Figure)
    assert len(fig_race.data) == 1
    assert fig_race.data[0].orientation == "h"


def test_build_teammate_matrix_fig_fallback():
    """Verify build_teammate_matrix_fig returns None on empty or invalid data."""
    assert build_teammate_matrix_fig({}) is None
    assert build_teammate_matrix_fig({"has_data": False}) is None
