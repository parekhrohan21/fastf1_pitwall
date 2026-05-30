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

---

## 1. Project Philosophy

The Pit Wall dashboard is built around three principles:

| Principle | What it means in practice |
|---|---|
| **Single source of truth** | One file (`app.py`) contains everything. No hidden config, no scattered modules. |
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

`COMPOUND_COLOURS` in the Constants block (~line 1349) is the **single source of truth** for all compound colours. Every consumer in the codebase derives from it — no inline dicts anywhere.

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

### Block 1 — Design System (lines 507–1124)
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

### Block 2 — Theme Override (lines 1125–1295)
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
```

Each chart section follows the same pattern:
1. `@st.cache_data` function builds the data
2. A figure-builder function creates the Plotly/Matplotlib figure
3. `st.plotly_chart(fig, width="stretch")` or `st.pyplot(fig, width="stretch")` renders it

---

## 10. Chart Inventory

| Chart | Library | Builder function | Figure function | Key data source |
|---|---|---|---|---|
| Session Statistics | HTML | — (inline) | `render_session_stats` | `sess.get_driver()`, `sess.laps` |
| Lap Time History | Plotly | `_build_lap_history` | `_lap_history_fig` | `sess.laps.pick_drivers()` — compound multiselect filter applied before render |
| Fuel-Adjusted Pace | Plotly | `_build_fuel_adjusted` | `_fuel_pace_fig` | `sess.laps.pick_drivers()` |
| Fuel-Corrected Qualifying Sim | HTML | `_build_fuel_sim_leaderboard` | `_render_fuel_sim_leaderboard` | `sess.laps` |
| Tyre Stint Timeline | Plotly | `_build_stints` | `_stint_fig` | `sess.laps.pick_drivers()` |
| Pit Stop Summary | HTML | `_build_pit_stops` | `_render_pit_stops` | `PitInTime`, `PitOutTime` |
| 6-Channel Telemetry | Matplotlib | `get_telemetry_cached` | `build_chart` | `lap.get_car_data()` |
| Export Telemetry CSV | CSV bytes | `_build_export_csv` | — | `tel_df` + `lap_obj` sector times |
| Speed Delta | Matplotlib | — (inline) | — (inline) | `tel1`, `tel2` DataFrames |
| Fastest Laps Leaderboard | HTML | `_build_leaderboard` | `_render_leaderboard` | `sess.laps.groupby("Driver")` |
| Ideal Lap vs Actual Lap | HTML | `_build_ideal_lap` | inline | `sess.laps` S1/S2/S3 min per driver |
| Gap to Leader | Plotly | `_build_gap_data` | inline | `sess.laps` cumulative time |
| Race Position | Plotly | `_build_position_data` | inline | `sess.laps["Position"]` per driver |
| Track Speed Map | Plotly | `_get_telemetry_for_map` | `_speed_map_fig` | `lap.get_car_data()`. In compare mode, colors sectors by dominance. |
| Driver Inputs Map | Plotly | `_get_telemetry_for_map` | `_input_map_fig` | `lap.get_car_data()`. Colors markers by Throttle/Brake state. |
| Race Replay | Plotly animated | — (inline) | inline | `sess.pos_data` per driver |

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

When you add a new Streamlit component that doesn't respond to theme changes, add a CSS override to the **Theme CSS block** (lines 1125–1295):

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

Use the section map in `AGENT.md` to find where in `app.py` your new section belongs. Insert after the closest related existing section.

### Step 2 — Add a section header

```python
# ── My New Section ────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>My New Section</div>", unsafe_allow_html=True)
```

### Step 3 — Write a cached data builder

```python
@st.cache_data(show_spinner=False, ttl=3600)
def _build_my_data(driver: str, sess_k: str) -> pd.DataFrame | None:
    """One-line docstring describing what this returns."""
    try:
        laps = st.session_state["session"].laps.pick_drivers(driver).copy()
        # ... transform data ...
        return result_df
    except Exception:
        return None
```

> Note: pass `sess_k` as a string parameter (not the session object) so `@st.cache_data` can hash it.

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
_my_data = _build_my_data(driver1, sess_key)
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

The heaviest single operation is `sess.load()` on first call. Everything else is sub-second once the session is cached.

---

## 16. Testing

There are currently no automated tests. The following are recommended additions:

### Unit tests (suggested with `pytest`)

```python
# tests/test_helpers.py
from app import format_laptime, hex_to_rgb
import pandas as pd

def test_format_laptime_normal():
    td = pd.Timedelta(seconds=86.543)
    assert format_laptime(td) == "1:26.543"

def test_format_laptime_null():
    assert format_laptime(pd.NaT) == "N/A"

def test_hex_to_rgb():
    assert hex_to_rgb("#FF8700") == "255,135,0"

def test_hex_to_rgb_short():
    assert hex_to_rgb("#FFF") == "255,255,255"
```

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
| ~~Medium~~ | ~~**Driver Input Track Map**~~ | ✅ **Done** — `_input_map_fig()` visualizes throttle/brake/coasting telemetry as colored markers on the track path. Supports side-by-side comparison. |
| Low | **Multi-session comparison** | Add a second set of year/GP/session selectors; load two sessions and pass both to chart builders |
| ~~Low~~ | ~~**Fuel-corrected qualifying sim**~~ | ✅ **Done** — Use fuel-adjusted pace median as a synthetic "single-lap pace" to simulate qualification order |
| ~~Tech debt~~ | ~~**Fix cache isolation**~~ | ✅ **Done** — All 7 data-builder functions (`_build_lap_history`, `_build_fuel_adjusted`, `_build_stints`, `_build_pit_stops`, `_build_leaderboard`, `_build_gap_data`, `_build_position_data`) now receive `laps_df: pd.DataFrame` as an explicit argument. `_all_laps = sess.laps.copy()` is extracted once after session load and passed to every builder. |
| ~~Tech debt~~ | ~~**Consolidate compound colour dicts**~~ | ✅ **Done** — `COMPOUND_COLOURS` is now the single canonical dict. `_CMP_PALETTE`, `cmp_dot`, and `cmp_colours_map` have all been removed. |

---

*Last updated: May 2026. Keep this document in sync when adding new sections, helpers, or architectural patterns.*
