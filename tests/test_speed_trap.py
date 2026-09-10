import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.data.loader import (
    _calculate_speed_trap_metrics,
    get_power_unit_supplier,
    POWER_UNIT_SUPPLIERS,
)
from src.charts.plotly import (
    build_speed_trap_radar_fig,
    build_speed_trap_bar_fig,
)


@pytest.fixture
def mock_speed_trap_laps():
    """Create a mock laps DataFrame with SpeedST, SpeedI1, SpeedI2, SpeedFL, and DRS."""
    return pd.DataFrame({
        "Driver": ["NOR", "NOR", "NOR", "VER", "VER", "VER", "HAM", "HAM", "HAM", "GAS", "GAS", "GAS"],
        "Team": [
            "McLaren", "McLaren", "McLaren",
            "Red Bull Racing", "Red Bull Racing", "Red Bull Racing",
            "Ferrari", "Ferrari", "Ferrari",
            "Alpine", "Alpine", "Alpine"
        ],
        "LapNumber": [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3],
        "SpeedST": [328.5, 342.0, 330.0, 332.0, 345.5, 334.0, 329.0, 341.5, 331.0, 325.0, 338.0, 326.0],
        "SpeedI1": [290.0, 292.5, 291.0, 294.0, 296.5, 295.0, 289.0, 291.0, 290.5, 285.0, 287.0, 286.0],
        "SpeedI2": [305.0, 308.0, 306.5, 309.0, 312.0, 310.0, 304.0, 307.0, 305.5, 300.0, 303.0, 301.0],
        "SpeedFL": [280.0, 282.0, 281.0, 283.0, 285.5, 284.0, 279.0, 281.5, 280.0, 276.0, 278.0, 277.0],
        # Lap 2 is DRS-assisted (DRS = 12), Laps 1 and 3 are non-DRS (DRS = 0)
        "DRS": [0, 12, 0, 0, 12, 0, 0, 12, 0, 0, 12, 0],
    })


def test_power_unit_supplier_mapping():
    """Verify that constructors correctly map to their official Power Unit manufacturers."""
    assert get_power_unit_supplier("Ferrari") == "Ferrari"
    assert get_power_unit_supplier("Haas") == "Ferrari"
    assert get_power_unit_supplier("Stake F1 Team Kick Sauber") == "Ferrari"

    assert get_power_unit_supplier("Mercedes") == "Mercedes"
    assert get_power_unit_supplier("McLaren") == "Mercedes"
    assert get_power_unit_supplier("Aston Martin") == "Mercedes"
    assert get_power_unit_supplier("Williams Racing") == "Mercedes"

    assert get_power_unit_supplier("Red Bull Racing") == "Red Bull Powertrains"
    assert get_power_unit_supplier("RB") == "Red Bull Powertrains"
    assert get_power_unit_supplier("Scuderia AlphaTauri") == "Red Bull Powertrains"

    assert get_power_unit_supplier("Alpine") == "Renault"
    assert get_power_unit_supplier("Renault") == "Renault"

    # Unknown or empty constructor fallback
    assert get_power_unit_supplier("Audi Sport") == "Audi Sport"
    assert get_power_unit_supplier("") == "Unknown"
    assert get_power_unit_supplier(None) == "Unknown"


def test_calculate_speed_trap_metrics_basic(mock_speed_trap_laps):
    """Test standard extraction of sensor velocities and rankings."""
    res = _calculate_speed_trap_metrics("2024_Test_R", mock_speed_trap_laps)
    assert res["has_data"] is True

    drivers_df = res["drivers_df"]
    assert len(drivers_df) == 4

    # VER should be P1 with SpeedST = 345.5
    p1 = drivers_df.iloc[0]
    assert p1["Driver"] == "VER"
    assert p1["SpeedST"] == 345.5
    assert p1["SpeedI1"] == 296.5
    assert p1["SpeedI2"] == 312.0
    assert p1["SpeedFL"] == 285.5
    assert p1["OverallMax"] == 345.5
    assert p1["PowerUnit"] == "Red Bull Powertrains"

    # Verify leaders dictionary
    leaders = res["leaders"]
    assert leaders["SpeedST"]["Driver"] == "VER"
    assert leaders["SpeedST"]["Speed"] == 345.5
    assert leaders["SpeedI1"]["Driver"] == "VER"
    assert leaders["SpeedI2"]["Driver"] == "VER"
    assert leaders["SpeedFL"]["Driver"] == "VER"
    assert leaders["Overall"]["Driver"] == "VER"


def test_drs_delta_calculation(mock_speed_trap_laps):
    """Test DRS vs non-DRS speed trap separation and boost delta calculation."""
    res = _calculate_speed_trap_metrics("2024_Test_R", mock_speed_trap_laps)
    drivers_df = res["drivers_df"]

    # For NOR: DRS Lap (Lap 2) = 342.0, non-DRS max (Laps 1 & 3) = 330.0 -> Delta = +12.0 km/h
    nor_row = drivers_df[drivers_df["Driver"] == "NOR"].iloc[0]
    assert nor_row["SpeedST_DRS"] == 342.0
    assert nor_row["SpeedST_NoDRS"] == 330.0
    assert nor_row["DRS_Delta"] == pytest.approx(12.0)

    # For VER: DRS Lap (Lap 2) = 345.5, non-DRS max (Laps 1 & 3) = 334.0 -> Delta = +11.5 km/h
    ver_row = drivers_df[drivers_df["Driver"] == "VER"].iloc[0]
    assert ver_row["SpeedST_DRS"] == 345.5
    assert ver_row["SpeedST_NoDRS"] == 334.0
    assert ver_row["DRS_Delta"] == pytest.approx(11.5)

    # For GAS: DRS Lap = 338.0, non-DRS max = 326.0 -> Delta = +12.0 km/h
    gas_row = drivers_df[drivers_df["Driver"] == "GAS"].iloc[0]
    assert gas_row["DRS_Delta"] == pytest.approx(12.0)


def test_constructor_and_power_unit_aggregations(mock_speed_trap_laps):
    """Test aggregation of speed metrics by Constructor and Power Unit."""
    res = _calculate_speed_trap_metrics("2024_Test_R", mock_speed_trap_laps)

    cons_df = res["constructor_summary"]
    assert len(cons_df) == 4
    # Red Bull should lead constructor rankings on max ST
    assert cons_df.iloc[0]["Team"] == "Red Bull Racing"
    assert cons_df.iloc[0]["SpeedST_Max"] == 345.5

    pu_df = res["power_unit_summary"]
    assert len(pu_df) == 4
    pu_names = set(pu_df["PowerUnit"])
    assert "Ferrari" in pu_names
    assert "Mercedes" in pu_names
    assert "Red Bull Powertrains" in pu_names
    assert "Renault" in pu_names


def test_speed_trap_edge_cases():
    """Test resilience against missing columns, empty data, and NaNs."""
    # Empty DataFrame
    empty_res = _calculate_speed_trap_metrics("2024_Test_R", pd.DataFrame())
    assert empty_res["has_data"] is False
    assert empty_res["drivers_df"].empty

    # Missing all speed trap columns
    no_speed_df = pd.DataFrame({"Driver": ["VER", "NOR"], "LapNumber": [1, 2]})
    no_speed_res = _calculate_speed_trap_metrics("2024_Test_R", no_speed_df)
    assert no_speed_res["has_data"] is False

    # Partial speed trap columns with all NaNs
    nan_df = pd.DataFrame({
        "Driver": ["VER", "NOR"],
        "SpeedST": [np.nan, np.nan],
        "SpeedI1": [np.nan, np.nan],
    })
    nan_res = _calculate_speed_trap_metrics("2024_Test_R", nan_df)
    assert nan_res["has_data"] is False


def test_build_speed_trap_radar_fig(mock_speed_trap_laps):
    """Verify Plotly polar radar figure generation."""
    res = _calculate_speed_trap_metrics("2024_Test_R", mock_speed_trap_laps)

    fig = build_speed_trap_radar_fig(
        res,
        selected_drivers=["VER", "NOR"],
        driver_colours={"VER": "#3671C6", "NOR": "#FF8000"},
        include_grid_max=True
    )
    assert isinstance(fig, go.Figure)
    # Check traces: Grid Maximum + VER + NOR = 3 traces
    assert len(fig.data) == 3
    assert fig.data[0].name == "Grid Maximum"
    assert fig.data[1].name == "VER"
    assert fig.data[2].name == "NOR"

    # Verify fallback on invalid data
    assert build_speed_trap_radar_fig({}, ["VER"], {}) is None


def test_build_speed_trap_bar_fig(mock_speed_trap_laps):
    """Verify Plotly grouped bar chart generation for Constructor and Power Unit."""
    res = _calculate_speed_trap_metrics("2024_Test_R", mock_speed_trap_laps)

    # Constructor grouping
    fig_cons = build_speed_trap_bar_fig(res, group_by="Constructor", metric_type="Max")
    assert isinstance(fig_cons, go.Figure)
    assert len(fig_cons.data) == 4  # ST, I1, I2, FL traces

    # Power Unit grouping
    fig_pu = build_speed_trap_bar_fig(res, group_by="PowerUnit", metric_type="Mean")
    assert isinstance(fig_pu, go.Figure)
    assert len(fig_pu.data) == 4

    # Verify fallback on empty data
    assert build_speed_trap_bar_fig({}, group_by="Constructor") is None
