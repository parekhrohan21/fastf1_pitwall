import io
import json
import pytest
import pandas as pd
import numpy as np
from src.data.loader import (
    _build_export_telemetry_df,
    _build_export_csv,
    _build_export_parquet,
    _build_export_json,
)


@pytest.fixture
def sample_telemetry():
    """Create a realistic sample telemetry DataFrame."""
    n_points = 50
    distance = np.linspace(0, 5000, n_points)
    time_deltas = [pd.Timedelta(seconds=float(i * 1.5)) for i in range(n_points)]
    session_time_deltas = [pd.Timedelta(seconds=float(3600 + i * 1.5)) for i in range(n_points)]

    return pd.DataFrame({
        "Distance": distance,
        "Speed": np.linspace(100, 320, n_points),
        "Throttle": np.linspace(50, 100, n_points),
        "Brake": np.zeros(n_points),
        "RPM": np.linspace(10000, 12500, n_points),
        "nGear": np.full(n_points, 7),
        "DRS": np.full(n_points, 12),
        "X": np.linspace(1000, 2000, n_points),
        "Y": np.linspace(500, 1500, n_points),
        "Z": np.zeros(n_points),
        "Time": time_deltas,
        "SessionTime": session_time_deltas,
    })


@pytest.fixture
def sample_lap_series():
    """Create a mock FastF1 lap series with full metadata."""
    return pd.Series({
        "LapNumber": 18,
        "LapTime": pd.Timedelta(seconds=78.432),
        "Compound": "MEDIUM",
        "Sector1Time": pd.Timedelta(seconds=27.123),
        "Sector2Time": pd.Timedelta(seconds=28.456),
        "Sector3Time": pd.Timedelta(seconds=22.853),
    })


def test_build_export_telemetry_df_structure(sample_telemetry, sample_lap_series):
    """Test that the unified telemetry export DataFrame contains metadata and renamed columns."""
    df = _build_export_telemetry_df("4 · NOR", sample_telemetry, sample_lap_series)

    assert df is not None
    assert isinstance(df, pd.DataFrame)
    assert len(df) == len(sample_telemetry)

    # Verify column presence
    expected_cols = [
        "Driver", "LapNumber", "LapTime", "Compound",
        "Sector3Time_s", "Sector2Time_s", "Sector1Time_s",
        "Distance", "Speed", "Throttle", "Brake", "RPM", "Gear", "DRS",
        "X", "Y", "Z", "Time", "SessionTime"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Column {col} should be present in export DataFrame"

    # Verify column renaming nGear -> Gear
    assert "nGear" not in df.columns
    assert "Gear" in df.columns

    # Verify metadata values
    assert df["Driver"].iloc[0] == "4 · NOR"
    assert df["LapNumber"].iloc[0] == 18
    assert df["Compound"].iloc[0] == "Medium"
    assert df["Sector1Time_s"].iloc[0] == 27.123
    assert df["Sector2Time_s"].iloc[0] == 28.456
    assert df["Sector3Time_s"].iloc[0] == 22.853


def test_build_export_telemetry_df_none_or_empty():
    """Test graceful handling when telemetry is None or empty."""
    assert _build_export_telemetry_df("4", None, None) is None
    assert _build_export_telemetry_df("4", pd.DataFrame(), None) is None


def test_build_export_telemetry_df_missing_lap_obj(sample_telemetry):
    """Test telemetry export when lap metadata object is None."""
    df = _build_export_telemetry_df("VER", sample_telemetry, None)

    assert df is not None
    assert df["Driver"].iloc[0] == "VER"
    assert df["Compound"].iloc[0] == ""
    assert df["Sector1Time_s"].iloc[0] == ""
    assert "Gear" in df.columns


def test_build_export_csv_output(sample_telemetry, sample_lap_series):
    """Test CSV exporter returns valid encoded CSV bytes with correct headers."""
    csv_bytes = _build_export_csv("NOR", sample_telemetry, sample_lap_series)

    assert isinstance(csv_bytes, bytes)
    assert len(csv_bytes) > 0

    csv_text = csv_bytes.decode("utf-8")
    lines = csv_text.strip().split("\n")
    header = lines[0]

    assert "Driver" in header
    assert "Gear" in header
    assert "Sector1Time_s" in header
    assert len(lines) == len(sample_telemetry) + 1  # header + data rows


def test_build_export_csv_empty():
    """Test CSV export on empty inputs returns empty bytes."""
    assert _build_export_csv("NOR", None, None) == b""
    assert _build_export_csv("NOR", pd.DataFrame(), None) == b""


def test_build_export_parquet_output(sample_telemetry, sample_lap_series):
    """Test Parquet exporter produces valid Apache Parquet binary bytes readable by pandas/pyarrow."""
    parquet_bytes = _build_export_parquet("44 · HAM", sample_telemetry, sample_lap_series)

    assert isinstance(parquet_bytes, bytes)
    assert len(parquet_bytes) > 0
    # Check Parquet magic bytes at start or end
    assert parquet_bytes.startswith(b"PAR1") or parquet_bytes.endswith(b"PAR1")

    # Roundtrip read with pandas pyarrow engine
    buf = io.BytesIO(parquet_bytes)
    df_read = pd.read_parquet(buf)

    assert len(df_read) == len(sample_telemetry)
    assert "Gear" in df_read.columns
    assert "Driver" in df_read.columns
    assert df_read["Driver"].iloc[0] == "44 · HAM"
    assert df_read["LapNumber"].iloc[0] == 18
    assert df_read["Compound"].iloc[0] == "Medium"


def test_build_export_parquet_empty():
    """Test Parquet export on empty inputs returns empty bytes."""
    assert _build_export_parquet("HAM", None, None) == b""
    assert _build_export_parquet("HAM", pd.DataFrame(), None) == b""


def test_build_export_json_output(sample_telemetry, sample_lap_series):
    """Test JSON exporter produces valid structured JSON parseable into record dicts."""
    json_bytes = _build_export_json("16 · LEC", sample_telemetry, sample_lap_series)

    assert isinstance(json_bytes, bytes)
    assert len(json_bytes) > 0

    json_text = json_bytes.decode("utf-8")
    records = json.loads(json_text)

    assert isinstance(records, list)
    assert len(records) == len(sample_telemetry)

    first_record = records[0]
    assert first_record["Driver"] == "16 · LEC"
    assert first_record["LapNumber"] == 18
    assert first_record["Gear"] == 7
    assert first_record["Compound"] == "Medium"
    assert first_record["Sector1Time_s"] == 27.123
    assert "Time" in first_record
    assert isinstance(first_record["Time"], (int, float))


def test_build_export_json_empty():
    """Test JSON export on empty inputs returns empty bytes."""
    assert _build_export_json("LEC", None, None) == b""
    assert _build_export_json("LEC", pd.DataFrame(), None) == b""
