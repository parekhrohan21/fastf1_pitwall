"""Regression tests for Issue #204 (umbrella) and sub-issues #205-#210."""
import pandas as pd
import plotly.graph_objects as go

import src.ui.components as components
from src.data.loader import get_telemetry_cached
from src.charts.plotly import build_weather_correlation_fig


def test_components_imports_ideal_gap_position_helpers():
    """#205/#206/#207: _fmt_sec, _build_gap_data, and _build_position_data are imported in src.ui.components."""
    # Missing any of these three symbols previously raised NameError mid-page and blocked all lower charts.
    assert callable(components._fmt_sec)
    assert components._fmt_sec(92.345) == "1:32.345"
    assert callable(components._build_gap_data)
    assert callable(components._build_position_data)


def test_traction_exit_and_session_compare_charts_use_unique_keys():
    """#208: Track Map and standalone Traction & Exit charts pass unique keys to st.plotly_chart."""
    # Verify that every reusable or tabbed Plotly chart passes an explicit key= so Streamlit >= 1.44
    # never raises StreamlitDuplicateElementId when the same figure appears in multiple tabs/sections.
    with open(components.__file__, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'key=f"traction_exit_chart_{sess_k}_{key_suffix}"' in src
    assert 'key=f"gap_to_leader_{sess_k}"' in src
    assert 'key=f"race_position_{sess_k}"' in src
    assert 'key=f"speed_map_{sess_k}_{key_suffix}"' in src
    assert 'key=f"corner_chart_{sess_k}_{key_suffix}"' in src
    assert 'key=f"teammate_matrix_{sess_k}"' in src
    assert 'key=f"pit_loss_chart_' in src


def test_get_telemetry_cached_isolates_lap_and_session(monkeypatch):
    """#209: get_telemetry_cached keys by session, driver, and lap number; app.py falls back to sess_key for tel2."""
    # Isolate st.session_state in both loader and components to confirm compound key separation
    # across different laps in the same race and the same lap number across different seasons.
    fake_state = {}
    monkeypatch.setattr(components.st, "session_state", fake_state)
    import src.data.loader as loader
    monkeypatch.setattr(loader.st, "session_state", fake_state)

    class _FakeLap(dict):
        def __init__(self, lap_no, marker):
            super().__init__(LapNumber=lap_no)
            self._marker = marker

        def get_car_data(self):
            return self

        def add_distance(self):
            return pd.DataFrame({"Speed": [self._marker], "Distance": [0.0]})

    t1 = get_telemetry_cached("VER", _FakeLap(1, 250.0), "2024_Bahrain_R")
    t2 = get_telemetry_cached("VER", _FakeLap(5, 290.0), "2024_Bahrain_R")
    t3 = get_telemetry_cached("VER", _FakeLap(1, 310.0), "2025_Bahrain_R")
    assert float(t1["Speed"].iloc[0]) == 250.0
    assert float(t2["Speed"].iloc[0]) == 290.0
    assert float(t3["Speed"].iloc[0]) == 310.0

    # In single-session Compare Mode sess_key2 is None, so app.py must fall back to sess_key.
    with open("/Users/rohanparekh/gitcommit/fastf1_pitwall/app.py", "r", encoding="utf-8") as f:
        app_src = f.read()
    assert "get_telemetry_cached(driver2, lap2, sess_key2 or sess_key)" in app_src


def test_weather_correlation_fig_renders_pace_without_track_temp():
    """#210: build_weather_correlation_fig plots driver pace traces even when TrackTemp weather data is empty."""
    # Simulates a 2018-2022 Jolpica-F1 historical session: laps_weather_df is empty,
    # but driver lap pace exists and must still be plotted on the primary y-axis.
    weather_data_no_temp = {
        "laps_weather_df": pd.DataFrame(),
        "driver_laps": {
            "VER": pd.DataFrame({"LapNumber": [1, 2, 3], "LapTime_s": [95.0, 93.2, 92.8]}),
        },
        "stats": {"track_temp_min": None, "track_temp_max": None, "crossover_laps": []},
    }
    fig = build_weather_correlation_fig(weather_data_no_temp, {"VER": "#3671C6"}, {"VER": "VER · Verstappen"})
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].name == "VER · Verstappen Pace"

    # Only when both weather sensors and driver lap pace are empty should the builder return None.
    empty_all = {"laps_weather_df": pd.DataFrame(), "driver_laps": {}, "stats": {}}
    assert build_weather_correlation_fig(empty_all) is None
