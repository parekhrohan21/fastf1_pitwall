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
| **Entry point** | `app.py` (4 000 + lines, single-file monolith) |
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
| 23–255 | FastF1 cache + requests patch | `fastf1.Cache.enable_cache`, requests monkey-patch via `curl_cffi` |
| 256–263 | Page config | `st.set_page_config` |
| 264–407 | PWA injection | Injects Web Manifest + Apple meta tags via `components.html` |
| 408–450 | Page-transition JS | `MutationObserver` replays `pageEnter` CSS on every rerender |
| 451–1071 | Custom CSS | Full design system — keyframes, typography, layout, cards, banner |
| 1072–1241 | Theme CSS override | Dark / light mode CSS injection driven by `st.session_state["dark_mode"]` |
| 1242–1323 | Constants | `TEAM_COLOURS`, `COMPOUND_COLOURS`, `TRACK_STATUS_MAP` |
| 1324–1669 | Helper functions | `hex_to_rgb`, `_team_logo`, `_team_colour`, `format_laptime`, `driver_colour`, `_build_driver_labels`, `_fmt_driver`, `get_telemetry_cached`, `_format_classification_time`, `_build_final_classification`, `_render_final_classification` |
| 1670–1800 | Sidebar | Year / GP / session selectors, theme toggle, Load Session button, and connection diagnostics |
| 1801–1862 | Session state | Initialises session variables in Streamlit state |
| 1863–1893 | Landing page | Welcome panel with features summary if no session is loaded |
| 1894–1949 | Driver & lap controls & labels | `all_drivers` extraction, `_fmt_driver` mapping, `_all_laps` extraction |
| 1950–2063 | Session Info Header | `_session_info_header()` — circuit, flag, round, session type, event date |
| 2064–2135 | Driver Selection & lap selector | Selection inputs, `lap_selector()`, telemetry caching |
| 2136–2299 | Lap summary banner | `render_summary()` — headshot, team logo, metric cards, tyre badge, weather |
| 2300–2381 | Session Statistics | `render_session_stats()` — Grid position, finish position, best lap, race pace, top speed |
| 2382–2553 | Lap Time History | `_build_lap_history`, `_lap_history_fig` with compound filter |
| 2554–2907 | Fuel-Adjusted Pace | `_build_fuel_adjusted`, `_fuel_pace_fig`, simulated qualifying leaderboard |
| 2908–3025 | Tyre Stint Timeline | `_build_stints`, stint timeline Gantt chart |
| 3026–3243 | Pit Stop Summary | HTML pit stop summary table with selection highlighting |
| 3244–3315 | Export Telemetry | CSV export widget for driver lap data |
| 3316–3347 | Speed Delta | Matplotlib comparison chart |
| 3348–3462 | Fastest Laps Leaderboard | Ranked leaderboard of best lap times |
| 3463–3667 | Ideal Lap vs Actual Lap | Theoretical best lap sector analysis |
| 3668–3821 | Gap to Leader | Plotly gap analysis over the race distance |
| 3822–3943 | Race Position Chart | Track positions over all laps |
| 3944–4467 | Track Map & Driver Inputs Map & Race Replay | Sector dominance, telemetry inputs, and animated replay map |
| 4468–end | Official Session Classification | Final classification leaderboard table |

---

## Key Design Decisions

### 1. Single-file monolith
`app.py` is intentionally kept as one file for simplicity and Streamlit Cloud compatibility. Do **not** split into modules unless explicitly instructed by the project owner.

### 2. CSS injection over Streamlit theming
The app injects raw CSS via `st.markdown(..., unsafe_allow_html=True)` to override Streamlit's BaseWeb components. This is necessary because Streamlit's native theme API does not expose enough hooks for full dark/light mode control. Maintain this approach.

When customizing or animating the sidebar (`[data-testid="stSidebar"]`), do not apply transform keyframe animations directly to the base `[data-testid="stSidebar"]` container using `forwards` or `infinite` fill-mode. Doing so overrides Streamlit's native inline collapsed state `transform` translation, preventing the sidebar from sliding off-screen on mobile. Always scope entry transitions to the open sidebar selector (`section[data-testid="stSidebar"][data-collapsed="false"]`).


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
- Selected drivers in the telemetry selector are highlighted in the classification table with their driver colors.


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
| Active & ongoing sessions | Live timing streaming is not supported. Active sessions will fail validation with empty lap data until the final static database is published to F1's CDN (usually 2–24h after session ends). |
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
|---|---|---|
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
|---|---|
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
|---|---|---|
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

Run this checklist before merging any PR or pushing a significant change directly to `main`:

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

**Syntax**
- [ ] `python3 -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"` passes

---

## Escalation & Out-of-Scope Rules

The agent must **not** autonomously:
- Change the project's single-file architecture to a multi-module structure.
- Switch from Streamlit to any other framework.
- Add paid API keys or external data sources beyond FastF1 + Ergast.
- Modify or delete the `cache/` directory contents.
- Push directly to `main` without a descriptive commit message.

These require explicit approval from the project owner before implementation.
