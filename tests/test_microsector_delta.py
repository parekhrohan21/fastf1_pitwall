"""Unit tests for Issue #199: Micro-Sector Speed Delta & Dominance Streamgraph Timeline."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.data.loader import MICRO_SECTOR_M, _build_microsector_delta
from src.charts.plotly import build_microsector_streamgraph_fig

LAP_M = 3000.0


def _lap(speed_fn, drs_fn=None, hz: float = 4.0, t_offset: float = 0.0):
    """Car-data-like trace for a 3 km lap driven at speed_fn(distance) km/h.

    Integrates finely, then samples at `hz` like FastF1 car data. The first
    sample is `t_offset` s after the timing line and Time is relative to the
    lap start, as in Lap.get_car_data(). Distance restarts at 0 on the first
    sample, as add_distance() does. Returns (trace, true lap time, cumulative
    time function of distance).
    """
    d_fine = np.linspace(0.0, LAP_M, 30001)
    v = np.array([speed_fn(d) for d in d_fine]) / 3.6
    t_fine = np.concatenate([[0.0], np.cumsum(np.diff(d_fine) / (0.5 * (v[1:] + v[:-1])))])
    lap_time = float(t_fine[-1])
    ts = np.arange(t_offset, lap_time, 1.0 / hz)
    ds = np.interp(ts, t_fine, d_fine)
    df = pd.DataFrame({
        "Time": pd.to_timedelta(ts, unit="s"),
        "Distance": ds - ds[0],
        "Speed": np.array([speed_fn(d) for d in ds]),
        "nGear": 7,
        "Throttle": 100.0,
        "DRS": [drs_fn(d) if drs_fn else 0 for d in ds],
    })
    return df, lap_time, lambda x: float(np.interp(x, d_fine, t_fine))


def test_identical_laps_are_even():
    """Comparing a lap with itself: zero gap everywhere and no micro-sector winner."""
    a, lt, _ = _lap(lambda d: 200.0)
    md = _build_microsector_delta(a, a.copy(), lap_times_s=(lt, lt))
    assert abs(md["summary"]["final_delta_ms"]) < 1e-6
    assert all(b["dominant"] == 0 for b in md["bins"])
    assert md["summary"]["metres1"] == 0 and md["summary"]["metres2"] == 0


def test_uniformly_faster_driver_dominates_whole_lap():
    """A driver 2 km/h faster everywhere wins every bin, and the lap gap equals the true lap-time difference."""
    a, lt1, _ = _lap(lambda d: 200.0)
    b, lt2, _ = _lap(lambda d: 198.0)
    md = _build_microsector_delta(a, b, lap_times_s=(lt1, lt2))
    assert abs(md["summary"]["final_delta_ms"] - (lt2 - lt1) * 1000) < 1.0
    assert md["summary"]["pct1"] > 99.0
    assert all(b["gain_ms"] > 0 for b in md["bins"])
    assert md["grid"]["speed_delta"][len(md["grid"]["dist"]) // 2] == np.float64(2.0)


def test_local_loss_only_shows_where_it_happens():
    """A slow 200 m stretch shows up only in the bins around it, and bin gains add up to the lap gap."""
    slow = lambda d: 150.0 if 1000 <= d < 1200 else 220.0
    a, lt1, _ = _lap(lambda d: 220.0)
    b, lt2, _ = _lap(slow)
    md = _build_microsector_delta(a, b, lap_times_s=(lt1, lt2))
    won = [x for x in md["bins"] if x["dominant"] == 1]
    assert won and all(950 <= x["start"] and x["end"] <= 1250 for x in won)
    assert abs(sum(x["gain_ms"] for x in md["bins"]) - md["summary"]["final_delta_ms"]) < 1.0
    expected = (200 / (150 / 3.6) - 200 / (220 / 3.6)) * 1000
    assert abs(md["summary"]["final_delta_ms"] - expected) < 5.0


def test_late_first_sample_is_anchored_to_official_lap_time():
    """Car data starting 0.2 s after the line still gives the official lap gap once anchored (and not without)."""
    # car data that starts 0.2 s after the line and stops short of it would
    # otherwise understate the gap
    a, lt1, _ = _lap(lambda d: 200.0, t_offset=0.0)
    b, lt2, _ = _lap(lambda d: 190.0, t_offset=0.2)
    md = _build_microsector_delta(a, b, lap_times_s=(lt1, lt2))
    assert abs(md["summary"]["final_delta_ms"] - (lt2 - lt1) * 1000) < 0.5
    unanchored = _build_microsector_delta(a, b)
    assert abs(unanchored["summary"]["final_delta_ms"] - (lt2 - lt1) * 1000) > 50


def test_sector_gains_match_official_sector_deltas():
    """With sector times supplied, each sector's summed gain equals the official sector-time difference."""
    f1 = lambda d: 210.0 + 20 * np.sin(d / 300.0)
    f2 = lambda d: 205.0 + 25 * np.sin(d / 280.0)
    a, lt1, T1 = _lap(f1, t_offset=0.1)
    b, lt2, T2 = _lap(f2, t_offset=0.15)
    s1, s2 = 1000.0, 2100.0  # timing lines (m)
    sec = (T1(s1), T1(s2) - T1(s1), T2(s1), T2(s2) - T2(s1))
    md = _build_microsector_delta(a, b, sector_times_s=sec, lap_times_s=(lt1, lt2))
    official = [(T2(s1) - T1(s1)) * 1000,
                ((T2(s2) - T2(s1)) - (T1(s2) - T1(s1))) * 1000,
                ((lt2 - T2(s2)) - (lt1 - T1(s2))) * 1000]
    for got, exp in zip([s["gain_ms"] for s in md["sectors"]], official):
        assert abs(got - exp) < 2.0
    assert abs(md["sector_bounds"][0] - s1) < 5 and abs(md["sector_bounds"][1] - s2) < 5


def test_bins_are_50m_and_never_straddle_sector_lines():
    """Bins are at most ~65 m, never cross a sector line, and together cover the whole lap."""
    a, lt, T = _lap(lambda d: 200.0)
    b, lt2, _ = _lap(lambda d: 199.0)
    md = _build_microsector_delta(a, b, sector_times_s=(T(1010.0), T(2033.0) - T(1010.0)), lap_times_s=(lt, lt2))
    lines = md["sector_bounds"]
    for x in md["bins"]:
        assert x["end"] - x["start"] <= MICRO_SECTOR_M * 1.3 + 1e-6
        assert not any(x["start"] < ln - 1e-6 and x["end"] > ln + 1e-6 for ln in lines)
    covered = sum(x["end"] - x["start"] for x in md["bins"])
    assert abs(covered - md["summary"]["lap_length_m"]) < 1e-6


def test_corner_and_drs_zones():
    """Corner bands come from marker distances (T1, T2A) and DRS bands from open-flap codes."""
    drs = lambda d: 12 if 2200 <= d < 2700 else 0
    a, lt1, _ = _lap(lambda d: 220.0, drs_fn=drs)
    b, lt2, _ = _lap(lambda d: 218.0, drs_fn=drs)
    corners = pd.DataFrame({"Number": [1, 2], "Letter": ["", "A"], "Distance": [500.0, 1500.0]})
    md = _build_microsector_delta(a, b, corners_df=corners, lap_times_s=(lt1, lt2))
    kinds = {z["label"]: z for z in md["zones"]}
    assert {"T1", "T2A", "DRS"} <= set(kinds)
    assert kinds["T1"]["start"] <= 500 <= kinds["T1"]["end"]
    assert 2150 <= kinds["DRS"]["start"] <= 2250 and 2650 <= kinds["DRS"]["end"] <= 2750
    assert {x["zone"] for x in md["bins"]} == {"corner", "drs", "straight"}


def test_missing_or_short_data_returns_none():
    """No data, too few samples or no Distance column returns None instead of raising."""
    a, lt, _ = _lap(lambda d: 200.0)
    assert _build_microsector_delta(None, a) is None
    assert _build_microsector_delta(a, a.head(5)) is None
    assert _build_microsector_delta(a.drop(columns=["Distance"]), a) is None


def test_streamgraph_figure_builds():
    """The figure has one bar per bin and two fill colours, even when both drivers share a team colour."""
    a, lt1, _ = _lap(lambda d: 200.0)
    b, lt2, _ = _lap(lambda d: 150.0 if 1000 <= d < 1200 else 205.0)
    md = _build_microsector_delta(a, b, lap_times_s=(lt1, lt2))
    fig = build_microsector_streamgraph_fig(md, "NOR", "PIA", "#FF8000", "#FF8000")
    assert isinstance(fig, go.Figure)
    bars = [t for t in fig.data if isinstance(t, go.Bar)]
    assert len(bars) == 1 and len(bars[0].x) == md["summary"]["n_bins"]
    # same team colour: Driver 2 gets a neutral colour so the ribbon still diverges
    fills = {t.fillcolor for t in fig.data if getattr(t, "fill", None) == "tozeroy"}
    assert len(fills) == 2
    assert build_microsector_streamgraph_fig(None, "A", "B") is None
