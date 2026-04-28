# 🏎 Pit Wall — F1 Telemetry Dashboard

A professional-grade **Streamlit + FastF1** dashboard with a dynamic, data-driven styling engine for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **6 telemetry channels** alongside driver headshots, lap time history, fuel-adjusted pace, tyre stint timelines, fastest laps leaderboard, track maps, full race replays, and detailed lap/weather summaries.

---

## 🚀 Key Features

- **Any Session**: Supports data from 2018 → present (Race, Qualifying, Sprint, Practice 1/2/3).
- **6-Channel Telemetry**: View combined or separate traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS.
- **Head-to-Head Comparison**: Overlay two drivers on the primary charts, plus a **Speed Delta (Δ)** chart showing where time is gained/lost.
- **Interactive Track Map**: A Plotly-powered map coloured by speed, with secondary driver path overlays.
- **Animated Race Replay**: Watch a full animated replay of the session plotting all drivers on the track with a scrubbable timeline.
- **Rich Dashboard Context**: Includes custom tyre visualizations (compound, age, freshness) and a detailed weather strip (air/track temp, humidity, rainfall, track status).
- **Driver Headshot in Banner**: The driver summary banner automatically fetches and renders the official F1 headshot photo (from FastF1's `HeadshotUrl` field) as a circular portrait with a team-coloured ring border. Falls back silently if the image is unavailable.
- **Lap Time History Chart**: An interactive Plotly line chart immediately below the driver banner showing every valid lap time across the race. Each point is colour-coded by **tyre compound** (Red/Gold/Grey/Green/Blue), pit-out laps are marked with ▲ triangles, and the currently selected lap is highlighted with a dotted vertical line.
- **Tyre Stint Timeline**: A Gantt-style horizontal bar chart showing each driver's complete tyre strategy at a glance. Every stint is rendered as a coloured bar labelled with compound name, a ★ badge for fresh sets, and lap count. Fully supports comparison mode with both drivers stacked on the same axis.
- **Fuel-Adjusted Pace Analysis**: Removes the fuel-load penalty from every lap time to reveal each driver's true one-lap pace. Uses the formula `adjusted = actual − (laps_remaining × fuel_effect)` to normalise all laps to equivalent empty-tank pace. Includes an interactive slider to tune the fuel effect assumption (default 0.030 s/lap), compound-coloured markers, raw vs adjusted dual traces, and per-driver stat cards showing best adjusted time and median pace.
- **Fastest Laps Leaderboard**: A full-field ranked table of every driver's best lap in the session. Columns include position, lap time, gap to P1, tyre compound (with coloured dot), lap number, and speed-trap top speed. The selected driver row is highlighted with a team-colour accent border and background tint.
- **Export Telemetry as CSV**: A collapsible export panel beneath the telemetry charts with per-driver `📥 Download CSV` buttons. The exported file includes Distance, Speed, Throttle, Brake, RPM, Gear, DRS, X/Y/Z position, and lap metadata (driver, lap number, lap time, compound).
- **Premium Aesthetics**: A custom built, fully responsive UI inspired by modern flat/frosted glass aesthetics. Features the premium **Inter** font, seamless keyframe animations (fade-ins, slide-ups), glassmorphism interactive hovers, and fully transparent overlay rendering for static Matplotlib telemetry charts.
- **Smooth Page Transitions**: Every Streamlit rerender triggers a polished `pageEnter` animation — a combined fade, upward slide, subtle scale, and soft blur-clear — powered by a `MutationObserver` that detects Streamlit's internal `data-stale` lifecycle attribute. The dark/light theme switch also cross-fades backgrounds smoothly via CSS `transition` rather than snapping.
- **Dynamic Constructor Theming**: The entire application automatically recolours its UI variables (buttons, cards, banners, charts) to aggressively match the real-world **Constructor Team Colour** of the selected primary driver!
- **Official Team Logos & Badges**: The Driver Summary banner integrates official high-resolution F1 team logos pulled dynamically via Python logic, laid out alongside the full FastF1 team name.
- **Dedicated Light/Dark Toggle**: Switch effortlessly between a midnight `#0d0d0d` dark mode and a bright `#f5f5f7` light mode. A strict CSS-override toggle tracks state in the sidebar and flawlessly colors edge-cases like dropdowns menus, checkboxes, and the top toolbars.
- **Native UI Compatibility**: Full support for Streamlit's native overlays (e.g. settings menus, sidebar navigation icons) and system-animated run indicators without custom CSS overlapping or breakage. Material Symbols icons (sidebar collapse arrow, toolbar buttons) are explicitly preserved via targeted CSS font rules.
- **Gap to Leader Chart**: Interactive Plotly chart showing every driver's time gap to the race leader lap-by-lap. Selected driver(s) are highlighted in team colour against a faded field, with ▼ pit lap markers and a final gap stat card per driver.
- **Mobile PWA Ready**: The dashboard acts as a native mobile application. Pin it to your iOS or Android home screen for a fullscreen, address-bar-free app experience powered by an injected embedded Web Manifest!
- **Session Info Header**: A contextual banner displayed immediately after loading a session, showing the **circuit name**, **country flag** emoji, **round number**, **session type** (with icon — 🏆 Race, ⏱ Qualifying, ⚡ Sprint, 🔧 Practice), and **event date**. The banner is styled with the active team colour as a left-accent border and a subtle gradient tint, and degrades silently if any field is unavailable.
- **Driver Name Mapping**: All driver dropdowns, lap selectors, and the fastest laps leaderboard display full formatted names (e.g. `NOR · Norris`) instead of raw FastF1 driver numbers. Built dynamically from FastF1 session data so it works correctly for any season, with a raw-number fallback for any driver whose info is unavailable.
- **High Performance**: FastF1 caching combined with Streamlit session state keeps the heavy data processing instant after the first load.

---

## 🛠 Prerequisites

| Without Docker | With Docker |
|---|---|
| Python 3.11+ | Docker Desktop installed & running |
| pip | No Python needed locally |

> [!NOTE]
> The app is built against **Streamlit 1.44+** and uses the current `width='stretch'` API (replacing the deprecated `use_container_width` parameter). Always use the version pinned in `requirements.txt`.

---

## 💻 Running Locally (Without Docker)

### Step 1 — Clone the repo

```bash
git clone https://github.com/parekhrohan21/fastf1_pitwall.git
cd fastf1_pitwall
```

### Step 2 — (Recommended) Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Run the app

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## 🐳 Running with Docker

### Step 1 — Build the image

```bash
docker build -t pitwall .
```

### Step 2 — Run the container with cache mount

FastF1 caches downloaded telemetry (~50-100MB per session) to disk. You should mount a local folder so you don't re-download data every time the container restarts:

```bash
docker run -p 8501:8501 -v $(pwd)/cache:/app/cache pitwall
```

Open **http://localhost:8501**.

---

## 📱 Mobile App Install (PWA)

Host the app on Streamlit Community Cloud (or your own cloud VM) and access the URL on your mobile phone.

### iOS Safari
1. Tap the **Share** icon at the bottom of the screen.
2. Scroll down and tap **Add to Home Screen**.

### Android Chrome
1. Tap the **Triple Dot ⋮** menu in the top right.
2. Tap **Add to Home screen** (or "Install app").

The app will install seamlessly onto your device with a custom 🏎 icon, opening without a browser border via `standalone` display mode!

---

## 📚 How to Use the Dashboard

> **Note:** The dashboard will automatically default to **Lando Norris**, **2025**, and the **British Grand Prix (Silverstone)** on first load.

1. **Sidebar → Season** — pick a year (2018 – present)
2. **Sidebar → Grand Prix** — pick any event from that season's calendar
3. **Sidebar → Session** — choose Race, Qualifying, Sprint, FP1, FP2, or FP3
4. **Click ⬇️ Load Session** — The first load streams the data from the F1 API and takes ~10-30 seconds. Afterwards, it is cached down to milliseconds.
5. **Select Drivers and Laps** — Pick a driver and select *Fastest* or a specific lap number.
6. **Compare Drivers** — Tick **👥 Compare with Driver 2** to overlay traces and generate the Speed Delta chart.
7. **Lap Time History** — Scroll past the driver banner to see the full race pace chart with compound-coloured dots, pit-out markers, and a highlighted line for your selected lap.
8. **Fuel-Adjusted Pace** — The next section removes the fuel-load penalty from each lap. Tune the fuel effect slider to explore sensitivity; the solid trace shows corrected pace, the faded dotted trace shows raw pace.
9. **Tyre Stint Timeline** — View the complete tyre strategy as a horizontal colour-coded bar chart. In comparison mode both drivers are stacked for easy strategy comparison.
10. **Export Telemetry** — Expand the *Export Telemetry Data* panel beneath the telemetry charts to download the raw channel data as a CSV file.
11. **Fastest Laps Leaderboard** — A ranked table of every driver's best lap with gap to P1, compound, and top speed. Your selected driver(s) are highlighted.
12. **Gap to Leader** — Scroll to the Gap to Leader section to see every driver's time gap per lap vs the leader. Your selected driver(s) are highlighted; pit stops are marked with ▼ triangles. A stat card shows the final gap and peak deficit.
13. **Track Map & Replay** — Scroll to the Track Map tabs to view the speed heat-map or build the full multi-car Race Replay animation!

---

## ⚠️ Known Limitations & Troubleshooting

| Problem | Fix |
|---|---|
| First load is slow | Expected behavior (FastF1 is downloading ~50-100MB of telemetry). Subsequent loads are cached. |
| Session fails to load | Some recent/future sessions may not be published fully yet. Try an older completed race. |
| Port 8501 already in use | Run `lsof -i :8501` and kill the process, or run Streamlit on a different port using `streamlit run app.py --server.port 8502` |
| Docker fails to connect API | The Docker Daemon is not running. Launch the Docker Desktop explicitly first using `open -a Docker`, wait 30 seconds for the engine to initialize, and try again. |
| Sidebar shows `keyboard_double_arrow_left` text | The custom font CSS is overriding Streamlit's icon font. Ensure you are running the latest version of the app — this was patched via explicit `Material Symbols` CSS restoration. |
| Plotly deprecation warning on `use_container_width` | The codebase now uses `width='stretch'` / `width='content'` throughout. If you see this warning, ensure you are running the latest version of the app. |
| Top bar doesn't change with theme | A known edge-case on older cached renders. Toggle the theme button once more — the CSS injection re-applies on every rerun. |

---

## ⚖️ Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
