import numpy as np
import pandas as pd
import pytest

from src.data.loader import _build_track_evolution_data, _robust_linear_fit
from src.charts.plotly import build_track_evolution_fig


def _make_session_laps(
    n_drivers: int = 4,
    n_laps: int = 8,
    base: float = 90.0,
    ramp_s_per_min: float = -0.02,
    lap_gap_min: float = 2.0,
):
    """Synthesise a multi-car qualifying-style session with a known evolution ramp."""
    rows = []
    drivers = ["NOR", "VER", "HAM", "LEC", "PIA", "RUS"][:n_drivers]
    for d_i, drv in enumerate(drivers):
        for lap in range(1, n_laps + 1):
            minutes = lap * lap_gap_min + d_i * 0.2
            lap_time = base + d_i * 0.15 + ramp_s_per_min * minutes
            rows.append({
                "Driver": drv,
                "LapNumber": lap,
                "LapTime": pd.Timedelta(seconds=lap_time),
                "Time": pd.Timedelta(minutes=minutes),
                "IsAccurate": True,
                "TrackStatus": "1",
                "PitInTime": pd.NaT,
                "PitOutTime": pd.NaT,
                "Compound": "SOFT",
            })
    return pd.DataFrame(rows)


class _MockSession:
    def __init__(self, weather_data):
        self.weather_data = weather_data


def test_robust_linear_fit_recovers_slope_despite_outliers():
    x = np.arange(0.0, 30.0, 1.0)
    y = 90.0 - 0.02 * x
    # Inject traffic laps far above the trend line
    y[5] += 8.0
    y[17] += 12.0

    slope, intercept, mask = _robust_linear_fit(x, y)

    assert slope == pytest.approx(-0.02, abs=2e-3)
    assert mask[5] == False
    assert mask[17] == False
    assert mask.sum() >= len(x) - 4


def test_build_track_evolution_data_basic_ramp():
    laps_df = _make_session_laps()

    res = _build_track_evolution_data("2024_Test_Q", laps_df)
    assert res is not None
    assert {"laps", "trend", "stats"}.issubset(res.keys())

    stats = res["stats"]
    # -0.02 s/min == -20 ms/min
    assert stats["ramp_rate_ms_per_min"] == pytest.approx(-20.0, abs=1.5)
    assert stats["total_grip_gain_s"] < 0
    assert stats["driver_count"] == 4
    assert stats["condition"] == "Gripping Up"
    assert stats["r_squared"] is not None



def test_build_track_evolution_data_removes_qualifying_knockout_bias():
    """Slow cars eliminated early must not make the late-session field look faster."""
    rows = []
    # 12 drivers 0.1s apart; the slowest 4 stop after Q1 (~18 min), the next 4 after Q2 (~36 min)
    for d_i in range(12):
        last_min = 18.0 if d_i >= 8 else (36.0 if d_i >= 4 else 54.0)
        minutes = 3.0 + d_i * 0.1
        lap = 1
        while minutes <= last_min:
            rows.append({
                "Driver": f"D{d_i:02d}",
                "LapNumber": lap,
                "LapTime": pd.Timedelta(seconds=90.0 + d_i * 0.1 - 0.01 * minutes),
                "Time": pd.Timedelta(minutes=minutes),
                "IsAccurate": True,
                "TrackStatus": "1",
                "PitInTime": pd.NaT,
                "PitOutTime": pd.NaT,
            })
            minutes += 5.0
            lap += 1

    res = _build_track_evolution_data("2024_Knockout_Q", pd.DataFrame(rows))
    assert res is not None
    # True track ramp is -10 ms/min; a pooled field fit reads roughly double
    assert res["stats"]["ramp_rate_ms_per_min"] == pytest.approx(-10.0, abs=1.0)
    assert "PaceAdjusted_s" in res["laps"].columns

def test_build_track_evolution_data_classifies_rapid_and_degrading():
    rapid = _build_track_evolution_data("2024_Rapid_Q", _make_session_laps(ramp_s_per_min=-0.06))
    assert rapid["stats"]["condition"] == "Rapidly Rubbering In"

    degrading = _build_track_evolution_data("2024_Degrade_Q", _make_session_laps(ramp_s_per_min=0.02))
    assert degrading["stats"]["condition"] == "Track Degrading"
    assert degrading["stats"]["total_grip_gain_s"] > 0

    stable = _build_track_evolution_data("2024_Stable_Q", _make_session_laps(ramp_s_per_min=0.0))
    assert stable["stats"]["condition"] == "Stable Track"


def test_build_track_evolution_data_filters_non_flyers():
    laps_df = _make_session_laps()
    # An in-lap, a yellow-flag lap and a slow cool-down lap must all be excluded
    extra = pd.DataFrame([
        {"Driver": "NOR", "LapNumber": 99, "LapTime": pd.Timedelta(seconds=91.0),
         "Time": pd.Timedelta(minutes=10.0), "IsAccurate": True, "TrackStatus": "1",
         "PitInTime": pd.Timedelta(seconds=5), "PitOutTime": pd.NaT, "Compound": "SOFT"},
        {"Driver": "VER", "LapNumber": 98, "LapTime": pd.Timedelta(seconds=91.0),
         "Time": pd.Timedelta(minutes=11.0), "IsAccurate": True, "TrackStatus": "2",
         "PitInTime": pd.NaT, "PitOutTime": pd.NaT, "Compound": "SOFT"},
        {"Driver": "HAM", "LapNumber": 97, "LapTime": pd.Timedelta(seconds=140.0),
         "Time": pd.Timedelta(minutes=12.0), "IsAccurate": True, "TrackStatus": "1",
         "PitInTime": pd.NaT, "PitOutTime": pd.NaT, "Compound": "SOFT"},
    ])
    combined = pd.concat([laps_df, extra], ignore_index=True)

    res = _build_track_evolution_data("2024_Filter_Q", combined)
    assert res is not None
    kept = res["laps"]
    assert 99 not in kept["LapNumber"].values   # in-lap dropped
    assert 98 not in kept["LapNumber"].values   # yellow flag dropped
    assert 97 not in kept["LapNumber"].values   # outside 107% dropped
    assert res["stats"]["flyer_lap_count"] == len(laps_df)


def test_build_track_evolution_data_insufficient_and_empty_input():
    assert _build_track_evolution_data("2024_Null_Q", None) is None
    assert _build_track_evolution_data("2024_Empty_Q", pd.DataFrame()) is None
    # Only 4 flyer laps — below the 10-lap minimum
    assert _build_track_evolution_data("2024_Few_Q", _make_session_laps(n_drivers=1, n_laps=4)) is None
    # Missing the Time column entirely
    no_time = _make_session_laps().drop(columns=["Time"])
    assert _build_track_evolution_data("2024_NoTime_Q", no_time) is None


def test_build_track_evolution_data_merges_track_temperature():
    laps_df = _make_session_laps()
    weather = pd.DataFrame({
        "Time": [pd.Timedelta(minutes=m) for m in range(0, 20, 2)],
        "TrackTemp": [40.0 - 0.5 * i for i in range(10)],
    })

    res = _build_track_evolution_data("2024_Weather_Q", laps_df, _MockSession(weather))
    assert res["temp_profile"] is not None
    assert res["stats"]["track_temp_start"] == 40.0
    assert res["stats"]["track_temp_end"] == 35.5


def test_build_track_evolution_data_survives_broken_weather_object():
    class _Broken:
        @property
        def weather_data(self):
            raise RuntimeError("weather unavailable")

    res = _build_track_evolution_data("2024_BrokenWx_Q", _make_session_laps(), _Broken())
    assert res is not None
    assert res["temp_profile"] is None
    assert res["stats"]["track_temp_start"] is None


def test_build_track_evolution_fig_renders():
    laps_df = _make_session_laps()
    weather = pd.DataFrame({
        "Time": [pd.Timedelta(minutes=m) for m in range(0, 20, 2)],
        "TrackTemp": [40.0 - 0.5 * i for i in range(10)],
    })
    res = _build_track_evolution_data("2024_Fig_Q", laps_df, _MockSession(weather))

    fig = build_track_evolution_fig(
        res,
        driver_colors={"NOR": "#FF8000"},
        driver_labels={"NOR": "NOR · Norris"},
    )
    assert fig is not None

    trace_names = [t.name for t in fig.data]
    assert "Track Temp (°C)" in trace_names
    assert "Field Flyers" in trace_names
    assert "NOR · Norris Flyers" in trace_names
    assert any(n.startswith("Track Evolution") for n in trace_names)


def test_build_track_evolution_fig_handles_missing_data():
    assert build_track_evolution_fig(None) is None
    assert build_track_evolution_fig({}) is None
    assert build_track_evolution_fig({"laps": pd.DataFrame()}) is None
