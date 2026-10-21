"""Tests for Clean Air vs Dirty Air Pace Impact & Overtaking Analysis (Issue #157)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from src.data.loader import _classify_traffic_zone, _lap_gaps_to_car_ahead, _build_dirty_air_analysis
from src.charts.plotly import build_dirty_air_fig


def _race(follower_pos=None, follower_gap=None, follower_pace=None, n=20):
    """Leader AAA plus follower BBB over ``n`` laps.

    follower_gap(lap)  -> gap behind the leader at the line (s)
    follower_pace(lap) -> BBB lap time (s); AAA always runs 90.0 s
    follower_pos(lap)  -> BBB's position (AAA is the other of P1/P2)
    """
    rows = []
    for lap in range(1, n + 1):
        gap = follower_gap(lap)
        pos_b = follower_pos(lap) if follower_pos else 2
        # Whoever is ahead sets the clock; the other is `gap` seconds later.
        t_lead = 90.0 * lap
        t_a, t_b = (t_lead, t_lead + gap) if pos_b == 2 else (t_lead + gap, t_lead)
        for drv, pos, t, lt in (("AAA", 3 - pos_b, t_a, 90.0), ("BBB", pos_b, t_b, follower_pace(lap))):
            rows.append({"Driver": drv, "LapNumber": lap, "Position": pos,
                         "Time": pd.to_timedelta(t, unit="s"), "LapTime": pd.to_timedelta(lt, unit="s"),
                         "IsAccurate": True, "TrackStatus": "1", "PitInTime": pd.NaT, "PitOutTime": pd.NaT})
    return pd.DataFrame(rows)


def test_zone_boundaries():
    assert _classify_traffic_zone(3.0) == "Clean Air"
    assert _classify_traffic_zone(2.5) == "Dirty Air"   # 2.5 is not > 2.5
    assert _classify_traffic_zone(0.8) == "Dirty Air"   # 0.8 is not < 0.8
    assert _classify_traffic_zone(0.79) == "DRS / Battle"
    assert _classify_traffic_zone(None) == "Clean Air"   # leader: no car ahead
    assert _classify_traffic_zone(float("nan")) == "Clean Air"


def test_gap_to_car_ahead_uses_adjacent_position_only():
    df = _race(follower_gap=lambda l: 1.2, follower_pace=lambda l: 90.0, n=3)
    gaps = _lap_gaps_to_car_ahead(df)
    assert gaps[df["Driver"] == "BBB"].round(3).tolist() == [1.2, 1.2, 1.2]
    assert gaps[df["Driver"] == "AAA"].isna().all()  # leader


def test_dirty_air_deficit_and_zone_split():
    # Laps 1-6 battle (0.5 s), 7-13 dirty (1.5 s), 14-20 clean (4 s).
    gap = lambda l: 0.5 if l <= 6 else (1.5 if l <= 13 else 4.0)
    pace = lambda l: 90.8 if l <= 6 else (90.4 if l <= 13 else 90.0)
    res = _build_dirty_air_analysis("t_zones", _race(follower_gap=gap, follower_pace=pace), ["BBB"])["drivers"]["BBB"]
    assert res["clean_median_s"] == pytest.approx(90.0, abs=0.2)
    assert res["dirty_deficit_s"] == pytest.approx(0.4, abs=0.2)
    assert res["battle_deficit_s"] > res["dirty_deficit_s"] > 0
    assert res["time_lost_s"] > 0
    assert 0 < res["clean_pct"] < 100


def test_leader_runs_in_clean_air():
    res = _build_dirty_air_analysis("t_leader", _race(follower_gap=lambda l: 0.5, follower_pace=lambda l: 90.5), ["AAA"])["drivers"]["AAA"]
    assert res["clean_pct"] == 100.0
    assert res["dirty_deficit_s"] is None and res["overtake_attempts"] == 0


def test_overtake_success_rate():
    # BBB sits 0.5 s behind for laps 1-6, then passes on lap 7.
    df = _race(follower_gap=lambda l: 0.5, follower_pace=lambda l: 90.5,
               follower_pos=lambda l: 2 if l < 7 else 1)
    res = _build_dirty_air_analysis("t_pass", df, ["BBB"])["drivers"]["BBB"]
    assert res["overtake_attempts"] >= 1 and res["overtakes"] == 1
    assert res["overtake_rate_pct"] == 100.0


def test_no_overtake_when_position_unchanged():
    df = _race(follower_gap=lambda l: 0.5, follower_pace=lambda l: 90.5)
    res = _build_dirty_air_analysis("t_nopass", df, ["BBB"])["drivers"]["BBB"]
    assert res["overtake_attempts"] == 1 and res["overtakes"] == 0
    assert res["overtake_rate_pct"] == 0.0


def test_missing_columns_or_empty_returns_none():
    assert _build_dirty_air_analysis("t_empty", pd.DataFrame(), None) is None
    assert _build_dirty_air_analysis("t_cols", pd.DataFrame({"Driver": ["A"]}), None) is None


def test_figure_has_zone_traces_and_reference_line():
    gap = lambda l: 0.5 if l <= 6 else (1.5 if l <= 13 else 4.0)
    pace = lambda l: 90.8 if l <= 6 else (90.4 if l <= 13 else 90.0)
    res = _build_dirty_air_analysis("t_fig", _race(follower_gap=gap, follower_pace=pace), ["BBB"])["drivers"]["BBB"]
    fig = build_dirty_air_fig(res)
    assert isinstance(fig, go.Figure)
    assert {t.name for t in fig.data} == {"Clean Air", "Dirty Air", "DRS / Battle"}
    assert [t for t in fig.data if t.name == "DRS / Battle"][0].marker.symbol == "diamond"
    assert build_dirty_air_fig(None) is None
