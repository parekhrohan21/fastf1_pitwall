# 🏎 Pit Wall — F1 Telemetry Dashboard

A professional-grade **Streamlit + FastF1** dashboard with a dynamic, data-driven styling engine for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **6 telemetry channels** alongside driver headshots, lap time history, fuel-adjusted pace, tyre stint timelines, intra-team teammate battles, braking dynamics, gear shift strategies, speed trap velocity radars, fastest laps leaderboard, track maps, full race replays, and detailed lap/weather summaries.

---

## 🚀 Key Features

- **Any Session**: Supports data from 2018 → present (Race, Qualifying, Sprint, Practice 1/2/3).
- **6-Channel Telemetry & Interactive Filtering**: View combined or separate traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS, with an interactive multiselect toggle to filter and reorder channels on the fly.
- **Head-to-Head Comparison**: Overlay two drivers on the primary charts, plus a **Speed Delta (Δ)** chart and a **Continuous Time Delta (Δ)** chart showing exactly where time is gained/lost per meter along the track.
- **Interactive Track Map**: A Plotly-powered map coloured by speed, with secondary driver path overlays. Gracefully falls back to a clean gray track outline with warning banners if telemetry data (like speed or driver pedal inputs) is incomplete or partially unavailable, ensuring the dashboard never crashes.
- **Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown** ([Issue #153](https://github.com/parekhrohan21/fastf1_pitwall/issues/153)): Deep-dive telemetry breakdown of pit lane time losses isolating pit lane speed-limiter transit duration ($t_{\text{pit\_lane}} = \text{PitOutTime} - \text{PitInTime}$), in-lap push delta against clean-air baseline flyer pace ($\Delta t_{\text{in}} = t_{\text{in}} - t_{\text{baseline}}$), out-lap cold tyre warm-up performance ($\Delta t_{\text{out}} = t_{\text{out}} - t_{\text{baseline}}$), net pit loss, and sector-by-sector warm-up deltas ($S_1, S_2, S_3$). Visualised via an interactive stacked horizontal bar chart (`build_pit_loss_fig`), 4 summary KPI cards (*Fastest Pit Lane Transit*, *Best In-Lap Push Delta*, *Best Out-Lap Warm-up*, *Grid Median Pit Loss*), Head-to-Head sector warm-up cards, and a full-field classified efficiency leaderboard table.
- **Intra-Team Teammate Battle & Qualifying Delta Matrix** ([Issue #152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)): Automated teammate head-to-head comparison analytics across all constructors for Qualifying and Race sessions. Renders a grid-wide horizontal diverging bar chart of teammate gaps, sector split advantages (S1, S2, S3), clean-air median race pace deltas, and an interactive classified matrix with top KPI cards for closest battle, largest delta, and grid median gap.
- **Speed Trap & Intermediate Velocity Radar Breakdown** ([Issue #150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)): Grid-wide speed trap and intermediate velocity analytics using official timing sensors (`SpeedST`, `SpeedI1`, `SpeedI2`, `SpeedFL`). Extracts maximum velocities, calculates DRS aerodynamic efficiency deltas, and aggregates top speeds by constructor and Power Unit manufacturer (Ferrari, Mercedes, Red Bull Powertrains, Renault). Renders an interactive 4-axis polar radar profile (`build_speed_trap_radar_fig`), grouped constructor/engine benchmark bar charts (`build_speed_trap_bar_fig`), and a classified Speed Trap Leaderboard table with top-speed advantage metric cards.
- **Gear Shift Strategy & RPM Power Band Optimization** ([Issue #149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)): Extracts engine RPM, gear selection, throttle application, and track distance to detect every upshift and downshift. Identifies tactical short-shifts (< 11,000 RPM under > 60% throttle) and redline shift events (≥ 11,800 RPM). Renders a dual-subplot Plotly figure with an RPM operating curve, interactive shift event markers, and horizontal percentage gear usage breakdown (Gears 1 through 8), accompanied by comparative shift count and RPM metrics cards.
- **Braking Efficiency & Trail-Braking Zone Analysis** ([Issue #148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)): High-precision braking telemetry around circuit turn apexes. Extracts longitudinal deceleration (G-force), initial braking distance (m before apex), peak deceleration (G), trail-braking release point, and brake-to-throttle transition time (ms), rendered across a stacked 3-subplot Plotly figure with comparative advantage callouts.
- **High-Throughput Telemetry Data Exporter (CSV, Parquet, JSON)** ([Issue #139](https://github.com/parekhrohan21/fastf1_pitwall/issues/139)): A collapsible export panel beneath the telemetry charts with a dynamic format selector for **CSV**, **Apache Parquet (`.parquet`)**, and **structured JSON (`.json`)**. The exported file includes high-frequency channels (Distance, Speed, Throttle, Brake, RPM, Gear, DRS, X/Y/Z coordinates, Time, SessionTime), **Sector 1/2/3 times** (in seconds), and lap metadata (driver, lap number, lap time, compound).
- **Interactive Telemetry Channel Toggle & Custom Trace Filtering** ([Issue #138](https://github.com/parekhrohan21/fastf1_pitwall/issues/138)): View combined or separate traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS, with an interactive multiselect toggle to filter and reorder channels on the fly with dynamic height scaling.
- **Tyre Degradation Modeling, Thermal Crossover & Fuel Burn Decoupler** ([Issue #81](https://github.com/parekhrohan21/fastf1_pitwall/issues/81), [Issue #137](https://github.com/parekhrohan21/fastf1_pitwall/issues/137), [Issue #151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)): A dedicated analysis section calculating OLS linear and quadratic regressions on valid flyer laps per stint. Features an interactive **Fuel Burn Decoupler** that removes artificial lap time gains from fuel mass reduction (~0.035 s/lap) to compute True Mechanical Tyre Wear and display true degradation rates, fuel masking offsets, and unmasked thermal cliff laps. Plots a scatter chart of tyre age vs lap time with regression trendlines and dashed quadratic thermal curves. Automatically estimates a **Cliff Lap** (TyreLife lap at which pace degrades ≥ 1.5 s above baseline) and a **Pit Window** (cliff ± 3 laps), displayed in a full-field **Tyre Life & Crossover Prediction Matrix** table with urgency badges (🟢 Safe / 🟡 Soon / 🔴 Critical / ✅ Past Cliff).
- **Corner-by-Corner Analysis with Steering & DRS Telemetry** ([Issue #80](https://github.com/parekhrohan21/fastf1_pitwall/issues/80), [Issue #136](https://github.com/parekhrohan21/fastf1_pitwall/issues/136)): An advanced performance tab that fetches track layout coordinates via FastF1 to let you select a corner (e.g. Turn 1). Automatically calculates apex speed, braking points, max steering angle (°), and DRS activation status, plotting racing line overlays, speed profiles, steering wheel input curves, and DRS channel subplots in a 4-trace layout.
- **Post-Race Debrief PDF Exporter** ([Issue #122](https://github.com/parekhrohan21/fastf1_pitwall/issues/122)): Capture the entire visual state of your analysis (Lap Time History, Tyre Stints, Gap to Leader, Position History) and export it as a clean, broadcast-style PDF report for easy offline sharing.
- **Multi-Year Historical Lap Comparison** ([Issue #121](https://github.com/parekhrohan21/fastf1_pitwall/issues/121)): Enables multi-season telemetry comparisons for the same circuit across different technical regulation eras (e.g. 2024 ground-effect vs 2020 high-downforce era). Aligns distance-based telemetry to plot speed profile overlays (km/h) and continuous time delta curves (Δ seconds), displaying comparative metrics for Era Lap Time Delta, Top Speed, Minimum Apex Speed, and Full Throttle Ratio.
- **Track Temperature & Weather Impact Correlation** ([Issue #120](https://github.com/parekhrohan21/fastf1_pitwall/issues/120)): Correlates track and air temperature shifts, rainfall intensity, and humidity with lap time drop-offs and tyre compound performance. Renders a dual-axis Plotly chart overlaying Track Temperature (°C) on driver pace, featuring automatic detection of **Rain Crossover Windows** (Slicks ↔ Intermediates/Wets) and Pearson pace-heat sensitivity scores.
- **Driver Consistency Index & Stint Pace Distribution** ([Issue #119](https://github.com/parekhrohan21/fastf1_pitwall/issues/119)): Calculates driver lap time variance per stint after filtering out in-laps, out-laps, and Safety Car / Red Flag periods. Evaluates a **Consistency Score** (0–100%), Lap Time Std Dev (±s), Clean Air Pace vs. **Traffic Deficit** (+s/lap), and renders interactive Plotly Violin and Boxplot distributions with raw lap points alongside a stint breakdown table.
- **Race Control Incident Timeline & Flag Overlays** ([Issue #118](https://github.com/parekhrohan21/fastf1_pitwall/issues/118)): Parses `race_control_messages` from the session to overlay semi-transparent Safety Car 🟠, VSC 🟡, Red Flag 🔴, and Yellow Flag 🟡 zone bands on the Lap Time History and Gap to Leader charts. A searchable and filterable **Race Control Feed** table below the Gap chart lists every incident, flag type, message, and lap number.
- **Pit Strategy & Undercut / Overcut Simulator** ([Issue #117](https://github.com/parekhrohan21/fastf1_pitwall/issues/117)): An automated strategic analysis engine in compare mode that identifies adjacent pit stops (within ±3 laps) between two drivers, isolates the pit window, calculates the time gap before and after the pit cycle, and plots a lap-by-lap gap chart with vertical pit markers and outcome status (Successful / Failed undercut/overcut).
- **Continuous Time Delta per Meter** ([Issue #116](https://github.com/parekhrohan21/fastf1_pitwall/issues/116)): Distance-aligned time delta (Δ seconds vs Distance) plotted directly beneath the Speed Delta chart in compare mode to show the cumulative time delta along every meter of the track.
- **Multi-Driver Grid Analysis & Heatmaps** ([Issue #85](https://github.com/parekhrohan21/fastf1_pitwall/issues/85)): Grid-wide analytical matrix allowing users to select 3 to 20 drivers across the field. Renders interactive Plotly heatmaps color-coded by time deltas or speed deficits for **Sector Split Deltas** (S1, S2, S3, Theoretical Best), **Lap-by-Lap Pace Heatmap** (Drivers × Laps), and **Top Speed Matrix** (ST, I1, I2, FL).
- **Real-Time Live Timing Mode** ([Issue #84](https://github.com/parekhrohan21/fastf1_pitwall/issues/84)): Stream live timing and telemetry via FastF1 SignalR WebSocket client with disk packet recording and auto-refresh intervals during active F1 race weekends.
- **AWS-Style Mini-Sector Speed Map** ([Issue #78](https://github.com/parekhrohan21/fastf1_pitwall/issues/78)): In Compare Mode, the track map is dynamically divided into dozens of 200m mini-sectors based on distance telemetry, coloured according to the driver who carried the highest average speed through that exact section.
- **Driver Input Track Map**: A dedicated map mode visualising driver foot pedal telemetry (Green for 100% Throttle, Red for Braking, Yellow for Coasting). Supports side-by-side comparison in Compare Mode.
- **Animated Race Replay**: Watch a full animated replay of the session plotting all drivers on the track with a scrubbable timeline.
- **Rich Dashboard Context**: Includes custom tyre visualisations (compound, age, freshness) and a detailed weather strip (air/track temp, humidity, rainfall, track status).
- **Driver Headshot in Banner**: The driver summary banner automatically fetches and renders the official F1 headshot photo (from FastF1's `HeadshotUrl` field) as a circular portrait with a team-coloured ring border. Falls back silently if the image is unavailable.
- **Session Statistics**: A dashboard of 6 high-level metrics per driver covering Grid Position, Finish Position, Status, Best Lap time, Race Pace (Avg), and Top Speed (ST). Displayed seamlessly underneath the driver summary banner.
- **Lap Time History Chart**: An interactive Plotly line chart immediately below the driver banner showing every valid lap time across the race with compound-coloured markers and pit-out flags.
- **Tyre Stint Timeline**: A Gantt-style horizontal bar chart showing each driver's complete tyre strategy at a glance with compound-coloured bars and fresh/used set indicators.
- **Pit Stop Summary Table**: A dedicated table showing each driver's pit stops, duration, and compound changes.
- **Fuel-Adjusted Pace Analysis**: Removes fuel penalty per lap to reveal true one-lap pace with sensitivity slider and Simulated Qualifying Leaderboard.
- **Fastest Laps Leaderboard**: A ranked table of every driver's best lap in the session with gap to P1, compound, lap number, and speed trap speed.
- **Official Session Classification Leaderboard**: Renders complete official session standings (points, DNFs, pit stop counts, Q1/Q2/Q3 split times) and Drivers' Championship points.
- **Constructors' Championship Standings**: Seasonal standings table loaded dynamically from the Ergast API with team-coloured indicators.
- **Ideal Lap vs Actual Lap**: Independent Sector 1, 2, 3 theoretical best extraction with Time Left on Table indicator cards.
- **Gap to Leader Chart**: Interactive Plotly chart showing every driver's time gap to the race leader lap-by-lap with pit markers.
- **Race Position Chart**: Inverted Y-axis line chart tracking positions across all race laps.
- **Dynamic Constructor Theming**: Aggressively recolours buttons, cards, banners, and charts to match the primary driver's team colour.
- **Dedicated Light/Dark Toggle** ([Issue #112](https://github.com/parekhrohan21/fastf1_pitwall/issues/112)): Switch effortlessly between a midnight `#0d0d0d` dark mode and a bright `#f5f5f7` light mode.
- **Mobile PWA Ready** ([Issue #73](https://github.com/parekhrohan21/fastf1_pitwall/issues/73)): Fully responsive layout, responsive Matplotlib graphs, and embedded Web Manifest for homescreen installation.
- **Connection Diagnostics & Bypass** ([Issue #100](https://github.com/parekhrohan21/fastf1_pitwall/issues/100), [Issue #105](https://github.com/parekhrohan21/fastf1_pitwall/issues/105)): TLS impersonation (`curl_cffi`) and sidebar diagnostics to bypass CloudFront/Cloudflare 403 blocks.
- **Design Origin Footer** ([Issue #72](https://github.com/parekhrohan21/fastf1_pitwall/issues/72), [Issue #75](https://github.com/parekhrohan21/fastf1_pitwall/issues/75)): Styled footer displaying `Made proudly in Great Britain 🇬🇧`.
- **Modular Codebase Architecture** ([Issue #82](https://github.com/parekhrohan21/fastf1_pitwall/issues/82)): Refactored into clean `src/` modules (`src/data/`, `src/charts/`, `src/ui/`).
- **Comprehensive Automated Test Suite** ([Issue #83](https://github.com/parekhrohan21/fastf1_pitwall/issues/83)): Fully automated test coverage with **95 pytest unit and integration tests** across 16 dedicated test modules.
- **High Performance**: FastF1 disk caching combined with Streamlit `@st.cache_data` keeps data processing instant after first load.

---

## 📁 Project Structure

```
fastf1_pitwall/
├── app.py              # Main Streamlit entry point & orchestration
├── src/                # Modular source package
│   ├── data/
│   │   └── loader.py   # FastF1 data loaders, caching, proxy bypass, fuel decoupler, teammate battle, pit transit loss & telemetry exporters (CSV/Parquet/JSON)
│   ├── charts/
│   │   ├── plotly.py   # Interactive Plotly chart builders (History, stints, maps, replays, corners, braking, gears, speed traps, teammate matrix, pit loss stacked bars, fuel decoupled deg)
│   │   └── matplotlib.py # Static Matplotlib telemetry charts & dynamic channel filtering
│   └── ui/
│       ├── styles.py    # CSS design system, team/compound constants & dark/light theme toggler
│       └── components.py # UI layout components, metrics cards, map blocks, teammate battle matrix, pit loss breakdown & telemetry export panel
├── tests/              # Pytest automated test suite (95 tests across 16 modules)
│   ├── test_pit_transit_loss.py       # Pit lane transit duration, in-lap/out-lap deltas & sector warm-up
│   ├── test_teammate_battle.py        # Teammate head-to-head battle, qualifying & race pace deltas
│   ├── test_fuel_decoupled_tyre_deg.py # Pure mechanical tyre degradation & fuel burn decoupler
│   ├── test_speed_trap.py             # Speed trap, intermediate velocity & radar metrics
│   ├── test_gear_shifts.py            # Powertrain dynamics, shift detection & gear distributions
│   ├── test_braking_analysis.py       # Braking dynamics, trail-braking & G-force metrics
│   ├── test_telemetry_export.py       # CSV, Apache Parquet & JSON export serialization
│   ├── test_telemetry_channels.py     # Channel toggle configuration & figure scaling
│   ├── test_tyre_crossover.py         # Quadratic degradation regression & cliff prediction
│   ├── test_consistency.py            # Driver Consistency Index & Stint distributions
│   ├── test_weather_correlation.py    # Track temperature correlation & rain detection
│   ├── test_multi_year_comparison.py  # 500-pt distance grid cross-era comparisons
│   ├── test_corner_analysis.py        # Corner telemetry (braking, apex, steering, DRS)
│   ├── test_grid_heatmap.py           # Multi-driver heatmap matrix data wrangling
│   ├── test_live_timing.py            # SignalR live timing stream recorder
│   └── test_data_wrangling.py         # Lap filtering & session statistics
├── requirements.txt    # Pinned Python dependencies (FastF1, Streamlit, PyArrow, etc.)
├── Dockerfile          # Containerisation setup
├── README.md           # User documentation & feature guide
├── AGENT.md            # AI developer agent guidelines & architecture decisions
└── DOCS.md             # Technical developer manual & pipeline architecture
```

---

## 🛠 Prerequisites & System Requirements

Depending on whether you choose to run the dashboard natively or via Docker, ensure the following requirements are met:

### System & Environment Requirements

| Requirement | Local (Without Docker) | Containerized (With Docker) |
|---|---|---|
| **Operating System** | macOS (Apple Silicon / Intel), Linux (Ubuntu/Debian/Fedora), Windows (WSL2 recommended) | Docker-supported host OS |
| **Runtime** | **Python 3.11+** (tested up to 3.12; 3.11 recommended) | **Docker Desktop** (macOS/Windows) or **Docker Engine ≥ 20.10** |
| **Package Manager** | `pip` (or `venv`, `uv`, `conda`) | Pre-packaged in image |
| **Memory (RAM)** | **4 GB minimum**, **8 GB+ recommended** for multi-driver animated replays | 4 GB allocated to Docker container |
| **Disk Space** | ~500 MB for Python environment + ~50–100 MB per cached Grand Prix session | ~1.5 GB for Docker image + local `./cache` volume |
| **Network** | Outbound access to `livetiming.formula1.com:443` and `api.jolpi.ca:443` | Outbound access to F1 timing APIs |

### Core Python Dependencies Matrix

The application is built on a modern, high-performance telemetry analytics stack:

| Package | Minimum Version | Purpose & Architectural Role |
|---|---|---|
| **`streamlit`** | `≥ 1.44.0` | Frontend dashboard framework using the modern `width='stretch'` responsive layout API and custom theme injection. |
| **`fastf1`** | `≥ 3.3.0` | Core F1 timing, telemetry waveform, circuit layout, and Ergast integration data engine. |
| **`pandas`** | `≥ 2.2.0` | High-frequency telemetry dataframe wrangling, lap filtering, and stint timeseries aggregation. |
| **`numpy`** | `≥ 1.26.0` | Longitudinal deceleration ($G$), polynomial regressions, distance grids, and statistical operations. |
| **`plotly`** | `≥ 5.18.0` | Interactive charts (lap time histories, stint Gantt bars, delta graphs, corner analysis, radar profiles). |
| **`matplotlib`** | `≥ 3.8.0` | Static 6-channel high-frequency telemetry waveform visualizations and speed delta overlays. |
| **`curl-cffi`** | `≥ 0.5.10` | TLS handshake browser impersonation (`chrome124`) to bypass F1 CloudFront / Cloudflare anti-bot blocks. |
| **`pyarrow`** | `≥ 14.0.0` | High-throughput columnar Apache Parquet (`.parquet`) telemetry file exporter. |
| **`fpdf2`** & **`Pillow`** | `≥ 2.7.5` / `≥ 10.0.0` | Broadcast-quality Post-Race Debrief PDF generation engine with high-DPI figure captures. |
| **`kaleido`** | `≥ 0.2.1` | Static image rendering engine for Plotly figures during report compilation. |
| **`pytest`** & **`pytest-mock`** | `≥ 8.0.0` / `≥ 3.12.0` | Automated test suite execution (87 unit/integration tests across 15 modules). |

> [!IMPORTANT]
> **Streamlit Version Warning**: The dashboard strictly utilizes Streamlit's modern `width='stretch'` / `width='content'` parameterization. Running on older Streamlit versions (< 1.44.0) will cause deprecation warnings or layout rendering errors. Always use the pinned dependencies in `requirements.txt`.

> [!TIP]
> **Network Proxy Configuration**: If running behind an enterprise firewall or restrictive proxy, set the `F1_PROXY` environment variable or Streamlit secret (`http://user:pass@proxy:port`) to route FastF1 and Ergast HTTP requests safely.
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

### Quick start

Build the image from the project root:

```bash
docker build -t fastf1_pitwall .
```

Run the container and mount the local cache directory so FastF1 data persists between restarts:

```bash
docker run --rm -p 8501:8501 \
  -v "$PWD/cache:/app/cache" \
  --name fastf1-pitwall \
  fastf1_pitwall
```

Then open **http://localhost:8501** in your browser.

### Notes

- The app listens on port `8501`.
- The cache directory is mounted to `/app/cache` to avoid re-downloading the same race data.
- This container is meant for local development or simple deployment; it uses the same Streamlit entrypoint defined in the Dockerfile.

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

1. **Sidebar → Season, Grand Prix & Session** — Pick a year (2018 – present), Grand Prix event from that season's calendar, and session type (Race, Qualifying, Sprint, FP1, FP2, or FP3).
2. **Click ⬇️ Load Session** — The first load streams the data from the F1 API and takes ~10-30 seconds. Afterwards, it is cached down to milliseconds.
3. **Session Info Banner** — View the contextual header showing circuit name, country flag, round number, session type (with icon — 🏆 Race, ⏱ Qualifying, ⚡ Sprint, 🔧 Practice), and event date.
4. **Select Drivers and Laps** — Pick a primary driver and select *Fastest* or a specific lap number. Optionally tick **👥 Compare with Driver 2** to enable head-to-head comparison mode.
5. **Driver Summary Banner & Session Statistics** — Inspect the official driver headshot portrait, constructor team logo badge, tyre status, weather strip, and session statistics (Grid, Finish, Status, Best Lap, Race Pace, Top Speed).
6. **Lap Time History & Compound Filter** — Scroll past the driver banner to view race pace with compound-coloured markers, pit-out markers, and selected lap lines. Use the **compound multiselect filter** above the chart to show or hide specific compounds.
7. **Fuel-Adjusted Pace Analysis & Qualifying Simulation** ([Issue #9](https://github.com/parekhrohan21/fastf1_pitwall/issues/9)) — Correct pace for burning fuel loads with the interactive sensitivity slider. Expand the **Simulated Qualifying Leaderboard** to see the field ranked on fuel-corrected median pace.
8. **Tyre Stint Timeline & Pit Stop Summary Table** ([Issue #64](https://github.com/parekhrohan21/fastf1_pitwall/issues/64)) — Inspect Gantt-style horizontal stint bars and the detailed pit stop summary table showing stop lap, duration, and compound transitions.
9. **Pit Strategy & Undercut / Overcut Simulator** ([Issue #117](https://github.com/parekhrohan21/fastf1_pitwall/issues/117)) — In compare mode, automatically detect adjacent pit cycles (within ±3 laps), view pre/post pit gaps, and analyze undercut/overcut success on the dedicated gap chart.
10. **Tyre Degradation Modeling, Crossover Matrix & Fuel Burn Decoupler** ([Issue #81](https://github.com/parekhrohan21/fastf1_pitwall/issues/81), [Issue #137](https://github.com/parekhrohan21/fastf1_pitwall/issues/137), [Issue #151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)) — Review linear and quadratic regression models, toggle fuel burn decoupling to isolate True Mechanical Tyre Wear from car weight loss, adjust fuel burn sensitivity slider, inspect true vs raw degradation rates and fuel masking offset cards, and track thermal cliff lap predictions (+1.5 s pace drop) in the full-field urgency matrix (🟢 Safe / 🟡 Soon / 🔴 Critical / ✅ Past Cliff).
11. **Driver Consistency Index & Stint Pace Distribution** ([Issue #119](https://github.com/parekhrohan21/fastf1_pitwall/issues/119)) — Inspect driver lap time variance per stint, Consistency Score (0–100%), Clean Air Pace vs. Traffic Deficit (+s/lap), and interactive Plotly violin/boxplots.
12. **Track Temperature & Weather Impact Correlation** ([Issue #120](https://github.com/parekhrohan21/fastf1_pitwall/issues/120)) — Explore the dual-axis chart overlaying Track Temperature (°C) on driver pace, with auto-detected Rain Crossover Windows and Pearson pace-heat sensitivity scores.
13. **Braking Efficiency & Trail-Braking Zone Analysis** ([Issue #148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)) — Select any corner from the track selector to analyze entry braking dynamics. Inspect metric cards for Initial Braking Distance (m before apex), Peak Deceleration (G), Trail-Brake Release Point, and Brake-to-Throttle Transition Time (ms) alongside stacked Speed, Brake %, and Deceleration G-force profiles with later-braking advantage callouts.
14. **Gear Shift Strategy & RPM Power Band Optimization** ([Issue #149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)) — Analyze continuous engine RPM operating curves with interactive shift event markers (upshifts and gold diamond short-shift markers), compare percentage gear usage across Gears 1 to 8, and review metric cards for Total Shifts, Average Engine RPM, Tactical Short-Shifts, and Mean Upshift RPM with automated comparative summaries.
15. **Multi-Year Historical Lap Comparison** ([Issue #121](https://github.com/parekhrohan21/fastf1_pitwall/issues/121)) — In compare mode, select a second season and Grand Prix to compare cars across technical regulation eras on an interpolated 500-point distance grid, displaying speed profile overlays, continuous time delta curves, and era performance metrics.
16. **High-Resolution Telemetry & Dynamic Channel Filter** ([Issue #138](https://github.com/parekhrohan21/fastf1_pitwall/issues/138)) — Inspect telemetry waveforms. Use the **Telemetry Channels** multiselect dropdown to toggle specific channels (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) on/off and reorder them dynamically with proportional chart height scaling.
17. **Export Telemetry Data (CSV, Parquet, JSON)** ([Issue #139](https://github.com/parekhrohan21/fastf1_pitwall/issues/139)) — Expand the *Export Telemetry Data* panel beneath the telemetry charts to choose **CSV**, **Apache Parquet (`.parquet`)**, or **structured JSON (`.json`)** and download high-frequency channel data with sector splits and metadata.
18. **Speed Delta & Continuous Time Delta per Meter** ([Issue #116](https://github.com/parekhrohan21/fastf1_pitwall/issues/116)) — In compare mode, view the distance-aligned Speed Delta (km/h) and continuous Time Delta (seconds gained/lost per meter) charts to identify exact track areas of advantage.
19. **Fastest Laps Leaderboard** — Review the ranked table of every driver's best lap with gap to P1, tyre compound dot, lap number, and speed-trap top speed.
20. **Speed Trap & Intermediate Velocity Radar Breakdown** ([Issue #150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)) — Inspect the 4-axis polar radar profile comparing straight-line speeds (Speed Trap, Intermediate 1, Intermediate 2, Finish Line), benchmark aero efficiency across constructors and power units, and analyze the classified speed trap table with DRS boost deltas.
21. **Ideal Lap vs Actual Lap (Theoretical Best)** — Evaluate independent Sector 1, 2, and 3 best times, theoretical best lap, and Time Left on Table indicator cards alongside the ranked theoretical leaderboard.
22. **Intra-Team Teammate Battle & Qualifying Delta Matrix** ([Issue #152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)) — Inspect automated head-to-head comparisons across all 10 constructor teammate pairings. Toggle between Qualifying Lap Delta (s) and Race Pace Delta (s/lap), inspect sector split advantages (S1, S2, S3), evaluate closest battle and largest gap KPI cards, and examine the classified matrix table.
23. **Multi-Driver Grid Analysis & Heatmaps** ([Issue #85](https://github.com/parekhrohan21/fastf1_pitwall/issues/85)) — Select 3 to 20 drivers across the grid to render colour-coded heatmaps for **Sector Split Deltas**, **Lap-by-Lap Pace Heatmap**, and **Top Speed Matrix**.
24. **Gap to Leader Chart & Stat Cards** — Follow lap-by-lap time gaps to the race leader with pit markers (▼) and peak deficit stat cards.
25. **Race Control Incident Timeline & Flag Overlays** ([Issue #118](https://github.com/parekhrohan21/fastf1_pitwall/issues/118)) — Review safety car and flag zone bands overlaid on the pace charts, or search the filterable **Race Control Feed** table for all official session messages.
26. **Race Position Chart** — Track position changes across all race laps with an inverted Y-axis (P1 at top) for Race and Sprint sessions.
27. **Track Maps, Corner Analysis & Animated Race Replay** ([Issue #4](https://github.com/parekhrohan21/fastf1_pitwall/issues/4), [Issue #6](https://github.com/parekhrohan21/fastf1_pitwall/issues/6), [Issue #78](https://github.com/parekhrohan21/fastf1_pitwall/issues/78), [Issue #80](https://github.com/parekhrohan21/fastf1_pitwall/issues/80), [Issue #136](https://github.com/parekhrohan21/fastf1_pitwall/issues/136)) — Explore the Track Map tabs to view the speed heat-map, AWS-style mini-sector dominance map, driver input pedal traces, 4-subplot corner analysis (racing line, speed, steering angle, DRS), or run the full animated multi-car Race Replay.
28. **Constructors' Championship Standings & Official Session Classification** ([Issue #46](https://github.com/parekhrohan21/fastf1_pitwall/issues/46), [Issue #55](https://github.com/parekhrohan21/fastf1_pitwall/issues/55), [Issue #56](https://github.com/parekhrohan21/fastf1_pitwall/issues/56), [Issue #60](https://github.com/parekhrohan21/fastf1_pitwall/issues/60), [Issue #66](https://github.com/parekhrohan21/fastf1_pitwall/issues/66)) — Review official session classifications (with points, retirements, and pit stop counts) and season constructor standings dynamically loaded from the Ergast API.
29. **Real-Time Live Timing Mode** ([Issue #84](https://github.com/parekhrohan21/fastf1_pitwall/issues/84), [Issue #105](https://github.com/parekhrohan21/fastf1_pitwall/issues/105)) — Enable **🔴 Real-Time Live Timing Mode** in the sidebar during a live race weekend to record WebSocket packets and stream live timing and telemetry.
30. **Post-Race Debrief PDF Exporter** ([Issue #122](https://github.com/parekhrohan21/fastf1_pitwall/issues/122)) — Export printable broadcast-quality PDF reports capturing telemetry and strategy charts for offline sharing.


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
Before staging or committing any code, always run the pytest automated test suite to ensure that all data wrangling, telemetry export, channel filtering, and model fitting functions pass cleanly without regression:
```bash
python3.11 -m pytest tests/
```
All **95 unit and integration tests** across 16 test modules should pass cleanly.

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

All development on FastF1 Pitwall is tracked transparently via GitHub Issues and Pull Requests following a rigorous branch-and-PR workflow. Below is the complete chronological index of active roadmap issues and resolved issues cross-referenced by issue number.

### 🔮 Active Roadmap & Open Issues

| Issue | Title | Category | Scope & Planned Capability |
|:---:|---|---|---|
| **[#172](https://github.com/parekhrohan21/fastf1_pitwall/issues/172)** | `add DECISIONS.md to document Architectural choices and AI implementation decisions` | Architecture & Governance | Standardised Architecture Decision Records (ADRs) cataloguing key algorithmic choices, mathematical rationale, engineering trade-offs, and rejected alternatives. |
| **[#171](https://github.com/parekhrohan21/fastf1_pitwall/issues/171)** | `Automated Session Brag Video Generation via Latent Space Telemetry Embeddings` | Telemetry & Generative Video | Dimensionality reduction (PCA / manifold embedding) projecting 9D telemetry into fluid camera tracking reels, HUD telemetry overlays, and exportable MP4 brag videos. |
| **[#164](https://github.com/parekhrohan21/fastf1_pitwall/issues/164)** | `repository cleanup, remove redundant code and AI slop, and streamline file tree` | Maintenance / Refactor | Comprehensive repository audit to eliminate dead code, AI-generated scratch files, unused assets, and keep the repository lean and minimal. |
| **[#157](https://github.com/parekhrohan21/fastf1_pitwall/issues/157)** | `Clean Air vs Dirty Air Pace Impact & Overtaking Analysis` | Telemetry & Strategy | Aerodynamic wake analysis quantifying lap time penalty and tyre degradation rate when following within 1.5s vs clean air. |
| **[#156](https://github.com/parekhrohan21/fastf1_pitwall/issues/156)** | `Full Grand Prix Weekend Multi-Session Progression Tracker` | Grid Analytics | Cross-session pace evolution and setup refinement tracking across FP1, FP2, FP3, Qualifying, and Race sessions. |
| **[#155](https://github.com/parekhrohan21/fastf1_pitwall/issues/155)** | `Corner Exit Traction & Throttle Pick-Up Aggression Analysis` | Powertrain & Telemetry | Throttle pick-up rate (%/s), wheelspin/traction management, and exit acceleration profiles out of low-speed apexes. |
| **[#154](https://github.com/parekhrohan21/fastf1_pitwall/issues/154)** | `Track Evolution & Grip Improvement Ramp Index` | Track & Weather Analytics | Modeling track rubbering-in rates, grip ramp curves, and lap time reduction across qualifying sessions and race distances. |

---

### ✅ Resolved Issues Index

| Issue | Title | Category | Key Capability Delivered |
|:---:|---|---|---|
| **[#174](https://github.com/parekhrohan21/fastf1_pitwall/pull/174)** | `Synchronize README, DOCS.md, and AGENT.md with active roadmap issues (#171, #172)` | Documentation | Synchronized active roadmap tables, developer manual roadmap, and agent guidelines with newly opened GitHub issues (#171, #172). |
| **[#173](https://github.com/parekhrohan21/fastf1_pitwall/pull/173)** / **[#153](https://github.com/parekhrohan21/fastf1_pitwall/issues/153)** | `Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown` | Strategy & Pit Stops | Micro-sector decomposition of pit lane transit duration ($t_{\text{pit\_lane}}$), in-lap push delta ($\Delta t_{\text{in}}$), out-lap cold tyre warm-up ($\Delta t_{\text{out}}$), net pit loss, and full-field efficiency leaderboard. |
| **[#170](https://github.com/parekhrohan21/fastf1_pitwall/pull/170)** | `Update README and documentation files sync` | Documentation | Synchronized test counts and PR indices across user and developer documentation. |
| **[#169](https://github.com/parekhrohan21/fastf1_pitwall/pull/169)** / **[#152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)** | `Intra-Team Teammate Battle & Qualifying Delta Matrix` | Leaderboards & Analytics | Grid-wide teammate comparison across all 10 constructors with diverging qualifying & race pace delta bars, sector dominance (S1/S2/S3), and classified matrix table. |
| **[#168](https://github.com/parekhrohan21/fastf1_pitwall/pull/168)** | `Synchronize README, AGENT.md, and DOCS.md documentation` | Documentation | Comprehensive documentation and agentic guidelines audit synchronizing test counts, roadmap items, and architecture decision records. |
| **[#167](https://github.com/parekhrohan21/fastf1_pitwall/pull/167)** / **[#151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)** | `Fuel-Corrected Pure Tyre Degradation & Fuel Burn Decoupler` | Tyre Modeling & Strategy | Decoupling fuel mass burn-off (lap-by-lap weight reduction) from compound wear to isolate pure tyre degradation curves, unmasked thermal cliff laps, and fuel masking offsets. |
| **[#166](https://github.com/parekhrohan21/fastf1_pitwall/pull/166)** / **[#150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)** | `Speed Trap & Intermediate Velocity Radar Breakdown` | Telemetry / Radar | 4-axis polar velocity radar (`ST`, `I1`, `I2`, `FL`), constructor/engine benchmarks, classified Speed Trap Leaderboard, and DRS gain deltas. |
| **[#163](https://github.com/parekhrohan21/fastf1_pitwall/pull/163)** / **[#149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)** | `Gear Shift Strategy & RPM Power Band Optimization` | Powertrain Dynamics | Dual-subplot engine RPM curve with shift markers, gear usage distribution (Gears 1–8), and tactical short-shift detection. |
| **[#162](https://github.com/parekhrohan21/fastf1_pitwall/pull/162)** / **[#148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)** | `Braking Efficiency & Trail-Braking Zone Analysis` | Corner Dynamics | Longitudinal deceleration ($G$), braking distance, trail-braking release point, and 3-subplot braking dynamics profile. |
| **[#145](https://github.com/parekhrohan21/fastf1_pitwall/issues/145)** | `Fix NameError: _drv_labels1 is not defined on session load` | Bugfix & Reliability | Initialized driver dropdown label variables safely to prevent crashes during initial session loading. |
| **[#139](https://github.com/parekhrohan21/fastf1_pitwall/issues/139)** | `High-Throughput Telemetry Data Exporter (Parquet & JSON)` | Data Architecture | High-speed telemetry export supporting Apache Parquet (`.parquet`), structured JSON (`.json`), and CSV. |
| **[#138](https://github.com/parekhrohan21/fastf1_pitwall/issues/138)** | `Interactive Telemetry Channel Toggle & Custom Trace Filtering` | Telemetry Waveforms | Dynamic channel selector (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) with proportional chart height scaling. |
| **[#137](https://github.com/parekhrohan21/fastf1_pitwall/issues/137)** | `Predictive Tyre Degradation & Thermal Crossover Matrix` | Tyre Modeling | Quadratic polynomial regression, thermal cliff lap prediction (+1.5s), and full-field urgency matrix (🟢/🟡/🔴/✅). |
| **[#136](https://github.com/parekhrohan21/fastf1_pitwall/issues/136)** | `Driver Steering & DRS Telemetry Subplots in Corner Analysis` | Corner Analytics | Expanded corner figure into 4 subplots adding Steering Angle (°) and DRS status profiles alongside Racing Line and Speed. |
| **[#130](https://github.com/parekhrohan21/fastf1_pitwall/issues/130)** | `Fix style command showing up as raw text in UI` | Bugfix & UI | Patched CSS style injection strings escaping into visible raw text in Streamlit frontend. |
| **[#124](https://github.com/parekhrohan21/fastf1_pitwall/issues/124)** | `Fix NameError: components is not defined in styles.py` | Bugfix & Reliability | Resolved undefined module reference in the stylesheet generator. |
| **[#123](https://github.com/parekhrohan21/fastf1_pitwall/issues/123)** | `Document code review artifact process in README and AGENT.md` | Documentation | Standardized formal code review checklist and artifact documentation workflow (`code_review_issue_<num>.md`). |
| **[#122](https://github.com/parekhrohan21/fastf1_pitwall/issues/122)** | `Printable PDF / High-Resolution PNG Post-Race Debrief Exporter` | Reporting & PDF | Broadcast-quality PDF debrief exporter using `fpdf2` and `kaleido` static figure rasterization. |
| **[#121](https://github.com/parekhrohan21/fastf1_pitwall/issues/121)** | `Multi-Year Historical Lap Comparison (e.g. 2024 vs 2020)` | Historical Telemetry | Multi-regulation era comparison on 500-point distance grid with speed overlay and era delta metrics. |
| **[#120](https://github.com/parekhrohan21/fastf1_pitwall/issues/120)** | `Track Temperature & Weather Impact Correlation` | Weather Analytics | Dual-axis weather correlation chart, rain crossover lap detection, and Pearson pace-heat sensitivity ($r$). |
| **[#119](https://github.com/parekhrohan21/fastf1_pitwall/issues/119)** | `Driver Consistency Index & Stint Pace Distribution` | Pace Distribution | Consistency score (0–100%), lap time std dev, clean air vs traffic deficit, and Plotly violin/boxplots. |
| **[#118](https://github.com/parekhrohan21/fastf1_pitwall/issues/118)** | `Race Control Incident Timeline & Flag Overlays` | Race Control | Safety car and flag period overlays on pace charts and filterable Race Control Feed table. |
| **[#117](https://github.com/parekhrohan21/fastf1_pitwall/issues/117)** | `Pit Strategy & Undercut / Overcut Simulator` | Strategy Simulation | Undercut/overcut detector for adjacent pit cycles (±3 laps) with pre/post gap tracking. |
| **[#116](https://github.com/parekhrohan21/fastf1_pitwall/issues/116)** | `Continuous Time Delta per Meter Chart (Delta t vs Distance)` | Telemetry Comparison | Distance-based continuous time delta curve ($\Delta t$ vs distance) using `fastf1.utils.delta_time`. |
| **[#112](https://github.com/parekhrohan21/fastf1_pitwall/issues/112)** | `Dark mode functionality & theme injection in app.py` | UI & Theming | Seamless toggle between midnight dark mode and light mode with early CSS injection. |
| **[#109](https://github.com/parekhrohan21/fastf1_pitwall/issues/109)** | `Fix double period and state reset in Session Loading Error` | Bugfix & Reliability | Clean session state clearing and formatted error banners on failed session downloads. |
| **[#107](https://github.com/parekhrohan21/fastf1_pitwall/issues/107)** | `Update issue list chronology in developer manual` | Documentation | Chronological synchronization of developer documentation and changelog entries. |
| **[#105](https://github.com/parekhrohan21/fastf1_pitwall/issues/105)** | `Update README documentation for Live Timing Mode & troubleshooting` | Documentation | Live timing documentation, connection diagnostics guidance, and British English localization. |
| **[#102](https://github.com/parekhrohan21/fastf1_pitwall/issues/102)** | `Add Solved Issues Changelog & Summary List to Documentation` | Documentation | Added Section 18 to DOCS.md logging all historical closed issues with 1-line explanations. |
| **[#100](https://github.com/parekhrohan21/fastf1_pitwall/issues/100)** | `Fix NameError _PATCH_STATUS is not defined in app.py` | Bugfix & Reliability | Restored missing connection diagnostics status variables in sidebar. |
| **[#85](https://github.com/parekhrohan21/fastf1_pitwall/issues/85)** | `Multi-Driver Grid Analysis & Heatmaps` | Grid Analytics | Full grid matrix (3–20 drivers) with Sector Split Deltas, Lap-by-Lap Pace, and Top Speed heatmaps. |
| **[#84](https://github.com/parekhrohan21/fastf1_pitwall/issues/84)** | `Real-Time Live Timing Mode via FastF1 SignalR client` | Live Timing | Real-time SignalR WebSocket streaming, live packet recording, and auto-refreshing timing tables. |
| **[#83](https://github.com/parekhrohan21/fastf1_pitwall/issues/83)** | `Introduce pytest automated testing suite for data wrangling` | Automated Testing | Comprehensive automated test suite with mock fixtures and CI pipeline validation. |
| **[#82](https://github.com/parekhrohan21/fastf1_pitwall/issues/82)** | `Refactor monolithic app.py into modular directory structure` | Architecture | Modularized monolith into `src/data/`, `src/charts/`, and `src/ui/`. |
| **[#81](https://github.com/parekhrohan21/fastf1_pitwall/issues/81)** | `Tyre Degradation Modeling and Pace Drop-off` | Tyre Modeling | OLS linear regression stint degradation scatter plots and pace drop-off metrics. |
| **[#80](https://github.com/parekhrohan21/fastf1_pitwall/issues/80)** | `Corner-by-Corner Analysis (Braking & Apex telemetry)` | Corner Analytics | Interactive apex corner analysis with minimum speed and braking points. |
| **[#78](https://github.com/parekhrohan21/fastf1_pitwall/issues/78)** | `AWS-Style Mini-Sector Speed Dominance Map` | Track Analytics | Track segmented into 25 micro-sectors coloured by fastest driver pace dominance. |
| **[#76](https://github.com/parekhrohan21/fastf1_pitwall/issues/76)** | `Update documentation files for recent features and footer sync` | Documentation | Documentation synchronization across README.md, DOCS.md, and AGENT.md. |
| **[#75](https://github.com/parekhrohan21/fastf1_pitwall/issues/75)** | `Sync bottom footer across all early exit states and pages` | Bugfix & UI | Bottom footer synchronization across all error boundaries and early exit branches. |
| **[#73](https://github.com/parekhrohan21/fastf1_pitwall/issues/73)** | `Adjust telemetry graphs to fit mobile screens dynamically` | Responsive UI | Dynamic mobile viewport scaling for Matplotlib telemetry charts. |
| **[#72](https://github.com/parekhrohan21/fastf1_pitwall/issues/72)** | `Add bottom footer with made proudly in great britain` | Branding & UI | Added styled footer displaying "Made proudly in Great Britain 🇬🇧". |
| **[#68](https://github.com/parekhrohan21/fastf1_pitwall/issues/68)** | `Clean up unused helper functions and redundant code comments` | Code Hygiene | Cleaned dead code, unused helpers, and consolidated compound colour definitions. |
| **[#66](https://github.com/parekhrohan21/fastf1_pitwall/issues/66)** | `Driver name and abbreviation missing in official classification table` | Bugfix & Leaderboards | Resolved missing driver names and constructor lookups in session classification. |
| **[#64](https://github.com/parekhrohan21/fastf1_pitwall/issues/64)** | `Add number of pit stops to the official session classification table` | Leaderboards | Added cumulative pit stop counts (`Stops`) to official classification table. |
| **[#60](https://github.com/parekhrohan21/fastf1_pitwall/issues/60)** | `Show driver's name alongside driver number in official classification table` | Leaderboards & UI | Formatted driver numbers into `ABR · Full Name` display labels. |
| **[#56](https://github.com/parekhrohan21/fastf1_pitwall/issues/56)** | `Add constructors championship standings table` | Leaderboards | Ergast API constructors' championship standings table with team-colour accents. |
| **[#55](https://github.com/parekhrohan21/fastf1_pitwall/issues/55)** | `Add drivers championship points column to official classification table` | Leaderboards | Added season championship points (`CH Points`) to session classification. |
| **[#54](https://github.com/parekhrohan21/fastf1_pitwall/issues/54)** | `Set default selected driver to the race/session winner` | UX Defaults | Automatically selects session winner (or fastest driver) as default driver. |
| **[#53](https://github.com/parekhrohan21/fastf1_pitwall/issues/53)** | `Set default season and session to the most recent ones` | UX Defaults | Automatically defaults season, event, and session to most recent completed Grand Prix. |
| **[#49](https://github.com/parekhrohan21/fastf1_pitwall/issues/49)** | `Track map fails to display when telemetry/position data is missing` | Bugfix & Reliability | Graceful fallback handling for missing car position coordinates in track maps. |
| **[#48](https://github.com/parekhrohan21/fastf1_pitwall/issues/48)** | `UnhashableParamError on results_df in _build_final_classification` | Bugfix & Caching | Standardized FastF1 DataFrame caching to prevent `@st.cache_data` unhashable errors. |
| **[#46](https://github.com/parekhrohan21/fastf1_pitwall/issues/46)** | `Add a final classification leaderboard at the end of the session` | Leaderboards | Complete official session classification covering Race, Sprint, Qualifying, and Practice. |
| **[#44](https://github.com/parekhrohan21/fastf1_pitwall/issues/44)** | `Side navigation is not perfectly hidden in mobile view` | Bugfix & Mobile | Fixed CSS transform rules to allow sidebar to collapse cleanly on mobile. |
| **[#42](https://github.com/parekhrohan21/fastf1_pitwall/issues/42)** | `FastF1 live timing stream is not supported for active sessions` | Bugfix & Reliability | Added fallback handling for ongoing/unfinalized sessions. |
| **[#40](https://github.com/parekhrohan21/fastf1_pitwall/issues/40)** | `Graphs fail to load due to requests_cache AttributeError` | Bugfix & Networking | Added MockRaw transport wrappers to fix requests_cache SQLite serialization under proxy. |
| **[#38](https://github.com/parekhrohan21/fastf1_pitwall/issues/38)** | `Optimize mobile responsive layout for vertical screens` | UI & Mobile | Responsive CSS layout optimization for vertical mobile screens. |
| **[#36](https://github.com/parekhrohan21/fastf1_pitwall/issues/36)** | `FastF1 data loading fails due to CloudFront 403 blocks` | Networking & Bypass | Implemented `curl_cffi` TLS impersonation to bypass CloudFront bot blocks. |
| **[#33](https://github.com/parekhrohan21/fastf1_pitwall/issues/33)** | `curl_cffi patch inactive on Streamlit Cloud due to IS_CLOUD failure` | Networking & Bypass | Made `curl_cffi` HTTPAdapter patch unconditional for all F1 domains. |
| **[#30](https://github.com/parekhrohan21/fastf1_pitwall/issues/30)** | `curl_cffi monkey-patch intercepts wrong requests layer` | Networking & Bypass | Low-level `HTTPAdapter.send` interceptor to guarantee bypass across all session requests. |
| **[#28](https://github.com/parekhrohan21/fastf1_pitwall/issues/28)** | `UnhashableParamError on session_obj in _build_gap_data` | Bugfix & Caching | Replaced session object cache keys with immutable string identifiers. |
| **[#26](https://github.com/parekhrohan21/fastf1_pitwall/issues/26)** | `Resolve F1 Timing API Cloudflare block on Streamlit Cloud` | Networking & Bypass | Added fallback user-agent headers and mirror URL rotation. |
| **[#25](https://github.com/parekhrohan21/fastf1_pitwall/issues/25)** | `Bypass anti-bot filters on mirror by setting browser headers` | Networking & Bypass | Chrome 124 browser header injection for mirror endpoints. |
| **[#23](https://github.com/parekhrohan21/fastf1_pitwall/issues/23)** | `Override fastf1._api.base_url to point to livetiming mirror` | Networking & Bypass | Automatic failover to FastF1 livetiming mirror URLs. |
| **[#21](https://github.com/parekhrohan21/fastf1_pitwall/issues/21)** | `Bypass Cloudflare bot-block on Streamlit Cloud` | Networking & Bypass | Configured mirror endpoints for live timing data requests. |
| **[#19](https://github.com/parekhrohan21/fastf1_pitwall/issues/19)** | `Implement progressive fallback loading inside load_session` | Reliability & Data | Multi-stage fallback loading (full → no messages → no weather → laps only). |
| **[#17](https://github.com/parekhrohan21/fastf1_pitwall/issues/17)** | `Auto-clear cache when FastF1 session load raises data not loaded yet` | Bugfix & Caching | Auto-clearing corrupt cache entries when FastF1 raises data load exceptions. |
| **[#15](https://github.com/parekhrohan21/fastf1_pitwall/issues/15)** | `Session Data Unavailable: FastF1 could not load lap data` | UX & Reliability | User-friendly error messaging and automatic cache reset controls. |
| **[#13](https://github.com/parekhrohan21/fastf1_pitwall/issues/13)** | `Dynamically populate session dropdown based on event schedule` | UX & Data | Dynamic session list populated from official Grand Prix weekend schedules. |
| **[#11](https://github.com/parekhrohan21/fastf1_pitwall/issues/11)** | `Improve mobile and vertical phone layout compatibility` | UI & Mobile | Mobile viewport meta tags and flexible container styling. |
| **[#10](https://github.com/parekhrohan21/fastf1_pitwall/issues/10)** | `Replace blob URL manifest with proper installable PWA manifest` | PWA & Mobile | Embedded base64 icons and installable W3C Web Manifest. |
| **[#9](https://github.com/parekhrohan21/fastf1_pitwall/issues/9)** | `Fuel-corrected qualifying sim` | Pace Modeling | Interactive fuel-adjusted pace slider and Simulated Qualifying Leaderboard. |
| **[#8](https://github.com/parekhrohan21/fastf1_pitwall/issues/8)** | `Multi-session comparison` | Telemetry & Comparison | Multi-session comparison mode enabling head-to-head driver telemetry. |
| **[#6](https://github.com/parekhrohan21/fastf1_pitwall/issues/6)** | `Driver Input Track Map` | Track Analytics | Track map overlays for driver pedal inputs (Throttle, Brake, Gear). |
| **[#4](https://github.com/parekhrohan21/fastf1_pitwall/issues/4)** | `Sector Mini-map Colouring` | Track Analytics | Interactive track map with speed heat-map coloring. |
| **[#1](https://github.com/parekhrohan21/fastf1_pitwall/issues/1)** | `Adding historical team colours` | Branding & Theming | Accurate historical team hex colours spanning 2018 to the present. |

For detailed architectural specifications, code deep-dives, and technical changelogs for every pull request, consult the developer manual:
👉 **[DOCS.md — Section 18: Solved Issues & Changelog](DOCS.md#18-solved-issues--changelog)**

---

## ⚖️ Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
