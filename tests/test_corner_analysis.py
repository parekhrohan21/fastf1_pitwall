import pandas as pd
import numpy as np
import pytest
from src.charts.plotly import build_corner_fig


def test_build_corner_fig_steering_and_drs():
    # Build synthetic telemetry with Steering and DRS
    dist = np.linspace(1000, 1300, 50)
    win1 = pd.DataFrame({
        "Distance": dist,
        "Speed": 250 - 100 * np.exp(-((dist - 1150) / 30) ** 2), # V-shaped speed curve
        "X": dist,
        "Y": 50 * np.sin(dist / 50),
        "Brake": [100 if 1100 <= d <= 1140 else 0 for d in dist],
        "Steering": [-45.5 * np.sin((d - 1100) / 50) for d in dist],
        "DRS": [12 if d >= 1200 else 0 for d in dist]
    })

    win2 = pd.DataFrame({
        "Distance": dist,
        "Speed": 245 - 95 * np.exp(-((dist - 1150) / 30) ** 2),
        "X": dist + 2,
        "Y": 50 * np.sin(dist / 50) + 1,
        "Brake": [100 if 1095 <= d <= 1140 else 0 for d in dist],
        "Steering": [-42.0 * np.sin((d - 1100) / 50) for d in dist],
        "DRS": [0 for _ in dist]
    })

    fig, stats1, stats2 = build_corner_fig(
        win1, win2,
        driver="VER", other_driver="NOR",
        colour="#FF8700", other_colour="#00E5FF",
        apex_dist=1150
    )

    assert fig is not None
    assert stats1 is not None
    assert stats2 is not None

    assert stats1["apex_speed"] < 200
    assert stats1["max_steering"] is not None
    assert stats1["max_steering"] > 0
    assert stats1["drs_active"] is True

    assert stats2["drs_active"] is False
