"""Unit tests for Issue #200: Start Line Reaction Time & Launch Telemetry Acceleration Analyzer."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.data.loader import (
    _interp_first_speed_crossing,
    _analyze_driver_launch,
    _build_launch_analysis_data,
)
from src.charts.plotly import build_launch_analysis_fig


def _make_standing_start_tel(
    t_react_s: float = 0.28,
    accel_mps2: float = 10.5,
    pre_rpm: float = 10200.0,
    dip_rpm: float = 4400.0,
    bite_thr: float = 32.0,
    wheelspin_feather: bool = False,
    t1_brake_s: float = 8.4,
    synthetic: bool = False,
) -> pd.DataFrame:
    """Build a realistic 4 Hz Lap 1 telemetry trace starting from rest on the grid."""
    t = np.arange(0.04, 22.0, 0.24)
    spd = np.zeros_like(t)
    rpm = np.full_like(t, pre_rpm)
    thr = np.full_like(t, bite_thr)
    brk = np.zeros(len(t), dtype=bool)
    gear = np.ones(len(t), dtype=int)

    for i, ti in enumerate(t):
        if ti <= t_react_s:
            spd[i] = 0.0
            rpm[i] = pre_rpm
            thr[i] = bite_thr
            brk[i] = True
            gear[i] = 1
        elif ti < t1_brake_s:
            dt = ti - t_react_s
            # Speed rises with slight high-speed aero drag taper
            v_ms = accel_mps2 * dt * (1.0 - 0.018 * dt)
            spd[i] = max(0.0, min(315.0, v_ms * 3.6))
            if dt < 0.85:
                # Clutch engagement RPM dip
                rpm[i] = dip_rpm + (pre_rpm - dip_rpm) * max(0.0, 1.0 - dt / 0.65)
                thr[i] = bite_thr + 12.0 * dt
                gear[i] = 1
            else:
                gear[i] = int(np.clip(1 + int(spd[i] // 42.0), 1, 8))
                rpm[i] = 9200.0 + ((spd[i] % 42.0) / 42.0) * 2600.0
                thr[i] = min(100.0, bite_thr + (dt - 0.5) * 35.0)
        elif ti < t1_brake_s + 3.2:
            # Heavy braking into Turn 1 down to 85 km/h (tests non-monotonic whole-lap speed)
            dt_b = ti - t1_brake_s
            spd[i] = max(85.0, spd[i - 1] - 42.0)
            thr[i] = 0.0
            brk[i] = True
            gear[i] = max(2, gear[i - 1] - 1)
            rpm[i] = 7500.0
        else:
            # Subsequent corner exit acceleration on Lap 1
            spd[i] = min(260.0, spd[i - 1] + 14.0)
            thr[i] = 100.0
            brk[i] = False
            gear[i] = 5
            rpm[i] = 10800.0

    if wheelspin_feather:
        # Inject a 1st/2nd gear RPM flare + throttle feathering hesitation
        for i, ti in enumerate(t):
            if t_react_s + 1.1 <= ti <= t_react_s + 1.6:
                thr[i] = max(20.0, thr[i - 1] - 14.0)
                rpm[i] = 12300.0

    dt_step = np.diff(t, prepend=0.0)
    dist = np.cumsum((spd / 3.6) * dt_step)
    # Zero distance while stationary
    dist[spd <= 0.1] = 0.0

    df = pd.DataFrame({
        "Time": pd.to_timedelta(t, unit="s"),
        "SessionTime": pd.to_timedelta(t + 3600.0, unit="s"),
        "Speed": spd,
        "RPM": rpm,
        "nGear": gear,
        "Throttle": thr,
        "Brake": brk,
        "Distance": dist,
    })
    if synthetic:
        df["Synthetic"] = True
    return df


def test_first_crossing_interpolation_ignores_later_lap_deceleration():
    """0-100 and 0-200 km/h interpolation finds the initial launch pull even when Turn 1 drops back below 100 km/h."""
    tel = _make_standing_start_tel(t_react_s=0.30, accel_mps2=11.0)
    res = _analyze_driver_launch(tel, driver="VER", grid_pos=1, lap1_pos=1, lap1_time_s=96.5)
    assert res is not None
    assert 2.0 <= res["t_0_100_s"] <= 3.5
    assert 4.2 <= res["t_0_200_s"] <= 6.8
    assert res["t_0_200_s"] > res["t_0_100_s"]
    assert 25.0 <= res["d_0_100_m"] <= 65.0
    assert 110.0 <= res["d_0_200_m"] <= 230.0
    assert abs(res["t_100_200_s"] - (res["t_0_200_s"] - res["t_0_100_s"])) < 0.05


def test_faster_starter_has_lower_reaction_and_acceleration_times():
    """A driver reacting earlier with higher launch acceleration beats a slower starter on RT, 0-100, and 0-200."""
    fast_tel = _make_standing_start_tel(t_react_s=0.22, accel_mps2=11.5)
    slow_tel = _make_standing_start_tel(t_react_s=0.52, accel_mps2=9.4)

    fast_res = _analyze_driver_launch(fast_tel, driver="NOR", grid_pos=2, lap1_pos=1)
    slow_res = _analyze_driver_launch(slow_tel, driver="LEC", grid_pos=1, lap1_pos=2)

    assert fast_res is not None and slow_res is not None
    assert fast_res["reaction_time_ms"] < slow_res["reaction_time_ms"]
    assert fast_res["t_0_100_s"] < slow_res["t_0_100_s"]
    assert fast_res["t_0_200_s"] < slow_res["t_0_200_s"]
    assert fast_res["positions_gained"] == 1
    assert slow_res["positions_gained"] == -1


def test_clutch_rpm_drop_and_bite_point_throttle_extraction():
    """Pre-launch RPM, post-engagement RPM dip, and bite-point throttle plateau are accurately recovered."""
    tel = _make_standing_start_tel(pre_rpm=10400.0, dip_rpm=4600.0, bite_thr=36.0)
    res = _analyze_driver_launch(tel, driver="LEC")
    assert res is not None
    assert abs(res["pre_launch_rpm"] - 10400.0) < 50.0
    assert abs(res["clutch_dip_rpm"] - 4600.0) < 400.0
    assert res["rpm_drop"] >= 5000.0
    assert 30.0 <= res["bite_point_throttle_pct"] <= 55.0


def test_wheelspin_and_throttle_feather_reduce_traction_efficiency():
    """A launch with RPM flare and throttle feathering records higher wheelspin index and lower traction efficiency."""
    clean_tel = _make_standing_start_tel(wheelspin_feather=False)
    spin_tel = _make_standing_start_tel(wheelspin_feather=True)

    clean_res = _analyze_driver_launch(clean_tel, driver="VER")
    spin_res = _analyze_driver_launch(spin_tel, driver="PER")

    assert clean_res is not None and spin_res is not None
    assert spin_res["wheelspin_events"] > clean_res["wheelspin_events"]
    assert spin_res["wheelspin_index"] > clean_res["wheelspin_index"]
    assert spin_res["traction_efficiency_pct"] < clean_res["traction_efficiency_pct"]


def test_turn1_braking_point_detected_without_circuit_info():
    """Turn 1 braking distance and peak speed are detected directly from telemetry even when t1_corner_dist_m is None."""
    tel = _make_standing_start_tel(t_react_s=0.28, accel_mps2=10.8, t1_brake_s=8.2)
    res = _analyze_driver_launch(tel, driver="HAM", t1_corner_dist_m=None)
    assert res is not None
    assert 7.0 <= res["t1_brake_time_s"] <= 9.0
    assert res["t1_brake_dist_m"] > 200.0
    assert res["t1_peak_speed_kmh"] > 220.0


def test_synthetic_or_rolling_start_traces_are_rejected():
    """Synthetic fallback traces and rolling Safety Car starts (> 25 km/h minimum speed) return None."""
    syn_tel = _make_standing_start_tel(synthetic=True)
    assert _analyze_driver_launch(syn_tel, driver="VER") is None

    rolling_tel = _make_standing_start_tel()
    rolling_tel["Speed"] = rolling_tel["Speed"] + 65.0
    assert _analyze_driver_launch(rolling_tel, driver="VER") is None

    assert _analyze_driver_launch(None, driver="VER") is None
    assert _analyze_driver_launch(pd.DataFrame({"Speed": [0, 10]}), driver="VER") is None


def test_build_launch_analysis_data_and_leaderboard():
    """Full-session builder produces driver profiles, sorted Lap 1 leaderboard, and field summary benchmarks."""
    tel_map = {
        "VER": _make_standing_start_tel(t_react_s=0.28, accel_mps2=10.8),
        "PER": _make_standing_start_tel(t_react_s=0.31, accel_mps2=11.3),
        "LEC": _make_standing_start_tel(t_react_s=0.36, accel_mps2=10.2),
    }

    class _DummyLap:
        def __init__(self, drv):
            self._drv = drv

        def get_car_data(self):
            return self

        def add_distance(self):
            return tel_map[self._drv]

    class _DummyLaps(pd.DataFrame):
        def pick_drivers(self, drv):
            sub = self[self["Driver"] == drv]
            return _DummyDriverLaps(sub, drv)

    class _DummyDriverLaps:
        def __init__(self, df, drv):
            self._df = df
            self._drv = drv

        def __len__(self):
            return len(self._df)

        def __getitem__(self, item):
            return self

        @property
        def iloc(self):
            return [_DummyLap(self._drv)]

    laps_df = pd.DataFrame({
        "Driver": ["VER", "PER", "LEC"],
        "DriverNumber": ["1", "11", "16"],
        "Team": ["Red Bull Racing", "Red Bull Racing", "Ferrari"],
        "LapNumber": [1, 1, 1],
        "Position": [1.0, 2.0, 3.0],
        "GridPosition": [1.0, 4.0, 2.0],
        "LapTime": [pd.Timedelta(seconds=95.2), pd.Timedelta(seconds=96.1), pd.Timedelta(seconds=96.8)],
        "Compound": ["SOFT", "SOFT", "SOFT"],
    })

    class _DummySession:
        laps = _DummyLaps(laps_df)
        results = pd.DataFrame({
            "Abbreviation": ["VER", "PER", "LEC"],
            "GridPosition": [1.0, 4.0, 2.0],
            "TeamName": ["Red Bull Racing", "Red Bull Racing", "Ferrari"],
        })

    data = _build_launch_analysis_data(
        "2024_Bahrain_R_test",
        laps_df,
        _sess_obj=_DummySession(),
        driver1="VER",
        driver2="PER",
        compare=True,
    )
    assert data is not None
    assert data["driver1_launch"]["driver"] == "VER"
    assert data["driver2_launch"]["driver"] == "PER"
    assert len(data["leaderboard"]) == 3
    assert [r["driver"] for r in data["leaderboard"]] == ["VER", "PER", "LEC"]
    assert data["leaderboard"][1]["pos_delta"] == 2  # PER: Grid P4 -> L1 P2 (+2)
    assert data["summary"]["biggest_gainer_driver"] == "PER"
    assert data["summary"]["biggest_gain_pos"] == 2
    assert data["summary"]["best_rt_driver"] == "VER"


def test_build_launch_analysis_fig_single_and_compare():
    """Plotly launch chart renders 3 subplots with milestone markers and falls back to grey when teammates share a colour."""
    l1 = _analyze_driver_launch(_make_standing_start_tel(t_react_s=0.26, accel_mps2=11.0), driver="VER")
    l2 = _analyze_driver_launch(_make_standing_start_tel(t_react_s=0.34, accel_mps2=10.4), driver="PER")

    fig_single = build_launch_analysis_fig(l1, None, driver1="VER", colour1="#3671C6")
    assert isinstance(fig_single, go.Figure)
    assert len(fig_single.data) == 4  # 3 channel traces + 1 milestone marker trace

    fig_cmp = build_launch_analysis_fig(l1, l2, driver1="VER", driver2="PER", colour1="#3671C6", colour2="#3671C6")
    assert isinstance(fig_cmp, go.Figure)
    assert len(fig_cmp.data) == 8  # 6 channel traces + 2 milestone marker traces
    line_colours = {t.line.color for t in fig_cmp.data if hasattr(t, "line") and t.line and t.line.color}
    assert "#9AA0A6" in line_colours
    assert build_launch_analysis_fig(None) is None
