"""Tests for the Weekend Multi-Session Progression Tracker (Issue #156).

Covers the two pure helpers (_summarise_weekend_session, _aggregate_weekend_progression)
and the Plotly figure builder. The network-bound _build_weekend_progression_data is not
exercised here.
"""
import pandas as pd
import plotly.graph_objects as go
from src.data.loader import _summarise_weekend_session, _aggregate_weekend_progression
from src.charts.plotly import build_weekend_progression_fig


def _laps(rows):
    """rows: (driver, lap_no, seconds, compound, stint, speed_st)."""
    return pd.DataFrame({
        "Driver": [r[0] for r in rows],
        "LapNumber": [r[1] for r in rows],
        "LapTime": [pd.to_timedelta(r[2], unit="s") if r[2] is not None else pd.NaT for r in rows],
        "Compound": [r[3] for r in rows],
        "Stint": [r[4] for r in rows],
        "SpeedST": [r[5] for r in rows],
    })


def test_summary_picks_fastest_lap_and_gap_to_field():
    laps = _laps([
        ("NOR", 1, 91.0, "SOFT", 1, 300.0),
        ("NOR", 2, 90.0, "SOFT", 1, 310.0),
        ("NOR", 3, None, "MEDIUM", 2, 290.0),
        ("VER", 1, 89.5, "SOFT", 1, 305.0),
    ])
    s = _summarise_weekend_session("FP1", laps, "NOR")
    assert s["fastest_s"] == 90.0 and s["fastest_lap_no"] == 2
    assert s["fastest_compound"] == "SOFT"
    assert abs(s["gap_to_field_s"] - 0.5) < 1e-9
    assert s["lap_count"] == 3 and s["top_speed"] == 310.0
    assert s["compounds"]["SOFT"] == {"laps": 2, "stints": 1}
    assert s["compounds"]["MEDIUM"]["laps"] == 1


def test_summary_none_when_driver_absent_or_empty():
    laps = _laps([("VER", 1, 89.5, "SOFT", 1, 305.0)])
    assert _summarise_weekend_session("FP1", laps, "NOR") is None
    assert _summarise_weekend_session("FP1", pd.DataFrame(), "NOR") is None


def _sum(code, t, gap, laps=10, cmp="SOFT"):
    return {"code": code, "label": code, "fastest_s": t, "fastest_compound": cmp,
            "field_best_s": t - gap if t is not None else None, "gap_to_field_s": gap,
            "lap_count": laps, "top_speed": 300.0, "compounds": {cmp: {"laps": laps, "stints": 1}}}


def test_aggregate_orders_sessions_and_computes_deltas():
    # Deliberately out of running order.
    data = _aggregate_weekend_progression(
        [_sum("Q", 88.0, 0.1), _sum("FP1", 91.0, 1.0), _sum("FP2", 90.0, 0.6)], circuit_length_km=5.0)
    assert [s["code"] for s in data["sessions"]] == ["FP1", "FP2", "Q"]
    assert [s["delta_prev_s"] for s in data["sessions"]] == [None, -1.0, -2.0]
    assert data["total_laps"] == 30 and data["total_km"] == 150.0


def test_aggregate_practice_to_quali_improvement():
    data = _aggregate_weekend_progression([_sum("FP1", 91.0, 1.0), _sum("FP2", 90.0, 0.6), _sum("Q", 88.0, 0.1)])
    imp = data["improvement"]
    assert imp["from_label"] == "FP2" and imp["to_label"] == "Q"
    assert abs(imp["delta_s"] + 2.0) < 1e-9
    assert abs(imp["field_gap_change_s"] - 0.5) < 1e-9  # gap closed from 0.6 to 0.1


def test_aggregate_handles_missing_quali_and_empty_input():
    assert _aggregate_weekend_progression([]) is None
    data = _aggregate_weekend_progression([_sum("FP1", 91.0, 1.0)])
    assert data["improvement"] is None and data["total_km"] is None


def test_tyre_matrix_collects_laps_per_session():
    data = _aggregate_weekend_progression([_sum("FP1", 91.0, 1.0, 8, "HARD"), _sum("R", 95.0, 2.0, 50, "HARD")])
    assert data["tyre_matrix"]["HARD"] == {"FP1": 8, "R": 50}


def test_figure_has_pace_and_step_traces():
    data = _aggregate_weekend_progression([_sum("FP1", 91.0, 1.0), _sum("FP2", 90.0, 0.6), _sum("Q", 88.0, 0.1)])
    fig = build_weekend_progression_fig(data, "#FF8700")
    assert isinstance(fig, go.Figure) and len(fig.data) == 2
    assert fig.data[1].line.shape == "hv"
    assert build_weekend_progression_fig(None) is None
