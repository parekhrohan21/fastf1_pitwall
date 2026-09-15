"""Tests for Issue #151 — Fuel-Corrected Pure Tyre Degradation & Fuel Burn Decoupler.

Validates:
- _build_fuel_decoupled_tyre_deg returns all required fuel-decoupled and raw fields.
- true_deg_rate (fuel_corrected_slope) decouples fuel burn mass gain (+alpha s/lap).
- Negative or flat raw slopes on durable compounds become positive true degradation.
- Fuel effect zero fallback matches raw pace metrics.
- Lap-level records contain both raw and fuel-corrected times with fuel correction offset.
- build_tyre_deg_fig accepts show_fuel_corrected and outputs decoupled table rows.
- Robust edge case handling (empty frames, unknown drivers, insufficient laps).
"""

import os
import sys
from datetime import timedelta
import numpy as np
import pandas as pd
import pytest

# Ensure repo root is on python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import _build_fuel_decoupled_tyre_deg, _build_tyre_deg_data
from src.charts.plotly import build_tyre_deg_fig


# ── Fixtures & Helpers ────────────────────────────────────────────────────────

def _make_sample_laps_df(
    driver: str = "VER",
    n_laps: int = 15,
    base_time_s: float = 85.0,
    raw_slope_per_lap: float = 0.020,
    start_lap: int = 1,
    start_tyre_life: int = 1,
    compound: str = "MEDIUM",
    stint: int = 1,
    total_race_laps: int = 50,
) -> pd.DataFrame:
    """Generate a clean synthetic laps DataFrame."""
    lap_nums = list(range(start_lap, start_lap + n_laps))
    tyre_lives = list(range(start_tyre_life, start_tyre_life + n_laps))
    lap_times_s = [base_time_s + raw_slope_per_lap * (t - start_tyre_life) for t in tyre_lives]

    records = []
    for ln, tl, lt in zip(lap_nums, tyre_lives, lap_times_s):
        records.append({
            "Driver": driver,
            "LapNumber": ln,
            "TyreLife": float(tl),
            "LapTime": timedelta(seconds=lt),
            "Compound": compound,
            "Stint": stint,
            "IsAccurate": True,
            "TrackStatus": "1",
        })
    df = pd.DataFrame(records)
    # Ensure LapNumber max matches total_race_laps if higher
    return df


# ── Unit Tests ────────────────────────────────────────────────────────────────

def test_fuel_decoupled_returns_expected_fields():
    """All required fuel-decoupling fields must be present in the stint dictionary."""
    df = _make_sample_laps_df("HAM", n_laps=12, raw_slope_per_lap=0.015)
    result = _build_fuel_decoupled_tyre_deg("HAM", df, fuel_effect=0.035, total_laps=50)

    assert result is not None
    assert len(result) == 1
    s = result[0]

    required_fields = [
        "stint", "compound", "laps", "slope", "base_pace", "raw_slope", "raw_base_pace",
        "fuel_corrected_slope", "fuel_corrected_base_pace", "true_deg_rate", "fuel_effect",
        "quad_coeffs", "raw_quad_coeffs", "cliff_lap", "raw_cliff_lap", "remaining_laps",
        "pit_window_low", "pit_window_high", "is_fuel_decoupled"
    ]
    for field in required_fields:
        assert field in s, f"Missing expected field: {field}"

    assert s["is_fuel_decoupled"] is True
    assert s["fuel_effect"] == pytest.approx(0.035, rel=1e-3)


def test_fuel_decoupled_slope_shift():
    """True degradation slope must be approximately raw_slope + fuel_effect."""
    raw_slope = 0.020
    fuel_effect = 0.035
    df = _make_sample_laps_df("VER", n_laps=15, raw_slope_per_lap=raw_slope)
    result = _build_fuel_decoupled_tyre_deg("VER", df, fuel_effect=fuel_effect, total_laps=50)

    assert result is not None
    s = result[0]
    expected_true_slope = raw_slope + fuel_effect
    assert s["raw_slope"] == pytest.approx(raw_slope, abs=1e-3)
    assert s["fuel_corrected_slope"] == pytest.approx(expected_true_slope, abs=1e-3)
    assert s["true_deg_rate"] == pytest.approx(expected_true_slope, abs=1e-3)


def test_negative_raw_slope_becomes_positive_true_deg():
    """Fuel burn masking (-0.010 s/lap raw) must become positive (+0.025 s/lap) once decoupled."""
    raw_slope = -0.010  # Car was getting faster on timing screens as fuel burned
    fuel_effect = 0.035
    df = _make_sample_laps_df("ALO", n_laps=14, raw_slope_per_lap=raw_slope, compound="HARD")
    result = _build_fuel_decoupled_tyre_deg("ALO", df, fuel_effect=fuel_effect, total_laps=50)

    assert result is not None
    s = result[0]
    assert s["raw_slope"] < 0, "Raw slope should be negative"
    assert s["true_deg_rate"] > 0, "True mechanical tyre degradation rate must be positive"
    assert s["true_deg_rate"] == pytest.approx(raw_slope + fuel_effect, abs=1e-3)


def test_zero_fuel_effect_matches_raw():
    """When fuel_effect is 0.0, fuel_corrected_slope and raw_slope must be identical."""
    df = _make_sample_laps_df("NOR", n_laps=10, raw_slope_per_lap=0.040)
    result = _build_fuel_decoupled_tyre_deg("NOR", df, fuel_effect=0.0, total_laps=50)

    assert result is not None
    s = result[0]
    assert s["is_fuel_decoupled"] is False
    assert s["slope"] == pytest.approx(s["raw_slope"], abs=1e-4)
    assert s["fuel_corrected_slope"] == pytest.approx(s["raw_slope"], abs=1e-4)


def test_lap_level_data_fields():
    """Each individual lap record must contain raw, fuel-corrected, and correction amounts."""
    df = _make_sample_laps_df("LEC", n_laps=8, raw_slope_per_lap=0.030)
    result = _build_fuel_decoupled_tyre_deg("LEC", df, fuel_effect=0.035, total_laps=50)

    assert result is not None
    laps = result[0]["laps"]
    assert len(laps) == 8

    first_lap = laps[0]
    for key in ("TyreLife", "LapTime_s", "LapTime_s_raw", "LapTime_s_fuel_corr", "FuelCorrection_s", "LapNumber"):
        assert key in first_lap, f"Missing lap-level key: {key}"

    # Verify that fuel correction calculation: LapTime_s_fuel_corr == LapTime_s_raw - FuelCorrection_s
    for lap in laps:
        assert lap["LapTime_s_fuel_corr"] == pytest.approx(
            lap["LapTime_s_raw"] - lap["FuelCorrection_s"], abs=1e-4
        )


def test_tyre_deg_data_backward_compatibility():
    """_build_tyre_deg_data must accept fuel_effect without breaking existing 2-arg calls."""
    df = _make_sample_laps_df("PIA", n_laps=10, raw_slope_per_lap=0.025)

    # 2-arg call (existing signature)
    res_legacy = _build_tyre_deg_data("PIA", df)
    assert res_legacy is not None
    assert res_legacy[0]["is_fuel_decoupled"] is False

    # 3-arg call with fuel_effect
    res_decoupled = _build_tyre_deg_data("PIA", df, fuel_effect=0.035)
    assert res_decoupled is not None
    assert res_decoupled[0]["is_fuel_decoupled"] is True
    assert res_decoupled[0]["true_deg_rate"] > res_legacy[0]["slope"]


def test_build_tyre_deg_fig_with_decoupling():
    """build_tyre_deg_fig must render Plotly figure and populate decoupled table rows."""
    df1 = _make_sample_laps_df("VER", n_laps=12, raw_slope_per_lap=0.020)
    df2 = _make_sample_laps_df("NOR", n_laps=12, raw_slope_per_lap=0.030)

    d1 = _build_fuel_decoupled_tyre_deg("VER", df1, fuel_effect=0.035, total_laps=50)
    d2 = _build_fuel_decoupled_tyre_deg("NOR", df2, fuel_effect=0.035, total_laps=50)

    fig, table_rows = build_tyre_deg_fig(
        d1, d2, "VER", "NOR", "#3671C6", "#FF8000", compare=True, show_fuel_corrected=True
    )

    assert fig is not None
    assert len(table_rows) == 2

    row1 = table_rows[0]
    assert row1["driver"] == "VER"
    assert row1["is_fuel_decoupled"] is True
    assert "true_deg_rate" in row1
    assert "raw_deg_rate" in row1
    assert row1["true_deg_rate"] > row1["raw_deg_rate"]


def test_edge_cases_and_graceful_failures():
    """Empty or malformed data must return None without raising unhandled exceptions."""
    assert _build_fuel_decoupled_tyre_deg("VER", None) is None
    assert _build_fuel_decoupled_tyre_deg("VER", pd.DataFrame()) is None

    # Unknown driver
    df = _make_sample_laps_df("VER", n_laps=8)
    assert _build_fuel_decoupled_tyre_deg("XYZ", df) is None

    # Insufficient laps (< 4 laps per stint)
    df_short = _make_sample_laps_df("VER", n_laps=3)
    assert _build_fuel_decoupled_tyre_deg("VER", df_short) is None
