# 🤖 AGENT.md — Pit Wall F1 Telemetry Dashboard

## Agent Role

You are the **Software Development & Maintenance Agent** for the **Pit Wall F1 Telemetry Dashboard** repository (`fastf1_pitwall`).

Your primary responsibilities are:

1. **Maintain** `app.py` as the single source of truth for the application.
2. **Update** features, fix bugs, and remove deprecated API usage proactively.
3. **Keep the project running** — ensure the app starts cleanly, loads session data, and renders all charts without errors.
4. **Preserve code quality** — enforce the standards defined in this file at all times.
5. **Keep `README.md` in sync** — every user-facing change to the app must be reflected in the README.

---

## Project Overview

| Property | Value |
| --- | --- |
| **Stack** | Python 3.11+ · Streamlit ≥ 1.44 · FastF1 ≥ 3.3 |
| **Entry point** | `app.py` (orchestrating `src/` package modules) |
| **Data source** | FastF1 library → official F1 timing API + Ergast |
| **Port** | `8501` (local and Docker) |
| **Cache dir** | `./cache/` (FastF1 disk cache, gitignored) |
| **Docker** | `Dockerfile` present; mount `./cache:/app/cache` |

---

## Repository File Map

```
fastf1_pitwall/
├── app.py              ← application entry point (orchestrates src/ packages)
├── src/                ← modular source package
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── loader.py   ← data fetching, caching, and proxy patching
│   ├── charts/
│   │   ├── __init__.py
│   │   ├── matplotlib.py ← Matplotlib figure builders (6-channel, speed delta)
│   │   └── plotly.py     ← Plotly figure builders (History, stints, gap, replay, maps, corner analysis)
│   └── ui/
│       ├── __init__.py
│       ├── styles.py    ← styling sheets, constants, PWA headers, dark/light injection
│       └── components.py ← layout rendering components (Summary, stats, classifications, map tabs, footer)
├── requirements.txt    ← pinned dependencies
├── Dockerfile          ← containerisation
├── .dockerignore
├── .gitignore
├── README.md           ← user-facing documentation (keep in sync)
├── AGENT.md            ← this file
├── DOCS.md             ← technical developer documentation
└── cache/              ← FastF1 disk cache (gitignored, never commit)
```

---

## Codebase Architecture Map

The application logic is modularised into individual packages under `src/` to separate data loading, UI layouts, and charts:

| Module | Purpose |
| --- | --- |
| `app.py` | Streamlit entry point. Initialises page configurations, loads UI sidebars, invokes data builders, and renders layout blocks. |
| `src/data/loader.py` | Configures FastF1 cache directory, runs Cloudflare/CloudFront TLS request monkey-patching, hosts all `@st.cache_data` session fetching and statistical data-builders (`_build_consistency_analysis`, `_build_tyre_deg_data`, `_build_grid_heatmap_data`, etc.), and provides multi-format telemetry exporters (`_build_export_csv`, `_build_export_parquet`, `_build_export_json`). |
| `src/ui/styles.py` | Housed with team/compound color constants, PWA manifest injections, CSS classes, transition JS scripts, and dark/light stylesheet togglers. |
| `src/ui/components.py` | Contains all Streamlit UI cards, weather grids, pit stop/ideal lap section details, final official classification tables, consistency section (`_render_consistency_section`), weather correlation section (`_render_weather_correlation_section`), multi-year comparison section (`_render_multi_year_comparison_section`), tyre crossover prediction matrix (`render_tyre_crossover_matrix`), grid heatmap section (`_render_grid_heatmap_section`), PDF export section (`render_export_section`), multi-format telemetry export panel (`render_telemetry_export_panel`), layout maps block tabs, and footer. |
| `src/charts/plotly.py` | Constructs and returns interactive Plotly figure objects for lap history, tyre strategy Gantt timelines, gap analysis, track maps, tyre degradation (linear + quadratic thermal curves + cliff vlines), stint consistency violin/boxplots (`build_stint_consistency_fig`), weather correlation dual-axis (`build_weather_correlation_fig`), multi-year comparison speed delta (`build_multi_year_comparison_fig`), animated replays, and 4-subplot corner analysis (`build_corner_fig`). |
| `src/charts/matplotlib.py` | Creates static Matplotlib figures for 6-channel telemetry profiles and speed delta overlays. |
| `tests/` | Pytest unit and integration tests (e.g. `test_telemetry_export.py`, `test_telemetry_channels.py`, `test_tyre_crossover.py`, `test_cf.py`). |

---

## Key Design Decisions

### 1. Modular Architecture

The app has been refactored into a modular layout under `src/` to isolate data loading, UI layout rendering, and chart figures. All state variables (like `driver1`, `compare`, `sess_key`) must be passed explicitly into functions to prevent circular import loops.

### 2. CSS injection over Streamlit theming

The app injects raw CSS via `st.markdown(..., unsafe_allow_html=True)` to override Streamlit's BaseWeb components. This is necessary because Streamlit's native theme API does not expose enough hooks for full dark/light mode control. Maintain this approach.

When customising or animating the sidebar (`[data-testid="stSidebar"]`), do not apply transform keyframe animations directly to the base `[data-testid="stSidebar"]` container using `forwards` or `infinite` fill-mode. Doing so overrides Streamlit's native inline collapsed state `transform` translation, preventing the sidebar from sliding off-screen on mobile. Always scope entry transitions to the open sidebar selector (`section[data-testid="stSidebar"][data-collapsed="false"]`).

### 3. `format_func` for all driver selectboxes

Driver numbers (e.g. `"4"`) are the internal keys throughout. The display layer uses `_fmt_driver(num)` → `"NOR · Norris"` via `format_func=`. Never change the underlying session state / FastF1 calls to use names — always use raw numbers internally.

`_fmt_driver` is applied in **every** user-visible location:

- Driver 1 / Driver 2 `st.selectbox` — via `format_func=_fmt_driver`
- Lap selector label and warning — `f"Lap — {_fmt_driver(driver)}"`
- Fastest Laps Leaderboard Driver column — `_fmt_driver(drv)` in HTML table cell
- Fuel-Adjusted Pace stat card label — `_fmt_driver(drv)` in metric card div

When adding new UI that shows a driver identifier, always wrap it with `_fmt_driver(drv)`.

### 4. `@st.cache_data` + `sess_key` pattern

All data-builder functions are cached with `@st.cache_data(ttl=3600)`. The cache key always includes `sess_key` (a string `"{year}_{gp}_{session_type}"`). Do **not** add new session-state accesses inside `@st.cache_data` functions — pass data as parameters instead.

### 5. Single canonical compound colour dict

`COMPOUND_COLOURS` at line ~1157 is the **only** definition of compound colours in the entire codebase.
It carries three keys per compound: `fill` (hex background), `text` (label contrast colour), `letter` (badge abbreviation).
`_CMP_PALETTE` and all other inline dicts (`cmp_dot`, `cmp_colours_map`) have been removed.
When adding new chart types, always derive colours with:

```python
pal = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])
```

Do **not** define a new inline compound colour dict anywhere in `app.py`.

### 6. Official Session Classification Leaderboard

The official classification results are fetched from `sess.results` and cached using `_build_final_classification(sess_key, sess.results)`.

- Practice sessions (`FP1`, `FP2`, `FP3`) do not contain official standings in `results.Position` (all values are NaN). The app detects this and prints a clean warning pointing the user to the Fastest Laps Leaderboard.
- Race/Sprint sessions format absolute time for the winner, relative gaps for subsequent finishers, and DNFs/laps using their status value.
- Qualifying/Shootout sessions display `Q1`, `Q2`, and `Q3` lap times.
- Selected drivers in the telemetry selector are highlighted in the classification table with their driver colours.
- To prevent Streamlit's cache manager from throwing an `UnhashableParamError`, the results DataFrame argument must be prefixed with a leading underscore in the function signature (e.g. `_results_df`), telling Streamlit to skip hashing this complex Pandas subclass object.

### 7. Track Map Telemetry Fallback

When telemetry data is incomplete (e.g., missing `Speed` or `Throttle`/`Brake` channels), the track maps must fall back gracefully rather than failing or showing a generic error.

- Check for `X` and `Y` coordinate columns first. If coordinate data is present, draw a gray track outline (in single or comparison sector dominance map).
- Draw the Start/Finish marker on the coordinates if coordinate data is available.
- If specific channels are missing, display an informational warning below the chart via `st.info()` (e.g., `"Speed telemetry is not available; showing track outline only."` or `"Throttle/Brake inputs telemetry is not available; showing track outline only."`).
- Unpack the return tuples `(fig, warning_msg)` safely in the UI callback layers.

### 8. Constructors' Championship Standings Table

To provide seasonal championship context, a Constructors' Championship standings table is rendered directly above the official session classification table at the bottom of the page.

- The standings data is fetched dynamically from the Jolpi (Ergast) API for the season and round being viewed: `https://api.jolpi.ca/ergast/f1/{year}/{round_no}/constructorStandings.json`.
- Standings are fetched and cached using `@st.cache_data(show_spinner=False, ttl=3600)` to prevent excessive network requests.
- Suffix cleaning (`F1 Team`, `Racing`) and substring matching are used to match team names dynamically against `TEAM_COLOURS` for coloured row indicators.
- The row corresponding to the selected driver's team is highlighted using their constructor colour.
- If the API call fails or there are no standings (e.g., pre-season testing), the dashboard recovers gracefully by displaying an informational warning instead of crashing.

### 9. Driver Standing Points in Session Classification Table

To give a holistic view of the championship standings alongside session results, the total Drivers' Championship standings points are rendered as an additional column (`CH Points`) in the official classification table.

- Driver standing records are fetched dynamically from the Jolpi (Ergast) API: `https://api.jolpi.ca/ergast/f1/{year}/{round_no}/driverStandings.json`.
- Requests are cached using `@st.cache_data(show_spinner=False, ttl=3600)` to ensure optimal performance.
- Drivers in the session classification DataFrame are mapped to their standing records by checking abbreviation codes (e.g., `NOR`), car/driver number strings, or driver last name substrings.
- If standings data is not available, the points column gracefully displays `—`.

### 10. Default Selected Driver as Race/Session Winner

To ensure the dashboard loads displaying the most relevant driver first, the default selected driver is set dynamically to the winner of that session:

- For Race, Sprint, and Qualifying sessions, the winner is determined by looking up the driver with Position 1 in `session.results`.
- For Practice sessions, where standings are not defined, the winner is resolved to the driver who set the overall fastest lap in `session.laps`.
- In cases where the F1 identifier returned by results or laps is a number or alternative key format, a mapping resolver matches it to the respective key in `all_drivers1` (which uses abbreviations or numbers depending on the session data).
- The default index falls back to Norris ("NOR" / "4") or index 0 if the winner cannot be resolved.

### 11. Default Season and Session/Event Selection to the Most Recent Ones

To improve user experience, the dashboard initialises both Season 1 and Season 2 selectors to the most recent season (the first entry in the descending list of years, currently 2026).
Furthermore, the default Grand Prix index is resolved dynamically by filtering the season's calendar schedule to locate the most recent completed Grand Prix (where the event date is less than or equal to the current system date).
If no races have occurred yet in the selected season, the dashboard falls back gracefully to the first event of the calendar (Round 1).

### 12. Combined Driver Car Number and Name in Classification Table

To provide clear mappings between driver numbers and full names, the Driver column in the final session classification table displays both the car number and the formatted name together (e.g., `44 · HAM · Hamilton` instead of just `HAM · Hamilton`). Rather than using selectbox formatting functions (which map from abbreviation strings and cause lookup key mismatches with car numbers), this is resolved directly from the `Abbreviation` and `LastName` columns in the FastF1 results DataFrame. A clean conditional fallback ensures that if driver name info is missing, only the car number is displayed.

### 13. Pit Stop Count in Session Classification Table

To provide a complete overview of the race strategy alongside results, a `Stops` column is displayed in the final official session classification table for Race and Sprint sessions. The number of stops is calculated dynamically by filtering the session's laps DataFrame for each driver and counting the number of laps containing both non-null `PitInTime` and `PitOutTime` values.

### 14. AWS-Style Mini-Sector Speed Dominance Map

In compare mode, the track map is divided into `NUM_MINISECTORS = 25` micro-sectors based on distance telemetry (roughly 150-250m per segment). Average speeds of both drivers are calculated in each distance interval, and the segment line is drawn using the colour of the fastest driver. To prevent visual gaps, each segment includes the first coordinate of the subsequent segment.

### 15. Corner-by-Corner Performance Analysis

An advanced tab `"🔍  Corner Analysis"` is provided inside `render_maps_block` to compare driver performance through specific turns. The analysis renders a **4-subplot Plotly layout** via `build_corner_fig`:

- Retrieves corner coordinates and apex distances via `session_obj.get_circuit_info()`.
- Slices telemetry to a distance window `[apex_distance - 200, apex_distance + 100]` around the apex.
- **Subplot 1 — Racing Line**: X/Y coordinate scatter with star marker (apex) and cross marker (braking point).
- **Subplot 2 — Speed Profile**: Speed (km/h) vs Distance relative to apex (m). Calculates apex speed (minimum speed) and braking point (first frame with `Brake > 0`, falling back to maximum deceleration `ds < -1` before the apex).
- **Subplot 3 — Steering Angle**: `Steering` channel coerced with `pd.to_numeric(..., errors="coerce")` to handle mixed string types; plotted in ° (degrees) vs distance relative to apex. Absolute max extracted as `max_steering`.
- **Subplot 4 — DRS Status**: `DRS` channel coerced with `pd.to_numeric(..., errors="coerce")`; binary activation flag (active if DRS ≥ 10) plotted vs distance. Boolean `drs_active` passed to metrics card.
- Displays four metrics side-by-side: *Apex Speed*, *Braking Point*, *Max Steering Angle (°)*, *DRS Activated (✅/❌)*.
- Graceful fallback annotations rendered if Steering or DRS data is all-NaN for the corner window.

### 16. Tyre Degradation Modeling and Pace Drop-off

To model pace drop-off and tyre wear characteristics:

- The data builder function `_build_tyre_deg_data` filters for valid flyer laps using `IsAccurate == True` and filters out yellow flags/safety car/virtual safety car periods.
- Linear regression (OLS) is performed using `np.polyfit` for stints with at least 4 valid laps to compute stint slope (degradation rate in seconds lost/gained per lap) and base pace.
- Laps are plotted on a Plotly scatter chart, overlaying stint OLS regression trendlines. Points and lines are coloured in driver team constructor colours (circular points and solid lines for primary driver, square points and dashed lines for secondary driver).
- Stint lengths and degradation rates are summarised in an HTML table, colour-coded to highlight positive or negative degradation trends.

### 17. Monolithic app.py Refactoring & Modular Structure

To resolve technical debt and maintainability issues:

- The monolithic `app.py` has been split into a modular directory structure under the `src/` directory.
- `src/data/loader.py` handles F1 data caching, proxy bypass patching, and raw telemetry wrangling.
- `src/ui/styles.py` encapsulates stylesheet injections, custom CSS classes, and team/tyre color constants.
- `src/ui/components.py` encapsulates user interface panels, final classification tables, weather widgets, live status banners, and map layout wrappers.
- `src/charts/plotly.py` hosts interactive Plotly chart builders (strategy timelines, gap charts, race replays, corner analysis subplots).
- `src/charts/matplotlib.py` hosts static Matplotlib telemetry and speed delta charts.
- **Decision #18**: *Real-Time Live Timing Stream Integration (`fastf1.livetiming`)* — Added support for recording and parsing live SignalR WebSocket streams via background threads (`start_live_recorder`, `stop_live_recorder`, `get_live_recorder_status`) and `load_live_session`. Included broadcast-grade live banner indicators and auto-refresh controls while adhering strictly to British English spellings across all comments, documentation, and user interfaces.
- **Decision #19**: *Dark Mode & Theme Injection Fix (`inject_styles`)* — Ensure `inject_styles()` is called early in `app.py` on every render cycle so theme state (`dark_mode`) and CSS variables take effect immediately across all landing, sidebar, and telemetry states.
- **Decision #20**: *Multi-Driver Grid Analysis & Heatmaps (`_build_grid_heatmap_data`)* — Added multi-driver grid analytics matrix supporting `Sector Split Deltas`, `Lap-by-Lap Pace Heatmap`, and `Top Speed Matrix` across 3 to 20 drivers using interactive Plotly heatmaps with dynamic height calculation and broadcast color scales.
- **Decision #21**: *Continuous Time Delta per Meter Chart (`build_time_delta_chart`)* — Added a continuous time delta chart using `fastf1.utils.delta_time` below the speed delta chart in compare mode to visualise exact time gained/lost (in seconds) vs distance (meters).
- **Decision #22**: *Pit Strategy & Undercut / Overcut Simulator (`build_undercut_chart`)* — Added automated strategic battle analysis pairing adjacent pit stops (±3 laps) between two drivers in compare mode, calculating pre/post pit gaps, and rendering a Plotly pit window gap chart with outcome metrics cards.
- **Decision #23**: *Race Control Incident Timeline & Flag Overlays (`_build_race_control_messages`, `_add_flag_zones`)* — Parses `sess.race_control_messages` into a classified DataFrame (SC, VSC, Red, Yellow, Clear, Investigation). Overlays semi-transparent flag zone bands on both the Lap Time History and Gap to Leader Plotly charts via `add_vrect`. Adds a searchable, filterable **Race Control Feed** table section below the Gap chart.
- **Decision #24**: *Code Review Artifacts* — Enforced the creation of a formal `code_review_issue_<number>.md` artifact during the PR workflow (Step 5) to document verification against the Code Review Checklist.
- **Decision #25**: *Post-Race Debrief PDF Exporter (`_build_pdf_report`)* — Automated printable broadcast-style report compilation using `kaleido`, `fpdf2`, and `Pillow` to capture and compile telemetry & strategy charts into downloadable PDFs.
- **Decision #26**: *Driver Consistency Index & Stint Pace Distribution (`_build_consistency_analysis`)* — Evaluates lap time standard deviation per stint after filtering in-laps, out-laps, and Safety Car / Red Flag periods. Calculates 0–100% Consistency Score index, Clean Air Pace, Traffic Deficit (+s/lap), and renders Plotly Violin/Boxplot distribution charts (`build_stint_consistency_fig`).
- **Decision #27**: *Track Temperature & Weather Impact Correlation (`_build_weather_correlation_data`)* — Extracts timeseries weather data merged via `pd.merge_asof` on lap completion timestamps (`Time`). Renders a dual-axis Plotly chart (`build_weather_correlation_fig`) overlaying track temperature (°C) on driver pace, calculating Pearson correlation scores and detecting Rain Crossover windows (`_render_weather_correlation_section`).
- **Decision #28**: *Multi-Year Historical Lap Comparison (`_build_multi_year_comparison`)* — Enables multi-season telemetry comparisons across technical regulation eras. Interpolates telemetry on a unified 500-point distance grid, plotting dual-subplot speed profile overlays and continuous time delta curves (`build_multi_year_comparison_fig`), with metric cards for Era Lap Time Delta, Top Speed, Min Apex Speed, and Full Throttle % (`_render_multi_year_comparison_section`).
- **Decision #29**: *Driver Steering & DRS Telemetry Subplots in Corner Analysis (`build_corner_fig`)* — Expanded corner-by-corner analysis into a 4-subplot Plotly layout adding Steering Angle (`Steering` in ° degrees) and DRS activation status (`DRS`) profiles aligned to distance relative to apex (m), alongside Max Steering Angle and DRS status metrics cards in `src/ui/components.py`.
- **Decision #30**: *Predictive Tyre Degradation & Thermal Crossover Matrix (`_build_tyre_deg_data`, `render_tyre_crossover_matrix`)* — Enhanced `_build_tyre_deg_data` with quadratic polynomial regression (≥ 5 laps) for non-linear thermal cliff estimation. Cliff lap computed by solving `a·x² + b·x + (c − cliff_target) = 0` where `cliff_target = base_pace + 1.5 s`. Linear fallback used when quadratic is unavailable. Pit window = `cliff ± 3 laps`. Visual enhancements to `build_tyre_deg_fig` include quadratic thermal curve overlays and dotted cliff vline markers per stint. `render_tyre_crossover_matrix` in `src/ui/components.py` renders a full-field urgency matrix (🟢/🟡/🔴/✅) below the existing degradation summary table.
- **Decision #31**: *Interactive Telemetry Channel Toggle & Custom Trace Filtering (`AVAILABLE_CHANNELS`, `CHANNEL_CONFIG`, `build_chart`)* — Added dynamic channel selection multiselect in `app.py` under the Telemetry section, allowing users to toggle individual channels (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) on/off and reorder traces dynamically. `build_chart` in `src/charts/matplotlib.py` filters traces based on `selected_channels` and dynamically scales figure height and subplot grid layout (`max(2.8, sum(h_ratios) * 1.05 + 0.5)`).
- **Decision #32**: *High-Throughput Multi-Format Telemetry Exporter (`render_telemetry_export_panel`, `_build_export_parquet`, `_build_export_json`)* — Expanded telemetry export into a multi-format panel supporting CSV, Apache Parquet (`.parquet`), and structured JSON (`.json`) with unified metadata column injection (`Driver`, `LapNumber`, `LapTime`, `Compound`, `Sector1Time_s`, `Sector2Time_s`, `Sector3Time_s`) and `nGear` → `Gear` renaming.

---

## Running the Project

### Local (development)

```bash
python3.11 -m streamlit run app.py
# Access at http://localhost:8501
```

### Docker

```bash
docker build -t pitwall .
docker run -p 8501:8501 -v $(pwd)/cache:/app/cache pitwall
```

### Health check

The app is healthy when:

- The sidebar loads with year / GP / session selectors
- Clicking **⬇️ Load Session** loads data without a Python traceback
- The driver banner, lap summary metrics, Lap Time History, Stint Timeline, and Telemetry charts all render

---

## Maintenance Responsibilities

### 🔁 Routine Checks

- [ ] **Streamlit deprecation warnings** — check the console after each run. Replace any deprecated parameters immediately (e.g. `use_container_width` → `width`).
- [ ] **FastF1 version compatibility** — after `fastf1` upgrades, verify `pick_drivers`, `pick_quicklaps`, `get_driver`, `laps["Compound"]` still work as expected.
- [ ] **Team colour accuracy** — update `TEAM_COLOURS` in the Constants block each season when constructors change liveries or names.
- [ ] **Team logo URLs** — `_team_logo()` references `media.formula1.com` URLs. Validate annually; update filenames if F1 restructures their CDN.

### 🐛 Bug Fix Protocol

1. Reproduce the bug locally with `python3.11 -m streamlit run app.py`.
2. Identify the responsible section using the Architecture Map above.
3. Fix with the minimal change — do not refactor surrounding code unnecessarily.
4. Run `python3 -m py_compile app.py` to confirm no syntax errors.
5. Reload the browser and validate the affected chart/feature.
6. Commit with a descriptive message: `fix: <what was broken and how it was fixed>`.

### ➕ Adding New Features

1. Identify the correct insertion point using the Architecture Map.
2. Follow the section pattern: `# ── Section Name ──────` header comment.
3. Use `@st.cache_data(show_spinner=False, ttl=3600)` for any data-loading function.
4. Use `st.plotly_chart(fig, width="stretch")` for all Plotly charts (never `use_container_width`).
5. Use `st.pyplot(fig, width="stretch")` for all Matplotlib charts. Do not use hardcoded `min-width` CSS on `stImage` containers; allow Streamlit's native responsive scaling to fit mobile viewports dynamically without clipping.
6. Update `README.md` Key Features and How to Use sections.
7. Commit code and README separately or together — always keep them in sync.

### 🗑️ Dead Code Policy

- Do not leave unused variables, computed values, or imports in `app.py`.
- Before removing, verify with `grep` that the variable name has no other usages.
- Known past cleanups:
  - `n_drivers`, `y_pos`, `label` — removed from `_stint_fig` (were assigned but never read).
  - `_CMP_PALETTE`, `cmp_dot`, `cmp_colours_map` — removed when compound colours were consolidated into `COMPOUND_COLOURS`.

---

## Coding Standards

| Standard | Rule |
| --- | --- |
| **Python version** | 3.11+ syntax only |
| **Streamlit API** | Use `width='stretch'` / `width='content'` — never `use_container_width` |
| **HTML injection** | Always include `unsafe_allow_html=True`; always sanitise user-derived values |
| **f-strings** | Preferred for all string formatting |
| **Type hints** | Required on all new function signatures |
| **Docstrings** | One-line summary on all `@st.cache_data` and data-builder functions |
| **Comments** | Section headers with `# ── Name ──────` (80-char line) |
| **`plt.close()`** | Always call `plt.close(fig)` immediately after `st.pyplot(fig)` |
| **Error handling** | Wrap FastF1 data access in `try/except Exception`; never let a chart crash the whole page |
| **`_all_laps` pattern** | Extract as `_all_laps: pd.DataFrame = pd.DataFrame(sess.laps.copy())`. The `pd.DataFrame()` cast is **required** — `fastf1.core.Laps` is a subclass that raises `UnhashableParamError` in `@st.cache_data`. Inside builders, filter by `laps_df[laps_df["Driver"] == driver].copy()` — **never** `.pick_drivers()` on a plain DataFrame |

---

## Dependency Versions (as of last update)

```
fastf1>=3.3.0
streamlit>=1.44.0
matplotlib>=3.8.0
pandas>=2.2.0
numpy>=1.26.0
plotly>=5.18.0
curl-cffi>=0.5.10
kaleido>=0.2.1
fpdf2>=2.7.5
Pillow>=10.0.0
pyarrow>=14.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

When upgrading any dependency:

1. Test locally with the new version.
2. Update `requirements.txt`.
3. Rebuild the Docker image and verify.
4. Note any breaking API changes in a commit message.

---

## Known Limitations

| Limitation | Notes |
| --- | --- |
| Active & ongoing sessions | Live sessions can be streamed in real-time via the sidebar **🔴 Real-Time Live Timing Mode** (SignalR client). For historical analysis, static timing databases become available on F1's CDN typically 2–24h after the session concludes. |
| Very recent sessions | FastF1 may not have timing data for sessions less than ~24h old. Show a clear `st.error` message. |
| Safety Car / Red Flag laps | Filtered out of Lap Time History and Fuel-Adjusted Pace using `> 2.5× median` outlier removal. |
| ~~`@st.cache_data` + `session_state`~~ | ✅ **Resolved** — All 7 data-builder functions now receive `laps_df` as an explicit parameter. `_all_laps` extracted once after session load. No cached function accesses `st.session_state["session"]` internally. |
| `fastf1.core.Laps` hashing | `sess.laps` is a pandas subclass with custom state. Streamlit's `@st.cache_data` hasher raises `UnhashableParamError` on it. Always cast: `pd.DataFrame(sess.laps.copy())`. Inside builders use `laps_df[laps_df["Driver"] == driver]` not `.pick_drivers()`. |
| Headshot availability | Older sessions (pre-2021) may not have `HeadshotUrl` in FastF1. The `onerror` JS attribute hides broken images silently. |
| Theme toggle first-click | Due to Streamlit's execution order, the first theme toggle click may not visually update the top bar. A second click always works. |

---

## GitHub Workflow

This section defines the mandatory git procedure for all changes to this repository. Whenever a code change (bug fix or feature request) is requested, follow these steps — no exceptions.

### Step-by-step procedure

```
1. Create a GitHub Issue describing the bug or feature request:
   gh issue create --title "<type>: <short summary>" --body "<description>" --label "<bug/enhancement>"

2. Pull latest changes and checkout a dedicated feature/fix branch:
   git checkout main
   git pull
   git checkout -b <prefix>/<short-description>  # e.g., fix/session-data-unavailable

3. Implement your code changes in app.py following the Coding Standards (including safety validation and state clearing: see below).

4. Verify syntax before staging:
   python3 -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"

5. Stage, commit, and push your changes to origin:
   git add app.py
   git commit -m "<type>: <short summary>

   Closes #<issue_number>"
   git push -u origin <branch-name>

6. Open a GitHub Pull Request:
   gh pr create --title "<type>: <short summary>" --body "Closes #<issue_number>"

7. Merge the PR and delete the branch:
   gh pr merge --merge --delete-branch

8. Clean up local repository:
   git checkout main
   git pull
   git fetch -p
```

### Safety & Robustness Standards

When modifying session loading or accessing session attributes, you must implement the following safeguards:

- **Validate Lap Data on Load**: Immediately after loading a session using `load_session()`, verify that the laps data is available and not empty. Accessing `.laps` throws a `ValueError` if the session is cancelled or too recent.

  ```python
  sess = load_session(year, gp, session_type)
  if not hasattr(sess, "laps") or sess.laps is None or sess.laps.empty:
      raise ValueError("No lap data available for this session.")
  ```

- **Prevent Stuck UI Lockups**: When loading or validating data fails and raises an exception, clear any invalid session objects from `st.session_state` inside the `except` handler before calling `st.stop()`. This ensures that subsequent Streamlit reruns return the user to a clean landing page rather than locking them in a broken state loop.

  ```python
  st.session_state["session"] = None
  st.session_state["session2"] = None
  st.session_state["sess_key"] = None
  st.session_state["sess_key2"] = None
  ```

- **Requests Monkey-Patching Caching Compatibility**: When monkey-patching `requests` (e.g., to bypass CloudFront blocks via `curl_cffi`), the returned custom `Response` objects must mock the `raw` attribute using a local `MockRaw` class. If `resp.raw` is `None` or lacks essential properties, `requests_cache` will crash during serialization with `AttributeError: 'NoneType' object has no attribute '_request_url'`.

---

### Commit message convention

| Prefix | When to use | Example |
| --- | --- | --- |
| `feat:` | New user-visible feature added | `feat: add Ideal Lap vs Actual Lap section` |
| `fix:` | Bug or runtime error corrected | `fix: _all_laps cast to plain DataFrame to avoid UnhashableParamError` |
| `refactor:` | Internal code restructure, no behaviour change | `refactor: fix cache isolation — pass laps_df to all builder functions` |
| `docs:` | Documentation-only change | `docs: update DOCS.md caching table and AGENT.md roadmap` |
| `chore:` | Dependency update, config tweak | `chore: pin fastf1==3.4.1 in requirements.txt` |
| `style:` | CSS or UI-only visual change | `style: update leaderboard table row highlight colour` |

Keep the summary under 72 characters. Add a body after a blank line for complex changes.

---

### What must be committed together

| Change made | Must also commit |
| --- | --- |
| New feature in `app.py` | `README.md` (feature bullet) + `DOCS.md` (pipeline, chart inventory, roadmap) + `AGENT.md` (architecture map if lines shifted) |
| Bug fix in `app.py` | `DOCS.md` and `AGENT.md` if the fix changes documented behaviour or known limitations |
| Architecture change (e.g. caching pattern) | `DOCS.md` §5 caching section + `AGENT.md` coding standards + known limitations |
| `requirements.txt` update | Rebuild Docker image locally; note version change in commit message |
| Docs-only update | No code commit required |

> **Never commit `cache/`** — it is gitignored. Never force-add it.

---

### Syncing with remote (daily start-of-session)

Always pull before starting any work session:

```bash
git pull
```

If there are conflicts in `app.py`, resolve manually. The file is a linear script — conflicts are usually in disjoint sections and can be resolved without context loss.

---

### Branch policy

This project enforces a strict **branch-and-PR policy** for all non-trivial changes (fixes or feature requests). Direct pushes to `main` are restricted to documentation-only updates or minor copy changes. All code modifications must be developed in a separate branch and merged via Pull Request (PR) to ensure code quality and stability.

---

### Issues

GitHub Issues track bugs, feature requests, and technical debt items.

**When to raise an issue:**

| Situation | Type | Label |
| --- | --- | --- |
| Chart crashes or shows wrong data | Bug report | `bug` |
| New analytical feature request | Feature request | `enhancement` |
| FastF1 API deprecation / breaking change | Maintenance | `chore` |
| Slow load or cache problems | Performance | `performance` |
| Documentation gap or error | Docs | `documentation` |

**Managing via GitHub CLI (`gh`):**

```bash
gh issue list                    # View all open issues
gh issue view 1                  # View details for issue #1
gh issue close 1                 # Close issue #1
gh issue create --title "..." --body "..." --label "bug"  # Create new issue
```

**Issue body template:**

```
## Description
What is happening / what is needed?

## Steps to reproduce (bugs only)
1. Load session: [year, GP, session type]
2. Select driver: [driver number]
3. Observe: [what went wrong]

## Expected behaviour
[what should happen]

## Environment
- Python: 3.11.x  |  Streamlit: x.x.x  |  FastF1: x.x.x  |  OS: macOS / Linux
```

**Auto-closing via commit message:**

```
fix: correct lap outlier filter for sprint sessions

Closes #12
```

---

### Pull Requests

Opening a PR before merging significant changes creates a reviewable diff and documents intent — recommended even for solo work. Whenever there is a separate branch merging into the main branch, follow the pull request steps to make sure everything is stable and working correctly.

**Open a PR for:**

- Any change adding more than ~50 lines to `app.py`
- New sections in the rendering pipeline
- Architectural changes (caching, state, helper functions)
- Changes touching more than one file

**Direct push to `main` is acceptable for:**

- One-line bug fixes
- Documentation-only changes
- Trivial copy / wording updates

**PR title** — same format as commit messages:

```
feat: add Sector Heatmap section
fix: resolve UnhashableParamError on fastf1.core.Laps
docs: sync DOCS.md with Ideal Lap implementation
```

**Managing via GitHub CLI (`gh`):**

```bash
gh pr create --title "feat: ..." --body "Closes #1"  # Push branch and open PR
gh pr list                                           # View open PRs
gh pr checkout 5                                     # Checkout PR #5 locally to test
gh pr merge                                          # Merge current PR into main interactively
```

**PR body template:**

```markdown
## What changed
Brief description of what was added / changed / fixed.

## Why
Motivation or context for the change.

## Files changed
- `app.py` — [describe changes]
- `README.md` — [if applicable]
- `DOCS.md` — [if applicable]

## Testing done
- [ ] Pytest unit tests pass (`python3.11 -m pytest tests/`)
- [ ] Syntax check passes
- [ ] App starts without error
- [ ] Affected section renders correctly
- [ ] Compare mode tested (if applicable)
- [ ] Dark mode and light mode verified

## Related issues
Closes #[issue number]
```

---

### Code Review

Before merging any PR or pushing a significant change directly to `main`, you **MUST** perform a formal code review and generate a markdown artifact named `code_review_issue_<number>.md` summarising the verification of the following checklist:

**Correctness**

- [ ] No `st.session_state["session"].laps` accessed inside a `@st.cache_data` function
- [ ] `laps_df` passed as `pd.DataFrame(sess.laps.copy())` — not raw `fastf1.core.Laps`
- [ ] Driver filtering uses `laps_df[laps_df["Driver"] == driver]` — not `.pick_drivers()`
- [ ] All new `@st.cache_data` functions include `sess_k: str` in their signature
- [ ] All new UI showing driver identifiers wraps them in `_fmt_driver(drv)`
- [ ] No new inline compound colour dicts — `COMPOUND_COLOURS` is the only source of truth

**Code quality**

- [ ] Type hints on all new functions
- [ ] One-line docstring on all new `@st.cache_data` and data-builder functions
- [ ] Section headers follow `# ── Name ────────────────────────────` format
- [ ] `plt.close(fig)` called immediately after every `st.pyplot(fig)`
- [ ] All FastF1 data access wrapped in `try/except Exception`

**Documentation**

- [ ] `README.md` updated if user-visible behaviour changed
- [ ] `DOCS.md` rendering pipeline updated if a new section was added
- [ ] `DOCS.md` chart inventory updated if a new chart was added
- [ ] `AGENT.md` architecture map line ranges updated if sections shifted
- [ ] `DOCS.md` roadmap item marked ✅ Done if it was implemented

**Syntax & Testing**

- [ ] Pytest unit tests pass (`python3.11 -m pytest tests/`)
- [ ] Codebase compile check passes (`python3 -m py_compile app.py src/data/loader.py src/ui/styles.py src/ui/components.py src/charts/matplotlib.py src/charts/plotly.py`)

---

## Escalation & Out-of-Scope Rules

The agent must **not** autonomously:

- Change the project's modular `src/` architecture or introduce unauthorized third-party framework layers.
- Switch from Streamlit to any other framework.
- Add paid API keys or external data sources beyond FastF1 + Ergast.
- Modify or delete the `cache/` directory contents.
- Push directly to `main` without a descriptive commit message.

These require explicit approval from the project owner before implementation.
