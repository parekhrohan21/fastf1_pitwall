"""Unit tests for Issue #198: Corner Geometry & Minimum-Radius Apex Trajectory Curvature."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.data.loader import (
    _build_corner_geometry,
    _compare_corner_lines,
    _path_curvature,
    _radius_from_curvature,
    _resample_xy_path,
)
from src.charts.plotly import build_corner_geometry_fig


def _stadium(radius_m: float = 50.0, straight_m: float = 400.0, n: int = 4000,
             units_per_m: float = 10.0, with_distance: bool = False) -> pd.DataFrame:
    """Anticlockwise stadium lap: straight, left hairpin, straight, left hairpin.

    Starts at the beginning of the bottom straight. X/Y are in FastF1 units
    (1/10 m) by default.
    """
    R, L = radius_m, straight_m
    per = 2 * L + 2 * np.pi * R
    u = np.linspace(0.0, per, n, endpoint=False)
    x = np.empty(n)
    y = np.empty(n)
    for i, ui in enumerate(u):
        if ui < L:
            x[i], y[i] = ui, -R
        elif ui < L + np.pi * R:
            a = (ui - L) / R - np.pi / 2
            x[i], y[i] = L + R * np.cos(a), R * np.sin(a)
        elif ui < 2 * L + np.pi * R:
            x[i], y[i] = L - (ui - L - np.pi * R), R
        else:
            a = (ui - 2 * L - np.pi * R) / R + np.pi / 2
            x[i], y[i] = R * np.cos(a), R * np.sin(a)
    df = pd.DataFrame({"X": x * units_per_m, "Y": y * units_per_m,
                       "Speed": np.where(np.abs(y) < R - 1, 120.0, 290.0)})
    if with_distance:
        df["Distance"] = u
    return df


def _corners(radius_m: float = 50.0, straight_m: float = 400.0, units_per_m: float = 10.0) -> pd.DataFrame:
    # markers at the midpoint of each hairpin arc
    return pd.DataFrame({
        "X": [(straight_m + radius_m) * units_per_m, -radius_m * units_per_m],
        "Y": [0.0, 0.0],
        "Number": [1, 2],
        "Letter": ["", ""],
    })


def test_circle_curvature_matches_radius():
    t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    R = 80.0
    path = _resample_xy_path(pd.DataFrame({"X": R * np.cos(t) * 10, "Y": R * np.sin(t) * 10}))
    kappa = _path_curvature(path["x"], path["y"], path["step"])
    r = _radius_from_curvature(kappa)
    inner = r[20:-20]  # Savitzky-Golay edges are less accurate
    assert np.median(inner) == pytest.approx(R, rel=0.03)
    assert np.all(kappa[20:-20] > 0), "anticlockwise circle should have positive (left) curvature"


def test_hairpin_minimum_radius_and_apex_on_marker():
    geo = _build_corner_geometry(_stadium(), _corners())
    assert geo is not None
    t1 = next(c for c in geo["corners"] if c["corner"] == "T1")
    assert t1["min_radius_m"] == pytest.approx(50.0, rel=0.06)
    assert t1["direction"] == "L"
    assert t1["apex_offset_m"] < 3.0
    assert abs(t1["apex_shift_m"]) < 5.0
    assert t1["apex_speed_kmh"] == pytest.approx(120.0)
    assert geo["summary"]["marker_source"] == "circuit"


def _ellipse(a: float = 300.0, b: float = 100.0, n: int = 6000):
    """Anticlockwise ellipse lap starting at the bottom; tightest points at (±a, 0),
    where R_min = b²/a. Returns the telemetry frame and the metre-space points."""
    t = np.linspace(-np.pi / 2, 3 * np.pi / 2, n, endpoint=False)
    x, y = a * np.cos(t), b * np.sin(t)
    # ~100 km/h through the 33 m tightest point (~2.4 g), as a real car would be
    return pd.DataFrame({"X": x * 10, "Y": y * 10, "Speed": np.full(n, 100.0)}), x, y


def test_ellipse_apex_at_tightest_point():
    df, x, y = _ellipse()
    corners = pd.DataFrame({"X": [3000.0], "Y": [0.0], "Number": [1], "Letter": [""]})
    t1 = _build_corner_geometry(df, corners)["corners"][0]
    assert t1["min_radius_m"] == pytest.approx(100.0 ** 2 / 300.0, rel=0.1)
    assert t1["apex_offset_m"] < 3.0


def test_marker_before_apex_reads_as_late_apex():
    df, x, y = _ellipse()
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    apex_i = int(np.argmin((x - 300.0) ** 2 + y ** 2))
    # marker 30 m earlier along the lap than the true apex
    mark_i = int(np.argmin(np.abs(s - (s[apex_i] - 30.0))))
    corners = pd.DataFrame({"X": [x[mark_i] * 10], "Y": [y[mark_i] * 10], "Number": [1], "Letter": [""]})
    t1 = _build_corner_geometry(df, corners)["corners"][0]
    assert t1["apex_shift_m"] == pytest.approx(30.0, abs=4.0)


def test_distance_column_calibrates_xy_units():
    # same lap with X/Y in metres instead of decimetres; Distance gives the true scale
    geo = _build_corner_geometry(_stadium(units_per_m=1.0, with_distance=True), _corners(units_per_m=1.0))
    t1 = next(c for c in geo["corners"] if c["corner"] == "T1")
    assert t1["min_radius_m"] == pytest.approx(50.0, rel=0.06)


def test_auto_detects_corners_without_circuit_info():
    # rotate the lap start to mid-straight so neither hairpin touches the path ends
    df = _stadium()
    df = pd.concat([df.iloc[200:], df.iloc[:200]], ignore_index=True)
    geo = _build_corner_geometry(df, None)
    assert geo["summary"]["marker_source"] == "auto"
    assert geo["summary"]["corners_analysed"] == 2
    for c in geo["corners"]:
        assert c["min_radius_m"] == pytest.approx(50.0, rel=0.08)
        assert c["apex_offset_m"] is None


def test_compare_lines_wider_line_reads_outside():
    geo_tight = _build_corner_geometry(_stadium(radius_m=50.0), _corners())
    geo_wide = _build_corner_geometry(_stadium(radius_m=53.0), _corners())
    rows = {r["corner"]: r for r in _compare_corner_lines(geo_tight, geo_wide)}
    assert set(rows) == {"T1", "T2"}
    r = rows["T1"]
    assert r["radius_delta_m"] == pytest.approx(3.0, abs=1.0)
    # Driver 2 (wide line) is ~3 m to the outside, so the inside offset is negative
    assert r["apex_lateral_m"] == pytest.approx(-3.0, abs=0.5)
    reverse = {x["corner"]: x for x in _compare_corner_lines(geo_wide, geo_tight)}
    assert reverse["T1"]["apex_lateral_m"] == pytest.approx(3.0, abs=0.5)


def test_missing_or_short_xy_returns_none():
    assert _build_corner_geometry(None) is None
    assert _build_corner_geometry(pd.DataFrame({"Speed": [100.0] * 50})) is None
    assert _build_corner_geometry(pd.DataFrame({"X": [0.0, 1.0], "Y": [0.0, 1.0]})) is None
    assert _compare_corner_lines(None, None) == []


def test_corner_geometry_fig_builds_single_and_compare():
    geo1 = _build_corner_geometry(_stadium(), _corners())
    geo2 = _build_corner_geometry(_stadium(radius_m=53.0), _corners())
    fig = build_corner_geometry_fig(geo1, None, "NOR")
    assert isinstance(fig, go.Figure)
    names = [t.name for t in fig.data]
    assert "Official corner marker" in names and "NOR geometric apex" in names
    fig2 = build_corner_geometry_fig(geo1, geo2, "NOR", "PIA")
    assert any(t.name == "PIA line" for t in fig2.data)
    assert fig2.layout.yaxis.scaleanchor == "x"
    assert build_corner_geometry_fig(None) is None


def test_implausible_lateral_g_is_flagged_low_confidence():
    # a 50 m hairpin taken at 290 km/h would need ~13 g: flagged, and not reported
    # as the tightest corner while a trusted one exists
    df = _stadium()
    geo_ok = _build_corner_geometry(df, _corners())
    assert geo_ok["summary"]["low_confidence_corners"] == 0
    assert all(c["lateral_g"] < 6.5 for c in geo_ok["corners"])
    fast = df.copy()
    fast["Speed"] = 290.0
    geo_fast = _build_corner_geometry(fast, _corners())
    assert geo_fast["summary"]["low_confidence_corners"] == len(geo_fast["corners"])
    assert all(c["low_confidence"] for c in geo_fast["corners"])
