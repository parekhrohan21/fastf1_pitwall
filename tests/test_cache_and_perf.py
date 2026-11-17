"""Unit tests for Issue #203: Cache location unification, shared session cache, and lazy telemetry."""
import json
import os
import pandas as pd
import fastf1

import src.data.loader as loader
from src.data.loader import (
    CACHE_DIR,
    ROOT_CACHE_DIR,
    LEGACY_CACHE_DIR,
    FREE_API_CACHE_DIR,
    FreeF1Session,
    _find_cached_fastf1_dir,
    _free_api_get_json,
    load_session,
    ensure_session_telemetry,
    clear_session_cache,
    load_schedule,
)


def test_cache_dir_matches_root_cache_and_legacy_fallback():
    """CACHE_DIR defaults to repo-root ./cache (matching Docker/README) while preserving src/data/cache fallback."""
    if not os.environ.get("FASTF1_CACHE_DIR"):
        assert os.path.abspath(CACHE_DIR) == os.path.abspath(ROOT_CACHE_DIR)
    assert os.path.basename(LEGACY_CACHE_DIR) == "cache"
    assert FREE_API_CACHE_DIR == os.path.join(CACHE_DIR, "free_api_cache")


def test_find_cached_fastf1_dir_checks_root_and_legacy(tmp_path, monkeypatch):
    """_find_cached_fastf1_dir locates complete .ff1pkl caches in either CACHE_DIR or LEGACY_CACHE_DIR."""
    root_dir = tmp_path / "root_cache"
    legacy_dir = tmp_path / "legacy_cache"
    sess_dir = legacy_dir / "2024" / "2024-03-02_Bahrain_Grand_Prix" / "2024-03-02_Race"
    sess_dir.mkdir(parents=True)
    (sess_dir / "_extended_timing_data.ff1pkl").write_bytes(b"ok")

    monkeypatch.setattr(loader, "CACHE_DIR", str(root_dir))
    monkeypatch.setattr(loader, "ROOT_CACHE_DIR", str(root_dir))
    monkeypatch.setattr(loader, "LEGACY_CACHE_DIR", str(legacy_dir))

    found = _find_cached_fastf1_dir(2024, "Bahrain Grand Prix", "R")
    assert found == str(legacy_dir)


def test_free_api_cache_reads_legacy_fallback(tmp_path, monkeypatch):
    """_free_api_get_json falls back to LEGACY_FREE_API_CACHE_DIR when primary cache misses."""
    import hashlib
    url = "https://example.test/openf1/sessions?year=2025"
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    primary = tmp_path / "primary_free"
    legacy = tmp_path / "legacy_free"
    primary.mkdir()
    legacy.mkdir()
    (legacy / f"{key}.json").write_text(json.dumps([{"session_key": 123}]), encoding="utf-8")

    monkeypatch.setattr(loader, "FREE_API_CACHE_DIR", str(primary))
    monkeypatch.setattr(loader, "LEGACY_FREE_API_CACHE_DIR", str(legacy))

    data = _free_api_get_json(url, use_cache=True)
    assert data == [{"session_key": 123}]


def test_load_session_is_shared_cache_resource_and_clearable(monkeypatch):
    """load_session reuses the same parsed session object across calls via @st.cache_resource."""
    load_session.clear()
    calls = {"n": 0}

    class _FakeSess:
        laps = pd.DataFrame({"Driver": ["VER"], "LapNumber": [1]})

        def load(self, telemetry=True, laps=True, weather=True, messages=True):
            calls["n"] += 1

    monkeypatch.setattr(loader, "_find_cached_fastf1_dir", lambda y, g, s: loader.CACHE_DIR)
    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda *a, **kw: None)
    monkeypatch.setattr(fastf1, "get_session", lambda y, g, s: _FakeSess())

    s1 = load_session(2024, "Test GP", "R", load_telemetry=False)
    s2 = load_session(2024, "Test GP", "R", load_telemetry=False)
    assert s1 is s2
    assert calls["n"] == 1
    assert getattr(s1, "_pitwall_telemetry_loaded") is False

    clear_session_cache(2024, "Test GP")
    s3 = load_session(2024, "Test GP", "R", load_telemetry=False)
    assert s3 is not s1
    assert calls["n"] == 2
    load_session.clear()


def test_ensure_session_telemetry_upgrades_laps_only_session_once(monkeypatch):
    """ensure_session_telemetry loads telemetry exactly once on a laps-only FastF1 session."""
    load_calls = []

    class _FakeSess:
        _pitwall_telemetry_loaded = False
        _pitwall_cache_root = loader.CACHE_DIR

        def load(self, telemetry=True, laps=True, weather=True, messages=True):
            load_calls.append((telemetry, laps, weather, messages))

    monkeypatch.setattr(fastf1.Cache, "enable_cache", lambda *a, **kw: None)
    sess = _FakeSess()

    assert ensure_session_telemetry(sess) is True
    assert ensure_session_telemetry(sess) is True
    assert load_calls == [(True, True, True, True)]
    assert sess._pitwall_telemetry_loaded is True

    # FreeF1Session and None are already lazy / no-op
    assert ensure_session_telemetry(None) is True
    empty_df = pd.DataFrame()
    free_s = FreeF1Session(
        2025, "Test GP", "R", "Race", pd.Series({"EventName": "Test GP"}),
        empty_df, empty_df, empty_df, empty_df, empty_df,
    )
    assert ensure_session_telemetry(free_s) is True


def test_load_schedule_has_streamlit_cache():
    """load_schedule is cached with @st.cache_data so sidebar reruns do not re-fetch calendars."""
    assert hasattr(load_schedule, "clear")
