import pandas as pd
import numpy as np
import pytest
from src.data.loader import _build_multi_year_comparison
from src.charts.plotly import build_multi_year_comparison_fig


def test_build_multi_year_comparison_basic():
    # Build synthetic telemetry DataFrames for two eras
    dist = np.linspace(0, 5000, 100)
    tel1 = pd.DataFrame({
        "Distance": dist,
        "Speed": 200 + 100 * np.sin(dist / 500),
        "Throttle": [100 if i % 2 == 0 else 50 for i in range(100)],
        "Time": [pd.Timedelta(seconds=i * 0.9) for i in range(100)]
    })
    tel2 = pd.DataFrame({
        "Distance": dist,
        "Speed": 195 + 95 * np.sin(dist / 500),
        "Throttle": [100 if i % 2 == 0 else 40 for i in range(100)],
        "Time": [pd.Timedelta(seconds=i * 0.92) for i in range(100)]
    })

    res = _build_multi_year_comparison(
        tel1, tel2,
        label1="2020 HAM", label2="2024 NOR",
        lap1_time_s=90.0, lap2_time_s=92.0
    )

    assert res is not None
    assert "grid" in res
    assert "speed1" in res
    assert "speed2" in res
    assert "speed_delta" in res
    assert "stats" in res

    stats = res["stats"]
    assert stats["label1"] == "2020 HAM"
    assert stats["label2"] == "2024 NOR"
    assert stats["lap_delta_s"] == -2.0
    assert stats["top_speed1"] > 0
    assert stats["top_speed2"] > 0

    # Build Plotly figure
    fig = build_multi_year_comparison_fig(res, color1="#FF8700", color2="#00E5FF")
    assert fig is not None
