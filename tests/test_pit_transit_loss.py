import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.data.loader import _build_pit_transit_data
from src.charts.plotly import build_pit_loss_fig


class MockSession:
    """Mock FastF1 session object with results and laps DataFrame."""
    def __init__(self, results_df: pd.DataFrame | None = None, laps_df: pd.DataFrame | None = None):
        self.results = results_df
        self.laps = laps_df


@pytest.fixture
def sample_pit_laps():
    """
    Build realistic mock laps for two drivers:
    - VER (Red Bull): Baseline pace ~80.0s (S1: 25.0s, S2: 28.0s, S3: 27.0s)
      Lap 1-3: Flyer laps (~80.0s)
      Lap 4: In-lap (LapTime: 84.0s, PitInTime: 12:00:82.0) -> push delta +4.0s
      Lap 5: Out-lap (LapTime: 106.0s, PitOutTime: 12:01:03.0, S1: 32.0s, S2: 30.0s, S3: 28.0s)
             -> Pit lane transit = 103.0 - 82.0 = 21.0s
             -> Out-lap delta = 106.0 - 80.0 = +26.0s
             -> Sector warm-up: S1 delta = +7.0s, S2 delta = +2.0s, S3 delta = +1.0s
             -> Net pit loss = (84.0 + 106.0) - (2 * 80.0) = 30.0s
      Lap 6-8: Flyer laps (~80.0s)

    - NOR (McLaren): Baseline pace ~81.0s (S1: 25.5s, S2: 28.2s, S3: 27.3s)
      Lap 1-4: Flyer laps (~81.0s)
      Lap 5: In-lap (LapTime: 84.5s, PitInTime: 12:02:00.0) -> push delta +3.5s
      Lap 6: Out-lap (LapTime: 106.5s, PitOutTime: 12:02:22.0, S1: 32.5s, S2: 30.0s, S3: 28.0s)
             -> Pit lane transit = 22.0 - 0.0 = 22.0s
             -> Out-lap delta = 106.5 - 81.0 = +25.5s
             -> Net pit loss = (84.5 + 106.5) - (2 * 81.0) = 29.0s
    """
    records = []

    # VER (Laps 1-8)
    for lap in range(1, 9):
        if lap < 4:
            records.append({
                "Driver": "VER", "Team": "Red Bull Racing", "LapNumber": lap,
                "LapTime": pd.to_timedelta("80.0s"),
                "Sector1Time": pd.to_timedelta("25.0s"),
                "Sector2Time": pd.to_timedelta("28.0s"),
                "Sector3Time": pd.to_timedelta("27.0s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                "Compound": "MEDIUM", "TrackStatus": "1", "IsAccurate": True
            })
        elif lap == 4:  # In-lap
            records.append({
                "Driver": "VER", "Team": "Red Bull Racing", "LapNumber": 4,
                "LapTime": pd.to_timedelta("84.0s"),
                "Sector1Time": pd.to_timedelta("25.0s"),
                "Sector2Time": pd.to_timedelta("28.0s"),
                "Sector3Time": pd.to_timedelta("31.0s"),
                "PitInTime": pd.to_timedelta("300.0s"),
                "PitOutTime": pd.NaT,
                "Compound": "MEDIUM", "TrackStatus": "1", "IsAccurate": False
            })
        elif lap == 5:  # Out-lap
            records.append({
                "Driver": "VER", "Team": "Red Bull Racing", "LapNumber": 5,
                "LapTime": pd.to_timedelta("106.0s"),
                "Sector1Time": pd.to_timedelta("32.0s"),
                "Sector2Time": pd.to_timedelta("30.0s"),
                "Sector3Time": pd.to_timedelta("28.0s"),
                "PitInTime": pd.NaT,
                "PitOutTime": pd.to_timedelta("321.0s"),  # 321 - 300 = 21s transit
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": False
            })
        else:  # Flyer laps on Hard
            records.append({
                "Driver": "VER", "Team": "Red Bull Racing", "LapNumber": lap,
                "LapTime": pd.to_timedelta("80.0s"),
                "Sector1Time": pd.to_timedelta("25.0s"),
                "Sector2Time": pd.to_timedelta("28.0s"),
                "Sector3Time": pd.to_timedelta("27.0s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": True
            })

    # NOR (Laps 1-8)
    for lap in range(1, 9):
        if lap < 5:
            records.append({
                "Driver": "NOR", "Team": "McLaren", "LapNumber": lap,
                "LapTime": pd.to_timedelta("81.0s"),
                "Sector1Time": pd.to_timedelta("25.5s"),
                "Sector2Time": pd.to_timedelta("28.2s"),
                "Sector3Time": pd.to_timedelta("27.3s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                "Compound": "MEDIUM", "TrackStatus": "1", "IsAccurate": True
            })
        elif lap == 5:  # In-lap
            records.append({
                "Driver": "NOR", "Team": "McLaren", "LapNumber": 5,
                "LapTime": pd.to_timedelta("84.5s"),
                "Sector1Time": pd.to_timedelta("25.5s"),
                "Sector2Time": pd.to_timedelta("28.2s"),
                "Sector3Time": pd.to_timedelta("30.8s"),
                "PitInTime": pd.to_timedelta("400.0s"),
                "PitOutTime": pd.NaT,
                "Compound": "MEDIUM", "TrackStatus": "1", "IsAccurate": False
            })
        elif lap == 6:  # Out-lap
            records.append({
                "Driver": "NOR", "Team": "McLaren", "LapNumber": 6,
                "LapTime": pd.to_timedelta("106.5s"),
                "Sector1Time": pd.to_timedelta("32.5s"),
                "Sector2Time": pd.to_timedelta("30.0s"),
                "Sector3Time": pd.to_timedelta("28.0s"),
                "PitInTime": pd.NaT,
                "PitOutTime": pd.to_timedelta("422.0s"),  # 422 - 400 = 22s transit
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": False
            })
        else:
            records.append({
                "Driver": "NOR", "Team": "McLaren", "LapNumber": lap,
                "LapTime": pd.to_timedelta("81.0s"),
                "Sector1Time": pd.to_timedelta("25.5s"),
                "Sector2Time": pd.to_timedelta("28.2s"),
                "Sector3Time": pd.to_timedelta("27.3s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": True
            })

    return pd.DataFrame(records)


def test_pit_transit_data_extraction(sample_pit_laps):
    """Test calculation of pit lane transit duration from PitOutTime and PitInTime."""
    data = _build_pit_transit_data("mock_sess_2026_r1", sample_pit_laps)
    assert data["has_data"] is True
    assert len(data["all_stops"]) == 2

    # Find VER stop
    ver_stop = next(s for s in data["all_stops"] if s["driver"] == "VER")
    assert ver_stop["in_lap"] == 4
    assert ver_stop["out_lap"] == 5
    assert pytest.approx(ver_stop["pit_lane_time_s"], 0.1) == 21.0
    assert ver_stop["old_compound"] == "MEDIUM"
    assert ver_stop["new_compound"] == "HARD"


def test_in_lap_and_out_lap_deltas(sample_pit_laps):
    """Test calculation of in-lap push delta, out-lap warm-up delta, and net total pit loss."""
    data = _build_pit_transit_data("mock_sess_2026_r1", sample_pit_laps)
    ver_stop = next(s for s in data["all_stops"] if s["driver"] == "VER")

    # VER: in-lap = 84.0s, baseline = 80.0s -> delta = +4.0s
    assert pytest.approx(ver_stop["in_lap_delta_s"], 0.1) == 4.0
    # out-lap = 106.0s, baseline = 80.0s -> delta = +26.0s
    assert pytest.approx(ver_stop["out_lap_delta_s"], 0.1) == 26.0
    # Net pit loss = (84.0 + 106.0) - (2 * 80.0) = 30.0s
    assert pytest.approx(ver_stop["net_pit_loss_s"], 0.1) == 30.0

    nor_stop = next(s for s in data["all_stops"] if s["driver"] == "NOR")
    # NOR: in-lap = 84.5s, baseline = 81.0s -> delta = +3.5s
    assert pytest.approx(nor_stop["in_lap_delta_s"], 0.1) == 3.5
    # out-lap = 106.5s, baseline = 81.0s -> delta = +25.5s
    assert pytest.approx(nor_stop["out_lap_delta_s"], 0.1) == 25.5
    # Net pit loss = (84.5 + 106.5) - (2 * 81.0) = 29.0s
    assert pytest.approx(nor_stop["net_pit_loss_s"], 0.1) == 29.0


def test_sector_warmup_breakdown(sample_pit_laps):
    """Test sector-by-sector cold tyre warm-up deltas on the out-lap."""
    data = _build_pit_transit_data("mock_sess_2026_r1", sample_pit_laps)
    ver_stop = next(s for s in data["all_stops"] if s["driver"] == "VER")

    # VER out-lap: S1: 32.0s (base: 25.0s -> +7.0s)
    #              S2: 30.0s (base: 28.0s -> +2.0s)
    #              S3: 28.0s (base: 27.0s -> +1.0s)
    assert pytest.approx(ver_stop["out_lap_s1_delta_s"], 0.1) == 7.0
    assert pytest.approx(ver_stop["out_lap_s2_delta_s"], 0.1) == 2.0
    assert pytest.approx(ver_stop["out_lap_s3_delta_s"], 0.1) == 1.0


def test_summary_kpis(sample_pit_laps):
    """Test fastest pit lane, best in-lap push, best out-lap, and grid medians."""
    data = _build_pit_transit_data("mock_sess_2026_r1", sample_pit_laps)
    summary = data["summary"]

    # Fastest pit lane transit is VER (21.0s vs NOR 22.0s)
    assert summary["fastest_pit_lane"]["driver"] == "VER"
    assert pytest.approx(summary["fastest_pit_lane"]["time_s"], 0.1) == 21.0

    # Best in-lap push delta is NOR (+3.5s vs VER +4.0s)
    assert summary["best_in_lap"]["driver"] == "NOR"
    assert pytest.approx(summary["best_in_lap"]["delta_s"], 0.1) == 3.5

    # Best out-lap warm-up delta is NOR (+25.5s vs VER +26.0s)
    assert summary["best_out_lap"]["driver"] == "NOR"
    assert pytest.approx(summary["best_out_lap"]["delta_s"], 0.1) == 25.5

    # Lowest net pit loss is NOR (29.0s vs VER 30.0s)
    assert summary["lowest_net_pit_loss"]["driver"] == "NOR"
    assert pytest.approx(summary["lowest_net_pit_loss"]["loss_s"], 0.1) == 29.0

    # Grid medians
    assert pytest.approx(summary["grid_median_pit_loss"], 0.1) == 29.5
    assert pytest.approx(summary["grid_median_pit_lane"], 0.1) == 21.5


def test_multi_stop_handling():
    """Test drivers with multiple pit stops during a session."""
    records = []
    # 3 flyer laps, stop 1 on L4 (in) / L5 (out), 3 flyer laps, stop 2 on L9 (in) / L10 (out)
    for lap in range(1, 13):
        if lap == 4:
            records.append({
                "Driver": "HAM", "Team": "Mercedes", "LapNumber": 4,
                "LapTime": pd.to_timedelta("85.0s"), "Sector1Time": pd.to_timedelta("26.0s"),
                "Sector2Time": pd.to_timedelta("28.0s"), "Sector3Time": pd.to_timedelta("31.0s"),
                "PitInTime": pd.to_timedelta("300.0s"), "PitOutTime": pd.NaT,
                "Compound": "MEDIUM", "TrackStatus": "1", "IsAccurate": False
            })
        elif lap == 5:
            records.append({
                "Driver": "HAM", "Team": "Mercedes", "LapNumber": 5,
                "LapTime": pd.to_timedelta("105.0s"), "Sector1Time": pd.to_timedelta("32.0s"),
                "Sector2Time": pd.to_timedelta("30.0s"), "Sector3Time": pd.to_timedelta("28.0s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.to_timedelta("320.5s"),  # transit 20.5s
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": False
            })
        elif lap == 9:
            records.append({
                "Driver": "HAM", "Team": "Mercedes", "LapNumber": 9,
                "LapTime": pd.to_timedelta("84.8s"), "Sector1Time": pd.to_timedelta("26.0s"),
                "Sector2Time": pd.to_timedelta("28.0s"), "Sector3Time": pd.to_timedelta("30.8s"),
                "PitInTime": pd.to_timedelta("600.0s"), "PitOutTime": pd.NaT,
                "Compound": "HARD", "TrackStatus": "1", "IsAccurate": False
            })
        elif lap == 10:
            records.append({
                "Driver": "HAM", "Team": "Mercedes", "LapNumber": 10,
                "LapTime": pd.to_timedelta("104.5s"), "Sector1Time": pd.to_timedelta("31.5s"),
                "Sector2Time": pd.to_timedelta("29.5s"), "Sector3Time": pd.to_timedelta("28.0s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.to_timedelta("621.0s"),  # transit 21.0s
                "Compound": "SOFT", "TrackStatus": "1", "IsAccurate": False
            })
        else:
            records.append({
                "Driver": "HAM", "Team": "Mercedes", "LapNumber": lap,
                "LapTime": pd.to_timedelta("81.0s"), "Sector1Time": pd.to_timedelta("25.5s"),
                "Sector2Time": pd.to_timedelta("28.0s"), "Sector3Time": pd.to_timedelta("27.5s"),
                "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                "Compound": "MEDIUM" if lap < 5 else ("HARD" if lap < 10 else "SOFT"),
                "TrackStatus": "1", "IsAccurate": True
            })

    laps_df = pd.DataFrame(records)
    data = _build_pit_transit_data("mock_sess_ham_multistop", laps_df)
    assert data["has_data"] is True
    assert len(data["all_stops"]) == 2

    stops = data["driver_stops"]["HAM"]
    assert len(stops) == 2
    assert stops[0]["stop_num"] == 1
    assert stops[0]["in_lap"] == 4
    assert stops[0]["old_compound"] == "MEDIUM"
    assert stops[0]["new_compound"] == "HARD"
    assert pytest.approx(stops[0]["pit_lane_time_s"], 0.1) == 20.5

    assert stops[1]["stop_num"] == 2
    assert stops[1]["in_lap"] == 9
    assert stops[1]["old_compound"] == "HARD"
    assert stops[1]["new_compound"] == "SOFT"
    assert pytest.approx(stops[1]["pit_lane_time_s"], 0.1) == 21.0


def test_missing_data_and_edge_cases():
    """Test resilience when provided with empty DataFrame, missing columns, or no pit stops."""
    # Empty DataFrame
    res = _build_pit_transit_data("empty_sess", pd.DataFrame())
    assert res["has_data"] is False
    assert len(res["all_stops"]) == 0

    # DataFrame with no pit stops
    no_pits_df = pd.DataFrame({
        "Driver": ["VER", "VER"],
        "LapNumber": [1, 2],
        "LapTime": [pd.to_timedelta("80s"), pd.to_timedelta("80.5s")],
        "PitInTime": [pd.NaT, pd.NaT],
        "PitOutTime": [pd.NaT, pd.NaT],
        "TrackStatus": ["1", "1"],
        "IsAccurate": [True, True]
    })
    res2 = _build_pit_transit_data("no_pits_sess", no_pits_df)
    assert res2["has_data"] is False
    assert len(res2["all_stops"]) == 0


def test_build_pit_loss_fig(sample_pit_laps):
    """Test Plotly stacked horizontal bar figure construction in both compare and grid modes."""
    data = _build_pit_transit_data("mock_sess_2026_fig", sample_pit_laps)
    assert data["has_data"] is True

    # 1. Compare Mode
    fig_comp = build_pit_loss_fig(data, driver1="VER", driver2="NOR", compare=True)
    assert isinstance(fig_comp, go.Figure)
    assert len(fig_comp.data) == 3
    trace_names = [t.name for t in fig_comp.data]
    assert "In-Lap Push Delta" in trace_names
    assert "Pit Lane Transit" in trace_names
    assert "Out-Lap Warm-up Delta" in trace_names

    # 2. Full Grid Overview Mode
    fig_grid = build_pit_loss_fig(data, compare=False)
    assert isinstance(fig_grid, go.Figure)
    assert len(fig_grid.data) == 3
    assert fig_grid.layout.barmode == "stack"


def test_figure_fallback_when_empty():
    """Test build_pit_loss_fig handles None, empty, or missing data gracefully."""
    assert build_pit_loss_fig(None) is None
    assert build_pit_loss_fig({}) is None
    assert build_pit_loss_fig({"has_data": False, "all_stops": []}) is None
