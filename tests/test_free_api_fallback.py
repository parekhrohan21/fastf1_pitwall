"""Unit tests for the free no-sign-in multi-source F1 API fallback (OpenF1 + MultiViewer + Jolpica-F1)."""
import pandas as pd
import numpy as np
import pytest

import src.data.loader as loader
from src.data.loader import (
    FreeF1Telemetry,
    FreeF1Lap,
    FreeF1Laps,
    FreeF1CircuitInfo,
    FreeF1Session,
    _load_openf1_session,
    _load_jolpica_session,
    _build_pit_stops,
    load_schedule,
    load_session,
)


def test_free_f1_telemetry_add_distance():
    """Verify FreeF1Telemetry.add_distance() integrates Speed over Time and returns a DataFrame."""
    df = pd.DataFrame({
        "Time": pd.to_timedelta([0.0, 1.0, 2.0, 3.0], unit="s"),
        "Speed": [180.0, 180.0, 180.0, 180.0],  # 180 km/h = 50 m/s
        "RPM": [10500, 10800, 11100, 11400],
        "nGear": [5, 5, 6, 6],
        "Throttle": [100.0, 100.0, 100.0, 100.0],
        "Brake": [False, False, False, False],
        "DRS": [0, 12, 12, 12],
    })
    tel = FreeF1Telemetry(df)
    res = tel.add_distance()
    assert isinstance(res, FreeF1Telemetry)
    assert "Distance" in res.columns
    # 50 m/s over 3 seconds -> ~150 m
    assert np.isclose(float(res["Distance"].iloc[-1]), 150.0, atol=1.0)


def test_free_f1_laps_filtering_and_pick_fastest():
    """Verify FreeF1Laps supports pick_drivers, pick_fastest, pick_quicklaps, and iterlaps."""
    laps_df = pd.DataFrame({
        "Time": pd.to_timedelta([90.0, 181.0, 91.5], unit="s"),
        "Driver": ["NOR", "NOR", "VER"],
        "DriverNumber": ["4", "4", "1"],
        "LapNumber": [1.0, 2.0, 1.0],
        "LapTime": pd.to_timedelta([90.0, 91.0, 91.5], unit="s"),
        "Stint": [1.0, 1.0, 1.0],
        "Compound": ["MEDIUM", "MEDIUM", "SOFT"],
        "TyreLife": [1.0, 2.0, 1.0],
        "FreshTyre": [True, True, True],
        "Team": ["McLaren", "McLaren", "Red Bull Racing"],
        "PitInTime": [pd.NaT, pd.NaT, pd.NaT],
        "PitOutTime": [pd.NaT, pd.NaT, pd.NaT],
        "IsAccurate": [True, True, True],
    })
    laps = FreeF1Laps(laps_df)
    nor_laps = laps.pick_drivers("NOR")
    assert len(nor_laps) == 2

    num_laps = laps.pick_drivers("4")
    assert len(num_laps) == 2

    fastest = laps.pick_fastest()
    assert isinstance(fastest, FreeF1Lap)
    assert fastest["Driver"] == "NOR"
    assert fastest["LapNumber"] == 1.0

    quick = laps.pick_quicklaps(1.07)
    assert len(quick) == 3

    iter_items = list(nor_laps.iterlaps())
    assert len(iter_items) == 2
    assert isinstance(iter_items[0][1], FreeF1Lap)


def test_free_f1_lap_synthesizes_6_channel_telemetry_when_offline():
    """Verify FreeF1Lap.get_car_data().add_distance() synthesizes complete 6-channel + X/Y telemetry offline."""
    lap_series = pd.Series({
        "Driver": "NOR",
        "DriverNumber": "4",
        "LapNumber": 12.0,
        "LapTime": pd.Timedelta(seconds=82.4),
        "Sector1Time": pd.Timedelta(seconds=24.1),
        "Sector2Time": pd.Timedelta(seconds=33.8),
        "Sector3Time": pd.Timedelta(seconds=24.5),
        "LapStartDate": pd.Timestamp("2025-05-04 14:15:00"),
    })
    lap = FreeF1Lap(lap_series)
    tel = lap.get_car_data().add_distance()
    for col in ("Speed", "Throttle", "Brake", "RPM", "nGear", "DRS", "Distance", "Time", "X", "Y"):
        assert col in tel.columns
    assert len(tel) >= 200
    assert float(tel["Distance"].max()) > 3000.0


def test_build_pit_stops_supports_two_row_in_out_laps():
    """Verify _build_pit_stops pairs PitInTime on lap i with PitOutTime on lap i+1."""
    laps_df = pd.DataFrame({
        "Driver": ["NOR", "NOR", "NOR"],
        "LapNumber": [19.0, 20.0, 21.0],
        "Compound": ["MEDIUM", "MEDIUM", "HARD"],
        "PitInTime": [pd.NaT, pd.Timedelta(seconds=1800.0), pd.NaT],
        "PitOutTime": [pd.NaT, pd.NaT, pd.Timedelta(seconds=1822.4)],
    })
    stops = _build_pit_stops("NOR", "2025_Test_R", laps_df)
    assert stops is not None
    assert len(stops) == 1
    assert stops[0]["lap"] == 20
    assert stops[0]["duration"] == 22.4
    assert stops[0]["old_cmp"] == "Medium"
    assert stops[0]["new_cmp"] == "Hard"


def test_load_openf1_session_with_mocked_endpoints(monkeypatch):
    """Verify _load_openf1_session builds a complete FreeF1Session from OpenF1 + MultiViewer + Jolpica payloads."""
    def fake_get_json(url: str, timeout: int = 20):
        if "/sessions?year=2025" in url:
            return [{
                "session_key": 9999,
                "session_name": "Race",
                "session_type": "Race",
                "date_start": "2025-03-16T04:00:00+00:00",
                "location": "Melbourne",
                "country_name": "Australia",
                "circuit_short_name": "Melbourne",
                "circuit_key": 10,
            }]
        if "session_key=9999" in url and "/laps" in url:
            return [
                {
                    "driver_number": 4,
                    "lap_number": 1,
                    "date_start": "2025-03-16T04:03:00+00:00",
                    "lap_duration": 84.5,
                    "duration_sector_1": 28.0,
                    "duration_sector_2": 22.5,
                    "duration_sector_3": 34.0,
                    "i1_speed": 288,
                    "i2_speed": 302,
                    "st_speed": 318,
                    "is_pit_out_lap": False,
                },
                {
                    "driver_number": 4,
                    "lap_number": 2,
                    "date_start": "2025-03-16T04:04:24.500+00:00",
                    "lap_duration": 82.1,
                    "duration_sector_1": 27.1,
                    "duration_sector_2": 22.0,
                    "duration_sector_3": 33.0,
                    "i1_speed": 292,
                    "i2_speed": 305,
                    "st_speed": 322,
                    "is_pit_out_lap": False,
                },
            ]
        if "session_key=9999" in url and "/drivers" in url:
            return [{
                "driver_number": 4,
                "name_acronym": "NOR",
                "broadcast_name": "L NORRIS",
                "full_name": "Lando NORRIS",
                "first_name": "Lando",
                "last_name": "Norris",
                "team_name": "McLaren",
                "team_colour": "FF8000",
                "headshot_url": "https://example.com/nor.png",
                "country_code": "GBR",
            }]
        if "session_key=9999" in url and "/stints" in url:
            return [{
                "driver_number": 4,
                "stint_number": 1,
                "lap_start": 1,
                "lap_end": 2,
                "compound": "MEDIUM",
                "tyre_age_at_start": 0,
            }]
        if "session_key=9999" in url and "/session_result" in url:
            return [{
                "driver_number": 4,
                "position": 1,
                "number_of_laps": 2,
                "points": 25.0,
                "duration": 166.6,
                "gap_to_leader": 0,
                "dnf": False,
                "dns": False,
                "dsq": False,
            }]
        if "api.multiviewer.app" in url:
            return {
                "rotation": 45,
                "corners": [
                    {"number": 1, "angle": 30.0, "length": 310.0, "trackPosition": {"x": 100.0, "y": 200.0}},
                    {"number": 2, "angle": -40.0, "length": 450.0, "trackPosition": {"x": 150.0, "y": 260.0}},
                ],
                "marshalLights": [],
                "marshalSectors": [],
            }
        return []

    monkeypatch.setattr(loader, "_free_api_get_json", fake_get_json)
    event_row = pd.Series({
        "RoundNumber": 1,
        "Country": "Australia",
        "Location": "Melbourne",
        "OfficialEventName": "Formula 1 Australian Grand Prix 2025",
        "EventDate": pd.Timestamp("2025-03-16"),
        "EventName": "Australian Grand Prix",
        "EventFormat": "conventional",
    })
    sess = _load_openf1_session(2025, "Australian Grand Prix", "R", event_row=event_row)
    assert isinstance(sess, FreeF1Session)
    assert not sess.laps.empty
    assert len(sess.laps) == 2
    assert sess.get_driver("NOR")["TeamName"] == "McLaren"
    assert sess.get_driver("4")["Abbreviation"] == "NOR"
    cinfo = sess.get_circuit_info()
    assert isinstance(cinfo, FreeF1CircuitInfo)
    assert len(cinfo.corners) == 2
    assert cinfo.rotation == 45.0


def test_load_jolpica_session_with_mocked_endpoints(monkeypatch):
    """Verify _load_jolpica_session builds a historical FreeF1Session from Jolpica-F1."""
    def fake_get_json(url: str, timeout: int = 20):
        if "/2020/1/results.json" in url:
            return {
                "MRData": {
                    "RaceTable": {
                        "Races": [{
                            "Results": [{
                                "number": "77",
                                "position": "1",
                                "positionText": "1",
                                "points": "25",
                                "grid": "1",
                                "laps": "2",
                                "status": "Finished",
                                "Time": {"millis": "140500", "time": "2:20.500"},
                                "Driver": {
                                    "driverId": "bottas",
                                    "permanentNumber": "77",
                                    "code": "BOT",
                                    "givenName": "Valtteri",
                                    "familyName": "Bottas",
                                },
                                "Constructor": {
                                    "constructorId": "mercedes",
                                    "name": "Mercedes",
                                },
                            }]
                        }]
                    }
                }
            }
        if "/2020/1/laps.json" in url:
            return {
                "MRData": {
                    "total": "2",
                    "RaceTable": {
                        "Races": [{
                            "Laps": [
                                {"number": "1", "Timings": [{"driverId": "bottas", "position": "1", "time": "1:11.000"}]},
                                {"number": "2", "Timings": [{"driverId": "bottas", "position": "1", "time": "1:09.500"}]},
                            ]
                        }]
                    },
                }
            }
        if "/2020/1/pitstops.json" in url:
            return {"MRData": {"RaceTable": {"Races": []}}}
        return {}

    monkeypatch.setattr(loader, "_free_api_get_json", fake_get_json)
    event_row = pd.Series({
        "RoundNumber": 1,
        "Country": "Austria",
        "Location": "Spielberg",
        "EventDate": pd.Timestamp("2020-07-05"),
        "EventName": "Austrian Grand Prix",
    })
    sess = _load_jolpica_session(2020, "Austrian Grand Prix", "R", event_row=event_row)
    assert isinstance(sess, FreeF1Session)
    assert len(sess.laps) == 2
    assert sess.get_driver("BOT")["FullName"] == "Valtteri Bottas"
    best_lap = sess.laps.pick_fastest()
    assert np.isclose(best_lap["LapTime"].total_seconds(), 69.5)

