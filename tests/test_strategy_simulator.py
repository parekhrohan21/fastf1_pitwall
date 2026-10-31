"""Tests for the Tyre Stint Pace Degradation Matrix & Pit Window Re-optimisation Simulator (#196)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.data.loader import (
    STRAT_CLIFF_K,
    STRAT_MIN_DEG_S,
    _analyse_undercut_risk,
    _build_compound_deg_models,
    _build_strategy_simulation,
    _compound_lap_time,
    _extract_actual_strategy,
    _optimise_strategies,
    _simulate_strategy,
    _splice_reoptimised_sim,
    _undercut_gain,
)
from src.charts.plotly import build_deg_matrix_fig, build_strategy_timeline_fig

TOTAL = 40
FUEL = 0.035
TRUE = {  # zero-fuel base pace and linear degradation per compound
    "SOFT": (90.0, 0.12),
    "MEDIUM": (90.4, 0.07),
    "HARD": (90.8, 0.04),
}
PLANS = {
    "AAA": [("SOFT", 14), ("HARD", 26)],
    "BBB": [("MEDIUM", 20), ("HARD", 20)],
    "CCC": [("MEDIUM", 18), ("SOFT", 10), ("MEDIUM", 12)],
    "DDD": [("HARD", 24), ("SOFT", 16)],
}
OFFSET = {"AAA": 0.0, "BBB": 0.3, "CCC": 0.6, "DDD": 0.9}


def _race_laps(plans=PLANS, total=TOTAL, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    recs = []
    for drv, plan in plans.items():
        lap, clock = 0, 3600.0
        for stint_no, (cmp, n) in enumerate(plan, 1):
            base, deg = TRUE[cmp]
            for age in range(1, n + 1):
                lap += 1
                t = base + OFFSET[drv] + deg * age + FUEL * (total - lap) + rng.normal(0, 0.02)
                clock += t
                recs.append({
                    "Driver": drv, "LapNumber": lap, "Stint": stint_no, "Compound": cmp,
                    "TyreLife": age, "LapTime": pd.to_timedelta(t, unit="s"),
                    "Time": pd.to_timedelta(clock, unit="s"), "IsAccurate": True, "TrackStatus": "1",
                    "PitInTime": pd.NaT, "PitOutTime": pd.NaT,
                })
    return pd.DataFrame(recs)


@pytest.fixture
def laps():
    return _race_laps()


@pytest.fixture
def models(laps):
    return _build_compound_deg_models(laps, fuel_effect=FUEL)


def test_models_recover_compound_ordering(models):
    assert set(models) == {"SOFT", "MEDIUM", "HARD"}
    assert all(m["source"] == "observed" for m in models.values())
    assert models["SOFT"]["lin"] > models["MEDIUM"]["lin"] > models["HARD"]["lin"]
    assert models["SOFT"]["base"] < models["HARD"]["base"]
    # Fuel-decoupled slope should be close to the true mechanical wear.
    assert models["MEDIUM"]["lin"] == pytest.approx(TRUE["MEDIUM"][1], abs=0.03)


def test_missing_compound_is_estimated():
    plans = {"AAA": [("MEDIUM", 20), ("HARD", 20)], "BBB": [("HARD", 22), ("MEDIUM", 18)]}
    m = _build_compound_deg_models(_race_laps(plans), fuel_effect=FUEL)
    assert m["SOFT"]["source"] == "estimated"
    assert m["SOFT"]["base"] < m["MEDIUM"]["base"]
    assert m["SOFT"]["lin"] > m["MEDIUM"]["lin"]


def test_models_none_on_empty():
    assert _build_compound_deg_models(pd.DataFrame(), FUEL) is None
    assert _build_compound_deg_models(None, FUEL) is None


def test_degradation_floor_applied():
    m = {"base": 90.0, "lin": -0.05, "quad": 0.0, "cliff": 99}
    plans = {"AAA": [("MEDIUM", 20), ("HARD", 20)]}
    out = _build_compound_deg_models(_race_laps(plans), fuel_effect=FUEL)
    assert all(v["lin"] >= STRAT_MIN_DEG_S for v in out.values())
    assert _compound_lap_time(m, 1) < _compound_lap_time(m, 0)  # raw helper does not floor


def test_cliff_penalty_kicks_in():
    m = {"base": 90.0, "lin": 0.05, "quad": 0.0, "cliff": 10}
    before = _compound_lap_time(m, 10) - _compound_lap_time(m, 9)
    after = _compound_lap_time(m, 15) - _compound_lap_time(m, 14)
    assert before == pytest.approx(0.05)
    assert after == pytest.approx(0.05 + STRAT_CLIFF_K * (25 - 16))


def test_optimiser_total_matches_simulation(models):
    opt = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL)
    best = opt["best"]
    sim = _simulate_strategy(models, best["compounds"], best["stint_lengths"], 22.0, TOTAL, FUEL)
    assert sim["total_time_s"] == pytest.approx(best["total_time_s"], abs=1e-6)
    assert sum(best["stint_lengths"]) == TOTAL
    assert len(sim["lap_numbers"]) == TOTAL and sim["pit_laps"] == best["pit_laps"]


def test_optimiser_is_exhaustive_for_one_stop(models):
    opt = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL, max_stops=1)
    brute = min(
        _simulate_strategy(models, [a, b], [n, TOTAL - n], 22.0, TOTAL, FUEL)["total_time_s"]
        for a in models for b in models if a != b for n in range(5, TOTAL - 4)
    )
    assert opt["best"]["total_time_s"] == pytest.approx(brute, abs=1e-6)


def test_two_compound_rule(models):
    opt = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL)
    assert all(len(set(p["compounds"])) >= 2 for p in opt["ranked"])
    assert 0 not in opt["best_by_stops"]


def test_pit_loss_drives_stop_count(models):
    cheap = _optimise_strategies(models, TOTAL, 2.0, fuel_effect=FUEL)
    dear = _optimise_strategies(models, TOTAL, 60.0, fuel_effect=FUEL)
    assert cheap["best"]["stops"] == 2
    assert dear["best"]["stops"] == 1


def test_windows_contain_optimal_lap(models):
    opt = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL)
    for plan in opt["best_by_stops"].values():
        for (lo, hi), p in zip(plan["windows"], plan["pit_laps"]):
            assert lo <= p <= hi


def test_mid_race_reoptimisation(models):
    r = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL, start_lap=20,
                             current_compound="MEDIUM", current_tyre_age=20, used_compounds=("SOFT",))
    assert r["best"]["compounds"][0] == "MEDIUM"
    assert 0 in r["best_by_stops"]  # staying out is legal: SOFT already used
    assert all(sum(p["stint_lengths"]) == TOTAL - 20 for p in r["ranked"])
    r2 = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL, start_lap=20,
                              current_compound="MEDIUM", current_tyre_age=20)
    assert 0 not in r2["best_by_stops"]  # must still use a second compound


def test_risk_score_bounds(models):
    opt = _optimise_strategies(models, TOTAL, 22.0, fuel_effect=FUEL)
    for p in opt["ranked"]:
        assert 0 <= p["risk"]["score"] <= 100
        assert p["risk"]["level"] in {"Low", "Medium", "High"}


def test_extract_actual_strategy(laps):
    a = _extract_actual_strategy("CCC", laps)
    assert a["compounds"] == ["MEDIUM", "SOFT", "MEDIUM"]
    assert a["stint_lengths"] == [18, 10, 12]
    assert a["pit_laps"] == [18, 28]
    assert _extract_actual_strategy("ZZZ", laps) is None


def test_undercut_gain_positive_on_worn_tyres(models):
    assert _undercut_gain(models, "MEDIUM", 25, "HARD") > _undercut_gain(models, "MEDIUM", 2, "HARD")


def test_undercut_rows(laps, models):
    rows = _analyse_undercut_risk("BBB", laps, 20, 22.0, models, "HARD", actual_pit_laps=[20])
    assert [r["lap"] for r in rows] == list(range(17, 24))
    plan_row = next(r for r in rows if r["is_plan_lap"])
    assert plan_row["rejoin_pos"] >= plan_row["running_pos"]
    assert all(0 <= r["risk"] <= 100 for r in rows)
    assert any(r["after_actual_stop"] for r in rows)


def test_splice_reoptimised(models):
    actual = _simulate_strategy(models, ["MEDIUM", "HARD"], [20, 20], 22.0, TOTAL, FUEL)
    tail = _simulate_strategy(models, ["MEDIUM", "SOFT"], [5, 20], 22.0, TOTAL, FUEL,
                              start_lap=15, start_ages=[15, 0])
    sp = _splice_reoptimised_sim(actual, tail, 15, 22.0)
    assert sp["lap_numbers"] == list(range(1, TOTAL + 1))
    assert sp["compounds"] == ["MEDIUM", "SOFT"] and sp["stint_lengths"] == [20, 20]
    assert sp["total_time_s"] == pytest.approx(sum(actual["lap_times"][:15]) + tail["total_time_s"])


def test_build_strategy_simulation_end_to_end(laps):
    data = _build_strategy_simulation("test_196", laps, "BBB", 22.0, FUEL, 15)
    assert data is not None
    names = list(data["sims"])
    assert any(n.startswith("Actual") for n in names)
    assert any(n.startswith("Re-optimised") for n in names)
    assert data["actual_delta_s"] >= -1e-6  # nothing beats the optimum under the same model
    assert data["undercut"]
    fig = build_strategy_timeline_fig(data["sims"])
    assert isinstance(fig, go.Figure) and len(fig.data) > len(names)
    assert isinstance(build_deg_matrix_fig(data["models"]), go.Figure)


def test_figures_handle_empty():
    assert build_strategy_timeline_fig({}) is None
    assert build_deg_matrix_fig({}) is None

