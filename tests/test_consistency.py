import pandas as pd
import numpy as np
import pytest
from src.data.loader import _build_consistency_analysis
from src.charts.plotly import build_stint_consistency_fig


def test_build_consistency_analysis():
    # Construct a sample laps_df
    laps_data = {
        "Driver": ["VER"] * 10 + ["NOR"] * 10,
        "LapNumber": list(range(1, 11)) + list(range(1, 11)),
        "LapTime": [
            pd.Timedelta(seconds=90.0 + (i * 0.1)) for i in range(10)
        ] + [
            pd.Timedelta(seconds=91.0 + (i * 0.5)) for i in range(10)
        ],
        "Stint": [1] * 5 + [2] * 5 + [1] * 5 + [2] * 5,
        "Compound": ["MEDIUM"] * 5 + ["HARD"] * 5 + ["MEDIUM"] * 5 + ["HARD"] * 5,
        "IsAccurate": [True] * 20,
        "PitInTime": [pd.NaT] * 20,
        "PitOutTime": [pd.NaT] * 20,
        "TrackStatus": ["1"] * 20,
        "Position": [1] * 10 + [2] * 10,
    }
    df = pd.DataFrame(laps_data)

    res = _build_consistency_analysis("2024_Bahrain_Race", df, ["VER", "NOR"])
    assert res is not None
    assert "drivers" in res
    assert "VER" in res["drivers"]
    assert "NOR" in res["drivers"]

    ver_data = res["drivers"]["VER"]
    nor_data = res["drivers"]["NOR"]

    # VER should have a lower std dev and higher score than NOR
    assert ver_data["overall_std"] < nor_data["overall_std"]
    assert ver_data["overall_score"] > nor_data["overall_score"]
    assert len(ver_data["stints"]) == 2

    # Check Plotly Violin chart generation
    fig = build_stint_consistency_fig(res, ["VER", "NOR"], ["#3671C6", "#FF8000"])
    assert fig is not None
    assert len(fig.data) > 0


def test_build_consistency_analysis_empty_and_invalid():
    assert _build_consistency_analysis("key", None) is None
    assert _build_consistency_analysis("key", pd.DataFrame()) is None

    # DataFrame with missing LapTime
    df_no_time = pd.DataFrame({"Driver": ["VER"], "LapNumber": [1]})
    assert _build_consistency_analysis("key", df_no_time) is None
