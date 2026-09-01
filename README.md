# 🏎 Pit Wall — F1 Telemetry Dashboard

A professional-grade **Streamlit + FastF1** dashboard with a dynamic, data-driven styling engine for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **6 telemetry channels** alongside driver headshots, lap time history, fuel-adjusted pace, tyre stint timelines, fastest laps leaderboard, track maps, full race replays, and detailed lap/weather summaries.

---

## 🚀 Key Features

- **Any Session**: Supports data from 2018 → present (Race, Qualifying, Sprint, Practice 1/2/3).
- **6-Channel Telemetry & Interactive Filtering**: View combined or separate traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS, with an interactive multiselect toggle to filter and reorder channels on the fly.
- **Head-to-Head Comparison**: Overlay two drivers on the primary charts, plus a **Speed Delta (Δ)** chart and a **Continuous Time Delta (Δ)** chart showing exactly where time is gained/lost per meter along the track.
- **Interactive Track Map**: A Plotly-powered map coloured by speed, with secondary driver path overlays. Gracefully falls back to a clean gray track outline with warning banners if telemetry data (like speed or driver pedal inputs) is incomplete or partially unavailable, ensuring the dashboard never crashes.
- **AWS-Style Mini-Sector Speed Map**: In Compare Mode, the track map is dynamically divided into dozens of 200m mini-sectors based on distance telemetry. Each track segment is smoothly interpolated and coloured according to the driver who carried the highest average speed through that exact section, mimicking premium broadcast graphics.
- **Driver Input Track Map**: A dedicated map mode visualising driver foot pedal telemetry (Green for 100% Throttle, Red for Braking, Yellow for Coasting). Supports side-by-side comparison in Compare Mode.
- **Corner-by-Corner Analysis**: An advanced performance tab that fetches track layout coordinates via FastF1 to let you select a corner (e.g. Turn 1). Automatically calculates apex speed, braking points, max steering angle (°), and DRS activation status, plotting racing line overlays, speed profiles, steering wheel input curves, and DRS channel subplots in a multi-trace layout.
- **Animated Race Replay**: Watch a full animated replay of the session plotting all drivers on the track with a scrubbable timeline.
- **Rich Dashboard Context**: Includes custom tyre visualisations (compound, age, freshness) and a detailed weather strip (air/track temp, humidity, rainfall, track status).
- **Driver Headshot in Banner**: The driver summary banner automatically fetches and renders the official F1 headshot photo (from FastF1's `HeadshotUrl` field) as a circular portrait with a team-coloured ring border. Falls back silently if the image is unavailable.
- **Session Statistics**: A dashboard of 6 high-level metrics per driver covering Grid Position, Finish Position, Status, Best Lap time, Race Pace (Avg), and Top Speed (ST). Displayed seamlessly underneath the driver summary banner.
- **Lap Time History Chart**: An interactive Plotly line chart immediately below the driver banner showing every valid lap time across the race. Each point is colour-coded by **tyre compound** (Red/Gold/Grey/Green/Blue), pit-out laps are marked with ▲ triangles, and the currently selected lap is highlighted with a dotted vertical line. A **compound multiselect filter** above the chart lets you show or hide specific compounds instantly.
- **Tyre Stint Timeline**: A Gantt-style horizontal bar chart showing each driver's complete tyre strategy at a glance. Every stint is rendered as a coloured bar labelled with compound name, a ★ badge for fresh sets, and lap count. Fully supports comparison mode with both drivers stacked on the same axis.
- **Pit Stop Summary Table**: A dedicated table showing each driver's pit stops, including lap number, stop duration, and tyre compound changes (e.g. from Soft to Medium). Highlights the selected driver's row with a team-colour accent border.
- **Pit Strategy & Undercut / Overcut Simulator**: An automated strategic analysis engine in compare mode that identifies adjacent pit stops (within ±3 laps) between two drivers, isolates the pit window, calculates the time gap before and after the pit cycle, and plots a lap-by-lap gap chart with vertical pit markers and outcome status (Successful / Failed undercut/overcut).
- **Tyre Degradation Modeling & Predictive Crossover Matrix**: A dedicated analysis section calculating OLS linear and quadratic regressions on valid flyer laps per stint. Plots a scatter chart of tyre age vs lap time with regression trendlines and dashed quadratic thermal curves. Automatically estimates a **Cliff Lap** (TyreLife lap at which pace degrades ≥ 1.5 s above baseline) and a **Pit Window** (cliff ± 3 laps), displayed in a full-field **Tyre Life & Crossover Prediction Matrix** table with urgency badges (🟢 Safe / 🟡 Soon / 🔴 Critical / ✅ Past Cliff).
- **Fuel-Adjusted Pace Analysis**: Removes the fuel-load penalty from every lap time to reveal each driver's true one-lap pace. Uses the formula `adjusted = actual − (laps_remaining × fuel_effect)` to normalise all laps to equivalent empty-tank pace. Includes an interactive slider to tune the fuel effect assumption (default 0.030 s/lap), compound-coloured markers, raw vs adjusted dual traces, per-driver stat cards, and an expander containing a **Simulated Qualifying Leaderboard** that ranks the entire field based on their median fuel-corrected pace.
- **Fastest Laps Leaderboard**: A ranked table of every driver's best lap in the session. Columns include position, lap time, gap to P1, tyre compound (with coloured dot), lap number, and speed-trap top speed. The selected driver row is highlighted with a team-colour accent border and background tint.
- **Official Session Classification Leaderboard**: Renders the complete official session standings at the very bottom of the page. Automatically formats absolute lap time for the winner, relative timing gaps (e.g. `+1.234s`) or lapped status for subsequent finishers, points awarded, and retirements/DNFs in Race and Sprint sessions, alongside their cumulative Drivers' Championship standings points (`CH Points`) and the number of pit stops (`Stops`). For Qualifying, it displays `Q1`, `Q2`, and `Q3` sector/lap breakdowns. Practice sessions automatically notify the user that official standings are not applicable and redirect to the fastest laps list. Highlights the selected driver(s) using their constructor team colours.
- **Constructors' Championship Standings**: A seasonal standings table displayed directly above the official session classification, dynamically loaded from the Jolpi (Ergast) API for the season and round being viewed, with row highlighting matched to constructor team colours.
- **Ideal Lap vs Actual Lap**: For every driver, the best Sector 1, Sector 2, and Sector 3 times are extracted independently across all laps and summed to form their **Theoretical Best Lap**. A per-driver card (in team colour) shows each sector time, the lap it came from, the theoretical lap time, and the **Time Left on Table** (highlighted red if > 0.05 s). A full-field ranked table ordered by theoretical best is also shown. Gracefully hidden if sector data is unavailable for the session.
- **High-Throughput Telemetry Data Exporter (CSV, Parquet, JSON)**: A collapsible export panel beneath the telemetry charts with a dynamic format selector for **CSV**, **Apache Parquet (`.parquet`)**, and **structured JSON (`.json`)**. The exported file includes high-frequency channels (Distance, Speed, Throttle, Brake, RPM, Gear, DRS, X/Y/Z coordinates, Time, SessionTime), **Sector 1/2/3 times** (in seconds), and lap metadata (driver, lap number, lap time, compound).
- **Post-Race Debrief PDF Exporter**: Capture the entire visual state of your analysis (Lap Time History, Tyre Stints, Gap to Leader, Position History) and export it as a clean, broadcast-style PDF report for easy offline sharing.
- **Premium Aesthetics**: A custom built, fully responsive UI inspired by modern flat/frosted glass aesthetics. Features the premium **Inter** font, seamless keyframe animations (fade-ins, slide-ups), glassmorphism interactive hovers, and fully transparent overlay rendering for static Matplotlib telemetry charts.
- **Smooth Page Transitions**: Every Streamlit rerender triggers a polished `pageEnter` animation — a combined fade, upward slide, subtle scale, and soft blur-clear — powered by a `MutationObserver` that detects Streamlit's internal `data-stale` lifecycle attribute. The dark/light theme switch also cross-fades backgrounds smoothly via CSS `transition` rather than snapping.
- **Dynamic Constructor Theming**: The entire application automatically recolours its UI variables (buttons, cards, banners, charts) to aggressively match the real-world **Constructor Team Colour** of the selected primary driver!
- **Official Team Logos & Badges**: The Driver Summary banner integrates official high-resolution F1 team logos pulled dynamically via Python logic, laid out alongside the full FastF1 team name.
- **Dedicated Light/Dark Toggle**: Switch effortlessly between a midnight `#0d0d0d` dark mode and a bright `#f5f5f7` light mode. A strict CSS-override toggle tracks state in the sidebar and flawlessly colours edge-cases like dropdowns menus, checkboxes, and the top toolbars.
- **Native UI Compatibility**: Full support for Streamlit's native overlays (e.g. settings menus, sidebar navigation icons) and system-animated run indicators without custom CSS overlapping or breakage. Material Symbols icons (sidebar collapse arrow, toolbar buttons) are explicitly preserved via targeted CSS font rules.
- **Gap to Leader Chart**: Interactive Plotly chart showing every driver's time gap to the race leader lap-by-lap. Selected driver(s) are highlighted in team colour against a faded field, with ▼ pit lap markers and a final gap stat card per driver.
- **Race Control Incident Timeline & Flag Overlays**: Parses `race_control_messages` from the session to overlay semi-transparent Safety Car 🟠, VSC 🟡, Red Flag 🔴, and Yellow Flag 🟡 zone bands on the Lap Time History and Gap to Leader charts. A searchable and filterable **Race Control Feed** table below the Gap chart lists every incident, flag type, message, and lap number.
- **Race Position Chart**: Plotly line chart showing every driver's track position across all race laps. All 20 drivers are rendered as faint background traces; selected driver(s) are overlaid in full team colour with lap markers. The Y-axis is inverted so P1 sits at the top. Automatically hidden for non-race session types (Qualifying, Practice) where lap-by-lap position is unavailable.
- **Mobile PWA Ready**: The dashboard acts as a native mobile application with fully responsive layouts, including dynamically scaling Matplotlib telemetry graphs to fit the viewport without horizontal scrollbars or clipping. Pin it to your iOS or Android home screen for a fullscreen, address-bar-free app experience powered by an injected embedded Web Manifest!
- **Session Info Header**: A contextual banner displayed immediately after loading a session, showing the **circuit name**, **country flag** emoji, **round number**, **session type** (with icon — 🏆 Race, ⏱ Qualifying, ⚡ Sprint, 🔧 Practice), and **event date**. The banner is styled with the active team colour as a left-accent border and a subtle gradient tint, and degrades silently if any field is unavailable.
- **Driver Name Mapping**: All driver dropdowns, lap selectors, and the fastest laps leaderboard display full formatted names (e.g. `NOR · Norris`) instead of raw FastF1 driver numbers. Built dynamically from FastF1 session data so it works correctly for any season, with a raw-number fallback for any driver whose info is unavailable.
- **Connection Diagnostics & Bypass**: Bypasses anti-bot/CloudFront datacenter blockades automatically on cloud hosting platforms using unconditional TLS handshake emulation (via `curl_cffi`) impersonating a genuine browser signature. Includes a sidebar **Connection Diagnostics** widget to test connectivity and optional proxy configuration (`F1_PROXY`).
- **Design Origin Footer**: A subtle, beautifully styled bottom footer displaying `Made proudly in Great Britain 🇬🇧` at the bottom of all pages and states.
- **Multi-Driver Grid Analysis & Heatmaps**: Grid-wide analytical matrix allowing users to select 3 to 20 drivers across the field. Renders interactive Plotly heatmaps color-coded by time deltas or speed deficits for **Sector Split Deltas** (S1, S2, S3, Theoretical Best), **Lap-by-Lap Pace Heatmap** (Drivers × Laps), and **Top Speed Matrix** (ST, I1, I2, FL).
- **Driver Consistency Index & Stint Pace Distribution**: Calculates driver lap time variance per stint after filtering out in-laps, out-laps, and Safety Car / Red Flag periods. Evaluates a **Consistency Score** (0–100%), Lap Time Std Dev (±s), Clean Air Pace vs. **Traffic Deficit** (+s/lap), and renders interactive Plotly Violin and Boxplot distributions with raw lap points alongside a stint breakdown table.
- **Track Temperature & Weather Impact Correlation**: Correlates track and air temperature shifts, rainfall intensity, and humidity with lap time drop-offs and tyre compound performance. Renders a dual-axis Plotly chart overlaying Track Temperature (°C) on driver pace, featuring automatic detection of **Rain Crossover Windows** (Slicks ↔ Intermediates/Wets) and Pearson pace-heat sensitivity scores.
- **Multi-Year Historical Lap Comparison**: Enables multi-season telemetry comparisons for the same circuit across different technical regulation eras (e.g. 2024 ground-effect vs 2020 high-downforce era). Aligns distance-based telemetry to plot speed profile overlays (km/h) and continuous time delta curves (Δ seconds), displaying comparative metrics for Era Lap Time Delta, Top Speed, Minimum Apex Speed, and Full Throttle Ratio.
- **High Performance**: FastF1 caching combined with Streamlit session state keeps the heavy data processing instant after the first load.

---

## 📁 Project Structure

```
fastf1_pitwall/
├── app.py              # Main Streamlit entry point & orchestration
├── src/                # Modular source package
│   ├── data/
│   │   └── loader.py   # FastF1 data loaders, caching & proxy bypass
│   ├── charts/
│   │   ├── plotly.py   # Interactive Plotly chart builders
│   │   └── matplotlib.py # Static Matplotlib telemetry charts
│   └── ui/
│       ├── styles.py    # CSS design system, constants & themes
│       └── components.py # UI cards, headers, tables & map blocks
├── tests/              # Pytest unit and integration tests
├── requirements.txt    # Pinned Python dependencies
├── Dockerfile          # Containerisation setup
├── README.md           # User documentation
├── AGENT.md            # AI developer agent guidelines
└── DOCS.md             # Developer manual
```

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

> **Note:** On first load, the dashboard automatically defaults to the most recent season (currently 2026), the most recently completed Grand Prix of that season (or the first race of the calendar if no races have completed yet), and dynamically selects the driver who won that session (or the fastest driver for practice sessions).

1. **Sidebar → Season** — pick a year (2018 – present)
2. **Sidebar → Grand Prix** — pick any event from that season's calendar
3. **Sidebar → Session** — choose Race, Qualifying, Sprint, FP1, FP2, or FP3
4. **Click ⬇️ Load Session** — The first load streams the data from the F1 API and takes ~10-30 seconds. Afterwards, it is cached down to milliseconds.
5. **Select Drivers and Laps** — Pick a driver and select *Fastest* or a specific lap number.
6. **Compare Drivers** — Tick **👥 Compare with Driver 2** to overlay traces and generate the Speed Delta chart.
7. **Lap Time History** — Scroll past the driver banner to see the full race pace chart with compound-coloured dots, pit-out markers, and a highlighted line for your selected lap.
8. **Fuel-Adjusted Pace** — The next section removes the fuel-load penalty from each lap. Tune the fuel effect slider to explore sensitivity; the solid trace shows corrected pace, the faded dotted trace shows raw pace.
9. **Tyre Stint Timeline** — View the complete tyre strategy as a horizontal colour-coded bar chart. In comparison mode both drivers are stacked for easy strategy comparison.
10. **Pit Stop Summary** — See a detailed breakdown of every pit stop made by your selected driver(s), including the exact duration and tyre change strategy.
11. **Telemetry & Channel Toggle** — Inspect high-resolution telemetry traces. Use the **Telemetry Channels** multiselect dropdown to toggle specific channels (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) on/off and reorder them dynamically with proportional chart height scaling.
12. **Export Telemetry** — Expand the *Export Telemetry Data* panel beneath the telemetry charts to download the raw channel data as a CSV file.
13. **Fastest Laps Leaderboard** — A ranked table of every driver's best lap with gap to P1, compound, and top speed. Your selected driver(s) are highlighted.
14. **Gap to Leader** — Scroll to the Gap to Leader section to see every driver's time gap per lap vs the leader. Your selected driver(s) are highlighted; pit stops are marked with ▼ triangles. A stat card shows the final gap and peak deficit.
15. **Track Map & Replay** — Scroll to the Track Map tabs to view the speed heat-map, driver input pedal traces, or build the full multi-car Race Replay animation!
16. **Championship Standings & Classification** — Scroll to the very bottom to view the Constructors' Championship standings (dynamically matched to constructor colours) and the official final standings table (with points, retirements/laps, stops, and Q1/Q2/Q3 split times where applicable).
17. **Real-Time Live Timing Mode** — Enable **🔴 Real-Time Live Timing Mode** in the sidebar during a live race weekend. Start the SignalR stream recorder to save WebSocket stream packets to disk, select an auto-refresh rate (5s, 10s, 15s, 30s), and click **⬇️ Load Session(s)** to view live streaming telemetry and lap times!
18. **Multi-Driver Grid Analysis & Heatmaps** — Scroll to the Multi-Driver Grid Analysis section to select 3 to 20 drivers across the grid. Toggle between **Sector Split Deltas**, **Lap-by-Lap Pace Heatmap**, and **Top Speed Matrix** to view color-coded performance heatmaps.
19. **Corner-by-Corner Analysis** — Navigate to the **Track Map → 🔍 Corner Analysis** tab. Select a corner from the dropdown. The dashboard automatically calculates apex speed, braking point, max steering angle (°), and DRS activation status, and renders a 4-subplot telemetry layout: Racing Line, Speed Profile, Steering Angle, and DRS channel.
20. **Track Temperature & Weather Correlation** — Scroll to the **Weather Impact Correlation** section. View the dual-axis Plotly chart overlaying Track Temperature (°C) on driver pace, with auto-detected Rain Crossover Windows and Pearson pace-heat sensitivity scores.
21. **Multi-Year Historical Lap Comparison** — Scroll to the **Multi-Year Comparison** section. Select a second year and Grand Prix to compare telemetry from different technical regulation eras. Speed profile overlays and a continuous time delta curve (Δ seconds vs Distance) are rendered with metric cards for Era Lap Time Delta, Top Speed, Min Apex Speed, and Full Throttle %.
22. **Tyre Life & Crossover Prediction Matrix** — Within the **Tyre Degradation Modelling** section, the Crossover Prediction Matrix table shows the predicted cliff lap (TyreLife at +1.5 s pace drop), remaining laps to cliff, and a colour-coded pit window recommendation per stint.


---

## ⚠️ Known Limitations & Troubleshooting

| Problem | Fix |
|---|---|
| First load is slow | Expected behaviour (FastF1 is downloading ~50-100MB of telemetry). Subsequent loads are cached. |
| Active / Ongoing Sessions | Toggle **🔴 Real-Time Live Timing Mode** in the sidebar to stream live SignalR WebSocket packets during live sessions. For historical sessions, static timing data is loaded once published on F1's CDN. |
| Session fails to load | Some recent/future sessions may not be published fully yet. Try an older completed race. |
| Port 8501 already in use | Run `lsof -i :8501` and kill the process, or run Streamlit on a different port using `streamlit run app.py --server.port 8502` |
| Docker fails to connect API | The Docker Daemon is not running. Launch the Docker Desktop explicitly first using `open -a Docker`, wait 30 seconds for the engine to initialise, and try again. |
| Sidebar shows `keyboard_double_arrow_left` text | The custom font CSS is overriding Streamlit's icon font. Ensure you are running the latest version of the app — this was patched via explicit `Material Symbols` CSS restoration. |
| Plotly deprecation warning on `use_container_width` | The codebase now uses `width='stretch'` / `width='content'` throughout. If you see this warning, ensure you are running the latest version of the app. |
| Top bar doesn't change with theme | A known edge-case on older cached renders. Toggle the theme button once more — the CSS injection re-applies on every rerun. |
| F1 API HTTP 403 blocks (CloudFront/Cloudflare) | Bypassed automatically on cloud hosting platforms (e.g. Streamlit Community Cloud) using TLS impersonation. If blocks persist, set the `F1_PROXY` environment variable or Streamlit secret to route requests through a proxy. |
| Verify API connectivity or TLS status | Expand the **🔌 Connection Diagnostics** widget at the bottom of the sidebar and click **Test Connection** to check if the F1 Timing CDN is accessible from your host. |

---

## 🧑‍💻 Contributing & Development Workflow

To ensure code stability and maintain a clean git history, all code changes (fixes or feature requests) must follow this systematic branch-and-PR development workflow:

### Step 1 — Create a GitHub Issue
Always start by documenting the bug or feature request in a GitHub Issue:
```bash
gh issue create --title "<type>: <short summary>" --body "<description and details>" --label "<bug/enhancement>"
```

### Step 2 — Create a Feature or Fix Branch
Switch to a clean `main` branch, pull remote changes, and checkout a dedicated feature/fix branch:
```bash
git checkout main
git pull
git checkout -b <prefix>/<short-description>  # e.g., fix/session-data-unavailable or feature/gap-chart
```

### Step 3 — Implementation Guidelines
When modifying modules in `src/` or `app.py`, adhere to the following safety patterns:
- **Immediate Data Validation**: When loading F1 session data via `load_session()`, always check that the loaded session object contains valid lap data immediately after loading:
  ```python
  sess = load_session(year, gp, session_type)
  if not hasattr(sess, "laps") or sess.laps is None or sess.laps.empty:
      raise ValueError("No lap data available for this session.")
  ```
- **UI Lockup Prevention**: If a session fails to load or fails validation later in the rendering cycle, clear any invalid session objects from `st.session_state` inside the `except` block to prevent the app from getting stuck in an infinite crash loop:
  ```python
  st.session_state["session"] = None
  st.session_state["session2"] = None
  st.session_state["sess_key"] = None
  st.session_state["sess_key2"] = None
  ```

### Step 4 — Run Unit Tests & Verify Syntax
Before staging or committing any code, always run the pytest automated test suite to ensure that data wrangling functions have no regressions:
```bash
python3.11 -m pytest tests/
```

Then run a python syntax compilation check across all source modules:
```bash
python3 -m py_compile app.py src/data/loader.py src/ui/styles.py src/ui/components.py src/charts/matplotlib.py src/charts/plotly.py
```

### Step 5 — Perform Code Review
Before committing, document a formal code review evaluating the changes against the `AGENT.md` Code Review Checklist. Create a markdown artifact named `code_review_issue_<number>.md` summarising the verification of correctness, code quality, documentation updates, and testing results.

### Step 6 — Commit, Push and Open a PR
1. Stage and commit your changes referencing the issue number:
   ```bash
   git add .
   git commit -m "<type>: <short summary>

   Closes #<issue_number>"
   ```
2. Push your branch to the remote repository:
   ```bash
   git push -u origin <branch-name>
   ```
3. Open a Pull Request (PR) on GitHub:
   ```bash
   gh pr create --title "<type>: <short summary>" --body "Closes #<issue_number>"
   ```

### Step 7 — Merge the PR & Clean Up
Once the PR is verified, merge it and delete the remote branch using:
```bash
gh pr merge --merge --delete-branch
```
Clean up your local workspace by switching back to `main`, pulling, and pruning remote tracking branches:
```bash
git checkout main
git pull
git fetch -p
```

---

## 📜 Solved Issues & Changelog

A full historical log of every resolved GitHub issue along with 1-line explanations is available in the developer manual:
👉 **[DOCS.md — Section 18: Solved Issues & Changelog](DOCS.md#18-solved-issues--changelog)**

---

## ⚖️ Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
