# 📖 Developer Documentation — Pit Wall F1 Telemetry Dashboard

> **Audience:** Software engineers contributing to, extending, or debugging this project.
> **Companion files:** `README.md` (user-facing), `AGENT.md` (AI maintenance agent spec).

---

## Table of Contents

1. [Project Philosophy](#1-project-philosophy)
2. [Technology Stack](#2-technology-stack)
3. [Application Lifecycle](#3-application-lifecycle)
4. [Data Layer — FastF1](#4-data-layer--fastf1)
5. [Caching Strategy](#5-caching-strategy)
6. [State Management](#6-state-management)
7. [Helper Function Reference](#7-helper-function-reference)
8. [CSS Architecture](#8-css-architecture)
9. [Rendering Pipeline](#9-rendering-pipeline)
10. [Chart Inventory](#10-chart-inventory)
11. [Theme System](#11-theme-system)
12. [Driver Name Mapping](#12-driver-name-mapping)
13. [Extending the Dashboard — How to Add a New Feature](#13-extending-the-dashboard--how-to-add-a-new-feature)
14. [Common Pitfalls & Gotchas](#14-common-pitfalls--gotchas)
15. [Performance Notes](#15-performance-notes)
16. [Testing](#16-testing)
17. [Future Roadmap](#17-future-roadmap)
18. [Solved Issues & Changelog](#18-solved-issues--changelog)
19. [Multi-Driver Grid Analysis & Heatmaps Architecture](#19-multi-driver-grid-analysis--heatmaps-architecture)

---

## 1. Project Philosophy

The Pit Wall dashboard is built around three principles:

| Principle | What it means in practice |
|---|---|
| **Modular Architecture** | Monolithic `app.py` has been refactored into a modular layout under `src/` to separate data loading, UI widgets, and plotting logic. |
| **Data first** | All UI derives from FastF1 data — no hardcoded lap times, driver stats, or team info. |
| **Zero backend** | Streamlit *is* the server. No Flask, no REST API, no database. FastF1 caching replaces a database. |

---

## 2. Technology Stack

| Layer | Library | Version | Role |
|---|---|---|---|
| Web framework | Streamlit | ≥ 1.44 | UI, routing, state, server |
| F1 data | FastF1 | ≥ 3.3 | Session loading, lap data, telemetry, driver info |
| Static charts | Matplotlib | ≥ 3.8 | 6-channel telemetry, speed delta (transparent overlay) |
| Interactive charts | Plotly | ≥ 5.18 | Track map, race replay, lap history, stint timeline, gap chart |
| Data wrangling | Pandas | ≥ 2.2 | All lap/telemetry DataFrames |
| Numerics | NumPy | ≥ 1.26 | Interpolation for speed delta, position replay |
| HTTP request engine | curl-cffi | ≥ 0.5.10 | TLS fingerprint impersonation to bypass anti-bot / CloudFront filters |

---

## 3. Application Lifecycle

Streamlit re-runs the **entire script** from top to bottom on every user interaction. Understanding this is essential for working on this codebase.

```
Browser interaction
        │
        ▼
  Streamlit reruns app.py top → bottom
        │
        ├─ 1. PWA injection (components.html, height=0, silent)
        ├─ 2. Page-transition JS injected (MutationObserver)
        ├─ 3. CSS injected (design system + theme override)
        ├─ 4. Constants & helpers defined
        ├─ 5. Sidebar rendered (year/GP/session selectors, load button)
        ├─ 6. Session state checked → load session if Load button pressed
        ├─ 7. Landing screen shown if session not loaded → st.stop()
        ├─ 8. Session Info Header rendered (_session_info_header)
        ├─ 9. Driver & lap selectors rendered
        ├─ 10. Telemetry fetched (session_state cache)
        ├─ 11. Driver banner + metrics rendered
        ├─ 12. Charts rendered in sequence (Lap History → Fuel-Adj → Stints → Telemetry → Export → Leaderboard → Gap → Map)
        └─ End of script
```

> **Key implication:** Every variable is re-evaluated every rerun. Only `st.session_state` and `@st.cache_data` persist across reruns.

---

## 4. Data Layer — FastF1

### Session Loading

```python
sess = fastf1.get_session(year, gp, session_type)
sess.load(telemetry=True, laps=True, weather=True, messages=True)
```

`sess.load()` downloads and caches to `./cache/`. First call per session takes 10–30 seconds; subsequent calls return in milliseconds from disk.

> [!NOTE]
> **Active/Ongoing Sessions:** The dashboard is designed to load and visualise historical, completed sessions. Live timing streams (ongoing sessions) are not supported. Attempting to load an active session will fail validation with a "No lap data available" error until F1 compiles and publishes the static timing database files on their CDN (usually 2–24 hours after the session ends).

### Key FastF1 Objects

| Object | Type | How accessed | Contains |
|---|---|---|---|
| `sess.laps` | `Laps` (DataFrame subclass) | Direct | All laps for all drivers — LapTime, Compound, TyreLife, Position, SpeedST, Sector times, etc. |
| `sess.laps.pick_drivers(drv)` | `Laps` | Method | Filtered to one driver |
| `sess.laps.pick_quicklaps()` | `Laps` | Method | Removes laps with anomalous times (pit laps, SC laps) |
| `lap.get_car_data().add_distance()` | `Telemetry` | Method on a single lap row | Speed, Throttle, Brake, RPM, nGear, DRS + Distance column |
| `sess.get_driver(drv_num)` | `dict` | Method | Abbreviation, LastName, TeamName, HeadshotUrl, TeamColour |
| `sess.weather_data` | DataFrame | Attribute | Air/track temp, humidity, rainfall per timestamp |
| `sess.race_control_messages` | DataFrame | Attribute | Track status flags |
| `sess.event` | `Event` (Series) | Attribute | Circuit name, country, round number, date |

### Driver Numbers vs Names

FastF1 identifies drivers by **number strings** (`"4"`, `"81"`), not names. Always use numbers as the internal key. Convert to display names only at render time via `_fmt_driver()`.

---

## 5. Caching Strategy

Three distinct cache layers are in use:

### Layer 1 — FastF1 disk cache
```python
fastf1.Cache.enable_cache("./cache")
```
Persists raw API responses to disk. Lives in `./cache/` (gitignored). Survives app restarts. Mount as a Docker volume to persist across container restarts.

### Layer 1b — Real-Time Live Timing Stream Data (`fastf1.livetiming`)
```python
start_live_recorder(filename="live_timing.txt")
load_live_session(year, gp, session_type, live_filename="live_timing.txt")
```
Streams and records active SignalR WebSocket packets directly from F1's live timing server. Uses `fastf1.livetiming.client.SignalRClient` in a background thread to record raw text messages, and parses saved `.txt` streams into structured FastF1 session objects via `fastf1.livetiming.data.LiveTimingData`.

#### Monkey-Patch Caching Compatibility (`requests_cache` serialization)
FastF1 uses `requests_cache` to cache raw API calls. Because we monkey-patched `requests.adapters.HTTPAdapter.send` using `curl_cffi` (to rotate proxies and bypass CloudFront blocks), we bypass the standard `requests` response instantiation.
If the mock response object returned by our patch does not have a properly populated `response.raw` attribute, the `requests_cache` SQLite serializer crashes with an `AttributeError: 'NoneType' object has no attribute '_request_url'`.

To prevent this:
1. Define a `MockRaw` helper class inside the patch:
   ```python
   class MockRaw:
       def __init__(self, url, headers=None, reason=None, status=None):
           self._request_url = url
           self.decode_content = True
           self.headers = headers
           self.reason = reason
           self.status = status
           self.version = 11
           self.closed = True
   ```
2. Construct and assign `resp.raw` inside the patch function:
   ```python
   resp.raw = MockRaw(
       url=str(curl_resp.url),
       headers=CaseInsensitiveDict(dict(curl_resp.headers)),
       reason=resp.reason,
       status=curl_resp.status_code
   )
   ```


### Layer 2 — `@st.cache_data`
```python
@st.cache_data(show_spinner=False, ttl=3600)
def load_session(year, gp, session_type): ...
```
In-memory cache keyed by function arguments. TTL of 3600s prevents stale data accumulating during long development sessions. All data-builder functions use this pattern:

| Function | Cache key inputs |
|---|---|
| `load_schedule(year)` | `year` |
| `load_session(year, gp, session_type)` | `year, gp, session_type` |
| `_build_lap_history(driver, sess_k, laps_df)` | `driver, sess_key, laps_df` |
| `_build_fuel_adjusted(driver, sess_k, fuel_effect, laps_df)` | `driver, sess_key, fuel_effect, laps_df` |
| `_build_fuel_sim_leaderboard(sess_k, fuel_effect, laps_df)` | `sess_key, fuel_effect, laps_df` |
| `_build_stints(driver, sess_k, laps_df)` | `driver, sess_key, laps_df` |
| `_build_pit_stops(driver, sess_k, laps_df)` | `driver, sess_key, laps_df` |
| `_build_tyre_deg_data(driver, laps_df)` | `driver, laps_df` |
| `_build_leaderboard(sess_k, laps_df)` | `sess_key, laps_df` |
| `_build_ideal_lap(sess_k, laps_df)` | `sess_key, laps_df` |
| `_build_gap_data(sess_k, laps_df)` | `sess_key, laps_df` |
| `_build_position_data(sess_k, laps_df)` | `sess_key, laps_df` |
| `_get_telemetry_for_map(driver, lap_num, sess_k)` | `driver, lap_num, sess_key` |

`sess_key` is a string formatted as `"{year}_{gp}_{session_type}"` (e.g. `"2025_British Grand Prix_R"`).

**`_all_laps` pattern (cache isolation fix):**
`_all_laps` is extracted immediately after session validation and passed to every data-builder as `laps_df: pd.DataFrame`.

**Critical implementation detail — always cast to plain `pd.DataFrame`:**
```python
_all_laps: pd.DataFrame = pd.DataFrame(sess.laps.copy())
```
`sess.laps` is a `fastf1.core.Laps` object (a pandas subclass with custom internal state). Streamlit's `@st.cache_data` hasher cannot serialise it and raises `UnhashableParamError`. Wrapping in `pd.DataFrame()` strips the subclass identity and produces a hashable, standard DataFrame.

**Consequence — no `.pick_drivers()` inside builders:**
Because `laps_df` is now a plain `pd.DataFrame`, the FastF1 `.pick_drivers(driver)` method is unavailable. All 4 per-driver builders filter using standard pandas:
```python
# ✅ correct — plain DataFrame filter
laps = laps_df[laps_df["Driver"] == driver].copy()

# ❌ wrong — pick_drivers() is a fastf1.core.Laps method only
laps = laps_df.pick_drivers(driver)
```
Functions affected: `_build_lap_history`, `_build_fuel_adjusted`, `_build_stints`, `_build_pit_stops`.

### Layer 3 — `st.session_state` for telemetry
```python
def get_telemetry_cached(driver, lap, sess_key):
    key = f"tel_{sess_key}_{driver}_{lap_num}"
    if key not in st.session_state:
        st.session_state[key] = lap.get_car_data().add_distance()
    return st.session_state[key]
```
Telemetry DataFrames are large (~3000 rows) and can't be efficiently cached with `@st.cache_data` (unhashable types). They are stored directly in `session_state` under a compound key.

---

## 6. State Management

All persistent state lives in `st.session_state`. Key entries:

| Key | Type | Set by | Purpose |
|---|---|---|---|
| `"dark_mode"` | `bool` | `_toggle_theme()` callback | Current theme state |
| `"session"` | FastF1 Session | Load button handler | The loaded session object |
| `"session_key"` | `str` | Load button handler | `"{year}_{gp}_{type}"` cache key |
| `"d1"`, `"d2"` | `str` | `st.selectbox` | Selected driver numbers |
| `"lap_<drv>_<suffix>"` | `str` | `st.selectbox` | Selected lap for each driver |
| `"tel_{key}_{drv}_{lap}"` | DataFrame or None | `get_telemetry_cached` | Cached telemetry per lap |
| `"replay_{key}"` | Plotly Figure or None | Race replay button | Cached replay animation |
| `"fuel_effect_slider"` | `float` | `st.slider` | Fuel effect assumption |

### Theme Toggle Pattern

The theme toggle uses an `on_click` callback to update state *before* the next rerender:

```python
def _toggle_theme():
    st.session_state["dark_mode"] = not st.session_state["dark_mode"]

st.button("Toggle Theme", on_click=_toggle_theme)
```

This ensures the CSS injection block reads the updated value on the same rerun rather than one rerun behind.

---

## 6b. Compound Colour System

`COMPOUND_COLOURS` in `src/ui/styles.py` is the **single source of truth** for all compound colours. Every consumer in the codebase derives from it — no inline dicts anywhere.

```python
COMPOUND_COLOURS = {
    "SOFT":         {"fill": "#FF3333", "text": "#ffffff", "letter": "S"},
    "MEDIUM":       {"fill": "#FFD700", "text": "#111111", "letter": "M"},
    "HARD":         {"fill": "#CCCCCC", "text": "#111111", "letter": "H"},
    "INTERMEDIATE": {"fill": "#39B54A", "text": "#ffffff", "letter": "I"},
    "WET":          {"fill": "#0067FF", "text": "#ffffff", "letter": "W"},
    "UNKNOWN":      {"fill": "#888888", "text": "#ffffff", "letter": "?"},
}
```

| Key | Used by |
|---|---|
| `fill` | Chart markers (lap history, fuel pace), stint timeline bars, leaderboard dot |
| `text` | Stint bar label contrast colour, tyre badge letter |
| `letter` | Tyre badge abbreviation (`S`, `M`, `H`, `I`, `W`) |

**Rule:** Always look up with `.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])`. Never define a new inline compound colour dict — extend `COMPOUND_COLOURS` instead.

---

## 7. Helper Function Reference

### `_session_info_header(session, sess_type_code: str) -> None`
Renders a slim contextual banner immediately before Driver Selection. Reads `session.event` for:
- `Location` → circuit name (falls back to `EventName`)
- `Country` → country name + flag emoji (27 countries mapped; `🏁` fallback)
- `RoundNumber` → round number
- `EventDate` → formatted as `"%-d %B %Y"` (e.g. `"27 April 2025"`)
- `sess_type_code` → human-readable label (`R` → `Race`, `Q` → `Qualifying`, etc.) + icon

Styled with team-colour left border (`var(--primary-color)`) and a subtle gradient tint.
Wrapped in `try/except` — never crashes the page if `sess.event` fields are missing.

### `hex_to_rgb(hex_col: str) -> str`
Converts `"#FF8700"` → `"255,135,0"`. Used for CSS `rgba()` variables.
Falls back to `"255,135,0"` (McLaren orange) on malformed input.

### `_team_logo(team: str) -> str`
Maps a FastF1 team name string to an F1 Media CDN URL for the constructor logo PNG.
Partial-match based — `"Red Bull Racing"` matches `"red bull"`.
Returns `""` if no match (silently hides the logo in the banner).

### `_team_colour(team: str) -> str`
Maps a team name to its hex brand colour via `TEAM_COLOURS` dict.
Returns `"#FF8700"` (orange) as fallback.

### `load_schedule(year: int) -> pd.DataFrame`
Returns the full event schedule for a season via `fastf1.get_event_schedule`.
Cached per year.

### `load_session(year, gp, session_type) -> fastf1.core.Session`
Loads and fully hydrates a FastF1 session (telemetry + laps + weather + messages).
Cached per `(year, gp, session_type)` tuple.

### `format_laptime(td) -> str`
Converts a `pd.Timedelta` to `"M:SS.mmm"` string (e.g. `"1:26.543"`).
Returns `"N/A"` for null/invalid input.

### `driver_colour(sess, driver: str) -> str`
Returns the hex team colour for a driver number in a given session.
Calls `sess.get_driver(driver)` → `TeamName` → `_team_colour()`.

### `_build_driver_labels(session) -> dict`
Builds `{"4": "NOR · Norris", "81": "PIA · Piastri", ...}` from live FastF1 driver info.
Safe — individual driver failures don't break the whole dict.

### `_fmt_driver(num: str) -> str`
`format_func` for `st.selectbox`. Returns `_drv_labels.get(num, num)`.
Use this everywhere a driver number is displayed to a user.

### `_build_constructor_standings(year: int, round_no: int = None) -> list`
Fetches season Constructors' Championship standings from Jolpi (Ergast) API. Cached using `@st.cache_data(show_spinner=False, ttl=3600)` with failure fallback.

### `_render_constructor_standings(standings_list, highlight_teams: list, highlight_colours: list)`
Renders Constructors' Championship standings as a styled HTML table. Highlighted rows indicate constructor teams associated with the selected driver(s).

### `_build_driver_standings(year: int, round_no: int = None) -> list`
Fetches season Drivers' Championship standings from Jolpi (Ergast) API. Cached using `@st.cache_data(show_spinner=False, ttl=3600)` with failure fallback. Used to append total standings points to the classification table.

### `get_telemetry_cached(driver, lap, sess_key) -> pd.DataFrame | None`
Fetches and caches raw telemetry for one lap via `lap.get_car_data().add_distance()`.
Stores result in `st.session_state` under a compound key.
Returns `None` if telemetry is unavailable (shows a warning).

### `style_ax(ax, ylabel, special="")`
Applies consistent Matplotlib axis styling (grey grid, spine opacity, label sizes).
`special="brake"` → binary Y axis (Off/On).
`special="drs"` → DRS states (0/8/12).
`special="gear"` → integer Y ticks.

### `render_summary(lap, driver, colour)`
Renders the full driver banner section:
- Circular headshot (`HeadshotUrl`) with team-coloured ring
- Driver code + lap number
- Team logo + team name badge (top-right)
- 4-column metric cards (Lap Time, S1, S2, S3)
- 4-column speed trap cards (I1, I2, FL, ST)
- Tyre badge (compound, age, fresh flag)
- Weather strip

---

## 8. CSS Architecture

All CSS is injected via `st.markdown(..., unsafe_allow_html=True)` in two blocks:

### Block 1 — Design System (lines 451–1071)
Static, loaded once. Defines:

| Component | CSS class / selector |
|---|---|
| Page & sidebar background | `[data-testid="stAppViewContainer"]`, `[data-testid="stSidebar"]` |
| Entry animations | `@keyframes pageEnter`, `@keyframes slideInLeft` |
| Metric cards | `.metric-card`, `.metric-label`, `.metric-value`, `.metric-sub` |
| Driver banner | `.driver-banner`, `.driver-headshot`, `.team-badge`, `.team-logo` |
| Tyre badge | `.tyre-badge` |
| Weather strip | `.weather-strip`, `.weather-item` |
| Section titles | `.section-title` |
| Buttons | `[data-testid="stSidebar"] .stButton > button` |

### Block 2 — Theme Override (lines 1072–1241)
Dynamic, re-injected on every rerender based on `st.session_state["dark_mode"]`.

**Dark mode** variables:
```css
--background-color: #0d0d0d;
--secondary-background-color: #161616;
--text-color: #f5f5f5;
```

**Light mode** variables:
```css
--background-color: #f5f5f7;
--secondary-background-color: #ffffff;
--text-color: #1a1a1a;
```

The theme CSS also overrides Streamlit's internal BaseWeb selectors for:
- `[data-baseweb="select"]` (dropdowns)
- `[data-testid="stHeader"]` (top toolbar)
- Radio buttons, checkboxes, expanders

### CSS Variables for Team Colour

At session load the primary CSS variable is set dynamically:
```css
:root {
  --primary-color: #FF8700;   /* team hex colour */
  --primary-rgb: 255, 135, 0; /* rgb triplet for rgba() */
}
```
This flows to button glows, card accents, banner borders, and chart highlights automatically.

### Sidebar Collapsed Control Compatibility

When customising sidebar styles or adding transitions (like the slide-in entry animation), do not target the base `[data-testid="stSidebar"]` selector directly with keyframe animations using `forwards` or `infinite` fill-modes. 

Streamlit hides the sidebar natively when collapsed by applying a dynamic `transform` translation (e.g., `translate3d(-336px, 0px, 0px)`). An overriding keyframe animation with `forwards` forces `transform: translateX(0)` (or the final frame state), which overrides Streamlit's collapsed state translation. This leaves the sidebar stuck on the screen or squished in mobile viewports.

To prevent this layout break:
- Target `section[data-testid="stSidebar"][data-collapsed="false"]` for expanded-state animations.
- Let Streamlit's native `transform` handle the collapsed state (`data-collapsed="true"`).

### Page Transition JS

A `MutationObserver` (injected via `components.html`) watches for Streamlit's `data-stale="false"` flip (which signals a rerender completed) and resets the `animation` property on `.block-container` to replay `pageEnter` every time. This makes every button click feel like a smooth page transition.

---

## 9. Rendering Pipeline

After data is loaded, the script renders sections in this fixed order:

```
_session_info_header()  ← Session banner (circuit, country, round, session type, date)
        │
render_summary()        ← Driver banner, metrics, tyre, weather
        │
render_session_stats()  ← Session Statistics (Grid, Finish, Pace, Speed)
        │
_lap_history_fig()      ← Lap Time History (Plotly) + compound multiselect filter
        │
_fuel_pace_fig()        ← Fuel-Adjusted Pace (Plotly, dual traces)
        │
_stint_fig()            ← Tyre Stint Timeline (Plotly Gantt bars)
        │
_render_pit_stops()     ← Pit Stop Summary (HTML table)
        │
build_chart()           ← 6-channel Telemetry (Matplotlib)
        │
_build_export_csv()     ← Export panel — Distance, Speed, Throttle, Brake, RPM, Gear, DRS, Sector1/2/3 times, lap metadata
        │
Speed Delta             ← Matplotlib fill-between (compare mode only)
        │
_render_leaderboard()   ← Fastest Laps Leaderboard (HTML table)
        │
_build_ideal_lap()      ← Ideal Lap vs Actual Lap — best S1+S2+S3 per driver, delta cards + full table
        │
Gap to Leader           ← Plotly line chart (all drivers)
        │
Race Position           ← Plotly line chart — all drivers faded, selected highlighted (_build_position_data)
        │
Track Map               ← Plotly scatter (speed-coloured path)
        │
Race Replay             ← Plotly animated scatter (all drivers)
        │
Constructors' Standings ← Constructors' Championship Standings (HTML table)
        │
Official Classification ← Official Session Classification (HTML table)
```

Each chart section follows the same pattern:
1. `@st.cache_data` function builds the data
2. A figure-builder function creates the Plotly/Matplotlib figure
3. `st.plotly_chart(fig, width="stretch")` or `st.pyplot(fig, width="stretch")` renders it

---

## 10. Chart Inventory

| Chart / Table | Library | Builder function | Figure/Render function | Key data source |
|---|---|---|---|---|
| Session Statistics | HTML | — (inline) | `render_session_stats` | `sess.get_driver()`, `laps_df` |
| Lap Time History | Plotly | `_build_lap_history` | `_lap_history_fig` | `laps_df` filtered by driver — compound multiselect filter applied before render |
| Fuel-Adjusted Pace | Plotly | `_build_fuel_adjusted` | `_fuel_pace_fig` | `laps_df` filtered by driver |
| Fuel-Corrected Qualifying Sim | HTML | `_build_fuel_sim_leaderboard` | `_render_fuel_sim_leaderboard` | `laps_df` |
| Tyre Stint Timeline | Plotly | `_build_stints` | `_stint_fig` | `laps_df` filtered by driver |
| Pit Stop Summary | HTML | `_build_pit_stops` | `_render_pit_table` | `laps_df` filtered by driver (relying on `PitInTime` and `PitOutTime`) |
| Tyre Degradation | Plotly | `_build_tyre_deg_data` | inline | `laps_df` filtered by driver; OLS regression of LapTime vs TyreLife per stint. |
| 6-Channel Telemetry | Matplotlib | `get_telemetry_cached` | `build_chart` | `lap.get_car_data()` |
| Export Telemetry CSV | CSV bytes | `_build_export_csv` | — | `tel_df` + `lap_obj` sector times |
| Speed Delta | Matplotlib | — (inline) | — (inline) | `tel1`, `tel2` DataFrames |
| Fastest Laps Leaderboard | HTML | `_build_leaderboard` | `_render_leaderboard` | `laps_df` grouped by driver |
| Ideal Lap vs Actual Lap | HTML | `_build_ideal_lap` | `_render_ideal_lap_section` | `laps_df` sector times per driver |
| Gap to Leader | Plotly | `_build_gap_data` | `_render_gap_to_leader_section` | `laps_df` cumulative time |
| Race Position | Plotly | `_build_position_data` | `_render_position_section` | `laps_df["Position"]` per driver |
| Track Speed Map | Plotly | `_get_telemetry_for_map` | `_speed_map_fig` | `lap.get_car_data()`. In compare mode, colours mini-sectors by dominance. |
| Driver Inputs Map | Plotly | `_get_telemetry_for_map` | `_input_map_fig` | `lap.get_car_data()`. Colours markers by Throttle/Brake state. |
| Corner Analysis | Plotly subplots | `_get_telemetry_for_map` | inline (`with map_tab4`) | `lap.get_car_data()`. Displays racing line overlay with apex/braking markers + Speed profile. |
| Race Replay | Plotly animated | — (inline) | inline | `sess.pos_data` per driver |
| Constructors' Championship Standings | HTML | `_build_constructor_standings` | `_render_constructor_standings` | Jolpi (Ergast) API constructor standings |
| Official Session Classification | HTML | `_build_final_classification` | `_render_final_classification` | `sess.results` (Q1/Q2/Q3 or Time/Status/Grid/Points), `laps_df` (for pit stop counts), and Jolpi (Ergast) API driver standings (for championship points) |

---

## 11. Theme System

### How it works end-to-end

```
User clicks theme toggle
        │
_toggle_theme() callback fires (BEFORE rerun)
        │
st.session_state["dark_mode"] flips
        │
Streamlit reruns app.py
        │
Theme CSS block reads dark_mode → injects correct variable set
        │
CSS transitions (0.35s ease) animate background/colour change
        │
MutationObserver replays pageEnter animation
```

### Adding new components to the theme

When you add a new Streamlit component that doesn't respond to theme changes, add a CSS override to the **Theme CSS block** (lines 1072–1241):

```python
# Inside the dark/light mode conditional CSS string:
f"""
[data-testid="yourNewComponent"] {{
    background: {bg} !important;
    color: {text} !important;
}}
"""
```

---

## 12. Driver Name Mapping

Driver identification flows through three layers:

```
FastF1 raw number ("4")
        │
_drv_labels dict {"4": "NOR · Norris"}
        │
_fmt_driver("4") → "NOR · Norris"
        │
st.selectbox(..., format_func=_fmt_driver)
```

`_drv_labels` is built once per session load by `_build_driver_labels(sess)`.
**All internal logic uses raw numbers.** Only the final display layer uses names.

### Coverage — every location `_fmt_driver` is applied

| UI Location | How it's applied |
|---|---|
| Driver 1 / Driver 2 selectboxes | `format_func=_fmt_driver` on `st.selectbox` |
| Lap selector label | `f"Lap — {_fmt_driver(driver)}"` passed as `st.selectbox` label |
| Lap selector warning | `f"No valid laps for {_fmt_driver(driver)}."` in `st.warning` |
| Fastest Laps Leaderboard Driver column | `_fmt_driver(drv)` in `_render_leaderboard` HTML table cell |
| Fuel-Adjusted Pace stat card label | `_fmt_driver(drv)` in metric card `metric-label` div |

To extend this to any new component, call `_fmt_driver(driver_num)` on the display value:

```python
# Example: rendering a driver label in any HTML context
f"<td>{_fmt_driver(drv)}</td>"
```

---

## 13. Extending the Dashboard — How to Add a New Feature

### Step 1 — Identify the insertion point

Add your data loading / data processing function to `src/data/loader.py`, chart builders to `src/charts/` (either `plotly.py` or `matplotlib.py`), and the UI rendering widgets to `src/ui/components.py`. Import and coordinate them in the main entry point `app.py`.

### Step 2 — Add a section header

In the UI components module, use the standard section title format:

```python
st.markdown("<div class='section-title'>My New Section</div>", unsafe_allow_html=True)
```

### Step 3 — Write a cached data builder

```python
@st.cache_data(show_spinner=False, ttl=3600)
def _build_my_data(driver: str, sess_k: str, laps_df: pd.DataFrame) -> pd.DataFrame | None:
    """One-line docstring describing what this returns."""
    try:
        drv_laps = laps_df[laps_df["Driver"] == driver].copy()
        # ... transform data ...
        return drv_laps
    except Exception:
        return None
```

> Note: pass `sess_k` as a string parameter (not the session object) and `laps_df` as a casted plain `pd.DataFrame` (never raw `fastf1.core.Laps`) to prevent Streamlit from throwing `UnhashableParamError`. Inside the builder, use boolean filtering (never `.pick_drivers()`).

### Step 4 — Write a figure builder

**For Plotly:**
```python
def _my_fig(data: pd.DataFrame, colour: str) -> go.Figure:
    fig = go.Figure()
    # ... add traces ...
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=16, b=0),
        height=300,
    )
    return fig
```

Always set `paper_bgcolor` and `plot_bgcolor` to transparent so charts adapt to dark/light theme.

**For Matplotlib:**
```python
def _my_matplotlib_fig(tel_df, colour):
    fig, ax = plt.subplots(figsize=(14, 3), facecolor="none")
    ax.set_facecolor("none")
    # ... plot ...
    style_ax(ax, "Y Label")
    fig.tight_layout()
    return fig
```

Always call `plt.close(fig)` immediately after `st.pyplot(fig)`.

### Step 5 — Render it

```python
_my_data = _build_my_data(driver1, sess_key, _all_laps1)
if _my_data is None or _my_data.empty:
    st.info("Data not available for this session.")
else:
    st.plotly_chart(_my_fig(_my_data, colour1), width="stretch")
```

### Step 6 — Handle comparison mode

```python
_my_data_pairs = [(driver1, colour1, _build_my_data(driver1, sess_key))]
if compare and driver2:
    _my_data_pairs.append((driver2, colour2, _build_my_data(driver2, sess_key)))
```

### Step 7 — Update `README.md`

Add a bullet to **Key Features** and a numbered step to **How to Use**.

---

## 14. Common Pitfalls & Gotchas

### ① `pick_drivers()` expects a string
```python
# Wrong — FastF1 may not match integer
sess.laps.pick_drivers(4)

# Correct
sess.laps.pick_drivers("4")
```

### ② `pd.isna()` on Timedelta
```python
# Wrong — raises TypeError for Timedelta
if lap["LapTime"] is None: ...

# Correct
if pd.isna(lap["LapTime"]): ...
```

### ③ Matplotlib + Streamlit memory leak
Always close figures after rendering:
```python
st.pyplot(fig, width="stretch")
plt.close(fig)   # ← essential
```

### ④ `st.cache_data` cannot hash complex objects
Pass a string `sess_key` (not the session object) to cached functions.

### ⑤ `on_click` vs inline state mutation
For toggles and buttons that affect CSS injection, always use `on_click=callback` — not inline `if st.button(...)` — to ensure state updates before CSS is re-evaluated on the same rerender.

### ⑥ Streamlit re-runs on every widget interaction
Do not put expensive operations (FastF1 API calls, large DataFrame operations) outside of `@st.cache_data` functions or `st.session_state` checks.

### ⑦ `width='stretch'` not `use_container_width`
Since Streamlit 1.44, `use_container_width=True` is deprecated. Always use:
```python
st.plotly_chart(fig, width="stretch")
st.pyplot(fig, width="stretch")
st.button("Label", width="stretch")
```

### ⑧ Monkey-Patched requests Compatibility with `requests_cache`
When wrapping requests or custom adapters in FastF1, never return a `requests.Response()` object with `response.raw` left as `None`. Doing so causes `requests_cache`'s serializer to throw an `AttributeError` when trying to save timing data. Always mock the `raw` attribute using a helper class (e.g. `MockRaw`) providing `_request_url`, `decode_content`, `headers`, `status`, `reason`, `version`, and `closed`.

### ⑨ Custom Sidebar Animations and Collapsed State Overrides
If you apply a custom CSS keyframe animation to `[data-testid="stSidebar"]` directly with `forwards` or `infinite` fill-mode, it will block Streamlit's native sidebar hiding translation on mobile. You must scope the animation to the open sidebar selector (`section[data-testid="stSidebar"][data-collapsed="false"]`) so that the collapsed sidebar can transition and translate off-screen cleanly.

### ⑩ Empty Official Standings in Practice Sessions
Do not assume `sess.results` contains official standings or non-NaN `Position` column entries for practice sessions (`FP1`, `FP2`, `FP3`). They are unordered and `results.Position` is fully null/NaN. For practice sessions, intercept the results check and display an informational note pointing users to the `Fastest Laps Leaderboard` instead of rendering a table of NaNs.

### ⑪ Unhashable Session Results Object in st.cache_data
FastF1's results DataFrame (`SessionResults`) is a custom pandas DataFrame subclass with extra attributes. Passing it to an `@st.cache_data` cached function throws an `UnhashableParamError` because Streamlit's hash engine doesn't support custom subclassed DataFrames. To fix this, prefix the parameter name in the cached function signature with a leading underscore (e.g., `_results_df`) to exclude it from the hash key calculation.

### ⑫ GPS Coordinates vs Telemetry Channels in Track Maps
Do not assume all telemetry channels (like `Speed`, `Throttle`, `Brake`, or Sector timing session data) are present just because a lap's telemetry is successfully retrieved. Always check for the presence of the required coordinate columns `X` and `Y` to render the basic track outline first. If speed or input data is missing, draw a gray track outline (or sector-dominance fallback) and display an informational warning banner instead of failing/crashing the entire map component.

### ⑬ External Championship Standings API Caching and Matching
Championship standings data is loaded from the external Jolpi (Ergast) API. Because network requests can introduce latency or potentially fail, always wrap standings fetching inside `@st.cache_data` with a reasonable TTL (e.g., 3600 seconds) and handle exceptions gracefully. When matching constructors from the standings list to the local `TEAM_COLOURS` dictionary, apply name normalization (stripping suffixes like 'F1 Team' and 'Racing') to avoid mismatching due to minor variations between FastF1 naming and the Ergast database.

### ⑭ Multi-Key Matching for Standings Drivers
Drivers in the standings database (Ergast) may have minor record variations compared to FastF1 results (such as Verstappen's number mapping, name spelling, or temporary replacement drivers). To ensure robust mapping between the session classification results DataFrame and the standings API, resolve drivers using a fallback multi-key matching function check checking driver three-letter abbreviation codes, car number strings, and last/family name substrings before defaulting to a missing value indicator (`—`).

### ⑮ Normalising Winner Lookup Identifiers
FastF1 session results and lap telemetry might store driver identifiers as driver numbers (e.g., '4', '1') or abbreviation strings (e.g., 'NOR', 'VER') depending on the session data and year. When resolving the winner to set selectbox default selection indices, always run resolved winners through a mapping resolver checking abbreviation codes and driver numbers against the session's driver labels to translate them safely to the exact key format present in the list of selectbox options.

### ⑯ Safely Comparing Dates and Timezones for Default Event Selection
When resolving the default Grand Prix index dynamically by comparing event dates with the current time `pd.Timestamp.now()`, mismatching timezone properties (offset-aware vs. offset-naive timestamps) can trigger a `TypeError`. To ensure safe comparisons, normalize both datetimes to timezone-naive by stripping timezone info (e.g. via `dt.tz_localize(None)`) before filtering events in the schedule.

### ⑰ Accurately Counting Pit Stops from Laps Data
When counting a driver's pit stops in F1 sessions, rely on identifying laps containing both non-null `PitInTime` and `PitOutTime` columns. Do not count `PitInTime` alone, as this will also count retirements that occurred in the pit lane (which are not completed pit stops).


---

## 15. Performance Notes

| Bottleneck | Mitigation |
|---|---|
| Session first load (10–30s) | `@st.cache_data` + FastF1 disk cache — subsequent loads in <1s |
| Race replay animation build | Cached in `st.session_state`; only built on button click |
| Telemetry per lap | Cached in `st.session_state` under compound key |
| Leaderboard (all drivers) | `@st.cache_data` per session key |
| Gap to Leader (all drivers) | `@st.cache_data` per session key |
| Driver name labels | Built once at session load, stored in `_drv_labels` module-level dict |
| Standings data fetch (Ergast) | `@st.cache_data(show_spinner=False, ttl=3600)` with exception safety filters |

The heaviest single operation is `sess.load()` on first call. Everything else is sub-second once the session is cached.

---

## 16. Testing

The dashboard contains an automated unit testing suite targeting data-wrangling functions to prevent regressions when dependencies or the upstream FastF1 library update.

### Unit Tests (`pytest`)

The tests reside in the `tests/` directory:
- `tests/__init__.py`: Package initialisation.
- `tests/conftest.py`: Reusable `pytest` fixtures providing static mock `results` and `laps` DataFrames. These fixtures allow testing the data wrangling pipeline entirely offline, avoiding slow API calls.
- `tests/test_data_wrangling.py`: Tests the following core data-wrangling components:
  - `_build_final_classification` under race (sorting and index conversion), qualifying (sector split-time validation), and practice (returning `"PRACTICE"` indicator code for NaN results) configurations.
  - `_build_fuel_adjusted` checking fuel-load adjustments, exclusion of in-laps and out-laps (`PitInTime` and `PitOutTime`), and exclusion of outlier laps (>2.5x median pace).
- `tests/test_live_timing.py`: Tests the following live timing components:
  - `get_live_recorder_status`: Verifies status calculation, stream file existence, line counts, and file size formatting for missing vs mock stream files.
  - `stop_live_recorder`: Validates inactive stream recorder shutdown handling.
  - `load_live_session`: Verifies graceful fallback and error message handling for missing or empty live stream text files.

To run the automated tests locally:
```bash
python3.11 -m pytest tests/
```

### CI/CD Integration

Automated tests are integrated via GitHub Actions in `.github/workflows/test.yml`. The test suite runs automatically on Python 3.11 for every push or pull request targeting the `main` branch.

### Manual smoke test checklist

Run this after any significant change:

- [ ] App loads at `http://localhost:8501` without error
- [ ] Load Session button downloads and displays data
- [ ] Driver 1 selectbox shows formatted names (`NOR · Norris`)
- [ ] Driver banner shows headshot, team logo, and metrics
- [ ] Lap Time History chart renders with compound markers
- [ ] Compound multiselect filter shows/hides laps correctly
- [ ] Fuel-Adjusted Pace slider updates the chart
- [ ] Tyre Stint Timeline shows coloured bars
- [ ] Telemetry chart renders all 6 channels
- [ ] Export CSV button downloads a valid file with Sector1/2/3 columns
- [ ] Fastest Laps Leaderboard shows all drivers
- [ ] Ideal Lap table renders with correct S1/S2/S3 and theoretical times
- [ ] Delta card shows green (≤0.05s) or red (>0.05s) colour correctly
- [ ] Gap to Leader chart renders
- [ ] Race Position chart renders (Race/Sprint sessions only)
- [ ] Track Map renders with speed colours
- [ ] Dark mode toggle switches all backgrounds including top bar
- [ ] Light mode toggle reverses all backgrounds

---

## 17. Future Roadmap

Items agreed by the project owner as desirable but not yet implemented:

| Priority | Feature | Technical notes |
|---|---|---|
| ~~High~~ | ~~**Session info header**~~ | ✅ **Done** — `_session_info_header()` renders circuit, flag, round, session type + icon, and date in a team-colour-accented banner above Driver Selection. |
| ~~High~~ | ~~**Race position chart**~~ | ✅ **Done** — `_build_position_data()` reads `sess.laps["Position"]`; all drivers shown as faint grey lines, selected driver(s) overlaid in team colour. Y-axis inverted (P1 at top). Gracefully hidden on non-race sessions. |
| ~~Medium~~ | ~~**Pit stop summary table**~~ | ✅ **Done** — `_build_pit_stops()` reads `PitInTime`/`PitOutTime`; renders stop #, lap, duration, From/To compound per driver. |
| ~~Low~~ | ~~**Ideal Lap vs Actual Lap**~~ | ✅ **Done** — `_build_ideal_lap()` finds best S1+S2+S3 across all laps per driver. Per-driver delta card shows time left on table in red/green. Full-field ranked table ordered by TheoreticalBest. Gracefully hidden when sector data absent. |
| ~~Medium~~ | ~~**Sector mini-map colouring**~~ | ✅ **Done** — Track map converted to Sector Dominance Map in Compare Mode. Track is divided into 3 zones based on `Sector1SessionTime` and `Sector2SessionTime`. Coloured automatically using the team colour of the driver who was fastest in each sector. |
| ~~Medium~~ | ~~**Compound filter on lap history**~~ | ✅ **Done** — `st.multiselect` above `_lap_history_fig` filters by compound. Options derived live from session data. All compounds selected by default; uses `COMPOUND_COLOURS` letter badges in labels. |
| ~~Low~~ | ~~**Export adds sector times**~~ | ✅ **Done** — `_build_export_csv` now inserts `Sector1Time_s`, `Sector2Time_s`, `Sector3Time_s` (float seconds, 3 dp) after `Compound` column. Empty string fallback if sector time is null. |
| ~~Medium~~ | ~~**Driver Input Track Map**~~ | ✅ **Done** — `_input_map_fig()` visualises throttle/brake/coasting telemetry as coloured markers on the track path. Supports side-by-side comparison. |
| ~~Medium~~ | ~~**Tyre Degradation Modeling**~~ | ✅ **Done** — `_build_tyre_deg_data()` and OLS regression plots track pace drop-off vs tyre age per stint. |
| Low | **Multi-session comparison** | Add a second set of year/GP/session selectors; load two sessions and pass both to chart builders |
| ~~Low~~ | ~~**Fuel-corrected qualifying sim**~~ | ✅ **Done** — Use fuel-adjusted pace median as a synthetic "single-lap pace" to simulate qualification order |
| ~~Tech debt~~ | ~~**Fix cache isolation**~~ | ✅ **Done** — All 7 data-builder functions (`_build_lap_history`, `_build_fuel_adjusted`, `_build_stints`, `_build_pit_stops`, `_build_leaderboard`, `_build_gap_data`, `_build_position_data`) now receive `laps_df: pd.DataFrame` as an explicit argument. `_all_laps = sess.laps.copy()` is extracted once after session load and passed to every builder. |
| ~~Tech debt~~ | ~~**Consolidate compound colour dicts**~~ | ✅ **Done** — `COMPOUND_COLOURS` is now the single canonical dict. `_CMP_PALETTE`, `cmp_dot`, and `cmp_colours_map` have all been removed. |
| ~~Medium~~ | ~~**Constructors' Championship Standings**~~ | ✅ **Done** — Added `_build_constructor_standings` and `_render_constructor_standings` to render the constructor standings table dynamically using Ergast API. |
| ~~Medium~~ | ~~**Driver points in classification table**~~ | ✅ **Done** — Integrated Ergast driver standings API to display total Drivers' Championship standings points in a `CH Points` column in the final classification table. |
| ~~Low~~ | ~~**Winner-based default selection**~~ | ✅ **Done** — Set default selected driver dynamically to the session winner (or driver with fastest lap in practice) on first load. |
| ~~Medium~~ | ~~**Dynamic calendar default GP/season**~~ | ✅ **Done** — Automatically resolve the default season to the most recent calendar year and default Grand Prix index to the most recently completed race using system date comparison. |
| ~~Medium~~ | ~~**Driver name/number classification columns**~~ | ✅ **Done** — Combined driver number, abbreviation, and lastName in the official session classification table, resolving it safely directly from results DataFrame columns. |
| ~~High~~ | ~~**Pit stop counts in classification**~~ | ✅ **Done** — Renders a `Stops` column in the session classification table, calculated by counting laps with both non-null `PitInTime` and `PitOutTime`. |
| ~~Low~~ | ~~**Design origin footer**~~ | ✅ **Done** — Renders a styled, theme-friendly footer displaying `Made proudly in Great Britain 🇬🇧` at the bottom of the page and welcome states. |
| ~~Medium~~ | ~~**Responsive mobile telemetry**~~ | ✅ **Done** — Matplotlib telemetry charts scale dynamically to fit mobile viewports without horizontal scrolling or clipping. |
| ~~High~~ | ~~**Mini-Sector Dominance Map**~~ | ✅ **Done** — AWS-style micro-sector track map colouring based on interpolated telemetry distance/speed arrays. |
| ~~Medium~~ | ~~**Corner-by-Corner Analysis**~~ | ✅ **Done** — Extracts corner coordinates via `get_circuit_info()`, detects braking point and apex speed, and renders racing line and speed profile comparisons. |

---

## 18. Solved Issues & Changelog

Every resolved GitHub issue and pull request in the repository is logged below in strict reverse-chronological order:

> [!NOTE]
> **GitHub ID Numbering**: GitHub utilizes a single, unified auto-incrementing ID counter for both **Issues** and **Pull Requests**. IDs between #85 and #100 (e.g. #86–#99) represent feature and documentation Pull Requests opened during development.

- **PR #114** / **Issue #85** (`feat: Multi-Driver Grid Analysis & Heatmaps`): Introduced multi-driver grid analysis matrix supporting `Sector Split Deltas`, `Lap-by-Lap Pace Heatmap`, and `Top Speed Matrix` across 3 to 20 drivers using custom interactive Plotly heatmaps.
- **PR #113** / **Issue #112** (`fix: Dark mode functionality & theme injection in app.py`): Invoked `inject_styles()` early in `app.py` on every render cycle to ensure dark/light mode state and constructor team themes are applied immediately.
- **PR #111** (`docs: update Section 18 changelog for Issue #109`): Updated Section 18 of `DOCS.md` with PR #110 / Issue #109 entry.
- **PR #110** / **Issue #109** (`fix: double period & session state reset on Session Loading Error`): Cleans up session state variables and formats exception error messages without trailing double periods (`servers..`) when session loading fails.
- **PR #108** / **Issue #107** (`docs: update issue list chronology in developer manual`): Updated Section 18 of `DOCS.md` to prepend PR #106 / Issue #105 and PR #104.
- **PR #106** / **Issue #105** (`docs: update README documentation for Live Timing Mode and troubleshooting fixes`): Updated `README.md` Troubleshooting section to document Real-Time Live Timing Mode and enforced British English spellings.
- **PR #104** (`docs: clarify GitHub ID sequence & list PRs/Issues chronologically`): Added explanatory note on GitHub's unified ID sequence and formatted Section 18 of `DOCS.md` in strict reverse-chronological order.
- **PR #103** / **Issue #102** (`docs: Add Solved Issues Changelog & Summary List to Documentation`): Added Section 18 to `DOCS.md` and anchor link in `README.md` logging all historical closed issues with 1-line explanations.
- **PR #101** / **Issue #100** (`fix: NameError _PATCH_STATUS is not defined in app.py`): Imported `_PATCH_STATUS` and `test_curl_cffi_request` into `app.py` to fix NameError in sidebar diagnostics.
- **PR #99** (`docs: expand user guide & developer manual for Live Timing Mode`): Expanded `README.md` How to Use section and `DOCS.md` testing documentation for Live Timing Mode.
- **PR #98** / **Issue #84** (`feat: Real-Time Live Timing Mode via FastF1 SignalR client`): Added background WebSocket stream recording via `SignalRClient`, `LiveTimingData` session parsing, broadcast status banner, and auto-refresh controls.
- **PR #97** (`docs: update manuals for pytest automated tests`): Updated `README.md`, `DOCS.md`, and `AGENT.md` guidelines to require running pytest before code commits.
- **PR #96** / **Issue #83** (`test: Introduce pytest automated testing suite for data wrangling`): Implemented a `pytest` unit test suite in `tests/` with mock fixtures and GitHub Actions CI workflow integration.
- **PR #95** (`docs: refine README guidelines for modular structure`): Updated contributing guidelines in `README.md` to reference `src/` package modules.
- **PR #94** (`docs: update documentation for issue 82 modular structure`): Synchronised `README.md`, `DOCS.md`, and `AGENT.md` for codebase modularisation.
- **PR #93** / **Issue #82** (`tech-debt: Refactor monolithic app.py into modular directory structure`): Modularised `app.py` into `src/data/loader.py`, `src/ui/styles.py`, `src/ui/components.py`, `src/charts/plotly.py`, and `src/charts/matplotlib.py`.
- **PR #91** / **Issue #81** (`feat: Tyre Degradation Modeling and Pace Drop-off`): Added OLS linear regression stint degradation scatter charts and pace drop-off summary tables.
- **PR #90** / **Issue #80** (`feat: Corner-by-Corner Analysis (Braking & Apex telemetry)`): Introduced interactive corner telemetry subplots mapping minimum speed, apex throttle, and braking points.
- **PR #89** / **Issue #78** (`feat: AWS-Style Mini-Sector Speed Dominance Map`): Divided track maps into 25 micro-sectors coloured by the fastest driver's pace dominance.
- **PR #88** / **Issue #76** (`docs: update all documentation files for recent features and footer sync`): Synchronised `README.md`, `DOCS.md`, and `AGENT.md` to cover latest telemetry features and footer rules.
- **PR #87** / **Issue #75** (`fix: sync bottom footer across all early exit states and pages`): Ensured `_render_footer()` is called across all error boundaries and early exit states.
- **PR #86** / **Issue #73** (`style: adjust telemetry graphs to fit mobile screens dynamically`): Removed static minimum width CSS bounds from Matplotlib images to enable responsive scaling on mobile viewports.
- **Issue #72** (`feat: add bottom footer with made proudly in great britain`): Added a styled footer displaying "Made proudly in Great Britain 🇬🇧" at the bottom of all pages.
- **Issue #68** (`chore: clean up unused helper functions and redundant code comments`): Removed dead code, unused helper variables, and consolidated compound colour definitions.
- **Issue #66** (`bug: driver name and abbreviation missing in official classification table`): Resolved driver name and team abbreviation lookup gaps in official session results.
- **Issue #64** (`feature: add number of pit stops to the official session classification table`): Added cumulative pit stop counts (`Stops`) to the session classification table.
- **Issue #60** (`feature: show driver's name alongside driver number in official classification table`): Formatted driver numbers into `ABR · Full Name` display labels in classification tables.
- **Issue #56** (`feature: add constructors championship standings table`): Integrated Ergast API constructor standings tables with team-colour accent highlighting.
- **Issue #55** (`feature: add drivers championship points column to official classification table`): Added cumulative Drivers' Championship points (`CH Points`) to session classification tables.
- **Issue #54** (`feature: set default selected driver to the race/session winner`): Automatically selected the session winner (or fastest flyer) as the default driver on page load.
- **Issue #53** (`feature: set default season and session to the most recent ones`): Automatically defaulted season, Grand Prix, and session selectors to the latest completed event.
- **Issue #49** (`Bug: Track map fails to display when telemetry/position data is missing`): Handled missing position telemetry gracefully without crashing track map renders.
- **Issue #48** (`Bug: UnhashableParamError on 'results_df' in _build_final_classification`): Cast `FastF1` custom DataFrame subclasses to standard `pd.DataFrame` to prevent `@st.cache_data` hashing errors.
- **Issue #46** (`Feature: Add a final classification leaderboard at the end of the session`): Rendered complete official session standings tables covering Race, Sprint, Qualifying, and Practice.
- **Issue #44** (`bug: side navigation is not perfectly hidden in mobile view`): Fixed CSS transform rules to allow the Streamlit sidebar to collapse completely on mobile viewports.
- **Issue #42** (`bug: FastF1 live timing stream is not supported for active sessions`): Added live timing CDN data stream fallback handling.
- **Issue #40** (`bug: graphs fail to load due to requests_cache AttributeError`): Added `MockRaw` transport wrappers to fix `requests_cache` SQLite serialization during proxy requests.
- **Issue #38** (`style: optimize mobile responsive layout for vertical screens`): Applied responsive CSS styles and media queries for vertical mobile viewports.
- **Issue #36** (`bug: FastF1 data loading fails due to CloudFront 403 blocks`): Implemented `curl_cffi` TLS impersonation to bypass CloudFront and Cloudflare anti-bot blocks on datacenter IPs.
- **Issue #33** (`fix: curl_cffi patch inactive on Streamlit Cloud due to IS_CLOUD detection failure`): Made the `curl_cffi` HTTPAdapter patch unconditional for all F1 domain requests.
- **Issue #30** (`fix: curl_cffi monkey-patch intercepts wrong requests layer`): Intercepted `requests.adapters.HTTPAdapter.send` at the lowest transport level so all FastF1 requests bypass bot blocks.
- **Issue #28** (`fix: UnhashableParamError on session_obj in _build_gap_data`): Replaced direct session object parameter passing with string session keys to fix cache hashing.
- **Issue #26** (`fix: resolve F1 Timing API Cloudflare block on Streamlit Cloud`): Added fallback user-agent headers and mirror URL rotation.
- **Issue #25** (`fix: bypass anti-bot filters on mirror by setting browser headers`): Injected Chrome 124 browser headers into outbound request sessions.
- **Issue #23** (`fix: override fastf1._api.base_url to point to livetiming mirror`): Added automatic fallback to FastF1 livetiming mirror endpoints.
- **Issue #21** (`fix: bypass Cloudflare bot-block on Streamlit Cloud`): Configured mirror URL fallback for live timing requests.
- **Issue #19** (`fix: implement progressive fallback loading inside load_session`): Added multi-stage fallback attempts (full → no-messages → no-weather → laps-only) in `load_session`.
- **Issue #17** (`fix: auto-clear cache when FastF1 session load raises data not loaded yet`): Implemented automatic local cache clearing when loading an incomplete or corrupt session.
- **Issue #15** (`Session Data Unavailable: FastF1 could not load lap data`): Added user-friendly error banners and automatic cache reset buttons.
- **Issue #13** (`feat: dynamically populate session selection dropdown based on event schedule`): Dynamically populated session dropdowns (FP, Quali, Sprint, Race) based on official event schedules.
- **Issue #11** (`Improve mobile and vertical phone layout compatibility`): Added mobile viewport meta tags and responsive container styling.
- **Issue #10** (`fix(pwa): Replace blob URL manifest with proper installable PWA manifest`): Embedded base64 PNG icons and W3C Web Manifest for installable PWA support.
- **Issue #9** (`Fuel-corrected qualifying sim`): Built the fuel-adjusted pace calculation model and simulated qualifying leaderboard.
- **Issue #8** (`Multi-session comparison`): Added Session 2 selector and head-to-head comparison mode.
- **Issue #6** (`Driver Input Track Map`): Created driver pedal telemetry map tabs (Throttle, Brake, Gear).
- **Issue #4** (`Sector Mini-map Colouring`): Added track map speed heatmap rendering.
- **Issue #1** (`Adding historical team colours`): Configured historical constructor team colours from 2018 to present.


---

## 19. Multi-Driver Grid Analysis & Heatmaps Architecture

The **Multi-Driver Grid Analysis & Heatmaps** module (`src/data/loader.py`, `src/charts/plotly.py`, `src/ui/components.py`) expands driver comparison from 1v1 to full grid-wide matrix analysis.

### Data Layer (`_build_grid_heatmap_data`)
- **Cached Builder**: Annotated with `@st.cache_data(show_spinner=False, ttl=3600)` to ensure fast rerenders.
- **Data Structuring**:
  - `Sector Split Deltas`: Calculates `Sector 1`, `Sector 2`, `Sector 3`, `Theoretical Best`, and `Actual Best` for selected drivers, returning delta matrices (+seconds) relative to the overall grid-best split times.
  - `Lap-by-Lap Pace Heatmap`: Computes a `Drivers × Laps` matrix calculating pace deltas relative to the fastest lap time of each lap.
  - `Top Speed Matrix`: Extracts maximum speeds for `SpeedST`, `SpeedI1`, `SpeedI2`, and `SpeedFL` across drivers, returning speed deficits (km/h) relative to the top speed.

### Visualisation Layer (`build_grid_heatmap_fig`)
- **Plotly Heatmap**: Renders `go.Heatmap` with high-contrast broadcast color scales (`#00E676` green for 0.0s / top speed, scaling to `#FF5252` red for deficits).
- **Interactive Tooltips**: Formats `customdata` values to show absolute times alongside relative deltas.
- **Responsive Layout**: Dynamically computes figure height based on driver selection count (`max(420, len(drivers) * 32 + 100)`).

---

*Last updated: July 2026. Keep this document in sync when adding new sections, helpers, or architectural patterns.*
