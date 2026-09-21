import os
import io
import streamlit as st
import fastf1
import pandas as pd
import numpy as np
import urllib3
import logging
import threading
from datetime import datetime
from curl_cffi import requests as curl_requests
from src.ui.styles import TEAM_COLOURS, COMPOUND_COLOURS, TRACK_STATUS_MAP

# ── FastF1 cache ──────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)



# ── Cloudflare / CloudFront bypass via curl_cffi ─────────────────────────────
# Streamlit Community Cloud runs on AWS datacenter IPs.  F1's live-timing CDN
# (CloudFront) and the FastF1 mirror (Cloudflare) both return HTTP 403 for
# requests originating from known datacenter ranges.
#
# Fix: intercept every outbound HTTPS request at requests.adapters.HTTPAdapter.send
# — the lowest transport layer called by *all* requests.Session subclasses
# (including FastF1's _SessionWithRateLimiting and requests_cache.CachedSession).
# We replace the TLS handshake with curl_cffi which presents a genuine Chrome 124
# JA3/JA4 fingerprint, bypassing bot-detection rules.
#
# Key design choices:
#   • No IS_CLOUD guard — environment-variable detection was silently False on
#     newer Streamlit Cloud builds, so curl_cffi was never activated.  The patch
#     is now unconditional for all F1 domains (negligible overhead locally).
#   • No urllib3.HTTPResponse raw wrapping — constructing a fake urllib3 response
#     from BytesIO caused iter_lines() failures in FastF1's .jsonStream path.
#     Instead we pre-load _content; requests.Response.iter_lines() checks
#     _content first and works correctly without a live socket.
_PATCH_STATUS = {
    "imported": False,
    "import_err": None,
    "patched": False,
    "request_errs": [],
}

# No public proxy rotation list. We support a dedicated proxy config F1_PROXY via st.secrets or os.environ.
def test_curl_cffi_request():
    """Diagnostic: direct curl_cffi GET to the F1 livetiming — call from sidebar."""
    try:
        if not _PATCH_STATUS["imported"]:
            return f"curl_cffi not imported.\nError: {_PATCH_STATUS['import_err']}"
        from curl_cffi import requests as _cr
        
        # Check if proxy is configured
        proxy_url = os.environ.get("F1_PROXY")
        if not proxy_url and hasattr(st, "secrets"):
            try:
                proxy_url = st.secrets.get("F1_PROXY")
            except Exception:
                pass
                
        # Try proxy first if configured
        if proxy_url:
            try:
                proxies = {"http": proxy_url, "https": proxy_url}
                resp = _cr.get(
                    "https://livetiming.formula1.com/static/StreamingStatus.json",
                    impersonate="chrome124",
                    proxies=proxies,
                    timeout=5,
                )
                return (
                    f"Proxy request worked using configured F1_PROXY!\n"
                    f"Status: {resp.status_code}\n"
                    f"Body prefix: {resp.text[:200]}"
                )
            except Exception as exc:
                proxy_err = str(exc)
            
            # Fallback to direct request
            try:
                resp = _cr.get(
                    "https://livetiming.formula1.com/static/StreamingStatus.json",
                    impersonate="chrome124",
                    timeout=5,
                )
                return (
                    f"Proxy request failed: {proxy_err}\n"
                    f"Fallback direct request worked!\n"
                    f"Status: {resp.status_code}\n"
                    f"Body prefix: {resp.text[:200]}"
                )
            except Exception as exc:
                return (
                    f"Proxy request failed: {proxy_err}\n"
                    f"Fallback direct request failed: {exc}"
                )
        else:
            # Direct request only
            try:
                resp = _cr.get(
                    "https://livetiming.formula1.com/static/StreamingStatus.json",
                    impersonate="chrome124",
                    timeout=5,
                )
                return (
                    f"Direct request worked (no proxy configured)!\n"
                    f"Status: {resp.status_code}\n"
                    f"Body prefix: {resp.text[:200]}"
                )
            except Exception as exc:
                return f"Direct request failed: {exc}"
    except Exception as exc:
        import traceback
        return f"Error: {exc}\n{traceback.format_exc()}"

try:
    import requests
    import requests.adapters
    from curl_cffi import requests as curl_requests
    from requests.structures import CaseInsensitiveDict

    _PATCH_STATUS["imported"] = True
    _F1_DOMAINS = (
        "formula1.com",
        "fastf1.dev",
        "ergast.com",
        "jolpica.net",
        "jolpi.ca",
    )
    _original_adapter_send = requests.adapters.HTTPAdapter.send

    def _patched_adapter_send(
        self, request, stream=False, timeout=None,
        verify=True, cert=None, proxies=None,
    ):
        url = getattr(request, "url", "") or ""
        if any(domain in url for domain in _F1_DOMAINS):
            hdrs = {k: v for k, v in request.headers.items()
                    if k not in ("TE", "Connection", "Transfer-Encoding",
                                 "Keep-Alive", "Proxy-Authorization", "Upgrade",
                                 "User-Agent")}
            
            class MockRaw:
                def __init__(self, url, headers=None, reason=None, status=None):
                    self._request_url = url
                    self.decode_content = True
                    self.headers = headers
                    self.reason = reason
                    self.status = status
                    self.version = 11
                    self.closed = True

            # Get proxy url from env or secrets
            proxy_url = os.environ.get("F1_PROXY")
            if not proxy_url and hasattr(st, "secrets"):
                try:
                    proxy_url = st.secrets.get("F1_PROXY")
                except Exception:
                    pass

            def do_curl_request(p_url):
                curl_proxies = None
                if p_url:
                    curl_proxies = {"http": p_url, "https": p_url}
                
                curl_resp = curl_requests.request(
                    method=request.method,
                    url=url,
                    headers=hdrs,
                    data=request.body,
                    timeout=timeout or 30,
                    impersonate="chrome124",
                    allow_redirects=True,
                    proxies=curl_proxies,
                )
                
                resp = requests.Response()
                resp.status_code = curl_resp.status_code
                resp.url = str(curl_resp.url)
                resp._content = curl_resp.content
                resp.encoding = curl_resp.encoding or "utf-8"
                resp.headers = CaseInsensitiveDict(dict(curl_resp.headers))
                resp.request = request
                resp.history = []
                resp.reason = "OK" if curl_resp.status_code < 400 else "Error"
                
                # Mock raw response for requests_cache compatibility
                resp.raw = MockRaw(
                    url=str(curl_resp.url),
                    headers=CaseInsensitiveDict(dict(curl_resp.headers)),
                    reason=resp.reason,
                    status=curl_resp.status_code
                )
                return resp

            errors = []
            
            # If proxy is configured, try proxy first, then direct as fallback
            if proxy_url:
                try:
                    resp = do_curl_request(proxy_url)
                    if resp.status_code < 400:
                        return resp
                    errors.append(f"Proxy request status: {resp.status_code}")
                except Exception as e:
                    errors.append(f"Proxy request exception: {e}")
                
                try:
                    resp = do_curl_request(None)
                    if resp.status_code < 400:
                        return resp
                    errors.append(f"Fallback direct request status: {resp.status_code}")
                except Exception as e:
                    errors.append(f"Fallback direct request exception: {e}")
            else:
                # No proxy, try direct only
                try:
                    resp = do_curl_request(None)
                    if resp.status_code < 400:
                        return resp
                    errors.append(f"Direct request status: {resp.status_code}")
                except Exception as e:
                    errors.append(f"Direct request exception: {e}")
                
            # Log all errors to _PATCH_STATUS
            import traceback
            _PATCH_STATUS["request_errs"].append({
                "url": url,
                "err": " | ".join(errors),
                "traceback": traceback.format_exc(),
            })

        return _original_adapter_send(
            self, request,
            stream=stream, timeout=timeout,
            verify=verify, cert=cert, proxies=proxies,
        )

    requests.adapters.HTTPAdapter.send = _patched_adapter_send
    _PATCH_STATUS["patched"] = True
except Exception as exc:
    import traceback
    _PATCH_STATUS["import_err"] = f"{exc}\n{traceback.format_exc()}"



def hex_to_rgb(hex_col: str) -> str:
    hex_col = hex_col.lstrip("#")
    if len(hex_col) == 3:
        hex_col = "".join([c*2 for c in hex_col])
    try:
        return ",".join(str(int(hex_col[i:i+2], 16)) for i in (0, 2, 4))
    except Exception:
        return "255, 135, 0"


def _team_logo(team: str, year: int = 2024) -> str:
    t = team.lower()
    mapping = {
        "red bull": "red-bull-racing-logo.png",
        "ferrari": "ferrari-logo.png",
        "mclaren": "mclaren-logo.png",
        "mercedes": "mercedes-logo.png",
        "aston martin": "aston-martin-logo.png",
        "haas": "haas-f1-team-logo.png",
        "williams": "williams-logo.png",
        "alpine": "alpine-logo.png",
        "rb": "rb-logo.png",
        "vcarb": "rb-logo.png",
        "sauber": "kick-sauber-logo.png",
        "alfa romeo": "alfaromeo-logo.png",
        "racing point": "racing-point-logo.png",
        "renault": "renault-logo.png",
        "alphatauri": "alphatauri-logo.png"
    }
    for k, filename in mapping.items():
        if k in t:
            return f"https://media.formula1.com/content/dam/fom-website/teams/{year}/{filename}"
    return ""


def _team_colour(team: str) -> str:
    for k, v in TEAM_COLOURS.items():
        if k.lower() in team.lower():
            return v
    return "#FF8700"


def load_schedule(year: int) -> pd.DataFrame:
    return fastf1.get_event_schedule(year, include_testing=False)


def load_session(year: int, gp: str, session_type: str = "R"):
    sess = fastf1.get_session(year, gp, session_type)
    
    def has_laps(s) -> bool:
        try:
            return hasattr(s, "laps") and s.laps is not None and not s.laps.empty
        except Exception:
            return False

    # Try 1: Load everything (Standard)
    try:
        sess.load(telemetry=True, laps=True, weather=True, messages=True)
        if has_laps(sess):
            return sess
    except Exception:
        pass
        
    # Try 2: Load without messages (Messages often fail/absent)
    try:
        sess.load(telemetry=True, laps=True, weather=True, messages=False)
        if has_laps(sess):
            return sess
    except Exception:
        pass
        
    # Try 3: Load without telemetry
    try:
        sess.load(telemetry=False, laps=True, weather=True, messages=False)
        if has_laps(sess):
            return sess
    except Exception:
        pass

    # Try 4: Minimal load (Only laps)
    try:
        sess.load(telemetry=False, laps=True, weather=False, messages=False)
        if has_laps(sess):
            return sess
    except Exception:
        pass

    # Try 5: Final fallback check/raise
    raise ValueError("No lap timing data is available for this session on F1 servers.")


# ── Live Timing SignalR Recorder Management ───────────────────────────────────
_LIVE_RECORDERS = {}
_LIVE_THREADS = {}


def start_live_recorder(filename: str = "live_timing.txt", timeout: int = 60) -> dict:
    """Start a background SignalRClient recording thread saving live WebSocket timing stream data."""
    try:
        from fastf1.livetiming.client import SignalRClient
        
        filepath = os.path.join(CACHE_DIR, filename) if not os.path.isabs(filename) else filename
        
        if filepath in _LIVE_THREADS and _LIVE_THREADS[filepath].is_alive():
            return {"success": True, "message": "Live SignalR recorder is already running.", "filepath": filepath}
            
        client = SignalRClient(filepath, timeout=timeout)
        _LIVE_RECORDERS[filepath] = client
        
        def _run_recorder():
            try:
                client.start()
            except Exception as exc:
                logging.error(f"Live SignalR recorder error: {exc}")
                
        thread = threading.Thread(target=_run_recorder, daemon=True)
        _LIVE_THREADS[filepath] = thread
        thread.start()
        
        return {"success": True, "message": "Live SignalR recorder started successfully.", "filepath": filepath}
    except Exception as e:
        return {"success": False, "message": f"Failed to start live recorder: {e}", "filepath": filename}


def stop_live_recorder(filename: str = "live_timing.txt") -> dict:
    """Stop live recorder instance if running."""
    filepath = os.path.join(CACHE_DIR, filename) if not os.path.isabs(filename) else filename
    if filepath in _LIVE_THREADS:
        _LIVE_RECORDERS.pop(filepath, None)
        _LIVE_THREADS.pop(filepath, None)
        return {"success": True, "message": "Live recorder stopped successfully."}
    return {"success": False, "message": "No active live recorder found for specified file."}


def get_live_recorder_status(filename: str = "live_timing.txt") -> dict:
    """Return dictionary containing active state, file existence, size, line count, and timestamp."""
    filepath = os.path.join(CACHE_DIR, filename) if not os.path.isabs(filename) else filename
    is_active = filepath in _LIVE_THREADS and _LIVE_THREADS[filepath].is_alive()
    
    if not os.path.exists(filepath):
        return {
            "active": is_active,
            "exists": False,
            "filepath": filepath,
            "size_bytes": 0,
            "line_count": 0,
            "last_modified": "N/A"
        }
        
    try:
        size = os.path.getsize(filepath)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S")
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = sum(1 for _ in f)
        return {
            "active": is_active,
            "exists": True,
            "filepath": filepath,
            "size_bytes": size,
            "line_count": lines,
            "last_modified": mtime
        }
    except Exception:
        return {
            "active": is_active,
            "exists": True,
            "filepath": filepath,
            "size_bytes": 0,
            "line_count": 0,
            "last_modified": "Error reading file"
        }


def load_live_session(year: int, gp: str, session_type: str, live_filename: str = "live_timing.txt"):
    """Load a session using live stream data parsed via LiveTimingData(live_filename)."""
    try:
        from fastf1.livetiming.data import LiveTimingData
        
        filepath = os.path.join(CACHE_DIR, live_filename) if not os.path.isabs(live_filename) else live_filename
        
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return None, f"Live timing data file '{live_filename}' is empty or does not exist."
            
        livedata = LiveTimingData(filepath)
        sess = fastf1.get_session(year, gp, session_type)
        sess.load(livedata=livedata)
        return sess, None
    except Exception as e:
        return None, f"Failed to load live session data: {e}"


def clear_session_cache(year: int, gp: str):
    """Clear local FastF1 cache directories and Streamlit cache resource for a GP."""
    try:
        import shutil
        import glob
        gp_clean = str(gp).replace(" ", "_")
        gp_dir_pattern = os.path.join(CACHE_DIR, str(year), f"*{gp_clean}*")
        for gp_dir in glob.glob(gp_dir_pattern):
            shutil.rmtree(gp_dir, ignore_errors=True)
    except Exception:
        pass
    try:
        load_session.clear()
    except Exception:
        pass


def format_laptime(td) -> str:
    try:
        if pd.isna(td):
            return "N/A"
        total = td.total_seconds()
        return f"{int(total // 60)}:{total % 60:06.3f}"
    except Exception:
        return "N/A"


def driver_colour(sess, driver: str) -> str:
    try:
        return _team_colour(sess.get_driver(driver).get("TeamName", ""))
    except Exception:
        return "#FF8700"


def _build_driver_labels(session) -> dict:
    """
    Build a mapping of driver number → display label, e.g. '4' → 'NOR · Norris'.
    Uses FastF1 driver info for the actual season; falls back to the raw number.
    """
    labels = {}
    try:
        for drv in session.laps["Driver"].dropna().unique():
            try:
                info    = session.get_driver(str(drv))
                abbr    = info.get("Abbreviation", str(drv))
                last    = info.get("LastName", "").strip()
                labels[str(drv)] = f"{abbr} · {last}" if last else abbr
            except Exception:
                labels[str(drv)] = str(drv)
    except Exception:
        pass
    return labels


def get_telemetry_cached(driver: str, lap, sess_key: str):
    if lap is None:
        return None
    try:
        lap_num = int(lap["LapNumber"])
    except Exception:
        lap_num = -1
    key = f"tel_{sess_key}_{driver}_{lap_num}"
    if key not in st.session_state:
        try:
            st.session_state[key] = lap.get_car_data().add_distance()
        except Exception as exc:
            st.warning(f"⚠️ No telemetry for {driver}: {exc}")
            st.session_state[key] = None
    return st.session_state[key]


def _format_classification_time(row, is_first=False) -> str:
    """Format final classification time / status for display."""
    try:
        t = row.get("Time")
        status = row.get("Status")
        if pd.isna(t) or status not in ("Finished",):
            return str(status) if pd.notna(status) else "—"
        
        total_seconds = t.total_seconds()
        if is_first:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:06.3f}"
            else:
                return f"{minutes}:{seconds:06.3f}"
        else:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = total_seconds % 60
            if hours > 0:
                return f"+{hours}:{minutes:02d}:{seconds:06.3f}"
            elif minutes > 0:
                return f"+{minutes}:{seconds:06.3f}s"
            else:
                return f"+{seconds:.3f}s"
    except Exception:
        return "—"


def _map_driver_id_to_number(session, driver_id: str, all_drivers: list) -> str:
    """Map a driver ID (number or abbreviation) to the key used in all_drivers."""
    if not driver_id or not all_drivers:
        return ""
    
    driver_id = str(driver_id).strip().upper()
    if driver_id in all_drivers:
        return driver_id
        
    for key in all_drivers:
        try:
            info = session.get_driver(key)
            abbr = str(info.get("Abbreviation", "")).strip().upper()
            dnum = str(info.get("DriverNumber", "")).strip().upper()
            lname = str(info.get("LastName", "")).strip().upper()
            
            if driver_id in (abbr, dnum) or (lname and driver_id == lname):
                return key
        except Exception:
            pass
            
    return all_drivers[0] if all_drivers else ""


def _get_session_winner(session, all_drivers: list) -> str:
    """Return the driver number/abbreviation string of the session winner / fastest driver."""
    try:
        results = session.results
        if results is not None and not results.empty:
            if "Position" in results.columns and results["Position"].notna().any():
                p1_row = results[results["Position"] == 1]
                if not p1_row.empty:
                    for col in ["Abbreviation", "DriverNumber", "Driver"]:
                        if col in p1_row.columns:
                            val = str(p1_row.iloc[0][col]).strip()
                            if val in all_drivers:
                                return val
                    if "Abbreviation" in p1_row.columns:
                        abbr = str(p1_row.iloc[0]["Abbreviation"]).strip()
                        mapped = _map_driver_id_to_number(session, abbr, all_drivers)
                        if mapped in all_drivers:
                            return mapped
                    if "DriverNumber" in p1_row.columns:
                        dnum = str(p1_row.iloc[0]["DriverNumber"]).strip()
                        mapped = _map_driver_id_to_number(session, dnum, all_drivers)
                        if mapped in all_drivers:
                            return mapped
                            
        if hasattr(session, "laps") and session.laps is not None and not session.laps.empty:
            fastest_lap = session.laps.pick_fastest()
            if fastest_lap is not None and not pd.isna(fastest_lap.get("Driver")):
                val = str(fastest_lap["Driver"]).strip()
                if val in all_drivers:
                    return val
                mapped = _map_driver_id_to_number(session, val, all_drivers)
                if mapped in all_drivers:
                    return mapped
    except Exception:
        pass
    return "NOR" if "NOR" in all_drivers else (all_drivers[0] if all_drivers else "")


def _get_default_gp_index(schedule, event_names: list) -> int:
    """Determine the default Grand Prix index based on the most recent completed event (Issue #53)."""
    try:
        now = pd.Timestamp.now()
        if not schedule.empty and "EventDate" in schedule.columns:
            s_dates = pd.to_datetime(schedule["EventDate"])
            if s_dates.dt.tz is not None:
                s_dates = s_dates.dt.tz_localize(None)
            if now.tz is not None:
                now = now.tz_localize(None)
            past_events = schedule[s_dates <= now]
            if not past_events.empty:
                last_completed_gp = past_events.iloc[-1]["EventName"]
                if last_completed_gp in event_names:
                    return event_names.index(last_completed_gp)
    except Exception:
        pass
        
    if not schedule.empty:
        first_race = schedule.iloc[0]["EventName"]
        if first_race in event_names:
            return event_names.index(first_race)
            
    return 0


def get_constructor_colour(name: str) -> str:
    # Try exact match first
    if name in TEAM_COLOURS:
        return TEAM_COLOURS[name]
    # Try case-insensitive matching/substring matching
    for k, v in TEAM_COLOURS.items():
        if k.lower() in name.lower() or name.lower() in k.lower():
            return v
    # Try stripping common suffixes like "F1 Team", "Racing", etc.
    clean_name = name.replace("F1 Team", "").replace("Racing", "").strip()
    for k, v in TEAM_COLOURS.items():
        clean_k = k.replace("F1 Team", "").replace("Racing", "").strip()
        if clean_k.lower() == clean_name.lower():
            return v
    return "#B6BABD"  # Default gray


def is_same_team(team_a: str, team_b: str) -> bool:
    if not team_a or not team_b:
        return False
    clean_a = team_a.replace("F1 Team", "").replace("Racing", "").strip().lower()
    clean_b = team_b.replace("F1 Team", "").replace("Racing", "").strip().lower()
    return clean_a in clean_b or clean_b in clean_a


def _build_constructor_standings(year: int, round_no: int = None):
    """Fetch Constructor Standings from the Jolpi Ergast API."""
    import requests
    try:
        if round_no is not None and round_no > 0:
            url = f"https://api.jolpi.ca/ergast/f1/{year}/{round_no}/constructorStandings.json"
        else:
            url = f"https://api.jolpi.ca/ergast/f1/{year}/constructorStandings.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            if lists:
                return lists[0].get("ConstructorStandings", [])
    except Exception:
        pass
    return None


def get_driver_standings_points(standings_list, drv_abbr: str, drv_num: str, drv_lastname: str) -> str:
    if not standings_list:
        return "—"
    
    # Try match by code, permanentNumber, or last name (case-insensitive)
    for item in standings_list:
        points = item.get("points", "0")
        driver_info = item.get("Driver", {})
        code = driver_info.get("code", "").upper()
        perm_num = driver_info.get("permanentNumber", "")
        family_name = driver_info.get("familyName", "")
        
        # Check abbreviation match
        if drv_abbr and code and drv_abbr.upper() == code:
            return points
        # Check number match
        if drv_num and perm_num and str(drv_num) == str(perm_num):
            return points
        # Check family name match
        if drv_lastname and family_name and drv_lastname.lower() in family_name.lower():
            return points
            
    return "—"


def _build_driver_standings(year: int, round_no: int = None):
    """Fetch Driver Standings from the Jolpi Ergast API."""
    import requests
    try:
        if round_no is not None and round_no > 0:
            url = f"https://api.jolpi.ca/ergast/f1/{year}/{round_no}/driverStandings.json"
        else:
            url = f"https://api.jolpi.ca/ergast/f1/{year}/driverStandings.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            if lists:
                return lists[0].get("DriverStandings", [])
    except Exception:
        pass
    return None


def _build_final_classification(sess_k: str, _results_df: pd.DataFrame):
    """Process and return classification results from FastF1."""
    try:
        df = _results_df.copy()
        if df.empty:
            return None
        
        # Check if it is practice session
        if "Position" in df.columns and df["Position"].isna().all():
            return "PRACTICE"
        
        # Sort by Position
        if "Position" in df.columns:
            df = df.dropna(subset=["Position"]).sort_values("Position").reset_index(drop=True)
            df["Pos"] = df["Position"].astype(int)
        else:
            # Fallback sort by index/position if column not present
            df["Pos"] = df.index + 1
            
        return df
    except Exception:
        return None


def _make_fmt_driver(drv_labels: dict, fallback: dict | None = None):
    """Return a format_func closure for st.selectbox that shows 'ABR · Last Name'.

    Args:
        drv_labels: Primary labels dict built by _build_driver_labels for the session.
        fallback:   Optional fallback dict (e.g. Session 1 labels when Session 2 is
                    missing a driver). Consulted only when drv_labels has no match.

    Usage in app.py::

        _fmt_driver1 = _make_fmt_driver(_drv_labels1)
        _fmt_driver2 = _make_fmt_driver(_drv_labels2 or _drv_labels1, fallback=_drv_labels1)
    """
    def _fmt(num: str) -> str:
        key = str(num)
        label = drv_labels.get(key)
        if label is not None:
            return label
        if fallback is not None:
            return fallback.get(key, key)
        return key
    return _fmt


def _build_lap_history(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return cleaned lap DataFrame for a single driver."""
    try:
        # laps_df is a plain pd.DataFrame (not fastf1.core.Laps), so we
        # filter by the Driver column instead of using .pick_drivers().
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # filter out obvious outliers (safety car laps, pit laps > 3× median)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)
        return laps
    except Exception:
        return None


def _build_fuel_adjusted(driver: str, sess_k: str, fuel_effect: float,
                         laps_df: pd.DataFrame):
    """
    Return DataFrame with raw LapTimeSec and FuelAdjSec columns.
    Fuel correction: subtract (total_laps - lap_number) * fuel_effect
    → normalises all laps to empty-tank pace (equivalent to a flying Q-lap).
    Filters out in-laps and out-laps for accurate analysis.
    """
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        
        # Exclude in-laps and out-laps to focus on flying/pace laps
        if "PitOutTime" in laps.columns:
            laps = laps[laps["PitOutTime"].isna()]
        if "PitInTime" in laps.columns:
            laps = laps[laps["PitInTime"].isna()]
            
        if laps.empty:
            return None
            
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

        # Outlier filter — same as lap history (>2.5× median removed)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        # Total laps in the session (used to compute remaining fuel)
        total_laps = int(laps_df["LapNumber"].max())

        # Remaining fuel = laps left to run AFTER current lap
        laps["FuelLapsRemaining"] = (total_laps - laps["LapNumber"]).clip(lower=0)
        laps["FuelCorrection"]    = laps["FuelLapsRemaining"] * fuel_effect
        laps["FuelAdjSec"]        = laps["LapTimeSec"] - laps["FuelCorrection"]

        return laps[["LapNumber", "LapTimeSec", "FuelAdjSec",
                     "FuelCorrection", "Compound"]].copy()
    except Exception:
        return None


def _build_fuel_sim_leaderboard(sess_k: str, fuel_effect: float, laps_df: pd.DataFrame):
    """
    Simulate qualifying order by calculating the median fuel-adjusted pace
    for each driver in the session. Filters out in-laps and out-laps.
    """
    try:
        results = []
        all_drvs = laps_df["Driver"].unique()
        total_laps = int(laps_df["LapNumber"].max())
        
        for drv in all_drvs:
            drv_laps = laps_df[laps_df["Driver"] == drv].copy()
            drv_laps = drv_laps.dropna(subset=["LapTime", "LapNumber"])
            if drv_laps.empty:
                continue
                
            # Exclude in-laps and out-laps to get true representative pace
            if "PitOutTime" in drv_laps.columns:
                drv_laps = drv_laps[drv_laps["PitOutTime"].isna()]
            if "PitInTime" in drv_laps.columns:
                drv_laps = drv_laps[drv_laps["PitInTime"].isna()]
                
            if drv_laps.empty:
                continue
                
            drv_laps["LapTimeSec"] = drv_laps["LapTime"].dt.total_seconds()
            
            # Outlier filter
            median_t = drv_laps["LapTimeSec"].median()
            drv_laps = drv_laps[drv_laps["LapTimeSec"] < median_t * 2.5].copy()
            if drv_laps.empty:
                continue
                
            drv_laps = drv_laps.sort_values("LapNumber").reset_index(drop=True)
            drv_laps["FuelLapsRemaining"] = (total_laps - drv_laps["LapNumber"]).clip(lower=0)
            drv_laps["FuelCorrection"]    = drv_laps["FuelLapsRemaining"] * fuel_effect
            drv_laps["FuelAdjSec"]        = drv_laps["LapTimeSec"] - drv_laps["FuelCorrection"]
            
            median_adj = drv_laps["FuelAdjSec"].median()
            best_adj   = drv_laps["FuelAdjSec"].min()
            laps_count = len(drv_laps)
            
            # Extract tyre compound used on the best fuel-adjusted lap
            best_idx = drv_laps["FuelAdjSec"].idxmin()
            best_compound = str(drv_laps.loc[best_idx, "Compound"]).upper() if "Compound" in drv_laps.columns else "UNKNOWN"
            if best_compound in ("NAN", "NONE", ""):
                best_compound = "UNKNOWN"
            
            results.append({
                "Driver": drv,
                "MedianAdjSec": median_adj,
                "BestAdjSec": best_adj,
                "BestCompound": best_compound,
                "Laps": laps_count
            })
            
        if not results:
            return None
            
        df = pd.DataFrame(results)
        df = df.sort_values("MedianAdjSec").reset_index(drop=True)
        df["Pos"] = df.index + 1
        
        p1_median = df.loc[0, "MedianAdjSec"]
        df["GapToLeader"] = df["MedianAdjSec"] - p1_median
        
        return df
    except Exception:
        return None


def _build_stints(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return a list of stint dicts: {compound, start_lap, end_lap, laps, fresh}."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapNumber"]).sort_values("LapNumber")
        stints, current = [], None
        for _, row in laps.iterrows():
            cmp = str(row.get("Compound", "UNKNOWN")).upper()
            if cmp in ("NAN", "NONE", ""):
                cmp = "UNKNOWN"
            ln = int(row["LapNumber"])
            fresh = bool(row.get("FreshTyre", False))
            if current is None or cmp != current["compound"] or (
                "PitOutTime" in row and pd.notna(row.get("PitOutTime"))
            ):
                if current:
                    stints.append(current)
                current = {"compound": cmp, "start_lap": ln,
                           "end_lap": ln, "fresh": fresh}
            else:
                current["end_lap"] = ln
        if current:
            stints.append(current)
        for s in stints:
            s["laps"] = s["end_lap"] - s["start_lap"] + 1
        return stints
    except Exception:
        return []


def _build_pit_stops(driver: str, sess_k: str, laps_df: pd.DataFrame) -> list[dict] | None:
    """Return a list of pit stop dicts for one driver: lap, duration_s, old_cmp, new_cmp."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        stops = []
        for i, row in laps.iterrows():
            if pd.isna(row.get("PitInTime")) or pd.isna(row.get("PitOutTime")):
                continue
            try:
                duration_s = (row["PitOutTime"] - row["PitInTime"]).total_seconds()
            except Exception:
                duration_s = None

            # Compound before pit = this lap's compound
            old_cmp = str(row.get("Compound", "?")).title()

            # Compound after pit = next lap's compound
            new_cmp = "?"
            if i + 1 < len(laps):
                next_cmp = laps.iloc[i + 1].get("Compound", "?")
                if pd.notna(next_cmp):
                    new_cmp = str(next_cmp).title()

            stops.append({
                "lap":      int(row["LapNumber"]),
                "duration": round(duration_s, 1) if duration_s is not None else None,
                "old_cmp":  old_cmp,
                "new_cmp":  new_cmp,
            })
        return stops if stops else None
    except Exception:
        return None


def _build_fuel_decoupled_tyre_deg(
    driver: str,
    laps_df: pd.DataFrame,
    fuel_effect: float = 0.035,
    total_laps: int | None = None
) -> list[dict] | None:
    """Build per-stint tyre degradation data decoupled from fuel burn-off mass gains.

    As a Formula 1 car burns ~0.3 kg of fuel per lap, it naturally accelerates by
    approximately 0.030–0.040 s/lap. This weight reduction masks the true rate of
    mechanical tyre degradation, creating artificially flat or negative degradation slopes.

    This function decouples fuel burn to compute True Mechanical Tyre Wear:
    - Normalizes lap times to zero-fuel (qualifying weight):
      ``LapTime_s_fuel_corr = LapTime_s_raw - fuel_effect * (TotalLaps - LapNumber)``
    - Computes both raw timing-screen degradation slope (``raw_slope``) and pure
      mechanical tyre wear slope (``fuel_corrected_slope`` / ``true_deg_rate``).
    - Fits degree-2 quadratic polynomial curves on both raw and decoupled pace.
    - Estimates true thermal cliff lap (+1.5 s pace drop relative to fresh tyre base pace).

    Parameters
    ----------
    driver : str
        Three-letter driver code or identifier.
    laps_df : pd.DataFrame
        Session laps DataFrame containing at minimum ``Driver``, ``LapNumber``,
        ``TyreLife``, ``LapTime``, ``Stint``, ``Compound``, ``IsAccurate``, ``TrackStatus``.
    fuel_effect : float, default 0.035
        Pace penalty per lap of fuel (seconds per lap). Default is 0.035 s/lap.
    total_laps : int | None, optional
        Total session laps. If None, inferred from ``laps_df["LapNumber"].max()``.

    Returns
    -------
    list[dict] | None
        List of stint dictionaries containing raw and fuel-decoupled degradation
        metrics, regression models, cliff lap predictions, and individual lap records.
    """
    CLIFF_THRESHOLD_S = 1.5

    try:
        if laps_df is None or laps_df.empty:
            return None

        laps = laps_df[laps_df["Driver"] == driver].copy()
        if laps.empty:
            return None

        # Filter out in-laps, out-laps and safety car periods
        clean_laps = laps[
            (laps["IsAccurate"] == True) &
            (~laps["TrackStatus"].astype(str).str.contains("4|5|6|7")) &
            (laps["LapTime"].notna())
        ].copy()

        if clean_laps.empty:
            return None

        if "LapNumber" not in clean_laps.columns or clean_laps["LapNumber"].dropna().empty:
            clean_laps["LapNumber"] = np.arange(1, len(clean_laps) + 1)

        clean_laps = clean_laps.dropna(subset=["LapNumber", "LapTime"]).copy()
        if clean_laps.empty:
            return None

        clean_laps["LapTime_s_raw"] = clean_laps["LapTime"].dt.total_seconds()

        # Determine total session laps
        if total_laps is None:
            if "LapNumber" in laps_df.columns and not laps_df["LapNumber"].dropna().empty:
                total_laps = int(laps_df["LapNumber"].max())
            else:
                total_laps = int(clean_laps["LapNumber"].max())

        # Compute fuel mass correction: lap time without remaining fuel weight
        fuel_laps_remaining = (total_laps - clean_laps["LapNumber"]).clip(lower=0)
        clean_laps["FuelCorrection_s"] = fuel_laps_remaining * fuel_effect
        clean_laps["LapTime_s_fuel_corr"] = clean_laps["LapTime_s_raw"] - clean_laps["FuelCorrection_s"]

        # Default LapTime_s is fuel-corrected when fuel_effect > 0, else raw
        if fuel_effect > 0:
            clean_laps["LapTime_s"] = clean_laps["LapTime_s_fuel_corr"]
        else:
            clean_laps["LapTime_s"] = clean_laps["LapTime_s_raw"]

        stints_data = []
        for (stint, compound), group in clean_laps.groupby(["Stint", "Compound"]):
            group = group.sort_values("LapNumber")
            # Only consider stints with at least 4 valid laps
            if len(group) < 4:
                continue

            x_vals = np.array(group["TyreLife"].values, dtype=float)
            y_raw = np.array(group["LapTime_s_raw"].values, dtype=float)
            y_corr = np.array(group["LapTime_s_fuel_corr"].values, dtype=float)
            y_active = y_corr if fuel_effect > 0 else y_raw

            # ── Linear regressions ──────────────────────────────────────────
            raw_slope, raw_intercept = np.polyfit(x_vals, y_raw, 1)
            corr_slope, corr_intercept = np.polyfit(x_vals, y_corr, 1)

            active_slope = corr_slope if fuel_effect > 0 else raw_slope
            active_base_pace = corr_intercept if fuel_effect > 0 else raw_intercept

            # ── Quadratic regressions (non-linear thermal degradation) ──────
            quad_coeffs = None
            cliff_lap: int | None = None
            raw_quad_coeffs = None
            raw_cliff_lap: int | None = None

            # 1) Fuel-corrected (or active) quadratic model
            try:
                if len(x_vals) >= 5:
                    a, b, c = np.polyfit(x_vals, y_active, 2)
                    quad_coeffs = (float(a), float(b), float(c))
                    quad_base = np.polyval([a, b, c], x_vals.min())
                    cliff_target = quad_base + CLIFF_THRESHOLD_S

                    discriminant = b**2 - 4 * a * (c - cliff_target)
                    if a > 1e-9 and discriminant >= 0:
                        x_cliff = (-b + np.sqrt(discriminant)) / (2 * a)
                        if x_cliff > x_vals.min():
                            cliff_lap = max(int(round(x_cliff)), int(x_vals.min()) + 1)
            except Exception:
                quad_coeffs = None
                cliff_lap = None

            # Fallback: linear cliff extrapolation for active pace
            if cliff_lap is None and active_slope > 1e-6:
                x_cliff_linear = (active_base_pace + CLIFF_THRESHOLD_S - active_base_pace) / active_slope
                if x_cliff_linear > 0:
                    cliff_lap = max(int(round(x_vals.min() + x_cliff_linear)), int(x_vals.min()) + 1)

            # 2) Raw uncorrected quadratic model (for baseline comparison)
            try:
                if len(x_vals) >= 5:
                    ra, rb, rc = np.polyfit(x_vals, y_raw, 2)
                    raw_quad_coeffs = (float(ra), float(rb), float(rc))
                    r_quad_base = np.polyval([ra, rb, rc], x_vals.min())
                    r_cliff_target = r_quad_base + CLIFF_THRESHOLD_S

                    r_discriminant = rb**2 - 4 * ra * (rc - r_cliff_target)
                    if ra > 1e-9 and r_discriminant >= 0:
                        r_x_cliff = (-rb + np.sqrt(r_discriminant)) / (2 * ra)
                        if r_x_cliff > x_vals.min():
                            raw_cliff_lap = max(int(round(r_x_cliff)), int(x_vals.min()) + 1)
            except Exception:
                raw_quad_coeffs = None
                raw_cliff_lap = None

            if raw_cliff_lap is None and raw_slope > 1e-6:
                r_x_cliff_linear = (raw_intercept + CLIFF_THRESHOLD_S - raw_intercept) / raw_slope
                if r_x_cliff_linear > 0:
                    raw_cliff_lap = max(int(round(x_vals.min() + r_x_cliff_linear)), int(x_vals.min()) + 1)

            # ── Remaining laps and pit window ────────────────────────────────
            last_tyre_life = int(x_vals.max())
            remaining_laps = max(cliff_lap - last_tyre_life, 0) if cliff_lap is not None else None
            pit_window_low = max(cliff_lap - 3, 1) if cliff_lap is not None else None
            pit_window_high = cliff_lap + 3 if cliff_lap is not None else None

            stints_data.append({
                "stint": int(stint),
                "compound": str(compound),
                "laps": group[[
                    "TyreLife", "LapTime_s", "LapTime_s_raw", "LapTime_s_fuel_corr", "FuelCorrection_s", "LapNumber"
                ]].to_dict(orient="records"),
                # Predictive crossover fields
                "slope": float(active_slope),
                "base_pace": float(active_base_pace),
                "raw_slope": float(raw_slope),
                "raw_base_pace": float(raw_intercept),
                "fuel_corrected_slope": float(corr_slope),
                "fuel_corrected_base_pace": float(corr_intercept),
                "true_deg_rate": float(corr_slope),
                "fuel_effect": float(fuel_effect),
                "quad_coeffs": quad_coeffs,
                "raw_quad_coeffs": raw_quad_coeffs,
                "last_tyre_life": last_tyre_life,
                "cliff_lap": cliff_lap,
                "raw_cliff_lap": raw_cliff_lap,
                "remaining_laps": remaining_laps,
                "pit_window_low": pit_window_low,
                "pit_window_high": pit_window_high,
                "cliff_threshold_s": CLIFF_THRESHOLD_S,
                "is_fuel_decoupled": bool(fuel_effect > 0),
            })
        return stints_data if stints_data else None
    except Exception:
        return None


def _build_tyre_deg_data(
    driver: str,
    laps_df: pd.DataFrame,
    fuel_effect: float = 0.0
) -> list[dict] | None:
    """Build per-stint tyre degradation data with predictive cliff lap estimation.

    Maintains full backward compatibility for callers and automated test suites.
    When ``fuel_effect > 0``, delegates to :func:`_build_fuel_decoupled_tyre_deg`.
    """
    return _build_fuel_decoupled_tyre_deg(
        driver=driver,
        laps_df=laps_df,
        fuel_effect=fuel_effect
    )


def _build_consistency_analysis(sess_k: str, laps_df: pd.DataFrame, drivers: list[str] = None) -> dict | None:
    """
    Calculate driver lap time variance per stint, overall consistency index,
    and clean air vs traffic deficit.
    """
    try:
        if laps_df is None or laps_df.empty:
            return None

        df = laps_df.copy()
        if "LapTime" not in df.columns or "Driver" not in df.columns:
            return None

        df = df.dropna(subset=["LapTime", "Driver"]).copy()
        if df.empty:
            return None

        df["LapTime_s"] = df["LapTime"].dt.total_seconds()

        # Clean laps mask: filter out in-laps, out-laps, and safety car / red flag periods
        clean_mask = (df["LapTime_s"] > 0)
        if "IsAccurate" in df.columns:
            clean_mask = clean_mask & (df["IsAccurate"] == True)
        if "PitInTime" in df.columns:
            clean_mask = clean_mask & (df["PitInTime"].isna())
        if "PitOutTime" in df.columns:
            clean_mask = clean_mask & (df["PitOutTime"].isna())
        if "TrackStatus" in df.columns:
            clean_mask = clean_mask & (~df["TrackStatus"].astype(str).str.contains("4|5|6|7"))

        clean_df_all = df[clean_mask].copy()
        if clean_df_all.empty:
            return None

        if drivers:
            clean_df_all = clean_df_all[clean_df_all["Driver"].isin(drivers)].copy()
            if clean_df_all.empty:
                return None

        clean_df_all["IsTraffic"] = False

        # Categorize Clean Air vs Traffic via position gap if available
        try:
            if "Position" in clean_df_all.columns and "LapNumber" in clean_df_all.columns:
                pos_per_lap = clean_df_all.groupby(["LapNumber", "Driver"])["Position"].first().unstack(level=1)
                traffic_flags = {}
                for lap, lap_positions in pos_per_lap.iterrows():
                    sorted_pos = lap_positions.dropna().sort_values()
                    prev_drv = None
                    for drv, pos in sorted_pos.items():
                        if pos == 1 or prev_drv is None:
                            traffic_flags[(drv, lap)] = False
                        else:
                            drv_laps = clean_df_all[(clean_df_all["Driver"] == drv) & (clean_df_all["LapNumber"] <= lap)]["LapTime_s"].sum()
                            prev_laps = clean_df_all[(clean_df_all["Driver"] == prev_drv) & (clean_df_all["LapNumber"] <= lap)]["LapTime_s"].sum()
                            gap = drv_laps - prev_laps
                            traffic_flags[(drv, lap)] = (0.0 <= gap <= 1.5)
                        prev_drv = drv
                clean_df_all["IsTraffic"] = clean_df_all.apply(
                    lambda r: traffic_flags.get((r["Driver"], r["LapNumber"]), False), axis=1
                )
        except Exception:
            pass

        result_drivers = {}
        processed_clean_laps = []

        for drv, drv_df in clean_df_all.groupby("Driver"):
            drv_laps = drv_df.sort_values("LapNumber").copy()
            if drv_laps.empty:
                continue

            median_t = drv_laps["LapTime_s"].median()
            valid_laps = drv_laps[drv_laps["LapTime_s"] <= median_t * 1.20].copy()
            if valid_laps.empty:
                valid_laps = drv_laps.copy()

            processed_clean_laps.append(valid_laps)

            overall_std = float(valid_laps["LapTime_s"].std()) if len(valid_laps) > 1 else 0.0
            overall_score = round(max(0.0, min(100.0, 100.0 - overall_std * 30.0)), 1)

            clean_air_laps = valid_laps[~valid_laps["IsTraffic"]]
            traffic_laps = valid_laps[valid_laps["IsTraffic"]]

            if clean_air_laps.empty and traffic_laps.empty:
                clean_air_laps = valid_laps[valid_laps["LapTime_s"] <= median_t * 1.02]
                traffic_laps = valid_laps[valid_laps["LapTime_s"] > median_t * 1.02]

            clean_air_pace = float(clean_air_laps["LapTime_s"].median()) if not clean_air_laps.empty else median_t
            traffic_pace = float(traffic_laps["LapTime_s"].median()) if not traffic_laps.empty else clean_air_pace
            traffic_deficit = round(max(0.0, traffic_pace - clean_air_pace), 3)

            stints_list = []
            stint_col = "Stint" if "Stint" in valid_laps.columns else None

            if stint_col:
                for stint_num, s_group in valid_laps.groupby(stint_col):
                    cmp = str(s_group["Compound"].iloc[0]).upper() if "Compound" in s_group.columns else "UNKNOWN"
                    s_std = float(s_group["LapTime_s"].std()) if len(s_group) > 1 else 0.0
                    s_score = round(max(0.0, min(100.0, 100.0 - s_std * 30.0)), 1)
                    s_median = float(s_group["LapTime_s"].median())
                    stints_list.append({
                        "stint": int(stint_num),
                        "compound": cmp,
                        "std": round(s_std, 3),
                        "score": s_score,
                        "median": s_median,
                        "count": len(s_group),
                        "laps_df": s_group
                    })
            else:
                stints_list.append({
                    "stint": 1,
                    "compound": "UNKNOWN",
                    "std": round(overall_std, 3),
                    "score": overall_score,
                    "median": median_t,
                    "count": len(valid_laps),
                    "laps_df": valid_laps
                })

            result_drivers[drv] = {
                "overall_std": round(overall_std, 3),
                "overall_score": overall_score,
                "clean_air_pace": clean_air_pace,
                "traffic_pace": traffic_pace,
                "traffic_deficit": traffic_deficit,
                "clean_laps_count": len(valid_laps),
                "stints": stints_list,
                "clean_df": valid_laps
            }

        combined_clean_df = pd.concat(processed_clean_laps, ignore_index=True) if processed_clean_laps else None

        return {
            "drivers": result_drivers,
            "all_clean_laps": combined_clean_df
        }
    except Exception:
        return None


def _build_weather_correlation_data(sess_k: str, laps_df: pd.DataFrame, _session_obj=None, drivers: list[str] = None) -> dict | None:
    """
    Correlate track/air temperature changes and rainfall intensity with lap time
    drop-offs and tyre compound performance.
    """
    try:
        if laps_df is None or laps_df.empty:
            return None

        laps = laps_df.copy()
        if "LapTime" not in laps.columns or "Driver" not in laps.columns or "LapNumber" not in laps.columns:
            return None

        laps = laps.dropna(subset=["LapTime", "Driver", "LapNumber"]).copy()
        if laps.empty:
            return None

        laps["LapTime_s"] = laps["LapTime"].dt.total_seconds()
        laps["LapNumber"] = laps["LapNumber"].astype(int)

        clean_mask = (laps["LapTime_s"] > 0)
        if "IsAccurate" in laps.columns:
            clean_mask = clean_mask & (laps["IsAccurate"] == True)
        if "PitInTime" in laps.columns:
            clean_mask = clean_mask & (laps["PitInTime"].isna())
        if "PitOutTime" in laps.columns:
            clean_mask = clean_mask & (laps["PitOutTime"].isna())
        if "TrackStatus" in laps.columns:
            clean_mask = clean_mask & (~laps["TrackStatus"].astype(str).str.contains("4|5|6|7"))

        clean_laps = laps[clean_mask].copy()

        # Extract weather data from _session_obj if available
        weather_df = None
        if _session_obj is not None and hasattr(_session_obj, "weather_data"):
            try:
                w_raw = _session_obj.weather_data
                if w_raw is not None and not w_raw.empty and "Time" in w_raw.columns:
                    weather_df = w_raw.copy()
            except Exception:
                weather_df = None

        # Merge weather onto laps_df by Time using merge_asof if weather_df exists
        if weather_df is not None and "Time" in laps.columns:
            try:
                laps_sorted = laps.sort_values("Time").copy()
                w_sorted = weather_df.sort_values("Time").copy()
                laps = pd.merge_asof(laps_sorted, w_sorted, on="Time", direction="nearest", suffixes=("", "_w")).sort_values(["Driver", "LapNumber"]).copy()
                if not clean_laps.empty and "Time" in clean_laps.columns:
                    clean_laps = pd.merge_asof(clean_laps.sort_values("Time"), w_sorted, on="Time", direction="nearest", suffixes=("", "_w"))
            except Exception:
                pass

        # Build lap-level weather summary
        lap_weather = {}
        if "TrackTemp" in laps.columns:
            for lap_num, grp in laps.groupby("LapNumber"):
                t_trk = float(grp["TrackTemp"].dropna().median()) if not grp["TrackTemp"].dropna().empty else None
                t_air = float(grp["AirTemp"].dropna().median()) if "AirTemp" in grp.columns and not grp["AirTemp"].dropna().empty else None
                rain = bool(grp["Rainfall"].dropna().any()) if "Rainfall" in grp.columns and not grp["Rainfall"].dropna().empty else False
                hum = float(grp["Humidity"].dropna().median()) if "Humidity" in grp.columns and not grp["Humidity"].dropna().empty else None
                med_pace = float(clean_laps[clean_laps["LapNumber"] == lap_num]["LapTime_s"].median()) if not clean_laps[clean_laps["LapNumber"] == lap_num].empty else None
                lap_weather[int(lap_num)] = {
                    "TrackTemp": t_trk,
                    "AirTemp": t_air,
                    "Rainfall": rain,
                    "Humidity": hum,
                    "MedianPace": med_pace
                }

        lap_weather_df = pd.DataFrame.from_dict(lap_weather, orient="index")
        if not lap_weather_df.empty:
            lap_weather_df.index.name = "LapNumber"
            lap_weather_df = lap_weather_df.reset_index().sort_values("LapNumber")

        # Detect Slick vs Wet Rain Crossover Laps
        crossover_laps = []
        wet_compounds = {"INTERMEDIATE", "WET"}
        if "Compound" in laps.columns:
            prev_has_wet = None
            for lap_num, grp in laps.sort_values("LapNumber").groupby("LapNumber"):
                cmps = {str(c).upper() for c in grp["Compound"].dropna()}
                has_wet = bool(cmps.intersection(wet_compounds))
                if prev_has_wet is not None and has_wet != prev_has_wet:
                    crossover_laps.append(int(lap_num))
                prev_has_wet = has_wet

        driver_laps_dict = {}
        target_drivers = drivers if drivers else laps["Driver"].unique().tolist()
        for drv in target_drivers:
            drv_clean = clean_laps[clean_laps["Driver"] == drv].sort_values("LapNumber").copy()
            if not drv_clean.empty:
                driver_laps_dict[drv] = drv_clean

        trk_temps = laps["TrackTemp"].dropna() if "TrackTemp" in laps.columns else pd.Series(dtype=float)
        air_temps = laps["AirTemp"].dropna() if "AirTemp" in laps.columns else pd.Series(dtype=float)
        rain_laps = laps[laps["Rainfall"] == True]["LapNumber"].nunique() if "Rainfall" in laps.columns else 0

        corr_val = None
        if not clean_laps.empty and "TrackTemp" in clean_laps.columns:
            valid_corr_data = clean_laps.dropna(subset=["TrackTemp", "LapTime_s"])
            if len(valid_corr_data) >= 5:
                corr_val = float(valid_corr_data["TrackTemp"].corr(valid_corr_data["LapTime_s"]))

        stats = {
            "track_temp_min": round(float(trk_temps.min()), 1) if not trk_temps.empty else None,
            "track_temp_max": round(float(trk_temps.max()), 1) if not trk_temps.empty else None,
            "track_temp_avg": round(float(trk_temps.mean()), 1) if not trk_temps.empty else None,
            "air_temp_avg": round(float(air_temps.mean()), 1) if not air_temps.empty else None,
            "rainfall_detected": bool(rain_laps > 0),
            "wet_laps_count": int(rain_laps),
            "crossover_laps": crossover_laps,
            "temp_correlation": round(corr_val, 3) if corr_val is not None and not np.isnan(corr_val) else None,
        }

        return {
            "laps_weather_df": lap_weather_df,
            "driver_laps": driver_laps_dict,
            "stats": stats
        }
    except Exception:
        return None


def _build_multi_year_comparison(
    tel1: pd.DataFrame,
    tel2: pd.DataFrame,
    label1: str = "Era 1",
    label2: str = "Era 2",
    lap1_time_s: float = None,
    lap2_time_s: float = None
) -> dict | None:
    """
    Build multi-year historical lap comparison dataset aligning distance-based telemetry traces
    and computing era performance metrics (speed deltas, apex speeds, throttle ratios, delta time).
    """
    try:
        if tel1 is None or tel2 is None or tel1.empty or tel2.empty:
            return None

        if "Distance" not in tel1.columns or "Speed" not in tel1.columns:
            return None
        if "Distance" not in tel2.columns or "Speed" not in tel2.columns:
            return None

        t1 = tel1.sort_values("Distance").dropna(subset=["Distance", "Speed"]).copy()
        t2 = tel2.sort_values("Distance").dropna(subset=["Distance", "Speed"]).copy()

        if t1.empty or t2.empty:
            return None

        max_dist = min(t1["Distance"].max(), t2["Distance"].max())
        if max_dist <= 0:
            return None

        grid = np.linspace(0, max_dist, 500)
        speed1_interp = np.interp(grid, t1["Distance"], t1["Speed"])
        speed2_interp = np.interp(grid, t2["Distance"], t2["Speed"])

        speed_delta = speed1_interp - speed2_interp

        time_delta = None
        if "Time" in t1.columns and "Time" in t2.columns:
            try:
                t1_sec = t1["Time"].dt.total_seconds().values
                t2_sec = t2["Time"].dt.total_seconds().values
                time1_interp = np.interp(grid, t1["Distance"], t1_sec - t1_sec[0])
                time2_interp = np.interp(grid, t2["Distance"], t2_sec - t2_sec[0])
                time_delta = time1_interp - time2_interp
            except Exception:
                time_delta = None

        if time_delta is None:
            dx = grid[1] - grid[0]
            v1_ms = np.maximum(speed1_interp / 3.6, 1.0)
            v2_ms = np.maximum(speed2_interp / 3.6, 1.0)
            dt = (1.0 / v1_ms) - (1.0 / v2_ms)
            time_delta = np.cumsum(dt) * dx

        top_speed1 = float(t1["Speed"].max())
        top_speed2 = float(t2["Speed"].max())

        apex_speed1 = float(t1["Speed"].min())
        apex_speed2 = float(t2["Speed"].min())

        throttle_pct1 = float((t1["Throttle"] == 100).mean() * 100) if "Throttle" in t1.columns else None
        throttle_pct2 = float((t2["Throttle"] == 100).mean() * 100) if "Throttle" in t2.columns else None

        lap_delta_s = None
        if lap1_time_s is not None and lap2_time_s is not None:
            lap_delta_s = round(lap1_time_s - lap2_time_s, 3)

        return {
            "grid": grid,
            "speed1": speed1_interp,
            "speed2": speed2_interp,
            "speed_delta": speed_delta,
            "time_delta": time_delta,
            "stats": {
                "top_speed1": round(top_speed1, 1),
                "top_speed2": round(top_speed2, 1),
                "apex_speed1": round(apex_speed1, 1),
                "apex_speed2": round(apex_speed2, 1),
                "throttle_pct1": round(throttle_pct1, 1) if throttle_pct1 is not None else None,
                "throttle_pct2": round(throttle_pct2, 1) if throttle_pct2 is not None else None,
                "lap_delta_s": lap_delta_s,
                "label1": label1,
                "label2": label2,
            }
        }
    except Exception:
        return None


def _build_leaderboard(sess_k: str, laps_df: pd.DataFrame):
    """Return a ranked DataFrame of all drivers' fastest laps."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapTime", "Driver"])
        # Get each driver's fastest lap
        idx = laps.groupby("Driver")["LapTime"].idxmin()
        best = laps.loc[idx].copy().reset_index(drop=True)
        best["LapTimeSec"] = best["LapTime"].dt.total_seconds()
        best = best.sort_values("LapTimeSec").reset_index(drop=True)

        # Gap to P1
        p1_time = best["LapTimeSec"].iloc[0]
        best["GapToP1"] = best["LapTimeSec"] - p1_time

        # Format columns
        best["Pos"]      = best.index + 1
        best["Time"]     = best["LapTime"].apply(format_laptime)
        best["Gap"]      = best["GapToP1"].apply(
            lambda g: "—" if g == 0 else f"+{g:.3f}s"
        )
        best["Lap"]      = best["LapNumber"].astype(int)
        best["Compound"] = best["Compound"].fillna("?").astype(str).str.title()
        best["Top Speed (km/h)"] = best["SpeedST"].apply(
            lambda s: f"{s:.0f}" if pd.notna(s) else "—"
        )

        return best[["Pos", "Driver", "Time", "Gap", "Compound", "Lap", "Top Speed (km/h)"]]
    except Exception:
        return None


def _build_ideal_lap(sess_k: str, laps_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    For every driver, find best S1, best S2, best S3 across all valid laps.
    Returns a DataFrame with columns:
        Driver, BestS1, BestS2, BestS3, TheoreticalBest,
        ActualBest, Delta, BestS1Lap, BestS2Lap, BestS3Lap
    sorted by TheoreticalBest ascending.
    """
    try:
        laps = laps_df.copy()
        needed = ["Driver", "LapNumber", "Sector1Time", "Sector2Time",
                  "Sector3Time", "LapTime"]
        laps = laps.dropna(subset=["Driver", "LapTime"])

        # Check sector columns exist and have at least some data
        for col in ["Sector1Time", "Sector2Time", "Sector3Time"]:
            if col not in laps.columns or laps[col].dropna().empty:
                return None

        records = []
        for drv, grp in laps.groupby("Driver"):
            s1 = grp.dropna(subset=["Sector1Time"])
            s2 = grp.dropna(subset=["Sector2Time"])
            s3 = grp.dropna(subset=["Sector3Time"])
            lt = grp.dropna(subset=["LapTime"])
            if s1.empty or s2.empty or s3.empty or lt.empty:
                continue

            best_s1_row = s1.loc[s1["Sector1Time"].idxmin()]
            best_s2_row = s2.loc[s2["Sector2Time"].idxmin()]
            best_s3_row = s3.loc[s3["Sector3Time"].idxmin()]

            best_s1 = best_s1_row["Sector1Time"].total_seconds()
            best_s2 = best_s2_row["Sector2Time"].total_seconds()
            best_s3 = best_s3_row["Sector3Time"].total_seconds()

            theoretical = best_s1 + best_s2 + best_s3
            actual_best = lt["LapTime"].min().total_seconds()
            delta = actual_best - theoretical

            records.append({
                "Driver":          str(drv),
                "BestS1":          best_s1,
                "BestS2":          best_s2,
                "BestS3":          best_s3,
                "TheoreticalBest": theoretical,
                "ActualBest":      actual_best,
                "Delta":           delta,
                "BestS1Lap":       int(best_s1_row["LapNumber"]),
                "BestS2Lap":       int(best_s2_row["LapNumber"]),
                "BestS3Lap":       int(best_s3_row["LapNumber"]),
            })

        if not records:
            return None

        df = pd.DataFrame(records).sort_values("TheoreticalBest").reset_index(drop=True)
        df["Pos"] = df.index + 1

        # Gap to theoretical pole (best theoretical lap overall)
        pole_time = df["TheoreticalBest"].iloc[0]
        df["GapToPole"] = df["TheoreticalBest"] - pole_time

        return df
    except Exception:
        return None


def _fmt_sec(s: float) -> str:
    """Format seconds as M:SS.mmm lap-time string."""
    m = int(s // 60)
    return f"{m}:{s % 60:06.3f}"


def _build_gap_data(sess_k: str, laps_df: pd.DataFrame, _session_obj=None):
    """Return a dict {driver: pd.Series(gap_seconds, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        # Only use valid laps with a recorded LapTime
        laps = laps.dropna(subset=["LapTime", "LapNumber", "Driver"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # For each driver sort by lap number and compute cumulative race time
        gap_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber").copy()
            grp["CumTime"] = grp["LapTimeSec"].cumsum()
            gap_dict[drv] = grp.set_index("LapNumber")["CumTime"]
        if not gap_dict:
            return None, None
        # Build leader reference: at each lap, min cumulative time across drivers
        all_laps_idx = sorted({lap for s in gap_dict.values() for lap in s.index})
        leader_time = pd.Series(index=all_laps_idx, dtype=float)
        for lap in all_laps_idx:
            times_at_lap = [s.get(lap) for s in gap_dict.values() if lap in s.index]
            times_at_lap = [t for t in times_at_lap if t is not None]
            if times_at_lap:
                leader_time[lap] = min(times_at_lap)
        # Convert each driver's cumulative time to gap vs leader
        gap_to_leader = {}
        for drv, cum in gap_dict.items():
            gap = cum - leader_time.reindex(cum.index)
            gap_to_leader[drv] = gap
        # Also return track status by lap for shading
        try:
            ts = _session_obj.track_status.copy() if _session_obj is not None else None
            if ts is not None:
                ts["LapNumber"] = ts.index
        except Exception:
            ts = None
        return gap_to_leader, ts
    except Exception:
        return None, None


def _build_position_data(sess_k: str, laps_df: pd.DataFrame):
    """Return a dict {driver: pd.Series(position, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapNumber", "Position", "Driver"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["Position"]  = laps["Position"].astype(int)
        pos_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber")
            pos_dict[str(drv)] = grp.set_index("LapNumber")["Position"]
        return pos_dict if pos_dict else None
    except Exception:
        return None


def _get_telemetry_for_map(_lap, driver: str, sess_k: str):
    """Return merged position + car telemetry for a lap."""
    try:
        return _lap.get_telemetry()
    except Exception:
        return None


def _get_round(session):
    try:
        ev = session.event
        if ev is not None and "RoundNumber" in ev:
            val = ev["RoundNumber"]
            if pd.notna(val):
                return int(val)
    except Exception:
        pass
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def _build_grid_heatmap_data(sess_k: str, laps_df: pd.DataFrame, selected_drivers: list[str] | None = None, mode: str = "Sectors") -> dict | None:
    """
    Build multi-driver grid heatmap matrix data.
    Modes:
      - 'Sectors': Matrix of S1, S2, S3, Theoretical Best, Actual Best deltas (+seconds) vs grid best.
      - 'Laps': Matrix of Drivers x Laps deltas (+seconds) vs fastest lap time per lap.
      - 'Speed': Matrix of ST, I1, I2, FL speed deficits (km/h) vs top speed.
    """
    try:
        if laps_df is None or laps_df.empty:
            return None

        laps = laps_df.copy()
        laps = laps.dropna(subset=["Driver"])

        all_drivers = sorted(laps["Driver"].unique().tolist())
        if selected_drivers:
            drivers = [d for d in selected_drivers if d in all_drivers]
        else:
            drivers = all_drivers

        if not drivers:
            return None

        if mode == "Sectors":
            sector_cols = ["Sector1Time", "Sector2Time", "Sector3Time", "LapTime"]
            for col in ["Sector1Time", "Sector2Time", "Sector3Time"]:
                if col not in laps.columns or laps[col].dropna().empty:
                    return None

            records = []
            for drv in drivers:
                grp = laps[laps["Driver"] == drv]
                s1 = grp["Sector1Time"].dropna()
                s2 = grp["Sector2Time"].dropna()
                s3 = grp["Sector3Time"].dropna()
                lt = grp["LapTime"].dropna()

                if s1.empty or s2.empty or s3.empty or lt.empty:
                    continue

                b1 = s1.min().total_seconds()
                b2 = s2.min().total_seconds()
                b3 = s3.min().total_seconds()
                theo = b1 + b2 + b3
                act = lt.min().total_seconds()

                records.append({
                    "Driver": drv,
                    "S1": b1,
                    "S2": b2,
                    "S3": b3,
                    "Theoretical": theo,
                    "Actual": act,
                })

            if not records:
                return None

            df = pd.DataFrame(records)
            drv_order = df["Driver"].tolist()

            min_s1 = df["S1"].min()
            min_s2 = df["S2"].min()
            min_s3 = df["S3"].min()
            min_theo = df["Theoretical"].min()
            min_act = df["Actual"].min()

            delta_mat = np.zeros((len(df), 5))
            value_mat = []

            for i, row in df.iterrows():
                d_s1 = row["S1"] - min_s1
                d_s2 = row["S2"] - min_s2
                d_s3 = row["S3"] - min_s3
                d_theo = row["Theoretical"] - min_theo
                d_act = row["Actual"] - min_act

                delta_mat[i] = [d_s1, d_s2, d_s3, d_theo, d_act]
                value_mat.append([
                    f"{row['S1']:.3f}s",
                    f"{row['S2']:.3f}s",
                    f"{row['S3']:.3f}s",
                    f"{row['Theoretical']:.3f}s",
                    f"{row['Actual']:.3f}s",
                ])

            return {
                "drivers": drv_order,
                "columns": ["Sector 1", "Sector 2", "Sector 3", "Theoretical Best", "Actual Best"],
                "deltas": delta_mat,
                "values": value_mat,
                "best_values": [min_s1, min_s2, min_s3, min_theo, min_act],
            }

        elif mode == "Laps":
            laps = laps.dropna(subset=["LapNumber", "LapTime"])
            if laps.empty:
                return None

            laps["LapNumber"] = laps["LapNumber"].astype(int)
            laps["LapTime_s"] = laps["LapTime"].apply(lambda t: t.total_seconds() if pd.notna(t) else np.nan)
            laps = laps.dropna(subset=["LapTime_s"])

            max_lap = min(int(laps["LapNumber"].max()), 75)
            lap_range = list(range(1, max_lap + 1))

            pvt = laps.pivot_table(index="Driver", columns="LapNumber", values="LapTime_s", aggfunc="min")
            pvt = pvt.reindex(index=drivers, columns=lap_range)

            # Drop laps with no data across all selected drivers
            pvt = pvt.dropna(how="all", axis=1)
            if pvt.empty:
                return None

            valid_laps = pvt.columns.tolist()
            lap_bests = pvt.min(axis=0)

            delta_df = pvt.sub(lap_bests, axis=1)
            delta_mat = delta_df.fillna(np.nan).to_numpy()

            value_mat = []
            for drv in drivers:
                row_vals = []
                for lap_num in valid_laps:
                    val = pvt.loc[drv, lap_num] if drv in pvt.index else np.nan
                    if pd.notna(val):
                        m = int(val // 60)
                        s = val % 60
                        row_vals.append(f"{m}:{s:06.3f}" if m > 0 else f"{s:.3f}s")
                    else:
                        row_vals.append("—")
                value_mat.append(row_vals)

            return {
                "drivers": drivers,
                "columns": [f"Lap {l}" for l in valid_laps],
                "deltas": delta_mat,
                "values": value_mat,
                "best_values": lap_bests.tolist(),
            }

        elif mode == "Speed":
            speed_cols = ["SpeedST", "SpeedI1", "SpeedI2", "SpeedFL"]
            available = [c for c in speed_cols if c in laps.columns and not laps[c].dropna().empty]
            if not available:
                return None

            records = []
            for drv in drivers:
                grp = laps[laps["Driver"] == drv]
                row = {"Driver": drv}
                for col in available:
                    sp = grp[col].dropna()
                    row[col] = sp.max() if not sp.empty else np.nan
                records.append(row)

            df = pd.DataFrame(records)
            drv_order = df["Driver"].tolist()

            col_labels = [c.replace("Speed", "") + " Speed" for c in available]
            max_speeds = [df[c].max() for c in available]

            delta_mat = np.zeros((len(df), len(available)))
            value_mat = []

            for i, row in df.iterrows():
                row_deltas = []
                row_vals = []
                for j, col in enumerate(available):
                    val = row[col]
                    max_val = max_speeds[j]
                    if pd.notna(val) and pd.notna(max_val):
                        defic = max_val - val  # Speed deficit in km/h (positive value means slower than top speed)
                        row_deltas.append(defic)
                        row_vals.append(f"{val:.0f} km/h")
                    else:
                        row_deltas.append(np.nan)
                        row_vals.append("—")
                delta_mat[i] = row_deltas
                value_mat.append(row_vals)

            return {
                "drivers": drv_order,
                "columns": col_labels,
                "deltas": delta_mat,
                "values": value_mat,
                "best_values": max_speeds,
            }

        return None
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def _build_race_control_messages(sess_k: str, _sess_obj) -> pd.DataFrame | None:
    """Parse race_control_messages from the session into a clean DataFrame of flag events."""
    try:
        rc = getattr(_sess_obj, "race_control_messages", None)
        if rc is None or (hasattr(rc, "empty") and rc.empty):
            return None

        df = pd.DataFrame(rc).copy()
        if df.empty:
            return None

        # Normalise column names
        df.columns = [c.strip() for c in df.columns]

        # Keep relevant columns that are commonly present
        keep_cols = [c for c in ["Time", "LapNumber", "Category", "Message", "Flag", "Scope", "Sector", "RacingNumber", "Status"]
                     if c in df.columns]
        df = df[keep_cols].copy()

        # Compute LapNumber as int where available
        if "LapNumber" in df.columns:
            df["LapNumber"] = pd.to_numeric(df["LapNumber"], errors="coerce")

        # Classify flag type for colouring/filtering
        def _classify(row) -> str:
            msg = str(row.get("Message", "")).upper()
            flag = str(row.get("Flag", "")).upper()
            if "SAFETY CAR DEPLOYED" in msg or flag == "SC":
                return "SAFETY CAR"
            if "VIRTUAL SAFETY CAR" in msg or flag == "VSC":
                return "VIRTUAL SAFETY CAR"
            if "RED FLAG" in msg or flag == "RED":
                return "RED FLAG"
            if "YELLOW" in msg or flag == "YELLOW":
                return "YELLOW FLAG"
            if "CLEAR" in msg or flag == "CLEAR" or "RESUME" in msg:
                return "CLEAR"
            if "INVESTIGATION" in msg or "NOTED" in msg or "PENALTY" in msg:
                return "INVESTIGATION"
            return "INFO"

        df["FlagType"] = df.apply(_classify, axis=1)

        return df.reset_index(drop=True)
    except Exception:
        return None


# ── Multi-Format Telemetry Data Exporters ────────────────────────────────────

def _build_export_telemetry_df(driver: str, tel_df: pd.DataFrame | None, lap_obj: dict | pd.Series | None = None) -> pd.DataFrame | None:
    """Merge lap metadata, compound info, and sector times into a structured telemetry DataFrame."""
    if tel_df is None or (hasattr(tel_df, "empty") and tel_df.empty):
        return None
    try:
        export_cols = [c for c in
                       ["Distance", "Speed", "Throttle", "Brake", "RPM", "nGear", "DRS",
                        "X", "Y", "Z", "Time", "SessionTime"]
                       if c in tel_df.columns]
        df = tel_df[export_cols].copy()
        if "nGear" in df.columns:
            df = df.rename(columns={"nGear": "Gear"})

        # Resolve lap metadata
        lap_num = ""
        lap_time_str = ""
        compound_str = ""
        if lap_obj is not None:
            try:
                ln = lap_obj.get("LapNumber") if hasattr(lap_obj, "get") else getattr(lap_obj, "LapNumber", None)
                if ln is not None and pd.notna(ln):
                    lap_num = int(ln)
            except Exception:
                lap_num = ""
            try:
                lt = lap_obj.get("LapTime") if hasattr(lap_obj, "get") else getattr(lap_obj, "LapTime", None)
                if lt is not None and pd.notna(lt):
                    lap_time_str = format_laptime(lt)
            except Exception:
                lap_time_str = ""
            try:
                cmp_val = lap_obj.get("Compound") if hasattr(lap_obj, "get") else getattr(lap_obj, "Compound", None)
                if cmp_val is not None and pd.notna(cmp_val):
                    compound_str = str(cmp_val).title()
                else:
                    compound_str = "?"
            except Exception:
                compound_str = "?"

        df.insert(0, "Driver", str(driver))
        df.insert(1, "LapNumber", lap_num)
        df.insert(2, "LapTime", lap_time_str)
        df.insert(3, "Compound", compound_str)

        # Sector times formatted as seconds (3 dp)
        for _scol, _slabel in [
            ("Sector1Time", "Sector1Time_s"),
            ("Sector2Time", "Sector2Time_s"),
            ("Sector3Time", "Sector3Time_s"),
        ]:
            _sval = (lap_obj.get(_scol) if hasattr(lap_obj, "get") else getattr(lap_obj, _scol, None)) if lap_obj is not None else None
            try:
                _ssec = round(_sval.total_seconds(), 3) if _sval is not None and pd.notna(_sval) else ""
            except Exception:
                _ssec = ""
            df.insert(4, _slabel, _ssec)

        return df.reset_index(drop=True)
    except Exception:
        return None


def _build_export_csv(driver: str, tel_df: pd.DataFrame | None, lap_obj: dict | pd.Series | None = None) -> bytes:
    """Export unified telemetry and lap metadata as CSV bytes."""
    try:
        df = _build_export_telemetry_df(driver, tel_df, lap_obj)
        if df is None or df.empty:
            return b""
        return df.to_csv(index=False).encode("utf-8")
    except Exception:
        return b""


def _build_export_parquet(driver: str, tel_df: pd.DataFrame | None, lap_obj: dict | pd.Series | None = None) -> bytes:
    """Export unified telemetry and lap metadata as Apache Parquet binary bytes."""
    try:
        df = _build_export_telemetry_df(driver, tel_df, lap_obj)
        if df is None or df.empty:
            return b""
        df_pq = df.copy()
        # Coerce mixed/object metadata columns to string for clean Arrow schema serialization
        for col in ["Driver", "LapTime", "Compound"]:
            if col in df_pq.columns:
                df_pq[col] = df_pq[col].astype(str)
        # Convert numeric columns where possible
        for col in ["LapNumber", "Sector1Time_s", "Sector2Time_s", "Sector3Time_s"]:
            if col in df_pq.columns:
                df_pq[col] = pd.to_numeric(df_pq[col], errors="coerce")
        buf = io.BytesIO()
        df_pq.to_parquet(buf, index=False, engine="pyarrow")
        return buf.getvalue()
    except Exception:
        return b""


def _build_export_json(driver: str, tel_df: pd.DataFrame | None, lap_obj: dict | pd.Series | None = None, indent: int = 2) -> bytes:
    """Export unified telemetry and lap metadata as formatted JSON bytes."""
    try:
        df = _build_export_telemetry_df(driver, tel_df, lap_obj)
        if df is None or df.empty:
            return b""
        df_js = df.copy()
        # Convert timedeltas to float seconds for intuitive JSON consumption
        for t_col in ["Time", "SessionTime"]:
            if t_col in df_js.columns and pd.api.types.is_timedelta64_dtype(df_js[t_col]):
                df_js[t_col] = df_js[t_col].dt.total_seconds()
        return df_js.to_json(orient="records", indent=indent).encode("utf-8")
    except Exception:
        return b""


def _calculate_braking_metrics(df: pd.DataFrame | None, apex_dist: float) -> dict:
    """
    Calculate braking dynamics and trail-braking metrics around a circuit corner apex.
    Returns:
        dict with initial_brake_dist, peak_decel, trail_brake_release, trail_braking_dist,
        brake_to_throttle_ms, apex_speed, entry_speed, and df_processed.
    """
    metrics = {
        "initial_brake_dist": None,
        "peak_decel": None,
        "trail_brake_release": None,
        "trail_braking_dist": None,
        "brake_to_throttle_ms": None,
        "apex_speed": None,
        "entry_speed": None,
        "df_processed": None,
    }
    if df is None or df.empty or not {"Distance", "Speed", "Time"}.issubset(df.columns):
        return metrics

    try:
        df_calc = df.copy()
        df_calc["DistToApex"] = df_calc["Distance"] - apex_dist

        # Compute time delta in seconds
        if pd.api.types.is_timedelta64_dtype(df_calc["Time"]):
            dt = df_calc["Time"].dt.total_seconds().diff()
        else:
            dt = pd.to_numeric(df_calc["Time"], errors="coerce").diff()

        dt = dt.replace(0, np.nan)
        dv = df_calc["Speed"].diff() / 3.6  # km/h to m/s
        accel_ms2 = dv / dt
        # G force (negative is deceleration)
        df_calc["G_Force"] = (accel_ms2 / 9.81).rolling(window=3, min_periods=1, center=True).mean().clip(-6.0, 2.5)

        # Apex speed
        metrics["apex_speed"] = float(df_calc["Speed"].min())

        pre_apex = df_calc[df_calc["Distance"] <= apex_dist]
        if "Brake" in df_calc.columns and not pre_apex.empty:
            # Handle both boolean (0/1) and analog (0-100) Brake channels
            brake_thresh = 0 if df_calc["Brake"].max() <= 1.0 else 5
            brake_active = pre_apex[pre_apex["Brake"] > brake_thresh]

            if not brake_active.empty:
                init_brake = brake_active.iloc[0]
                init_d = float(init_brake["Distance"])
                metrics["initial_brake_dist"] = float(apex_dist - init_d)
                metrics["entry_speed"] = float(init_brake["Speed"])

                # Peak deceleration during braking phase
                braking_phase = df_calc[(df_calc["Distance"] >= init_d) & (df_calc["Distance"] <= apex_dist + 20)]
                if not braking_phase.empty and "G_Force" in braking_phase.columns and not braking_phase["G_Force"].isna().all():
                    metrics["peak_decel"] = float(braking_phase["G_Force"].min())

                # Trail braking release (first point after initial braking where brake <= threshold)
                after_init = pre_apex[pre_apex["Distance"] > init_d]
                brake_release = after_init[after_init["Brake"] <= brake_thresh]
                if not brake_release.empty:
                    release_pt = brake_release.iloc[0]
                    release_d = float(release_pt["Distance"])
                    metrics["trail_brake_release"] = float(apex_dist - release_d)
                    metrics["trail_braking_dist"] = float(release_d - init_d)

                    # Brake to throttle transition
                    after_release = df_calc[df_calc["Distance"] >= release_d]
                    if "Throttle" in after_release.columns:
                        throttle_active = after_release[after_release["Throttle"] > 5]
                        if not throttle_active.empty:
                            throttle_pt = throttle_active.iloc[0]
                            if pd.api.types.is_timedelta64_dtype(df_calc["Time"]):
                                trans_time = (throttle_pt["Time"] - release_pt["Time"]).total_seconds() * 1000.0
                            else:
                                trans_time = (float(throttle_pt["Time"]) - float(release_pt["Time"])) * 1000.0
                            if 0 <= trans_time <= 2500:
                                metrics["brake_to_throttle_ms"] = float(trans_time)

        metrics["df_processed"] = df_calc
        return metrics
    except Exception:
        return metrics


def _calculate_gear_shift_metrics(tel_df: pd.DataFrame | None) -> dict:
    """
    Calculate powertrain metrics, gear shift events, and gear usage distributions.
    Returns:
        dict with avg_rpm, max_rpm, total_upshifts, total_downshifts, total_shifts,
        short_shifts_count, redline_shifts_count, upshift_rpm_mean,
        gear_distribution (dict mapping gear 1..8 to % distance),
        shifts_df (DataFrame of individual shift events with Distance, RPM, Speed, from_gear, to_gear, type, is_short_shift),
        df_processed (DataFrame with Gear, RPM, Distance).
    """
    default_dist = {g: 0.0 for g in range(1, 9)}
    metrics = {
        "avg_rpm": None,
        "max_rpm": None,
        "total_upshifts": 0,
        "total_downshifts": 0,
        "total_shifts": 0,
        "short_shifts_count": 0,
        "redline_shifts_count": 0,
        "upshift_rpm_mean": None,
        "gear_distribution": default_dist,
        "shifts_df": pd.DataFrame(),
        "df_processed": None,
    }
    if tel_df is None or tel_df.empty:
        return metrics

    try:
        df = tel_df.copy()
        gear_col = "Gear" if "Gear" in df.columns else ("nGear" if "nGear" in df.columns else None)
        if not gear_col or "RPM" not in df.columns or "Distance" not in df.columns:
            return metrics

        df["Gear"] = pd.to_numeric(df[gear_col], errors="coerce").fillna(0).astype(int)
        df["RPM"] = pd.to_numeric(df["RPM"], errors="coerce")
        df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")
        df = df.dropna(subset=["RPM", "Distance"]).reset_index(drop=True)

        if df.empty:
            return metrics

        valid_rpm = df[df["RPM"] > 2000]["RPM"]
        if not valid_rpm.empty:
            metrics["avg_rpm"] = float(valid_rpm.mean())
            metrics["max_rpm"] = float(valid_rpm.max())
        else:
            metrics["avg_rpm"] = float(df["RPM"].mean())
            metrics["max_rpm"] = float(df["RPM"].max())

        df["Dist_Delta"] = df["Distance"].diff().fillna(0).clip(lower=0)
        total_dist = df["Dist_Delta"].sum()
        gear_dist = {}
        if total_dist > 0:
            for g in range(1, 9):
                g_dist = df[df["Gear"] == g]["Dist_Delta"].sum()
                gear_dist[g] = round(float((g_dist / total_dist) * 100.0), 1)
        else:
            gear_dist = default_dist
        metrics["gear_distribution"] = gear_dist

        df["Gear_Diff"] = df["Gear"].diff().fillna(0).astype(int)
        shift_indices = df[df["Gear_Diff"] != 0].index.tolist()

        shifts_records = []
        short_shifts = 0
        redline_shifts = 0
        upshift_rpms = []

        for idx in shift_indices:
            if idx == 0:
                continue
            prev_gear = int(df.loc[idx - 1, "Gear"])
            new_gear = int(df.loc[idx, "Gear"])
            if prev_gear == new_gear or prev_gear <= 0 or new_gear <= 0:
                continue

            dist = float(df.loc[idx, "Distance"])
            speed = float(df.loc[idx, "Speed"]) if "Speed" in df.columns else 0.0
            rpm_pre = float(df.loc[idx - 1, "RPM"])
            rpm_post = float(df.loc[idx, "RPM"])
            throttle = float(df.loc[idx - 1, "Throttle"]) if "Throttle" in df.columns else 100.0

            if new_gear > prev_gear:
                shift_type = "upshift"
                upshift_rpms.append(rpm_pre)
                is_short = bool(rpm_pre < 11000 and throttle > 60 and prev_gear >= 2)
                is_redline = bool(rpm_pre >= 11800)
                if is_short:
                    short_shifts += 1
                if is_redline:
                    redline_shifts += 1
            else:
                shift_type = "downshift"
                is_short = False
                is_redline = False

            shifts_records.append({
                "Distance": dist,
                "Speed": speed,
                "RPM": rpm_pre,
                "RPM_Post": rpm_post,
                "from_gear": prev_gear,
                "to_gear": new_gear,
                "type": shift_type,
                "is_short_shift": is_short,
                "is_redline": is_redline,
            })

        shifts_df = pd.DataFrame(shifts_records)
        metrics["shifts_df"] = shifts_df

        upshifts_count = len([s for s in shifts_records if s["type"] == "upshift"])
        downshifts_count = len([s for s in shifts_records if s["type"] == "downshift"])
        metrics["total_upshifts"] = upshifts_count
        metrics["total_downshifts"] = downshifts_count
        metrics["total_shifts"] = upshifts_count + downshifts_count
        metrics["short_shifts_count"] = short_shifts
        metrics["redline_shifts_count"] = redline_shifts

        if upshift_rpms:
            metrics["upshift_rpm_mean"] = float(np.mean(upshift_rpms))

        metrics["df_processed"] = df
        return metrics
    except Exception:
        return metrics


# ── Speed Trap & Intermediate Velocity Radar Breakdown ─────────────────────

POWER_UNIT_SUPPLIERS: dict[str, str] = {
    # Ferrari
    "Ferrari": "Ferrari",
    "Scuderia Ferrari": "Ferrari",
    "Haas": "Ferrari",
    "Haas F1 Team": "Ferrari",
    "MoneyGram Haas F1 Team": "Ferrari",
    "Sauber": "Ferrari",
    "Alfa Romeo": "Ferrari",
    "Alfa Romeo Racing": "Ferrari",
    "Alfa Romeo F1 Team Stake": "Ferrari",
    "Kick Sauber": "Ferrari",
    "Stake F1 Team Kick Sauber": "Ferrari",

    # Mercedes
    "Mercedes": "Mercedes",
    "Mercedes-AMG PETRONAS F1 Team": "Mercedes",
    "Mercedes-AMG Petronas": "Mercedes",
    "McLaren": "Mercedes",
    "McLaren F1 Team": "Mercedes",
    "Aston Martin": "Mercedes",
    "Aston Martin Aramco F1 Team": "Mercedes",
    "Racing Point": "Mercedes",
    "Force India": "Mercedes",
    "Williams": "Mercedes",
    "Williams Racing": "Mercedes",

    # Red Bull Powertrains / Honda
    "Red Bull": "Red Bull Powertrains",
    "Red Bull Racing": "Red Bull Powertrains",
    "Oracle Red Bull Racing": "Red Bull Powertrains",
    "AlphaTauri": "Red Bull Powertrains",
    "Scuderia AlphaTauri": "Red Bull Powertrains",
    "RB": "Red Bull Powertrains",
    "Visa Cash App RB F1 Team": "Red Bull Powertrains",
    "Racing Bulls": "Red Bull Powertrains",
    "Toro Rosso": "Red Bull Powertrains",
    "Scuderia Toro Rosso": "Red Bull Powertrains",

    # Renault
    "Alpine": "Renault",
    "BWT Alpine F1 Team": "Renault",
    "Alpine F1 Team": "Renault",
    "Renault": "Renault",
    "Renault F1 Team": "Renault",
}


def get_power_unit_supplier(constructor: str) -> str:
    """Return the Power Unit manufacturer for an F1 constructor."""
    if not constructor or pd.isna(constructor):
        return "Unknown"
    c_clean = str(constructor).strip()
    if c_clean in POWER_UNIT_SUPPLIERS:
        return POWER_UNIT_SUPPLIERS[c_clean]
    c_lower = c_clean.lower()
    for key, pu in POWER_UNIT_SUPPLIERS.items():
        if key.lower() in c_lower:
            return pu
    return c_clean


@st.cache_data(show_spinner=False, ttl=3600)
def _calculate_speed_trap_metrics(sess_k: str, laps_df: pd.DataFrame) -> dict:
    """
    Extract maximum velocities recorded at SpeedST, SpeedI1, SpeedI2, and SpeedFL.
    Separates DRS-assisted vs non-DRS speed traps and aggregates metrics across
    drivers, constructors, and power unit manufacturers.
    """
    fallback = {
        "drivers_df": pd.DataFrame(),
        "constructor_summary": pd.DataFrame(),
        "power_unit_summary": pd.DataFrame(),
        "leaders": {},
        "sensors": ["SpeedST", "SpeedI1", "SpeedI2", "SpeedFL"],
        "has_data": False,
    }
    try:
        if laps_df is None or laps_df.empty:
            return fallback

        laps = laps_df.copy()
        if "Driver" not in laps.columns:
            return fallback

        sensors = ["SpeedST", "SpeedI1", "SpeedI2", "SpeedFL"]
        avail_sensors = [s for s in sensors if s in laps.columns and laps[s].dropna().any()]
        if not avail_sensors:
            return fallback

        records = []
        for drv, grp in laps.groupby("Driver"):
            team = "Unknown"
            if "Team" in grp.columns:
                teams = grp["Team"].dropna()
                if not teams.empty:
                    team = str(teams.iloc[0])

            pu = get_power_unit_supplier(team)

            rec = {
                "Driver": str(drv),
                "Team": team,
                "PowerUnit": pu,
            }

            speeds_for_max = []
            for s in sensors:
                if s in grp.columns:
                    s_vals = grp[s].dropna()
                    max_s = float(s_vals.max()) if not s_vals.empty else np.nan
                else:
                    max_s = np.nan
                rec[s] = max_s
                if pd.notna(max_s):
                    speeds_for_max.append(max_s)

            rec["OverallMax"] = max(speeds_for_max) if speeds_for_max else np.nan

            # DRS vs Non-DRS speed trap
            drs_st_max = np.nan
            non_drs_st_max = np.nan
            drs_delta = np.nan

            if "SpeedST" in grp.columns:
                if "DRS" in grp.columns:
                    drs_num = pd.to_numeric(grp["DRS"], errors="coerce")
                    drs_mask = (drs_num >= 10) | (drs_num == 1) | (grp["DRS"] == True)
                    drs_laps = grp.loc[drs_mask, "SpeedST"].dropna()
                    non_drs_laps = grp.loc[~drs_mask, "SpeedST"].dropna()
                    if not drs_laps.empty:
                        drs_st_max = float(drs_laps.max())
                    if not non_drs_laps.empty:
                        non_drs_st_max = float(non_drs_laps.max())
                    if pd.notna(drs_st_max) and pd.notna(non_drs_st_max):
                        drs_delta = drs_st_max - non_drs_st_max

            rec["SpeedST_DRS"] = drs_st_max
            rec["SpeedST_NoDRS"] = non_drs_st_max
            rec["DRS_Delta"] = drs_delta

            records.append(rec)

        if not records:
            return fallback

        drivers_df = pd.DataFrame(records)
        # Sort primarily by SpeedST descending, then by OverallMax
        sort_col = "SpeedST" if "SpeedST" in drivers_df.columns and drivers_df["SpeedST"].notna().any() else "OverallMax"
        drivers_df = drivers_df.sort_values(by=[sort_col, "OverallMax"], ascending=[False, False]).reset_index(drop=True)
        drivers_df["Pos"] = drivers_df.index + 1

        # Constructor aggregation
        cons_records = []
        for team, cgrp in drivers_df.groupby("Team"):
            pu = get_power_unit_supplier(team)
            c_rec = {
                "Team": team,
                "PowerUnit": pu,
                "DriverCount": len(cgrp),
            }
            for s in sensors:
                c_rec[f"{s}_Max"] = cgrp[s].max()
                c_rec[f"{s}_Mean"] = cgrp[s].mean()
            c_rec["OverallMax"] = cgrp["OverallMax"].max()
            cons_records.append(c_rec)

        cons_df = pd.DataFrame(cons_records)
        if not cons_df.empty:
            c_sort = "SpeedST_Max" if "SpeedST_Max" in cons_df.columns and cons_df["SpeedST_Max"].notna().any() else "OverallMax"
            cons_df = cons_df.sort_values(by=c_sort, ascending=False).reset_index(drop=True)

        # Power unit aggregation
        pu_records = []
        for pu, pugrp in drivers_df.groupby("PowerUnit"):
            pu_rec = {
                "PowerUnit": pu,
                "DriverCount": len(pugrp),
                "Teams": ", ".join(sorted(pugrp["Team"].unique())),
            }
            for s in sensors:
                pu_rec[f"{s}_Max"] = pugrp[s].max()
                pu_rec[f"{s}_Mean"] = pugrp[s].mean()
            pu_rec["OverallMax"] = pugrp["OverallMax"].max()
            pu_records.append(pu_rec)

        pu_df = pd.DataFrame(pu_records)
        if not pu_df.empty:
            pu_sort = "SpeedST_Mean" if "SpeedST_Mean" in pu_df.columns and pu_df["SpeedST_Mean"].notna().any() else "OverallMax"
            pu_df = pu_df.sort_values(by=pu_sort, ascending=False).reset_index(drop=True)

        # Leaders computation
        leaders = {}
        for s in sensors:
            valid_s = drivers_df.dropna(subset=[s])
            if not valid_s.empty:
                best_row = valid_s.loc[valid_s[s].idxmax()]
                leaders[s] = {
                    "Driver": str(best_row["Driver"]),
                    "Team": str(best_row["Team"]),
                    "Speed": float(best_row[s]),
                }
            else:
                leaders[s] = None

        valid_max = drivers_df.dropna(subset=["OverallMax"])
        if not valid_max.empty:
            best_ov = valid_max.loc[valid_max["OverallMax"].idxmax()]
            leaders["Overall"] = {
                "Driver": str(best_ov["Driver"]),
                "Team": str(best_ov["Team"]),
                "Speed": float(best_ov["OverallMax"]),
            }
        else:
            leaders["Overall"] = None

        if not pu_df.empty and "SpeedST_Mean" in pu_df.columns and pu_df["SpeedST_Mean"].notna().any():
            top_pu_row = pu_df.loc[pu_df["SpeedST_Mean"].idxmax()]
            leaders["TopPU"] = {
                "PowerUnit": str(top_pu_row["PowerUnit"]),
                "SpeedMean": float(top_pu_row["SpeedST_Mean"]),
            }
        else:
            leaders["TopPU"] = None

        valid_drs = drivers_df.dropna(subset=["DRS_Delta"])
        if not valid_drs.empty:
            best_drs = valid_drs.loc[valid_drs["DRS_Delta"].idxmax()]
            leaders["MaxDRSDelta"] = {
                "Driver": str(best_drs["Driver"]),
                "Team": str(best_drs["Team"]),
                "Delta": float(best_drs["DRS_Delta"]),
            }
        else:
            leaders["MaxDRSDelta"] = None

        return {
            "drivers_df": drivers_df,
            "constructor_summary": cons_df,
            "power_unit_summary": pu_df,
            "leaders": leaders,
            "sensors": sensors,
            "has_data": True,
        }
    except Exception:
        return fallback


# ── Intra-Team Teammate Battle & Qualifying Delta Matrix ───────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _build_teammate_battle_data(
    sess_k: str,
    laps_df: pd.DataFrame | None,
    _session_obj=None
) -> dict | None:
    """
    Extract and compute intra-team teammate head-to-head comparison analytics.
    Pairs drivers by constructor, calculating qualifying lap gaps (seconds & percentage),
    sector split advantages (S1, S2, S3), clean-air median race pace deltas, and finishing positions.
    """
    fallback = {
        "pairs": [],
        "summary": {
            "closest_battle": None,
            "largest_delta": None,
            "median_delta_s": 0.0,
            "median_delta_pct": 0.0,
            "most_dominant_driver": None,
            "total_teams": 0,
        },
        "has_data": False,
    }
    if laps_df is None or laps_df.empty:
        return fallback

    try:
        laps = laps_df.copy()
        if "Driver" not in laps.columns:
            return fallback

        # 1. Resolve Driver <-> Team mappings and results metadata
        results_df = None
        if _session_obj is not None and hasattr(_session_obj, "results") and _session_obj.results is not None and not _session_obj.results.empty:
            results_df = pd.DataFrame(_session_obj.results).copy()

        # Build driver metadata lookup
        driver_meta: dict[str, dict] = {}
        if results_df is not None and not results_df.empty:
            for _, r in results_df.iterrows():
                abbr = str(r.get("Abbreviation", "")).strip()
                num = str(r.get("DriverNumber", "")).strip()
                full_name = str(r.get("FullName", "")).strip() or abbr or num
                team = str(r.get("TeamName", "")).strip() or str(r.get("Team", "")).strip() or "Unknown"
                pos = r.get("Position", np.nan)
                grid = r.get("GridPosition", np.nan)
                
                # Check for Q1, Q2, Q3 times
                q_best_s = None
                for q_col in ["Q3", "Q2", "Q1"]:
                    if q_col in r and pd.notna(r[q_col]):
                        try:
                            val = r[q_col]
                            if hasattr(val, "total_seconds"):
                                q_sec = val.total_seconds()
                            else:
                                q_sec = pd.to_timedelta(val).total_seconds()
                            if q_sec and q_sec > 0:
                                q_best_s = q_sec
                                break
                        except Exception:
                            pass

                entry = {
                    "abbr": abbr,
                    "number": num,
                    "name": full_name,
                    "team": team,
                    "pos": int(pos) if pd.notna(pos) else None,
                    "grid": int(grid) if pd.notna(grid) else None,
                    "q_best_s": q_best_s,
                }
                if abbr:
                    driver_meta[abbr] = entry
                if num:
                    driver_meta[num] = entry

        # Group laps by Team and Driver
        if "Team" not in laps.columns and results_df is not None:
            # Map Team from results into laps
            team_map = {}
            for k, v in driver_meta.items():
                if v.get("team"):
                    team_map[k] = v["team"]
            laps["Team"] = laps["Driver"].astype(str).map(team_map).fillna("Unknown")
        elif "Team" not in laps.columns:
            laps["Team"] = "Unknown"

        # Unique teams (excluding Unknown / empty)
        teams = [t for t in laps["Team"].dropna().unique() if t and t != "Unknown"]
        if not teams and results_df is not None:
            teams = [t for t in results_df["TeamName"].dropna().unique() if t and t != "Unknown"]

        if not teams:
            return fallback

        # Helper to convert timedelta to float seconds
        def _to_sec(td) -> float | None:
            if td is None or pd.isna(td):
                return None
            try:
                if hasattr(td, "total_seconds"):
                    s = float(td.total_seconds())
                else:
                    s = float(pd.to_timedelta(td).total_seconds())
                return s if s > 0 else None
            except Exception:
                return None

        # Pre-calculate per-driver lap & sector stats
        laps["LapTime_s"] = laps["LapTime"].apply(_to_sec)
        laps["S1_s"] = laps["Sector1Time"].apply(_to_sec) if "Sector1Time" in laps.columns else None
        laps["S2_s"] = laps["Sector2Time"].apply(_to_sec) if "Sector2Time" in laps.columns else None
        laps["S3_s"] = laps["Sector3Time"].apply(_to_sec) if "Sector3Time" in laps.columns else None

        driver_stats: dict[str, dict] = {}
        for drv, grp in laps.groupby("Driver"):
            drv_str = str(drv)
            valid_laps = grp.dropna(subset=["LapTime_s"])
            best_lap = float(valid_laps["LapTime_s"].min()) if not valid_laps.empty else None
            best_s1 = float(grp["S1_s"].dropna().min()) if "S1_s" in grp and not grp["S1_s"].dropna().empty else None
            best_s2 = float(grp["S2_s"].dropna().min()) if "S2_s" in grp and not grp["S2_s"].dropna().empty else None
            best_s3 = float(grp["S3_s"].dropna().min()) if "S3_s" in grp and not grp["S3_s"].dropna().empty else None

            # Clean flyer laps for race pace
            clean_laps = grp.copy()
            if "PitInTime" in clean_laps.columns:
                clean_laps = clean_laps[clean_laps["PitInTime"].isna()]
            if "PitOutTime" in clean_laps.columns:
                clean_laps = clean_laps[clean_laps["PitOutTime"].isna()]
            if "TrackStatus" in clean_laps.columns:
                clean_laps = clean_laps[~clean_laps["TrackStatus"].astype(str).str.contains("4|5|6|7", regex=True)]

            clean_laps = clean_laps.dropna(subset=["LapTime_s"])
            if not clean_laps.empty:
                med_t = clean_laps["LapTime_s"].median()
                clean_laps = clean_laps[clean_laps["LapTime_s"] <= med_t * 1.25]

            med_race_pace = float(clean_laps["LapTime_s"].median()) if not clean_laps.empty else None

            driver_stats[drv_str] = {
                "best_lap_s": best_lap,
                "best_s1": best_s1,
                "best_s2": best_s2,
                "best_s3": best_s3,
                "median_race_pace": med_race_pace,
                "clean_laps_count": len(clean_laps),
                "total_laps": len(grp),
            }

        pairs = []
        valid_deltas_s = []
        valid_deltas_pct = []

        for team in sorted(teams):
            team_laps = laps[laps["Team"] == team]
            team_drvs = team_laps["Driver"].astype(str).unique().tolist()

            # Also check results for drivers from this team
            if results_df is not None and not results_df.empty:
                t_col = "TeamName" if "TeamName" in results_df.columns else "Team"
                r_drvs = results_df[results_df[t_col] == team]
                for _, r_row in r_drvs.iterrows():
                    cand = str(r_row.get("Abbreviation", "")).strip() or str(r_row.get("DriverNumber", "")).strip()
                    if cand and cand not in team_drvs:
                        team_drvs.append(cand)

            if len(team_drvs) < 2:
                continue

            # If more than 2 drivers, select top 2 by classification or laps count
            if len(team_drvs) > 2:
                def _drv_rank(d: str) -> tuple[int, int]:
                    meta = driver_meta.get(d, {})
                    pos = meta.get("pos") if meta.get("pos") is not None else 99
                    st = driver_stats.get(d, {})
                    l_count = st.get("total_laps", 0)
                    return (pos, -l_count)

                team_drvs = sorted(team_drvs, key=_drv_rank)[:2]

            d_a, d_b = team_drvs[0], team_drvs[1]
            st_a = driver_stats.get(d_a, {})
            st_b = driver_stats.get(d_b, {})
            meta_a = driver_meta.get(d_a, {})
            meta_b = driver_meta.get(d_b, {})

            # Determine best qualifying lap (favor Q results if available, else best flyer)
            q_a = meta_a.get("q_best_s") or st_a.get("best_lap_s")
            q_b = meta_b.get("q_best_s") or st_b.get("best_lap_s")

            # Determine who is driver 1 (the faster/higher-ranked driver)
            # Default to d_a as driver 1 unless d_b is demonstrably faster
            invert = False
            if q_a is not None and q_b is not None:
                if q_b < q_a:
                    invert = True
            elif meta_a.get("pos") is not None and meta_b.get("pos") is not None:
                if meta_b["pos"] < meta_a["pos"]:
                    invert = True
            elif st_a.get("best_lap_s") is not None and st_b.get("best_lap_s") is not None:
                if st_b["best_lap_s"] < st_a["best_lap_s"]:
                    invert = True

            if invert:
                d1, d2 = d_b, d_a
                st1, st2 = st_b, st_a
                meta1, meta2 = meta_b, meta_a
                q1, q2 = q_b, q_a
            else:
                d1, d2 = d_a, d_b
                st1, st2 = st_a, st_b
                meta1, meta2 = meta_a, meta_b
                q1, q2 = q_a, q_b

            # Compute deltas
            qual_delta_s = None
            qual_delta_pct = None
            if q1 is not None and q2 is not None:
                qual_delta_s = round(float(q2 - q1), 3)
                if q1 > 0:
                    qual_delta_pct = round(float((qual_delta_s / q1) * 100.0), 2)
                valid_deltas_s.append(abs(qual_delta_s))
                if qual_delta_pct is not None:
                    valid_deltas_pct.append(abs(qual_delta_pct))

            # Sector comparison
            s1_1, s1_2 = st1.get("best_s1"), st2.get("best_s1")
            s2_1, s2_2 = st1.get("best_s2"), st2.get("best_s2")
            s3_1, s3_2 = st1.get("best_s3"), st2.get("best_s3")

            def _comp_s(val1, val2) -> tuple[str, float | None]:
                if val1 is None or val2 is None:
                    return ("TIE", None)
                diff = round(val2 - val1, 3)
                if diff > 0.001:
                    return (d1, diff)
                elif diff < -0.001:
                    return (d2, abs(diff))
                return ("TIE", 0.0)

            s1_adv, s1_delta = _comp_s(s1_1, s1_2)
            s2_adv, s2_delta = _comp_s(s2_1, s2_2)
            s3_adv, s3_delta = _comp_s(s3_1, s3_2)

            # Dominance tally
            d1_sector_wins = sum(1 for adv in [s1_adv, s2_adv, s3_adv] if adv == d1)
            d2_sector_wins = sum(1 for adv in [s1_adv, s2_adv, s3_adv] if adv == d2)

            # Race pace delta
            p1 = st1.get("median_race_pace")
            p2 = st2.get("median_race_pace")
            race_pace_delta_s = None
            if p1 is not None and p2 is not None:
                race_pace_delta_s = round(float(p2 - p1), 3)

            # Pos delta
            pos1 = meta1.get("pos")
            pos2 = meta2.get("pos")
            pos_delta = (pos2 - pos1) if (pos1 is not None and pos2 is not None) else None

            # Team colour
            t_colour = get_constructor_colour(team) or "#00E5FF"

            def _fmt_lap(s: float | None) -> str:
                if s is None or pd.isna(s):
                    return "—"
                m = int(s // 60)
                sec = s % 60
                return f"{m}:{sec:06.3f}" if m > 0 else f"{sec:.3f}s"

            pairs.append({
                "team": team,
                "team_colour": t_colour,
                "driver1": {
                    "code": d1,
                    "name": meta1.get("name", d1),
                    "pos": pos1,
                    "grid": meta1.get("grid"),
                    "best_lap_s": q1,
                    "best_lap_str": _fmt_lap(q1),
                    "s1": s1_1,
                    "s2": s2_1,
                    "s3": s3_1,
                    "median_race_pace": p1,
                    "median_race_pace_str": _fmt_lap(p1),
                    "clean_laps_count": st1.get("clean_laps_count", 0),
                },
                "driver2": {
                    "code": d2,
                    "name": meta2.get("name", d2),
                    "pos": pos2,
                    "grid": meta2.get("grid"),
                    "best_lap_s": q2,
                    "best_lap_str": _fmt_lap(q2),
                    "s1": s1_2,
                    "s2": s2_2,
                    "s3": s3_3 if (s3_3 := st2.get("best_s3")) is not None else None,
                    "median_race_pace": p2,
                    "median_race_pace_str": _fmt_lap(p2),
                    "clean_laps_count": st2.get("clean_laps_count", 0),
                },
                "faster_driver": d1,
                "trailing_driver": d2,
                "qual_delta_s": qual_delta_s,
                "qual_delta_pct": qual_delta_pct,
                "s1_advantage": s1_adv,
                "s1_delta": s1_delta,
                "s2_advantage": s2_adv,
                "s2_delta": s2_delta,
                "s3_advantage": s3_adv,
                "s3_delta": s3_delta,
                "d1_sector_wins": d1_sector_wins,
                "d2_sector_wins": d2_sector_wins,
                "sector_dominance": f"{d1} ({d1_sector_wins}–{d2_sector_wins})",
                "race_pace_delta_s": race_pace_delta_s,
                "pos_delta": pos_delta,
                "has_race_data": bool(p1 is not None and p2 is not None),
                "has_qual_data": bool(qual_delta_s is not None),
            })

        if not pairs:
            return fallback

        # Sort pairs by constructor ranking or delta
        pairs.sort(key=lambda p: (
            p["driver1"]["pos"] if p["driver1"]["pos"] is not None else 99,
            p["qual_delta_s"] if p["qual_delta_s"] is not None else 99
        ))

        # Grid summary calculations
        closest_battle = None
        largest_delta = None

        pairs_with_qual = [p for p in pairs if p["qual_delta_s"] is not None]
        if pairs_with_qual:
            closest_battle = min(pairs_with_qual, key=lambda p: abs(p["qual_delta_s"]))
            largest_delta = max(pairs_with_qual, key=lambda p: abs(p["qual_delta_s"]))

        # Most dominant driver (most sector wins & largest delta)
        most_dominant = None
        if pairs_with_qual:
            most_dominant = max(pairs_with_qual, key=lambda p: (p["d1_sector_wins"], p["qual_delta_s"] or 0))

        median_delta_s = round(float(np.median(valid_deltas_s)), 3) if valid_deltas_s else 0.0
        median_delta_pct = round(float(np.median(valid_deltas_pct)), 2) if valid_deltas_pct else 0.0

        return {
            "pairs": pairs,
            "summary": {
                "closest_battle": closest_battle,
                "largest_delta": largest_delta,
                "median_delta_s": median_delta_s,
                "median_delta_pct": median_delta_pct,
                "most_dominant_driver": most_dominant,
                "total_teams": len(pairs),
            },
            "has_data": True,
        }
    except Exception:
        return fallback


# ── Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown ────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _build_pit_transit_data(
    sess_k: str,
    laps_df: pd.DataFrame,
    sess_obj=None,
    driver: str | None = None
) -> dict:
    """Decompose pit lane time loss into in-lap, pit lane transit, and out-lap warm-up.

    Evaluates the complete pit cycle:
    - Clean-air racing pace baseline: Median of valid flying laps (no pit in/out,
      accurate laps, green flag status, <= 107% median pace).
    - In-lap delta: Delta between in-lap time and racing baseline (entry deceleration & pit approach).
    - Pit lane transit duration: Timestamp difference between PitOutTime and PitInTime.
    - Out-lap delta: Delta between out-lap time and racing baseline (pit exit acceleration & cold tyre warm-up).
    - Net Total Pit Loss: Total time surrendered relative to 2 racing laps:
      ``TotalPitDelta = (t_in + t_out) - 2 * t_baseline``.
    - Sector warm-up breakdown: S1, S2, S3 deltas on the out-lap vs clean sector baselines.

    Parameters
    ----------
    sess_k : str
        Session cache key (e.g. "2024_British Grand Prix_R").
    laps_df : pd.DataFrame
        Session laps DataFrame.
    sess_obj : fastf1.core.Session, optional
        Official session object containing results and team metadata.
    driver : str, optional
        Specific driver filter, or None for grid-wide evaluation.

    Returns
    -------
    dict
        Structured dictionary containing all pit stops, driver stops map,
        summary KPIs, and status flags.
    """
    fallback = {
        "all_stops": [],
        "driver_stops": {},
        "summary": {
            "fastest_pit_lane": None,
            "best_in_lap": None,
            "best_out_lap": None,
            "lowest_net_pit_loss": None,
            "grid_median_pit_loss": None,
            "grid_median_pit_lane": None,
            "total_stops": 0,
        },
        "has_data": False,
    }

    if laps_df is None or laps_df.empty:
        return fallback

    def _to_sec(val) -> float | None:
        if val is None or pd.isna(val):
            return None
        if hasattr(val, "total_seconds"):
            try:
                return round(float(val.total_seconds()), 3)
            except Exception:
                pass
        try:
            f = float(val)
            return round(f, 3) if not np.isnan(f) else None
        except Exception:
            return None

    try:
        df = laps_df.copy()

        # Build driver and constructor metadata lookup
        driver_meta = {}
        if sess_obj is not None and hasattr(sess_obj, "results") and sess_obj.results is not None:
            for _, r in sess_obj.results.iterrows():
                d_code = str(r.get("Abbreviation") or r.get("DriverNumber") or r.get("BroadcastName", ""))
                t_name = str(r.get("TeamName") or "Unknown")
                driver_meta[d_code] = {
                    "team": t_name,
                    "team_colour": TEAM_COLOURS.get(t_name, "#ffffff"),
                    "full_name": str(r.get("FullName") or d_code),
                    "pos": int(r["Position"]) if pd.notna(r.get("Position")) else None,
                }

        unique_drivers = df["Driver"].dropna().unique()

        # Phase 1: Compute baseline racing pace and sector baselines per driver
        driver_baselines = {}
        grid_lap_times = []

        for d in unique_drivers:
            d_laps = df[df["Driver"] == d].copy()
            clean = d_laps[d_laps["PitInTime"].isna() & d_laps["PitOutTime"].isna()].copy()
            if "IsAccurate" in clean.columns:
                acc = clean[clean["IsAccurate"] == True]
                if not acc.empty:
                    clean = acc
            if "TrackStatus" in clean.columns:
                clear = clean[clean["TrackStatus"].astype(str).str.contains("^[1]$", regex=True, na=True)]
                if not clear.empty:
                    clean = clear

            lap_secs = [_to_sec(t) for t in clean["LapTime"] if _to_sec(t) is not None]
            if len(lap_secs) >= 3:
                med_val = float(np.median(lap_secs))
                lap_secs = [t for t in lap_secs if t <= 1.07 * med_val]

            base_lap = round(float(np.median(lap_secs)), 3) if lap_secs else None
            if base_lap is not None:
                grid_lap_times.append(base_lap)

            # Sector baselines
            s1_secs = [_to_sec(t) for t in clean.get("Sector1Time", []) if _to_sec(t) is not None]
            s2_secs = [_to_sec(t) for t in clean.get("Sector2Time", []) if _to_sec(t) is not None]
            s3_secs = [_to_sec(t) for t in clean.get("Sector3Time", []) if _to_sec(t) is not None]

            driver_baselines[d] = {
                "base_lap_s": base_lap,
                "base_s1": round(float(np.median(s1_secs)), 3) if s1_secs else None,
                "base_s2": round(float(np.median(s2_secs)), 3) if s2_secs else None,
                "base_s3": round(float(np.median(s3_secs)), 3) if s3_secs else None,
            }

        grid_median_lap = round(float(np.median(grid_lap_times)), 3) if grid_lap_times else None

        # Phase 2: Detect pit stop sequences and evaluate losses
        all_stops = []
        driver_stops = {}

        for d in unique_drivers:
            d_laps = df[df["Driver"] == d].sort_values("LapNumber").reset_index(drop=True)
            meta = driver_meta.get(d, {})
            team_name = meta.get("team") or str(d_laps["Team"].iloc[0] if "Team" in d_laps.columns else "Unknown")
            team_col = meta.get("team_colour") or TEAM_COLOURS.get(team_name, "#ffffff")
            full_name = meta.get("full_name") or d

            base_info = driver_baselines.get(d, {})
            d_base_lap = base_info.get("base_lap_s") or grid_median_lap
            d_base_s1 = base_info.get("base_s1")
            d_base_s2 = base_info.get("base_s2")
            d_base_s3 = base_info.get("base_s3")

            d_stops = []
            stop_idx = 0
            handled_out_idx = -1

            for i in range(len(d_laps)):
                if i <= handled_out_idx:
                    continue

                row_in = d_laps.iloc[i]
                has_pit_in = pd.notna(row_in.get("PitInTime"))
                has_pit_out = pd.notna(row_in.get("PitOutTime"))

                if has_pit_in:
                    stop_idx += 1
                    in_lap_num = int(row_in["LapNumber"])
                    in_lap_time_s = _to_sec(row_in.get("LapTime"))

                    # Identify out-lap (next lap)
                    row_out = d_laps.iloc[i + 1] if i + 1 < len(d_laps) else None
                    if row_out is not None:
                        handled_out_idx = i + 1
                    out_lap_num = int(row_out["LapNumber"]) if row_out is not None else in_lap_num + 1
                    out_lap_time_s = _to_sec(row_out.get("LapTime")) if row_out is not None else None
                elif has_pit_out and i > 0:
                    # Fallback when PitInTime is missing but PitOutTime is present on out-lap
                    stop_idx += 1
                    row_out = row_in
                    row_in = d_laps.iloc[i - 1]
                    in_lap_num = int(row_in["LapNumber"])
                    in_lap_time_s = _to_sec(row_in.get("LapTime"))
                    out_lap_num = int(row_out["LapNumber"])
                    out_lap_time_s = _to_sec(row_out.get("LapTime"))
                else:
                    continue

                # Pit lane transit duration
                pit_lane_time_s = None
                if row_out is not None and pd.notna(row_out.get("PitOutTime")) and pd.notna(row_in.get("PitInTime")):
                    try:
                        dur = (row_out["PitOutTime"] - row_in["PitInTime"]).total_seconds()
                        if 3.0 <= dur <= 300.0:
                            pit_lane_time_s = round(float(dur), 3)
                    except Exception:
                        pass
                elif pd.notna(row_in.get("PitOutTime")) and pd.notna(row_in.get("PitInTime")):
                    try:
                        dur = (row_in["PitOutTime"] - row_in["PitInTime"]).total_seconds()
                        if 3.0 <= dur <= 300.0:
                            pit_lane_time_s = round(float(dur), 3)
                    except Exception:
                        pass

                # Compound transitions
                old_cmp = str(row_in.get("Compound", "?")).upper()
                new_cmp = str(row_out.get("Compound", "?")).upper() if row_out is not None else "?"

                # In-lap delta (time lost entering pit)
                in_lap_delta_s = None
                if in_lap_time_s is not None and d_base_lap is not None:
                    in_lap_delta_s = round(float(in_lap_time_s - d_base_lap), 3)

                # Out-lap delta (time lost exiting and warming cold tyres)
                out_lap_delta_s = None
                if out_lap_time_s is not None and d_base_lap is not None:
                    out_lap_delta_s = round(float(out_lap_time_s - d_base_lap), 3)

                # Net total pit loss: (t_in + t_out) - 2 * t_baseline
                net_pit_loss_s = None
                if in_lap_delta_s is not None and out_lap_delta_s is not None:
                    net_pit_loss_s = round(float(in_lap_delta_s + out_lap_delta_s), 3)
                elif pit_lane_time_s is not None:
                    # Fallback estimate: pit lane transit + estimated entry/exit delta
                    net_pit_loss_s = round(float(pit_lane_time_s + (in_lap_delta_s or 3.0)), 3)

                # Out-lap cold tyre sector breakdown
                out_s1 = _to_sec(row_out.get("Sector1Time")) if row_out is not None else None
                out_s2 = _to_sec(row_out.get("Sector2Time")) if row_out is not None else None
                out_s3 = _to_sec(row_out.get("Sector3Time")) if row_out is not None else None

                s1_warmup_s = round(float(out_s1 - d_base_s1), 3) if (out_s1 is not None and d_base_s1 is not None) else None
                s2_warmup_s = round(float(out_s2 - d_base_s2), 3) if (out_s2 is not None and d_base_s2 is not None) else None
                s3_warmup_s = round(float(out_s3 - d_base_s3), 3) if (out_s3 is not None and d_base_s3 is not None) else None

                stop_record = {
                    "driver": d,
                    "full_name": full_name,
                    "team": team_name,
                    "team_colour": team_col,
                    "team_color": team_col,
                    "stop_num": stop_idx,
                    "in_lap": in_lap_num,
                    "out_lap": out_lap_num,
                    "in_lap_time_s": in_lap_time_s,
                    "out_lap_time_s": out_lap_time_s,
                    "base_lap_s": d_base_lap,
                    "baseline_lap_s": d_base_lap,
                    "pit_lane_time_s": pit_lane_time_s,
                    "in_lap_delta_s": in_lap_delta_s,
                    "out_lap_delta_s": out_lap_delta_s,
                    "net_pit_loss_s": net_pit_loss_s,
                    "s1_warmup_s": s1_warmup_s,
                    "s2_warmup_s": s2_warmup_s,
                    "s3_warmup_s": s3_warmup_s,
                    "out_lap_s1_delta_s": s1_warmup_s,
                    "out_lap_s2_delta_s": s2_warmup_s,
                    "out_lap_s3_delta_s": s3_warmup_s,
                    "old_compound": old_cmp,
                    "new_compound": new_cmp,
                }

                d_stops.append(stop_record)
                all_stops.append(stop_record)

            if d_stops:
                driver_stops[d] = d_stops

        if not all_stops:
            return fallback

        # Phase 3: Compute Summary KPIs
        stops_with_pit_lane = [s for s in all_stops if s["pit_lane_time_s"] is not None]
        stops_with_in_lap = [s for s in all_stops if s["in_lap_delta_s"] is not None and s["in_lap_delta_s"] > 0]
        stops_with_out_lap = [s for s in all_stops if s["out_lap_delta_s"] is not None and s["out_lap_delta_s"] > 0]
        stops_with_net_loss = [s for s in all_stops if s["net_pit_loss_s"] is not None and s["net_pit_loss_s"] > 0]

        fastest_pit_lane = min(stops_with_pit_lane, key=lambda s: s["pit_lane_time_s"]) if stops_with_pit_lane else None
        best_in_lap = min(stops_with_in_lap, key=lambda s: s["in_lap_delta_s"]) if stops_with_in_lap else None
        best_out_lap = min(stops_with_out_lap, key=lambda s: s["out_lap_delta_s"]) if stops_with_out_lap else None
        lowest_net_pit_loss = min(stops_with_net_loss, key=lambda s: s["net_pit_loss_s"]) if stops_with_net_loss else None

        grid_median_pit_loss = round(float(np.median([s["net_pit_loss_s"] for s in stops_with_net_loss])), 3) if stops_with_net_loss else None
        grid_median_pit_lane = round(float(np.median([s["pit_lane_time_s"] for s in stops_with_pit_lane])), 3) if stops_with_pit_lane else None

        summary_fastest = {
            "driver": fastest_pit_lane["driver"],
            "lap": fastest_pit_lane["in_lap"],
            "time_s": fastest_pit_lane["pit_lane_time_s"],
            "pit_lane_time_s": fastest_pit_lane["pit_lane_time_s"],
            "team": fastest_pit_lane["team"],
            "team_color": fastest_pit_lane.get("team_colour"),
            "team_colour": fastest_pit_lane.get("team_colour"),
        } if fastest_pit_lane else None

        summary_best_in = {
            "driver": best_in_lap["driver"],
            "lap": best_in_lap["in_lap"],
            "delta_s": best_in_lap["in_lap_delta_s"],
            "in_lap_delta_s": best_in_lap["in_lap_delta_s"],
            "team": best_in_lap["team"],
            "team_color": best_in_lap.get("team_colour"),
            "team_colour": best_in_lap.get("team_colour"),
        } if best_in_lap else None

        summary_best_out = {
            "driver": best_out_lap["driver"],
            "lap": best_out_lap["out_lap"],
            "delta_s": best_out_lap["out_lap_delta_s"],
            "out_lap_delta_s": best_out_lap["out_lap_delta_s"],
            "team": best_out_lap["team"],
            "team_color": best_out_lap.get("team_colour"),
            "team_colour": best_out_lap.get("team_colour"),
        } if best_out_lap else None

        summary_lowest_loss = {
            "driver": lowest_net_pit_loss["driver"],
            "lap": lowest_net_pit_loss["in_lap"],
            "loss_s": lowest_net_pit_loss["net_pit_loss_s"],
            "net_pit_loss_s": lowest_net_pit_loss["net_pit_loss_s"],
            "team": lowest_net_pit_loss["team"],
            "team_color": lowest_net_pit_loss.get("team_colour"),
            "team_colour": lowest_net_pit_loss.get("team_colour"),
        } if lowest_net_pit_loss else None

        # Sort all stops by net pit loss (or pit lane duration if net loss missing)
        all_stops.sort(key=lambda s: (
            s["net_pit_loss_s"] if s["net_pit_loss_s"] is not None else 999.0,
            s["pit_lane_time_s"] if s["pit_lane_time_s"] is not None else 999.0
        ))

        return {
            "all_stops": all_stops,
            "driver_stops": driver_stops,
            "summary": {
                "fastest_pit_lane": summary_fastest,
                "best_in_lap": summary_best_in,
                "best_out_lap": summary_best_out,
                "lowest_net_pit_loss": summary_lowest_loss,
                "grid_median_pit_loss": grid_median_pit_loss,
                "grid_median_pit_lane": grid_median_pit_lane,
                "total_stops": len(all_stops),
            },
            "has_data": True,
        }
    except Exception:
        return fallback



