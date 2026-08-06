import os
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


def _fmt_driver1(num: str) -> str:
    """Format function for selectbox — shows 'ABR · Last Name' for Session 1."""
    return _drv_labels1.get(str(num), str(num))


def _fmt_driver2(num: str) -> str:
    """Format function for selectbox — shows 'ABR · Last Name' for Session 2."""
    if _drv_labels2 is not None:
        return _drv_labels2.get(str(num), str(num))
    return _drv_labels1.get(str(num), str(num))


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


def _build_tyre_deg_data(driver: str, laps_df: pd.DataFrame) -> list[dict] | None:
    try:
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

        clean_laps["LapTime_s"] = clean_laps["LapTime"].dt.total_seconds()

        stints_data = []
        for (stint, compound), group in clean_laps.groupby(["Stint", "Compound"]):
            group = group.sort_values("LapNumber")
            # Only consider stints with at least 4 valid laps
            if len(group) >= 4:
                stints_data.append({
                    "stint": int(stint),
                    "compound": str(compound),
                    "laps": group[["TyreLife", "LapTime_s"]].to_dict(orient="records"),
                })
        return stints_data if stints_data else None
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
