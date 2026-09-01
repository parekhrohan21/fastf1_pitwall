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
20. [Post-Race Debrief Exporter (PDF)](#20-post-race-debrief-exporter-pdf)
21. [Driver Consistency Index & Stint Pace Distribution Architecture](#21-driver-consistency-index--stint-pace-distribution-architecture)
22. [Track Temperature & Weather Impact Correlation Architecture](#22-track-temperature--weather-impact-correlation-architecture)
23. [Multi-Year Historical Lap Comparison Architecture](#23-multi-year-historical-lap-comparison-architecture)
24. [Corner Analysis — Steering & DRS Telemetry Subplots Architecture](#24-corner-analysis--steering--drs-telemetry-subplots-architecture)
25. [Predictive Tyre Degradation & Thermal Crossover Matrix Architecture](#25-predictive-tyre-degradation--thermal-crossover-matrix-architecture)
26. [Interactive Telemetry Channel Toggle & Custom Trace Filtering Architecture](#26-interactive-telemetry-channel-toggle--custom-trace-filtering-architecture)



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

FastF1 identifies drivers by **number strings** (`"4"`, `"81"`), not names. Always use numbers as the internal key. Convert to display names only at render time via `_fmt_driver1()` / `_fmt_driver2()`.



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
| `_build_consistency_analysis(driver, sess_k, laps_df)` | `driver, sess_key, laps_df` |
| `_build_weather_correlation_data(sess_k, laps_df, sess_obj)` | `sess_key, laps_df, sess_obj` |
| `_build_multi_year_comparison(tel1, tel2, label1, label2, ...)` | `tel1, tel2, label1, label2, lap1_time_s, lap2_time_s` |

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

### `_fmt_driver1(num: str) -> str` / `_fmt_driver2(num: str) -> str`
Formatting closures built per-session by `_build_driver_labels()`. Each closure captures the `_drv_labels` dict for its respective session (Driver 1 vs. Driver 2 compare session).
Returns `_drv_labels.get(num, num)` — formatted name like `"NOR · Norris"` or the raw driver number as fallback.
Use these everywhere a driver number is displayed to a user. **Never use raw driver numbers directly in the UI.**

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

### `_build_race_control_messages(sess_k: str, _sess_obj) -> pd.DataFrame | None`
Parses `sess.race_control_messages` into a classified DataFrame with a `Category` column (SC, VSC, Red, Yellow, Clear, Investigation). Returns `None` if unavailable. Used to populate the Race Control Feed table and overlay flag zones on Lap History and Gap charts.

### `_build_grid_heatmap_data(sess_k, laps_df, selected_drivers, mode) -> dict | None`
Builds grid-wide analytical data matrices for multi-driver heatmap analysis. Supports three modes: `"Sectors"` (S1/S2/S3/Theoretical delta from P1), `"Laps"` (lap-by-lap pace heatmap), `"Speed"` (ST/I1/I2/FL top speed deficit matrix). Returns `None` if fewer than 3 drivers selected.

### `render_tyre_crossover_matrix(table_rows, fmt_driver1, fmt_driver2, driver1, ...)`
Renders the full-field **Tyre Life & Crossover Prediction Matrix** HTML table after the degradation summary. Reads `cliff_lap`, `remaining_laps`, `pit_window_low/high` from `table_rows` (produced by `build_tyre_deg_fig`). Applies urgency colour-coding per row (🟢/🟡/🔴/✅). Returns early silently if no cliff estimates are available.

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
build_undercut_chart()  ← Pit Strategy & Undercut Analysis (Plotly gap line chart + metrics)
        │
build_chart()           ← 6-channel Telemetry (Matplotlib)
        │
render_telemetry_export_panel() ← Multi-Format Export panel — CSV, Apache Parquet (.parquet), JSON (.json)
        │
Speed Delta             ← Matplotlib fill-between (compare mode only)
Time Delta (Cont.)      ← Matplotlib fill-between (compare mode only)
        │
_render_leaderboard()   ← Fastest Laps Leaderboard (HTML table)
        │
_build_ideal_lap()      ← Ideal Lap vs Actual Lap — best S1+S2+S3 per driver, delta cards + full table
        │
Gap to Leader           ← Plotly line chart (all drivers)
        │
Race Control Feed       ← Filterable st.dataframe of flag events + flag zones overlaid on Lap History & Gap charts
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
| Pit Strategy & Undercut | Plotly | — (inline logic) | `build_undercut_chart` | `_all_laps1`, `_all_laps2` |
| Tyre Degradation + Crossover Matrix | Plotly + HTML | `_build_tyre_deg_data` | `build_tyre_deg_fig` + `render_tyre_crossover_matrix` | `laps_df` filtered by driver; linear & quadratic OLS + cliff lap prediction. |
| Driver Consistency | Plotly | `_build_consistency_analysis` | `build_stint_consistency_fig` | `laps_df` filtered by driver; std dev, clean air vs traffic, violin/boxplot stint distribution. |
| 6-Channel Telemetry | Matplotlib | `get_telemetry_cached` | `build_chart` | `lap.get_car_data()` |
| Export Telemetry (CSV, Parquet, JSON) | CSV/Parquet/JSON | `_build_export_csv`, `_build_export_parquet`, `_build_export_json` | `render_telemetry_export_panel` | `tel_df` + `lap_obj` metadata & sector times |
| Speed Delta | Matplotlib | — (inline) | — (inline) | `tel1`, `tel2` DataFrames |
| Time Delta | Matplotlib | `build_time_delta_chart` | `src/charts/matplotlib.py` | `lap1`, `lap2` Laps |
| Fastest Laps Leaderboard | HTML | `_build_leaderboard` | `_render_leaderboard` | `laps_df` grouped by driver |
| Ideal Lap vs Actual Lap | HTML | `_build_ideal_lap` | `_render_ideal_lap_section` | `laps_df` sector times per driver |
| Gap to Leader | Plotly | `_build_gap_data` | `_render_gap_to_leader_section` | `laps_df` cumulative time |
| Race Control Feed | st.dataframe + vrect | `_build_race_control_messages` | inline | `sess.race_control_messages` |
| Race Position | Plotly | `_build_position_data` | `_render_position_section` | `laps_df["Position"]` per driver |
| Track Speed Map | Plotly | `_get_telemetry_for_map` | `_speed_map_fig` | `lap.get_car_data()`. In compare mode, colours mini-sectors by dominance. |
| Driver Inputs Map | Plotly | `_get_telemetry_for_map` | `_input_map_fig` | `lap.get_car_data()`. Colours markers by Throttle/Brake state. |
| Corner Analysis (4-subplot) | Plotly subplots | `_get_telemetry_for_map` | `build_corner_fig` (`with map_tab4`) | `lap.get_car_data()`. 4 subplots: Racing Line, Speed Profile, Steering Angle (°), DRS Activation Status. |
| Race Replay | Plotly animated | — (inline) | inline | `sess.pos_data` per driver |
| Weather Correlation | Plotly dual-axis | `_build_weather_correlation_data` | `build_weather_correlation_fig` | `sess.weather_data` merged on `Time` via `pd.merge_asof`. Pearson pace-temp correlation, rain crossover detection. |
| Multi-Year Comparison | Plotly dual-subplot | `_build_multi_year_comparison` | `build_multi_year_comparison_fig` | Interpolated telemetry on 500-pt distance grid. Speed overlay + continuous time delta. |
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
- [ ] Tyre Degradation chart renders with regression trendlines and cliff vlines
- [ ] Tyre Life & Crossover Prediction Matrix renders with urgency badges
- [ ] Telemetry chart renders all 6 channels
- [ ] Export CSV button downloads a valid file with Sector1/2/3 columns
- [ ] Fastest Laps Leaderboard shows all drivers
- [ ] Ideal Lap table renders with correct S1/S2/S3 and theoretical times
- [ ] Delta card shows green (≤0.05s) or red (>0.05s) colour correctly
- [ ] Gap to Leader chart renders
- [ ] Race Position chart renders (Race/Sprint sessions only)
- [ ] Track Map renders with speed colours
- [ ] Corner Analysis tab: 4-subplot layout (Racing Line, Speed, Steering, DRS) renders
- [ ] Driver Consistency section renders violin/boxplot with stat cards
- [ ] Weather Impact Correlation chart renders with dual axis
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
| ~~High~~ | ~~**Driver Consistency Index & Stint Pace Distribution**~~ | ✅ **Done** — `_build_consistency_analysis` evaluates std dev, Consistency Score, Clean Air Pace, and Traffic Deficit. Renders Violin/Boxplot distributions (`build_stint_consistency_fig`). |
| ~~High~~ | ~~**Track Temperature & Weather Impact Correlation**~~ | ✅ **Done** — `_build_weather_correlation_data` merges weather timeseries via `pd.merge_asof`. Dual-axis chart overlaying Track Temp (°C) on driver pace (`build_weather_correlation_fig`). |
| ~~Medium~~ | ~~**Multi-Year Historical Lap Comparison**~~ | ✅ **Done** — `_build_multi_year_comparison` aligns two telemetry traces to a 500-pt distance grid. Plots speed profile overlays and continuous time delta curves (`build_multi_year_comparison_fig`). |
| ~~Medium~~ | ~~**Driver Steering & DRS Subplots in Corner Analysis**~~ | ✅ **Done** — `build_corner_fig` expanded to 4 subplots: Racing Line, Speed, Steering Angle (°), DRS Activation. Metrics include Max Steering Angle and DRS Activated status. |
| ~~Medium~~ | ~~**Interactive Telemetry Channel Toggle & Custom Trace Filtering**~~ | ✅ **Done** — Added dynamic multiselect channel filter in `app.py` and updated `build_chart` in `src/charts/matplotlib.py` with custom channel filtering and proportional layout height scaling. |
| ~~Low~~ | ~~**High-Throughput Telemetry Data Exporter (Parquet & JSON)**~~ | ✅ **Done** — Added dynamic format selector (CSV, Parquet, JSON) in `render_telemetry_export_panel`, with `_build_export_parquet` and `_build_export_json` in `src/data/loader.py`. |



---

## 18. Solved Issues & Changelog

Every resolved GitHub issue and pull request in the repository is logged below in strict reverse-chronological order:

> [!NOTE]
> **GitHub ID Numbering**: GitHub utilizes a single, unified auto-incrementing ID counter for both **Issues** and **Pull Requests**. IDs between #85 and #100 (e.g. #86–#99) represent feature and documentation Pull Requests opened during development.

- **PR #158** / **Issue #139** (`feat: High-Throughput Telemetry Data Exporter (Parquet & JSON)`): Added multi-format export support under the Telemetry section for Apache Parquet (`.parquet`) and structured JSON (`.json`) alongside CSV. Refactored telemetry export panel into `render_telemetry_export_panel` in `src/ui/components.py`, implemented `_build_export_telemetry_df`, `_build_export_parquet`, and `_build_export_json` in `src/data/loader.py`, added `pyarrow>=14.0.0` to requirements, and added full test suite (9 unit tests in `tests/test_telemetry_export.py`).
- **PR #147** / **Issue #138** (`feat: Interactive Telemetry Channel Toggle & Custom Trace Filtering`): Added dynamic channel selection multiselect in `app.py` under the Telemetry section, updated `build_chart` in `src/charts/matplotlib.py` to support dynamic channel subset filtering (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) with proportional figure height scaling (`max(2.8, sum(h_ratios) * 1.05 + 0.5)`), restored missing `CHANNEL_CONFIG` and `mpatches` definitions, and added comprehensive pytest suite (9 new unit tests).
- **Commit `3741b0d`** (`fix: resolve NameError for hex_to_rgb in app.py`): Fixed a crash in the Ideal Lap vs Actual Lap leaderboard by adding the missing `hex_to_rgb` import in `app.py` after recent file refactoring.

- **PR #143** / **Issue #137** (`feat: Predictive Tyre Degradation & Thermal Crossover Matrix`): Enhanced `_build_tyre_deg_data` with quadratic polynomial regression, cliff lap estimation (pace +1.5 s threshold), remaining laps to cliff, and pit window (±3 laps). Updated `build_tyre_deg_fig` with quadratic thermal curve overlay and dotted cliff vline markers. Added `render_tyre_crossover_matrix` to `src/ui/components.py` with urgency colour-coding (🟢/🟡/🔴/✅). 13/13 new unit tests pass.


- **PR #141** / **Issue #136** (`feat: Driver Steering & DRS Telemetry Subplots in Corner Analysis`): Expanded `build_corner_fig` in `src/charts/plotly.py` into a 4-subplot layout adding Steering Angle (`Steering` in ° degrees) and DRS activation (`DRS` status) profiles alongside Racing Line and Speed. Updated `compute_stats` to extract `max_steering` and `drs_active`. Metric cards display Max Steering Angle and DRS Activated status.
- **PR #140** / **Issue #121** (`feat: Multi-Year Historical Lap Comparison`): Implemented `_build_multi_year_comparison` (500-pt distance grid interpolation, speed delta, continuous time delta), `build_multi_year_comparison_fig` (dual-subplot Plotly), and `_render_multi_year_comparison_section` (metric cards: Era Lap Time Delta, Top Speed ST, Min Apex Speed, Full Throttle %).
- **PR #135** / **Issue #120** (`feat: Track Temperature & Weather Impact Correlation`): Implemented `_build_weather_correlation_data` (timeseries weather merge via `pd.merge_asof`), `build_weather_correlation_fig` (dual-axis Plotly), and `_render_weather_correlation_section` (metric cards: Track Temp Range, Pace-Temp Correlation, Weather Condition, Rain Crossover).
- **PR #132** / **Issue #119** (`feat: Driver Consistency Index & Stint Pace Distribution`): Implemented `_build_consistency_analysis` (std dev, Consistency Score, Clean Air Pace, Traffic Deficit per stint), `build_stint_consistency_fig` (Plotly Violin/Boxplot), and `_render_consistency_section` (metric cards and stint breakdown table).
- **PR #127** / **Issue #123** (`docs: document code review artifact process in README and AGENT.md`): Updated `README.md` and `AGENT.md` to formalize the code review process by mandating the creation of a `code_review_issue_<number>.md` artifact.
- **PR #126** (`docs: update changelog for issues 116, 117, and 118`): Updated Section 18 of `DOCS.md` to properly document recent completed features in reverse chronological order.
- **PR #125** / **Issue #118** (`feat: Race Control Incident Timeline & Flag Overlays`): Parses `sess.race_control_messages` into a classified DataFrame (SC, VSC, Red, Yellow, Clear, Investigation). Overlays semi-transparent flag zone bands on both the Lap Time History and Gap to Leader Plotly charts. Adds a searchable, filterable **Race Control Feed** table section below the Gap chart.
- **Issue #117** (`feat: Pit Strategy Simulator`): Added automated strategic battle analysis pairing adjacent pit stops (±3 laps) between two drivers in compare mode, calculating pre/post pit gaps, and rendering a Plotly pit window gap chart with outcome metrics cards.
- **Issue #116** (`feat: Continuous Time Delta per Meter Chart`): Added a continuous time delta chart using `fastf1.utils.delta_time` below the speed delta chart in compare mode to visualise exact time gained/lost (in seconds) vs distance (meters).
- **PR #115** (`docs: update README user guide & DOCS manual for grid heatmaps feature`): Updated README.md and DOCS.md to reflect the grid heatmaps feature.
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



## 20. Post-Race Debrief Exporter (PDF)

The **Post-Race Debrief Exporter** (`src/ui/components.py`, `app.py`) enables the automated generation of printable broadcast-style reports.

### Architecture Overview
- **Chart Collection (`_export_figs`)**: Key Plotly figures (Lap Time History, Tyre Stints, Gap to Leader, Position History) are saved to an `_export_figs` dictionary within `app.py` after being rendered.
- **Image Conversion (`kaleido`)**: In the `_build_pdf_report` function, each captured Plotly figure is rasterized into a high-resolution PNG using the `fig.to_image()` method powered by the `kaleido` engine.
- **PDF Generation (`fpdf2`)**: The `FPDF` class is used to compile these static PNGs into a paginated document layout, featuring custom title headers and automatic page breaking.
- **User Interface**: `render_export_section` surfaces a Streamlit `st.download_button` in the sidebar allowing the user to seamlessly generate and download the report client-side.


## 21. Driver Consistency Index & Stint Pace Distribution Architecture

The **Driver Consistency Index & Stint Pace Distribution** module (`src/data/loader.py`, `src/charts/plotly.py`, `src/ui/components.py`, `app.py`) evaluates lap time variance per stint to measure race pace consistency and visualises pace distributions.

### Data Layer (`_build_consistency_analysis`)
- **Filtering**: Excludes in-laps (`PitInTime`), out-laps (`PitOutTime`), inaccurate laps (`IsAccurate == False`), safety car / red flag periods (`TrackStatus` containing `"4|5|6|7"`), and extreme pace outliers (> 1.20x median).
- **Metric Computation**:
  - `Overall Std Dev`: Standard deviation of lap times across clean flyer laps in seconds.
  - `Consistency Index`: 0–100% normalized score calculated as `max(0, min(100, 100 - std * 30))`.
  - `Clean Air vs. Traffic Deficit`: Categorizes laps based on track position and time gap (gap <= 1.5s = traffic). Calculates median clean air pace vs traffic pace to evaluate seconds lost per lap in traffic.

### Visualisation Layer (`build_stint_consistency_fig`)
- **Plotly Violin & Boxplot**: Renders `go.Violin` per stint with `box_visible=True`, `meanline_visible=True`, and `points="all"` jittered lap data points.
- **Custom Color Coding**: Matched to constructor team colors (`driver_color_map`).

### UI Layer (`_render_consistency_section`)
- **Metric Cards**: Renders 4 high-level stat cards per selected driver (*Consistency Index*, *Lap Time Std Dev*, *Clean Air Pace*, *Traffic Deficit*).
- **Stint Breakdown Table**: Displays structured table summarizing Stint #, Compound, Valid Laps count, Median Pace, Std Dev (±s), and Stint Consistency Score.


## 22. Track Temperature & Weather Impact Correlation Architecture

The **Track Temperature & Weather Impact Correlation** module (`src/data/loader.py`, `src/charts/plotly.py`, `src/ui/components.py`, `app.py`) evaluates track and air temperature shifts, rainfall intensity, and weather transitions against driver lap times.

### Data Layer (`_build_weather_correlation_data`)
- **Timeseries Weather Merging**: Uses `pd.merge_asof` on lap completion timestamps (`Time`) to align `_session_obj.weather_data` (`TrackTemp`, `AirTemp`, `Rainfall`, `Humidity`, `WindSpeed`) with each driver's lap record.
- **Statistical Analytics**:
  - `Track Temp Range`: Minimum, maximum, and average track temperature (°C) across the session.
  - `Rain Crossover Laps`: Detects exact lap numbers where compound usage transitions between Slicks (Soft, Medium, Hard) and Wet Tyres (Intermediate, Wet).
  - `Pace-Temp Correlation`: Pearson correlation coefficient ($r$) between `TrackTemp` (°C) and lap time (s) across clean flyer laps.

### Visualisation Layer (`build_weather_correlation_fig`)
- **Plotly Dual-Axis Layout**:
  - Primary Y-axis (left): Driver lap time traces (colored by constructor team color).
  - Secondary Y-axis (right): Track temperature curve (°C) rendered with a filled area gradient.
- **Annotations & Shading**:
  - Shaded vertical bands (`rgba(0,191,255,0.12)`) highlighting rainfall laps.
  - Dashed vertical lines with annotations indicating Slick ↔ Wet crossover lap numbers.

### UI Layer (`_render_weather_correlation_section`)
- **Top Metric Cards**: Renders 4 high-level cards (*Track Temp Range*, *Pace-Temp Correlation*, *Weather Condition*, *Rain Crossover*).
- **Interactive Chart**: Displays the dual-axis Plotly figure.


## 23. Multi-Year Historical Lap Comparison Architecture

The **Multi-Year Historical Lap Comparison** module (`src/data/loader.py`, `src/charts/plotly.py`, `src/ui/components.py`, `app.py`) enables multi-season telemetry comparisons across different technical regulation eras.

### Data Layer (`_build_multi_year_comparison`)
- **Distance-Grid Alignment**: Interpolates speed, time, throttle, and distance arrays onto a unified distance grid (`np.linspace(0, max_dist, 500)`).
- **Metric Computation**:
  - `Era Lap Time Delta`: Computes exact lap time difference (s) between eras.
  - `Top Speed & Apex Speed`: Extracts maximum straight-line speed and minimum cornering speed per era.
  - `Full Throttle Ratio`: Calculates percentage of track distance driven at 100% throttle.
  - `Continuous Time Delta`: Integrates speed delta array over distance to compute time gained or lost per meter.

### Visualisation Layer (`build_multi_year_comparison_fig`)
- **Dual-Subplot Layout**:
  - Subplot 1 (top): Speed telemetry profile overlays (km/h) for Era 1 (solid line) vs Era 2 (dashed line).
  - Subplot 2 (bottom): Continuous time delta trace (Δ seconds) with filled area styling.

### UI Layer (`_render_multi_year_comparison_section`)
- **Metric Cards**: Displays 4 stat cards (*Era Lap Time Delta*, *Top Speed*, *Min Apex Speed*, *Full Throttle %*).
- **Chart Render**: Renders the Plotly dual-subplot figure.

---

## 24. Corner Analysis — Steering & DRS Telemetry Subplots Architecture

The **Corner-by-Corner Analysis** module (`src/charts/plotly.py` → `build_corner_fig`, `src/ui/components.py` → `render_maps_block`, `compute_stats`) was expanded from a 2-subplot layout (Racing Line, Speed) to a full **4-subplot telemetry layout** adding Steering Angle and DRS activation traces.

### Data Layer (`compute_stats` + `get_telemetry_cached`)
- **Telemetry Slice**: Telemetry is sliced to a distance window `[apex_distance − 200, apex_distance + 100]` around the detected corner apex.
- **Steering Angle**: `tel["Steering"]` is coerced with `pd.to_numeric(..., errors="coerce")` and the absolute max is extracted as `max_steering` (°).
- **DRS Status**: `tel["DRS"]` is coerced with `pd.to_numeric(..., errors="coerce")`; DRS is considered **active** if any sample in the corner window records a DRS value ≥ 10.
- **Existing Metrics**: Apex Speed (min Speed in window), Braking Point (first frame with `Brake > 0`, falling back to max deceleration `ds < −1`).

### Visualisation Layer (`build_corner_fig`)
Utilises `plotly.subplots.make_subplots` with 4 rows and `row_heights=[0.35, 0.28, 0.22, 0.15]`:

| Row | Subplot | Content |
|---|---|---|
| 1 | Racing Line | X/Y coordinate scatter with star marker for apex, cross marker for braking point |
| 2 | Speed Profile | Speed (km/h) vs Distance relative to apex (m) |
| 3 | Steering Angle | Steering (°) vs Distance relative to apex (m) — absolute value displayed for clarity |
| 4 | DRS Status | DRS activation bar/line vs Distance — 0 = inactive, 1 = active |

- All distance arrays are shifted so that `d = 0` aligns to the apex point.
- Missing or all-NaN Steering/DRS columns are handled gracefully — subplots display "No data" annotations rather than crashing.

### UI Layer (`render_maps_block`)
- **Metrics Row**: Four metric cards displayed side-by-side: *Apex Speed*, *Braking Point*, *Max Steering (°)*, *DRS Activated*.
- **DRS Card**: Rendered as `"✅ Yes"` or `"❌ No"` based on the boolean `drs_active` flag from `compute_stats`.

### Robustness Notes
- **Type Safety**: Both `Steering` and `DRS` FastF1 channels can be returned as strings or mixed types; `pd.to_numeric(..., errors="coerce")` is mandatory before any numeric operation.
- **Graceful Fallback**: If `Steering` or `DRS` is unavailable (fully NaN), subplots render a centered annotation: `"No steering / DRS data available for this corner window."`.


---

## 25. Predictive Tyre Degradation & Thermal Crossover Matrix Architecture

The **Predictive Tyre Degradation & Thermal Crossover Matrix** module extends the existing OLS-based tyre degradation section with a non-linear thermal model that estimates when a tyre compound will reach a critical pace drop-off, enabling pit strategy window recommendations.

### Data Layer (`_build_tyre_deg_data` — `src/data/loader.py`)

**Existing behaviour (preserved):** Filters laps by `IsAccurate == True`, excludes TrackStatus `4/5/6/7`, and groups by `(Stint, Compound)` requiring ≥ 4 laps.

**New behaviour:**

| Step | Logic |
|---|---|
| **Linear regression** | `np.polyfit(x_vals, y_vals, 1)` → `slope`, `intercept`. Identical to previous behaviour; now stored as `slope` and `base_pace` keys. |
| **Quadratic regression** | `np.polyfit(x_vals, y_vals, 2)` → `(a, b, c)` only when stint has ≥ 5 laps. Stored as `quad_coeffs`. |
| **Cliff lap (quadratic)** | Solves `a·x² + b·x + (c − cliff_target) = 0` where `cliff_target = quad_base + 1.5`. Takes the larger root. Guards: `a > 1e-9`, `discriminant >= 0`, `x_cliff > x_vals.min()`. |
| **Cliff lap (linear fallback)** | When quadratic unavailable, solves `x_cliff = (base_pace + 1.5 − intercept) / slope`. Guard: `slope > 1e-6`. |
| **Remaining laps** | `max(cliff_lap − last_tyre_life, 0)` |
| **Pit window** | `[max(cliff_lap − 3, 1), cliff_lap + 3]` |

**New dict keys per stint:**
```python
{
    "slope": float,           # linear degradation rate (s/lap)
    "base_pace": float,       # linear intercept (base pace s)
    "quad_coeffs": tuple | None,  # (a, b, c) or None
    "last_tyre_life": int,    # last observed TyreLife
    "cliff_lap": int | None,  # predicted TyreLife cliff lap
    "remaining_laps": int | None,
    "pit_window_low": int | None,
    "pit_window_high": int | None,
    "cliff_threshold_s": float,  # always 1.5
}
```

### Visualisation Layer (`build_tyre_deg_fig` — `src/charts/plotly.py`)

| Addition | Description |
|---|---|
| Linear trendline extension | Extended 5 laps beyond `x_vals.max()` to show extrapolated trend |
| Quadratic thermal curve | `np.polyval([a, b, c], x_quad)` extending 8 laps beyond data; drawn at 55% opacity with team colour |
| Cliff vline | `fig.add_vline(x=cliff_lap, line_dash="dot", ...)` with `"⚠ Cliff ~Lap N"` annotation per stint |
| `table_rows` extended | New fields `cliff_lap`, `remaining_laps`, `pit_window_low`, `pit_window_high`, `last_tyre_life` included |

### UI Layer (`render_tyre_crossover_matrix` — `src/ui/components.py`)

Rendered immediately after the Degradation Rates Summary table. Columns:
- **Driver** (team colour) · **Stint** · **Compound** (coloured dot) · **Deg Rate** · **Model** (Quadratic/Linear) · **Cliff Lap (TyreLife)** · **Remaining** · **Pit Window** · **Status**

**Urgency logic (`_urgency`):**

| `remaining_laps` | Badge | Row tint |
|---|---|---|
| `None` | — | transparent |
| `<= 0` | ✅ Past Cliff | subtle white |
| `<= 3` | 🔴 Critical | red tint |
| `<= 8` | 🟡 Soon | amber tint |
| `> 8` | 🟢 Safe | green tint |

Early return with info message if no cliff estimates are available (insufficient laps or flat slope).

### Robustness Notes
- `try/except Exception` wraps the entire quadratic block; failures fall through to linear fallback.
- `try/except Exception: return None` at the outer function level prevents app crashes on any unexpected data shape.
- All new `table_rows` fields accessed with `.get()` in the figure builder for backward compatibility.


---

## 26. Interactive Telemetry Channel Toggle & Custom Trace Filtering Architecture

The **Interactive Telemetry Channel Toggle & Custom Trace Filtering** module enhances the static 6-channel telemetry view by allowing users to dynamically select, filter, and reorder specific telemetry channels on the fly via a Streamlit multiselect widget.

### Configuration Layer (`AVAILABLE_CHANNELS` & `CHANNEL_CONFIG` — `src/charts/matplotlib.py`)
- Defines the canonical configuration for all possible telemetry channels.
- `AVAILABLE_CHANNELS`: Ordered list of keys `["Speed", "Throttle", "Brake", "RPM", "Gear", "DRS"]`.
- `CHANNEL_CONFIG`: Dictionary mapping each channel to a tuple containing `(Label, DataFrame Column, Y-Axis Label, Height Ratio, Special Flag)`.

### Visualisation Layer (`build_chart` — `src/charts/matplotlib.py`)
- Accepts a `selected_channels` list (defaults to `AVAILABLE_CHANNELS`).
- Filters `CHANNEL_CONFIG` based on user selection.
- **Dynamic Layout Scaling**: Calculates the optimal figure height using `max(2.8, sum(h_ratios) * 1.05 + 0.5)` to ensure that charts don't compress vertically when multiple traces are disabled, maintaining aspect ratios for remaining traces.
- Renders `matplotlib` subplots dynamically using `GridSpec` with calculated `height_ratios`.
- Hides X-axis labels on all subplots except the bottom-most active trace.
- Fails safely (returns `None`) if `selected_channels` is empty or all selections are invalid.

### UI Layer (`app.py`)
- Uses `st.multiselect` in the Telemetry section, allowing users to toggle and reorder channels.
- Passes the selected list to `build_chart`.

### Robustness Notes
- Invalid channel selections in the array are ignored gracefully.
- Maintains the legacy method signature for backward compatibility, automatically falling back to rendering all 6 channels if `selected_channels` is omitted.

---

*Last updated: August 2026. Keep this document in sync when adding new sections, helpers, or architectural patterns.*
