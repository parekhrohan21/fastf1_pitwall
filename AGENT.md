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
|---|---|
| **Stack** | Python 3.11+ · Streamlit ≥ 1.44 · FastF1 ≥ 3.3 |
| **Entry point** | `app.py` (2 500 + lines, single-file monolith) |
| **Data source** | FastF1 library → official F1 timing API + Ergast |
| **Port** | `8501` (local and Docker) |
| **Cache dir** | `./cache/` (FastF1 disk cache, gitignored) |
| **Docker** | `Dockerfile` present; mount `./cache:/app/cache` |

---

## Repository File Map

```
fastf1_pitwall/
├── app.py              ← entire application (do NOT split without agreement)
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

## `app.py` Architecture Map

The file is structured as a linear top-to-bottom Streamlit script. Sections run in this order on every rerender:

| Lines (approx) | Section | Purpose |
|---|---|---|
| 1–22 | Imports & warnings | All `import` statements |
| 23–34 | FastF1 cache + page config | `fastf1.Cache.enable_cache`, `st.set_page_config` |
| 36–99 | PWA injection | Injects Web Manifest + Apple meta tags via `components.html` |
| 100–142 | Page-transition JS | `MutationObserver` replays `pageEnter` CSS on every rerender |
| 143–607 | Custom CSS | Full design system — keyframes, typography, layout, cards, banner |
| 608–777 | Theme CSS override | Dark / light mode CSS injection driven by `st.session_state["dark_mode"]` |
| 778–811 | Constants | `TEAM_COLOURS`, `COMPOUND_COLOURS`, `TRACK_STATUS_MAP` |
| 812–937 | Helper functions | `hex_to_rgb`, `_team_logo`, `_team_colour`, `format_laptime`, `driver_colour`, `_build_driver_labels`, `_fmt_driver`, `get_telemetry_cached` |
| 938–985 | Sidebar | Year / GP / session selectors, theme toggle, Load Session button |
| 986–1028 | Session state & landing | Loads session via `load_session()`, shows landing if not loaded |
| 1029–1058 | Driver name labels | `_build_driver_labels`, `_fmt_driver` — maps raw numbers to display names |
| 1059–1165 | Session Info Header | `_session_info_header()` — circuit, country flag, round, session type + icon, event date |
| 1166–1200 | Driver & lap controls | `all_drivers`, `driver1/2` selectboxes with `format_func=_fmt_driver`, `lap_selector()` |
| 1229–1389 | Lap summary banner | `render_summary()` — headshot, team logo, metric cards, tyre badge, weather |
| 1390–1554 | Lap Time History | `_build_lap_history`, `_lap_history_fig` |
| 1555–1728 | Fuel-Adjusted Pace | `_build_fuel_adjusted`, `_fuel_pace_fig`, stat cards |
| 1729–1846 | Tyre Stint Timeline | `_build_stints`, `_stint_fig` |
| 1847–2024 | Pit Stop Summary | HTML table via `_build_pit_stops` and `_render_pit_stops` |
| 2025–2061 | Telemetry charts | Matplotlib overlapping / separate chart via `build_chart` |
| 2062–2133 | Export Telemetry | CSV download via `_build_export_csv` — includes Distance, Speed, Throttle, Brake, RPM, Gear, DRS, Sector1/2/3 times (seconds), lap metadata |
| 2134–2164 | Speed Delta | Matplotlib fill-between chart (compare mode only) |
| 2165–2264 | Fastest Laps Leaderboard | `_build_leaderboard`, `_render_leaderboard` (HTML table) |
| 2265–2465 | Ideal Lap vs Actual Lap | `_build_ideal_lap` — best S1+S2+S3, delta cards per selected driver, full-field ranked table |
| 2466–2609 | Gap to Leader | `_build_gap_data`, Plotly line chart |
| 2610–2716 | Race Position Chart | `_build_position_data` — all drivers faded, selected highlighted in team colour, Y-axis inverted |
| 2717–end | Track Map & Race Replay | Plotly speed map, animated race replay with Play/Pause |

---

## Key Design Decisions

### 1. Single-file monolith
`app.py` is intentionally kept as one file for simplicity and Streamlit Cloud compatibility. Do **not** split into modules unless explicitly instructed by the project owner.

### 2. CSS injection over Streamlit theming
The app injects raw CSS via `st.markdown(..., unsafe_allow_html=True)` to override Streamlit's BaseWeb components. This is necessary because Streamlit's native theme API does not expose enough hooks for full dark/light mode control. Maintain this approach.

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
`COMPOUND_COLOURS` at line ~787 is the **only** definition of compound colours in the entire codebase.
It carries three keys per compound: `fill` (hex background), `text` (label contrast colour), `letter` (badge abbreviation).
`_CMP_PALETTE` and all other inline dicts (`cmp_dot`, `cmp_colours_map`) have been removed.
When adding new chart types, always derive colours with:
```python
pal = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])
```
Do **not** define a new inline compound colour dict anywhere in `app.py`.

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
5. Use `st.pyplot(fig, width="stretch")` for all Matplotlib charts.
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
|---|---|
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
```

When upgrading any dependency:
1. Test locally with the new version.
2. Update `requirements.txt`.
3. Rebuild the Docker image and verify.
4. Note any breaking API changes in a commit message.

---

## Known Limitations

| Limitation | Notes |
|---|---|
| Very recent sessions | FastF1 may not have timing data for sessions less than ~24h old. Show a clear `st.error` message. |
| Safety Car / Red Flag laps | Filtered out of Lap Time History and Fuel-Adjusted Pace using `> 2.5× median` outlier removal. |
| ~~`@st.cache_data` + `session_state`~~ | ✅ **Resolved** — All 7 data-builder functions now receive `laps_df` as an explicit parameter. `_all_laps` extracted once after session load. No cached function accesses `st.session_state["session"]` internally. |
| `fastf1.core.Laps` hashing | `sess.laps` is a pandas subclass with custom state. Streamlit's `@st.cache_data` hasher raises `UnhashableParamError` on it. Always cast: `pd.DataFrame(sess.laps.copy())`. Inside builders use `laps_df[laps_df["Driver"] == driver]` not `.pick_drivers()`. |
| Headshot availability | Older sessions (pre-2021) may not have `HeadshotUrl` in FastF1. The `onerror` JS attribute hides broken images silently. |
| Theme toggle first-click | Due to Streamlit's execution order, the first theme toggle click may not visually update the top bar. A second click always works. |

---

## Escalation & Out-of-Scope Rules

The agent must **not** autonomously:
- Change the project's single-file architecture to a multi-module structure.
- Switch from Streamlit to any other framework.
- Add paid API keys or external data sources beyond FastF1 + Ergast.
- Modify or delete the `cache/` directory contents.
- Push directly to `main` without a descriptive commit message.

These require explicit approval from the project owner before implementation.
