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
| 23–35 | FastF1 cache + page config | `fastf1.Cache.enable_cache`, `st.set_page_config` |
| 36–179 | PWA injection | Injects Web Manifest + Apple meta tags via `components.html` |
| 180–222 | Page-transition JS | `MutationObserver` replays `pageEnter` CSS on every rerender |
| 223–814 | Custom CSS | Full design system — keyframes, typography, layout, cards, banner |
| 815–984 | Theme CSS override | Dark / light mode CSS injection driven by `st.session_state["dark_mode"]` |
| 985–1066 | Constants | `TEAM_COLOURS`, `COMPOUND_COLOURS`, `TRACK_STATUS_MAP` |
| 1067–1192 | Helper functions | `hex_to_rgb`, `_team_logo`, `_team_colour`, `format_laptime`, `driver_colour`, `_build_driver_labels`, `_fmt_driver`, `get_telemetry_cached` |
| 1193–1247 | Sidebar | Year / GP / session selectors, theme toggle, Load Session button |
| 1248–1266 | Session state | Initialises session variables in Streamlit state |
| 1267–1297 | Landing page | Welcome panel with features summary if no session is loaded |
| 1298–1329 | Driver controls & labels | `all_drivers` extraction, `_fmt_driver` mapping |
| 1330–1433 | Session Info Header | `_session_info_header()` — circuit, flag, round, session type, event date |
| 1434–1496 | Driver Selection & lap selector | Selection inputs, `lap_selector()`, telemetry caching |
| 1497–1657 | Lap summary banner | `render_summary()` — headshot, team logo, metric cards, tyre badge, weather |
| 1658–1736 | Session Statistics | `render_session_stats()` — Grid position, finish position, best lap, race pace, top speed |
| 1737–1901 | Lap Time History | `_build_lap_history`, `_lap_history_fig` |
| 1902–2240 | Fuel-Adjusted Pace | `_build_fuel_adjusted`, `_fuel_pace_fig`, simulated qualifying leaderboard |
| 2241–2358 | Tyre Stint Timeline | `_build_stints`, stint timeline Gantt chart |
| 2359–2536 | Pit Stop Summary | HTML pit stop summary table with selection highlighting |
| 2537–2573 | Telemetry charts | Matplotlib telemetry chart builder and renderer |
| 2574–2645 | Export Telemetry | CSV export widget for driver lap data |
| 2646–2676 | Speed Delta | Matplotlib comparison chart |
| 2677–2776 | Fastest Laps Leaderboard | Ranked leaderboard of best lap times |
| 2777–2977 | Ideal Lap vs Actual Lap | Theoretical best lap sector analysis |
| 2978–3121 | Gap to Leader | Plotly gap analysis over the race distance |
| 3122–3228 | Race Position Chart | Track positions over all laps |
| 3229–end | Track Map & Driver Inputs Map & Race Replay | Sector dominance, telemetry inputs, and animated replay map |

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

## GitHub Workflow

This section defines the standard git procedure for all changes to this repository. Follow these steps on every change — no exceptions.

### Step-by-step procedure

```
1. Pull latest changes from remote
   git pull

2. Make your code changes in app.py (and docs if needed)

3. Syntax-check before staging
   python3 -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"

4. Stage all changes
   git add .

5. Commit with a descriptive message
   git commit -m "<type>: <short summary>"

6. Push to remote
   git push
```

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

This project uses a **single `main` branch**. All changes go directly to `main`. Feature branches are not required unless the project owner explicitly requests one. However, if a separate branch is created, it must always be merged using a Pull Request (PR) to ensure all verification steps are completed before code hits `main`.

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
