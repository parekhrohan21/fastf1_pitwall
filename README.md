# 🏎 Pit Wall — F1 Telemetry Dashboard

A **Streamlit + FastF1** dashboard for exploring lap telemetry, strategy and race data from any Formula 1 session since 2018.

Pick a season, Grand Prix, session, driver and lap. Pit Wall then shows the lap's telemetry with strategy, tyre, pit stop, braking, traction, weather and grid-wide analysis around it. You can compare two drivers head-to-head, compare against a lap from another session or season, and export the data or a PDF debrief.

**Contents:** [Quick start](#-quick-start) · [Using the dashboard](#-using-the-dashboard) · [Features](#-features) · [Configuration](#%EF%B8%8F-configuration) · [Project structure](#-project-structure) · [Development](#-development) · [Troubleshooting](#%EF%B8%8F-troubleshooting) · [Roadmap & changelog](#-roadmap--changelog)

---

## 🚀 Quick start

You need **Python 3.11+** (3.11 recommended, tested up to 3.12) or Docker.

### Run locally

```bash
git clone https://github.com/parekhrohan21/fastf1_pitwall.git
cd fastf1_pitwall

python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
```

Open **http://localhost:8501**.

### Run with Docker

```bash
docker build -t fastf1_pitwall .
docker run --rm -p 8501:8501 -v "$PWD/cache:/app/cache" --name fastf1-pitwall fastf1_pitwall
```

Open **http://localhost:8501**. Mounting `./cache` keeps downloaded session data between container restarts.

### Run in GitHub Codespaces (no install)

On the repository page click **Code → Codespaces → Create codespace on main**. The dev container ([.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)) installs the requirements, starts Streamlit and opens port 8501 in a preview tab. The same definition works locally through VS Code's **Dev Containers → Reopen in Container**.

### System requirements

| | Local | Docker |
|---|---|---|
| **Runtime** | Python 3.11+ | Docker Desktop or Docker Engine ≥ 20.10 |
| **Memory** | 4 GB minimum, 8 GB+ for animated race replays | 4 GB allocated to the container |
| **Disk** | ~500 MB for the environment + ~50–100 MB per cached session | ~1.5 GB image + the `./cache` volume |
| **Network** | Outbound HTTPS to `livetiming.formula1.com` and `api.jolpi.ca` | Same |

---

## 📚 Using the dashboard

1. **Choose a session in the sidebar.** Pick the season, Grand Prix and session (Race, Qualifying, Sprint, FP1–FP3). On first open, the sidebar defaults to the most recent completed Grand Prix.
2. **Click ⬇️ Load Session(s).** The first load of a session downloads it from the F1 timing API and takes about 10–30 seconds. Later loads come from the disk cache.
3. **Pick drivers and laps.** The session winner (or fastest driver in practice) is selected by default. Choose *Fastest* or a specific lap number. Tick **Compare with Driver 2** to put a second driver on every chart and enable the delta charts.
4. **Scroll down.** Sections run from the lap summary through pace, tyres and pit stops, corner and powertrain analysis, raw telemetry, grid-wide leaderboards, race control and track maps, ending with the championship standings.

Optional sidebar controls:

- **Compare with another session**: loads a second season / Grand Prix / session, for example to compare the same circuit across regulation eras.
- **🔴 Real-Time Live Timing Mode**: during a live race weekend, records the FastF1 SignalR stream to a file and auto-refreshes.
- **Theme toggle**: switches between dark and light mode.
- **🛠️ Diagnostics & Debug Info → Run Connection Test**: checks whether the F1 timing CDN is reachable from your machine.
- **Generate PDF Report**: exports a post-race debrief PDF of the main charts.

---

## ✨ Features

Issue numbers link to the GitHub issue that introduced each feature. Implementation details for each are in [DOCS.md](DOCS.md).

### Lap & telemetry

- **6-channel telemetry**: Speed, Throttle, Brake, RPM, Gear and DRS, overlaid or stacked, with a multiselect to hide or reorder channels ([#138](https://github.com/parekhrohan21/fastf1_pitwall/issues/138)).
- **Head-to-head deltas**: Speed delta and a continuous time delta per metre of track, showing where time is gained or lost ([#116](https://github.com/parekhrohan21/fastf1_pitwall/issues/116)).
- **Ideal lap vs actual lap**: best sectors combined into a theoretical best, with "time left on table" cards.
- **Multi-year comparison**: the same circuit across seasons, aligned on a 500-point distance grid, with speed overlay, time delta and era metrics ([#121](https://github.com/parekhrohan21/fastf1_pitwall/issues/121)).
- **Telemetry export**: download a lap as CSV, Parquet or JSON, including X/Y/Z position, sector times and lap metadata ([#139](https://github.com/parekhrohan21/fastf1_pitwall/issues/139)).

### Corners & powertrain

- **Corner-by-corner analysis**: pick a turn to see apex speed, braking point, steering angle and DRS, with racing-line, speed, steering and DRS subplots ([#80](https://github.com/parekhrohan21/fastf1_pitwall/issues/80), [#136](https://github.com/parekhrohan21/fastf1_pitwall/issues/136)).
- **Braking efficiency & trail-braking**: braking distance before apex, peak deceleration (G), trail-brake release point and brake-to-throttle transition time ([#148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)).
- **Corner exit traction**: distance to full throttle, throttle ramp rate, hesitation lifts, oversteer corrections, exit acceleration and a 0–100 Traction Aggression Score. Corners taken flat out are labelled as such rather than scored ([#155](https://github.com/parekhrohan21/fastf1_pitwall/issues/155)).
- **Gear shift strategy**: RPM curve with shift markers, gear usage for gears 1–8, short-shift and redline detection ([#149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)).
- **Speed traps**: grid-wide ST / I1 / I2 / FL speeds on a radar chart, benchmarked by constructor and power unit, with DRS gain ([#150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)).

### Pace, tyres & strategy

- **Lap time history**: every lap coloured by compound, with pit-out markers, a compound filter and race-control flag bands.
- **Fuel-adjusted pace**: removes the fuel-burn effect with an adjustable sensitivity, plus a simulated qualifying leaderboard ([#9](https://github.com/parekhrohan21/fastf1_pitwall/issues/9)).
- **Tyre degradation & crossover**: linear and quadratic fits per stint, an optional fuel-burn decoupler, predicted cliff lap and pit window, and a full-field urgency matrix ([#81](https://github.com/parekhrohan21/fastf1_pitwall/issues/81), [#137](https://github.com/parekhrohan21/fastf1_pitwall/issues/137), [#151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)).
- **Tyre stints & pit stops**: Gantt-style stint timeline and pit stop table.
- **Undercut / overcut simulator**: in compare mode, detects pit stops within ±3 laps of each other and shows whether the undercut or overcut worked ([#117](https://github.com/parekhrohan21/fastf1_pitwall/issues/117)).
- **Pit lane transit loss**: splits each stop into pit-lane transit time, in-lap push delta, out-lap warm-up delta and per-sector warm-up, with a field leaderboard ([#153](https://github.com/parekhrohan21/fastf1_pitwall/issues/153)).
- **Driver consistency**: per-stint consistency score, lap-time spread, and clean-air pace vs traffic deficit, with violin/box plots ([#119](https://github.com/parekhrohan21/fastf1_pitwall/issues/119)).

### Track & conditions

- **Track evolution**: for practice and qualifying, a robust fit of the field's pace against session time, giving a ramp rate (ms/min) and total grip gain (s) ([#154](https://github.com/parekhrohan21/fastf1_pitwall/issues/154)).
- **Weather correlation**: track temperature overlaid on pace, rain crossover detection and a pace-vs-heat sensitivity score ([#120](https://github.com/parekhrohan21/fastf1_pitwall/issues/120)).
- **Track maps**: speed-coloured map, mini-sector dominance map in compare mode, and a driver-inputs map (throttle / brake / coast) ([#4](https://github.com/parekhrohan21/fastf1_pitwall/issues/4), [#6](https://github.com/parekhrohan21/fastf1_pitwall/issues/6), [#78](https://github.com/parekhrohan21/fastf1_pitwall/issues/78)).
- **Animated race replay**: every car on track with a scrubbable timeline.

### Grid & race overview

- **Teammate battles**: qualifying and race-pace gaps for every team, with sector splits ([#152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)).
- **Grid heatmaps**: choose 3–20 drivers for sector-delta, lap-by-lap pace and top-speed heatmaps ([#85](https://github.com/parekhrohan21/fastf1_pitwall/issues/85)).
- **Gap to leader & race position** charts, and a **fastest laps** leaderboard.
- **Race control**: safety car, VSC, red and yellow flag periods shaded on the charts, plus a filterable message feed ([#118](https://github.com/parekhrohan21/fastf1_pitwall/issues/118)).
- **Classification & standings**: official session classification with points, stops and Q1/Q2/Q3 times, plus drivers' and constructors' championship standings ([#46](https://github.com/parekhrohan21/fastf1_pitwall/issues/46), [#56](https://github.com/parekhrohan21/fastf1_pitwall/issues/56)).

### App

- **Live timing mode** via the FastF1 SignalR client ([#84](https://github.com/parekhrohan21/fastf1_pitwall/issues/84)).
- **PDF debrief export** of lap history, stints, gap and position charts ([#122](https://github.com/parekhrohan21/fastf1_pitwall/issues/122)).
- **Team-colour theming** and a **dark / light toggle** ([#112](https://github.com/parekhrohan21/fastf1_pitwall/issues/112)).
- **Installable mobile PWA** with a responsive layout ([#73](https://github.com/parekhrohan21/fastf1_pitwall/issues/73)). On iOS Safari use *Share → Add to Home Screen*; on Android Chrome use *⋮ → Install app*.
- **Resilient loading**: TLS impersonation (`curl_cffi`) to get past CloudFront/Cloudflare 403s, progressive fallback when parts of a session are missing, and two-layer caching (FastF1 disk cache + `st.cache_data`).

---

## ⚙️ Configuration

There is nothing to configure for normal use. One optional setting:

| Setting | Where | Purpose |
|---|---|---|
| `F1_PROXY` | Environment variable, or a Streamlit secret in `.streamlit/secrets.toml` | Routes FastF1 and Ergast requests through a proxy, e.g. `http://user:pass@proxy:port`. Use it behind a corporate firewall or if the F1 CDN blocks your host. |

FastF1 data is cached in `cache/`, which is created on first run and gitignored. Delete it to force a fresh download.

---

## 📁 Project structure

```
fastf1_pitwall/
├── app.py                  # Streamlit entry point: sidebar, session state, page layout
├── src/
│   ├── data/loader.py      # FastF1 loading, caching, proxy/TLS bypass, all metric calculations & exporters
│   ├── charts/plotly.py    # Interactive Plotly figure builders
│   ├── charts/matplotlib.py# Static telemetry charts & channel filtering
│   ├── ui/styles.py        # CSS design system, team/compound colours, theme toggle
│   └── ui/components.py    # Reusable UI sections, metric cards, map tabs, export panels
├── tests/                  # pytest suite, one module per feature (test_<feature>.py)
├── .github/workflows/test.yml  # CI: runs pytest on every push / PR to main
├── .devcontainer/          # Codespaces / Dev Container definition
├── Dockerfile, .dockerignore
├── requirements.txt
├── README.md               # This file: setup and usage
├── DOCS.md                 # Developer manual: architecture, caching, rendering pipeline, full changelog
└── AGENT.md                # Guidelines for AI coding agents working in this repo
```

A typical feature has a `_calculate_*` or `_build_*` function in `loader.py`, a `build_*_fig` in `charts/plotly.py`, a `_render_*_section` in `ui/components.py`, a call in `app.py`, and a `tests/test_<feature>.py`. [DOCS.md §13](DOCS.md#13-extending-the-dashboard--how-to-add-a-new-feature) walks through adding one.

---

## 🧑‍💻 Development

### Run the tests

```bash
python3.11 -m pytest tests/
```

The tests use mocked FastF1 data and need no network access. CI ([.github/workflows/test.yml](.github/workflows/test.yml)) runs the same command on Python 3.11 for every push and pull request to `main`.

A quick syntax check across the app:

```bash
python3 -m py_compile app.py src/data/loader.py src/ui/styles.py src/ui/components.py src/charts/matplotlib.py src/charts/plotly.py
```

### Contributing workflow

All changes go through an issue, a branch and a pull request:

1. **Open an issue**: `gh issue create --title "<type>: <summary>" --label "<bug|enhancement>"`
2. **Branch from an up-to-date `main`**: `git checkout main && git pull && git checkout -b <feat|fix|docs>/<short-description>`
3. **Implement**, following the patterns in [AGENT.md](AGENT.md) and [DOCS.md §14 Common Pitfalls](DOCS.md#14-common-pitfalls--gotchas). Two rules matter most:
   - After `load_session()`, check that `sess.laps` exists and is non-empty before using it.
   - If loading or rendering fails, reset `session`, `session2`, `sess_key` and `sess_key2` in `st.session_state` inside the `except` block, so the app doesn't get stuck in a crash loop.
4. **Test**: run the pytest suite and add tests for new logic.
5. **Review**: write `code_review_issue_<number>.md` against the checklist in [AGENT.md](AGENT.md).
6. **Commit and open a PR** that references the issue (`Closes #<number>`), then merge with `gh pr merge --merge --delete-branch`.
7. **Update the docs**: add the feature to this README and add a changelog entry in [DOCS.md](DOCS.md).

---

## ⚠️ Troubleshooting

| Problem | Fix |
|---|---|
| First load is slow | Expected. FastF1 downloads 50–100 MB per session; later loads are cached. |
| "Session data unavailable" | Recent sessions can take a while to be published in full. Try an older completed session, or click **Load Session(s)** again (the bad cache entry is cleared automatically). |
| HTTP 403 from the F1 API | TLS impersonation normally handles this. If it doesn't, set `F1_PROXY` (see [Configuration](#%EF%B8%8F-configuration)) and use **Run Connection Test** in the sidebar diagnostics. |
| Want data from an in-progress session | Turn on **🔴 Real-Time Live Timing Mode**. The normal loader only works once F1 publishes the session data. |
| Port 8501 already in use | `lsof -i :8501` and stop that process, or run `streamlit run app.py --server.port 8502`. |
| Docker can't connect to the daemon | Start Docker Desktop (`open -a Docker` on macOS), wait for it to finish starting, then retry. |
| Layout errors or `width=` warnings | Your Streamlit is too old. `pip install -r requirements.txt` to get ≥ 1.44. |
| Top bar keeps the old theme | Click the theme toggle again. The CSS is re-injected on every rerun. |

---

## 🗺 Roadmap & changelog

Open feature work:

- [#156](https://github.com/parekhrohan21/fastf1_pitwall/issues/156): Grand Prix weekend multi-session progression tracker
- [#157](https://github.com/parekhrohan21/fastf1_pitwall/issues/157): Clean air vs dirty air pace impact
- [#171](https://github.com/parekhrohan21/fastf1_pitwall/issues/171): Telemetry-driven session highlight video generation
- [#172](https://github.com/parekhrohan21/fastf1_pitwall/issues/172): `DECISIONS.md` architecture decision records

The full roadmap is in [DOCS.md §17](DOCS.md#17-future-roadmap), and a per-PR changelog of every resolved issue is in [DOCS.md §18](DOCS.md#18-solved-issues--changelog). You can also browse [closed issues on GitHub](https://github.com/parekhrohan21/fastf1_pitwall/issues?q=is%3Aissue+is%3Aclosed).

---

## ⚖️ Data & licensing

Data comes from the official F1 live timing service and the Ergast-compatible Jolpica API, via [FastF1](https://docs.fastf1.dev). Pit Wall is not affiliated with Formula 1. **For educational and non-commercial use only.**
