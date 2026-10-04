# 🏎 Pit Wall — F1 Telemetry Dashboard

A professional-grade **Streamlit + FastF1** dashboard with a dynamic, data-driven styling engine for exploring lap telemetry, strategic pacing, and performance analytics from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **6-channel high-frequency telemetry** alongside driver headshots, lap time history, fuel-adjusted pace, tyre stint timelines, corner exit traction aggression, track evolution grip ramp indexes, pit lane transit loss breakdowns, intra-team teammate battles, braking dynamics, gear shift strategies, speed trap velocity radars, fastest laps leaderboards, interactive track maps, full race replays, and detailed lap/weather summaries.

**Quick Navigation:** [🚀 Quick Start](#-quick-start) · [🛠 Prerequisites & Requirements](#-prerequisites--system-requirements) · [⚙️ Configuration](#%EF%B8%8F-configuration) · [✨ Key Features](#-key-features) · [📚 How to Use the Dashboard](#-how-to-use-the-dashboard) · [📁 Project Structure](#-project-structure) · [🧑‍💻 Development Workflow](#-contributing--development-workflow) · [⚠️ Troubleshooting](#%EF%B8%8F-known-limitations--troubleshooting) · [📜 Roadmap & Changelog](#-solved-issues--changelog)

---

## 🚀 Quick Start

You need **Python 3.11+** (Python 3.11 recommended, tested up to 3.12) or Docker.

### 1. Run Locally (Without Docker)

```bash
# Clone the repository
git clone https://github.com/parekhrohan21/fastf1_pitwall.git
cd fastf1_pitwall

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install pinned dependencies
pip install -r requirements.txt

# Launch the Streamlit dashboard
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

### 2. Run with Docker

The repository includes a production-ready [Dockerfile](Dockerfile) pre-configured with Python 3.11-slim, system build tools (`gcc`), and persistent FastF1 disk caching. Detailed build and execution commands are also documented directly inside the `Dockerfile`.

```bash
# Build the container image from the repository root
docker build -t fastf1_pitwall .

# Run the container with local cache volume mounting
docker run --rm -p 8501:8501 \
  -v "$PWD/cache:/app/cache" \
  --name fastf1-pitwall \
  fastf1_pitwall
```

Open **http://localhost:8501** in your browser. Mounting `./cache` preserves downloaded telemetry across container restarts, preventing redundant network requests.

---

### 3. Run in GitHub Codespaces (Zero Local Install)

Click **Code → Codespaces → Create codespace on main** on GitHub. The pre-configured Dev Container ([.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)) installs all system and Python dependencies, mounts persistent storage, and forwards port `8501` to an in-browser live preview. The identical container configuration also works locally via VS Code's **Dev Containers: Reopen in Container**.

---

### 4. Install as a Mobile App (PWA)

Host the dashboard on Streamlit Community Cloud or any cloud VM to install it as a standalone Progressive Web App (PWA) on your mobile device:

- **iOS Safari**: Tap the **Share** icon → scroll down and tap **Add to Home Screen**.
- **Android Chrome**: Tap the **Triple Dot (⋮)** menu → tap **Add to Home screen** (or **Install app**).

The dashboard launches in standalone app display mode with a custom 🏎 Pit Wall icon and responsive mobile-optimized layouts.

---

## 🛠 Prerequisites & System Requirements

### System & Environment Requirements

| Requirement | Local Execution | Docker Container |
|---|---|---|
| **Operating System** | macOS (Apple Silicon / Intel), Linux (Ubuntu/Debian/Fedora), Windows (WSL2 recommended) | Docker-supported host OS |
| **Runtime** | **Python 3.11+** (3.11 recommended, tested up to 3.12) | **Docker Desktop** (macOS/Windows) or **Docker Engine ≥ 20.10** |
| **Package Manager** | `pip` (or `venv`, `uv`, `conda`) | Pre-packaged in container image |
| **Memory (RAM)** | **4 GB minimum**, **8 GB+ recommended** for multi-driver animated replays | 4 GB memory allocated to Docker daemon |
| **Disk Space** | ~500 MB for Python environment + ~50–100 MB per cached Grand Prix session | ~1.5 GB for Docker image + local `./cache` volume |
| **Network** | Outbound HTTPS access to `livetiming.formula1.com:443` and `api.jolpi.ca:443` | Outbound HTTPS access to F1 timing APIs |

### Core Python Dependencies Matrix

The application is built on a modern, high-performance telemetry analytics stack:

| Package | Minimum Version | Purpose & Architectural Role |
|---|---|---|
| **`streamlit`** | `≥ 1.44.0` | Frontend dashboard framework using modern `width='stretch'` responsive layout API and custom theme injection. |
| **`fastf1`** | `≥ 3.3.0` | Core F1 timing, telemetry waveform, circuit layout, and Ergast integration data engine. |
| **`pandas`** | `≥ 2.2.0` | High-frequency telemetry dataframe wrangling, lap filtering, and timeseries aggregation. |
| **`numpy`** | `≥ 1.26.0` | Deceleration ($G$), polynomial regressions, distance grids, and statistical operations. |
| **`plotly`** | `≥ 5.18.0` | Interactive charts (lap time histories, stint Gantt bars, delta graphs, corner analysis, radar profiles). |
| **`matplotlib`** | `≥ 3.8.0` | Static 6-channel high-frequency telemetry waveform visualizations and speed delta overlays. |
| **`curl-cffi`** | `≥ 0.5.10` | TLS handshake browser impersonation (`chrome124`) to bypass F1 CloudFront / Cloudflare anti-bot blocks. |
| **`pyarrow`** | `≥ 14.0.0` | High-throughput columnar Apache Parquet (`.parquet`) telemetry file exporter. |
| **`fpdf2`** & **`Pillow`** | `≥ 2.7.5` / `≥ 10.0.0` | Broadcast-quality Post-Race Debrief PDF generation engine with high-DPI figure captures. |
| **`kaleido`** | `≥ 0.2.1` | Static image rendering engine for Plotly figures during report compilation. |
| **`pytest`** & **`pytest-mock`** | `≥ 8.0.0` / `≥ 3.12.0` | Automated test suite execution (**116 unit/integration tests across 18 dedicated modules**). |

> [!IMPORTANT]
> **Streamlit Version Warning**: The dashboard strictly utilizes Streamlit's modern `width='stretch'` / `width='content'` parameterization. Running on older Streamlit versions (< 1.44.0) will cause deprecation warnings or layout rendering errors. Always use the pinned dependencies in `requirements.txt`.

---

## ⚙️ Configuration

There is nothing required to configure for standard local usage. Optional environment variables:

| Setting | Configuration Location | Purpose & Practical Usage |
|---|---|---|
| `F1_PROXY` | Environment variable or `.streamlit/secrets.toml` (`http://user:pass@proxy:port`) | Routes FastF1 and Ergast HTTP/HTTPS requests through an external proxy. Use behind restrictive corporate firewalls or if CloudFront blocks your IP. |

FastF1 session telemetry is automatically cached in `./cache`, which is created on first run and gitignored. Delete this folder to force a completely fresh re-download of session telemetry.

---

## ✨ Key Features

Issue numbers link directly to the corresponding GitHub issue and Pull Request. Technical implementation details are documented in [DOCS.md](DOCS.md).

### 🏎 Lap Telemetry & Head-to-Head Dynamics

- **6-Channel High-Frequency Telemetry & Filtering** ([Issue #138](https://github.com/parekhrohan21/fastf1_pitwall/issues/138)): View synchronized or separated traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS, with an interactive multiselect toggle to filter and reorder channels on the fly with dynamic height scaling.
- **Head-to-Head Speed & Continuous Time Delta per Meter** ([Issue #116](https://github.com/parekhrohan21/fastf1_pitwall/issues/116)): In compare mode, overlays primary and secondary drivers alongside a Speed Delta (Δ km/h) chart and a distance-aligned Continuous Time Delta (Δ seconds vs Distance) chart showing exactly where time is gained or lost across every meter of the lap.
- **High-Throughput Telemetry Data Exporter (CSV, Parquet, JSON)** ([Issue #139](https://github.com/parekhrohan21/fastf1_pitwall/issues/139)): A collapsible export panel beneath the telemetry charts with a dynamic format selector for **CSV**, **Apache Parquet (`.parquet`)**, and **structured JSON (`.json`)**. The exported file includes high-frequency channels, X/Y/Z circuit coordinates, Sector 1/2/3 split times (seconds), and lap metadata.
- **Ideal Lap vs Actual Lap (Theoretical Best)**: Independent Sector 1, 2, and 3 theoretical best extraction with Time Left on Table indicator cards and a ranked grid-wide theoretical best leaderboard.
- **Multi-Year Historical Lap Comparison** ([Issue #121](https://github.com/parekhrohan21/fastf1_pitwall/issues/121)): Compare laps for the same circuit across different technical regulation eras (e.g. 2024 ground-effect vs 2020 high-downforce era) on an interpolated 500-point distance grid, displaying speed profile overlays, continuous time delta curves, and era performance metrics.

### 🎯 Corner Dynamics & Powertrain Strategy

- **Corner Exit Traction & Throttle Pick-Up Aggression Analysis** ([Issue #155](https://github.com/parekhrohan21/fastf1_pitwall/issues/155)): High-precision corner exit acceleration telemetry slicing a $[d_{\text{apex}} - 60\,\text{m}, d_{\text{apex}} + 260\,\text{m}]$ window around circuit turns. Extracts Distance to Initial Throttle ($d_{\text{init}}$), Distance to 100% Full Throttle ($d_{\text{full}}$), Spatial Throttle Ramp Rate (%/m), Temporal Throttle Gradient (%/s), Throttle Hesitations/Lifts ($\ge 3.5\%$ drops from running maximum envelope indicating wheelspin management), Oversteer Corrections Count ($d(\text{Steering})/dt \cdot \text{sign} < -2.5^\circ$), Peak Exit Acceleration ($G$), Exit Speed at 100m post-apex, and composite Traction Aggression Score (0–100). Flat-out corners (throttle $\ge 85\%$ within $\pm 10$m of apex) are automatically flagged as "Flat out" rather than erroneously scored. Visualised across a stacked 3-row Plotly figure and 4 KPI cards with automated driver advantage callouts.
- **Track Evolution & Grip Improvement Ramp Index** ([Issue #154](https://github.com/parekhrohan21/fastf1_pitwall/issues/154)): Models circuit rubbering-in across Practice and Qualifying by treating the entire field as an evolving sensor. Applies driver fixed-effects pace normalisation ($t_{\text{adj}} = t_{\text{lap}} - \tilde{t}_{\text{driver}} + \tilde{t}_{\text{field}}$) to eliminate qualifying knockout composition bias. Employs Theil-Sen seeded robust regression (`_theil_sen_estimate`) with MAD residual trimming (`_robust_linear_fit`, 1 ms scale floor, 0.5 minimum inlier fraction) to compute Track Ramp Rate (ms/min), Total Track Grip Gain (s), degree-2 quadratic saturation curves, and track temperature correlation profiles, accompanied by a 4-state condition classification banner.
- **Braking Efficiency & Trail-Braking Zone Analysis** ([Issue #148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)): High-precision braking telemetry around circuit turn apexes. Extracts longitudinal deceleration ($G$-force = $-\Delta v / (\Delta t \cdot 9.81)$), initial braking distance (m before apex), peak deceleration ($G$), trail-braking release point, trail-braking zone length, and brake-to-throttle transition time (ms), rendered across a stacked 3-subplot Plotly figure with comparative advantage callouts.
- **Gear Shift Strategy & RPM Power Band Optimization** ([Issue #149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)): Extracts engine RPM, gear selection, throttle application, and track distance to detect every upshift and downshift. Identifies tactical short-shifts (< 11,000 RPM under > 60% throttle) and redline shift events (≥ 11,800 RPM). Renders a dual-subplot Plotly figure with an RPM operating curve, interactive shift event markers, and horizontal percentage gear usage breakdown (Gears 1 through 8), accompanied by comparative shift count and RPM metrics cards.
- **Speed Trap & Intermediate Velocity Radar Breakdown** ([Issue #150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)): Grid-wide speed trap and intermediate velocity analytics using official timing sensors (`SpeedST`, `SpeedI1`, `SpeedI2`, `SpeedFL`). Extracts maximum velocities, calculates DRS aerodynamic efficiency deltas, and aggregates top speeds by constructor and Power Unit manufacturer (Ferrari, Mercedes, Red Bull Powertrains, Renault). Renders an interactive 4-axis polar radar profile (`build_speed_trap_radar_fig`), grouped constructor/engine benchmark bar charts (`build_speed_trap_bar_fig`), and a classified Speed Trap Leaderboard table with top-speed advantage metric cards.
- **Corner-by-Corner Analysis with Steering & DRS Telemetry** ([Issue #80](https://github.com/parekhrohan21/fastf1_pitwall/issues/80), [Issue #136](https://github.com/parekhrohan21/fastf1_pitwall/issues/136)): An advanced performance tab that fetches track layout coordinates via FastF1 to let you select a corner (e.g. Turn 1). Automatically calculates apex speed, braking points, max steering angle (°), and DRS activation status, plotting racing line overlays, speed profiles, steering wheel input curves, and DRS channel subplots in a 4-trace layout.

### ⏱ Pace, Tyres & Race Strategy

- **Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown** ([Issue #153](https://github.com/parekhrohan21/fastf1_pitwall/issues/153)): Deep-dive telemetry breakdown of pit lane time losses isolating pit lane speed-limiter transit duration ($t_{\text{pit\_lane}} = \text{PitOutTime} - \text{PitInTime}$), in-lap push delta against clean-air baseline flyer pace ($\Delta t_{\text{in}} = t_{\text{in}} - t_{\text{baseline}}$), out-lap cold tyre warm-up performance ($\Delta t_{\text{out}} = t_{\text{out}} - t_{\text{baseline}}$), net pit loss, and sector-by-sector warm-up deltas ($S_1, S_2, S_3$). Visualised via an interactive stacked horizontal bar chart (`build_pit_loss_fig`), 4 summary KPI cards (*Fastest Pit Lane Transit*, *Best In-Lap Push Delta*, *Best Out-Lap Warm-up*, *Grid Median Pit Loss*), Head-to-Head sector warm-up cards, and a full-field classified efficiency leaderboard table.
- **Intra-Team Teammate Battle & Qualifying Delta Matrix** ([Issue #152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)): Automated teammate head-to-head comparison analytics across all constructors for Qualifying and Race sessions. Renders a grid-wide horizontal diverging bar chart of teammate gaps, sector split advantages (S1, S2, S3), clean-air median race pace deltas, and an interactive classified matrix with top KPI cards for closest battle, largest delta, and grid median gap.
- **Fuel-Corrected Pure Tyre Degradation & Fuel Burn Decoupler** ([Issue #81](https://github.com/parekhrohan21/fastf1_pitwall/issues/81), [Issue #137](https://github.com/parekhrohan21/fastf1_pitwall/issues/137), [Issue #151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)): Calculates OLS linear and quadratic regressions on valid flyer laps per stint. Features an interactive **Fuel Burn Decoupler** that removes artificial lap time gains from fuel mass reduction (~0.035 s/lap) to compute True Mechanical Tyre Wear ($t_{\text{corrected}} = t_{\text{lap}} - \alpha \cdot (\text{TotalLaps} - \text{LapNumber})$). Plots scatter points of tyre age vs lap time with regression trendlines and dashed quadratic thermal curves. Automatically estimates a **Cliff Lap** (pace degrades ≥ 1.5 s above baseline) and a **Pit Window** (cliff ± 3 laps), displayed in a full-field **Tyre Life & Crossover Prediction Matrix** table with urgency badges (🟢 Safe / 🟡 Soon / 🔴 Critical / ✅ Past Cliff).
- **Pit Strategy & Undercut / Overcut Simulator** ([Issue #117](https://github.com/parekhrohan21/fastf1_pitwall/issues/117)): An automated strategic analysis engine in compare mode that identifies adjacent pit stops (within ±3 laps) between two drivers, isolates the pit window, calculates the time gap before and after the pit cycle, and plots a lap-by-lap gap chart with vertical pit markers and outcome status (Successful / Failed undercut/overcut).
- **Driver Consistency Index & Stint Pace Distribution** ([Issue #119](https://github.com/parekhrohan21/fastf1_pitwall/issues/119)): Calculates driver lap time variance per stint after filtering out in-laps, out-laps, and Safety Car / Red Flag periods. Evaluates a **Consistency Score** (0–100%), Lap Time Std Dev (±s), Clean Air Pace vs. **Traffic Deficit** (+s/lap), and renders interactive Plotly Violin and Boxplot distributions with raw lap points alongside a stint breakdown table.
- **Fuel-Adjusted Pace Analysis**: Removes fuel penalty per lap to reveal true single-lap pace with an interactive sensitivity slider and Simulated Qualifying Leaderboard.
- **Tyre Stint Timeline & Pit Stop Summary**: Gantt-style horizontal bar chart showing each driver's complete tyre strategy at a glance with compound-coloured bars, fresh/used indicators, and detailed pit stop tables.

### 🗺 Track Maps, Replays & Race Overview

- **Interactive Speed & Mini-Sector Dominance Track Maps** ([Issue #4](https://github.com/parekhrohan21/fastf1_pitwall/issues/4), [Issue #78](https://github.com/parekhrohan21/fastf1_pitwall/issues/78)): A Plotly track map coloured by speed with secondary driver path overlays. In Compare Mode, the track is dynamically divided into 25 micro-sectors coloured by the driver who carried the highest average speed through that exact section.
- **Driver Input Track Map** ([Issue #6](https://github.com/parekhrohan21/fastf1_pitwall/issues/6)): Visualises driver foot pedal telemetry directly onto the circuit layout (Green for 100% Throttle, Red for Braking, Yellow for Coasting), with side-by-side comparison support.
- **Animated Race Replay**: Watch a full animated replay of the session plotting all cars on track with a scrubbable timeline.
- **Track Temperature & Weather Impact Correlation** ([Issue #120](https://github.com/parekhrohan21/fastf1_pitwall/issues/120)): Correlates track/air temperatures, rainfall intensity, and humidity with lap time drop-offs. Renders a dual-axis chart overlaying Track Temperature (°C) on driver pace with auto-detected **Rain Crossover Windows** and Pearson pace-heat sensitivity scores.
- **Multi-Driver Grid Analysis & Heatmaps** ([Issue #85](https://github.com/parekhrohan21/fastf1_pitwall/issues/85)): Grid-wide analytical matrix allowing users to select 3 to 20 drivers across the field. Renders interactive Plotly heatmaps for **Sector Split Deltas**, **Lap-by-Lap Pace Heatmap**, and **Top Speed Matrix**.
- **Race Control Incident Timeline & Flag Overlays** ([Issue #118](https://github.com/parekhrohan21/fastf1_pitwall/issues/118)): Overlays semi-transparent Safety Car 🟠, VSC 🟡, Red Flag 🔴, and Yellow Flag 🟡 zone bands on pace and gap charts, accompanied by a searchable and filterable **Race Control Feed** table.
- **Gap to Leader & Race Position Charts**: Lap-by-lap time gap chart to race leader with pit markers (▼) and an inverted Y-axis position tracking chart.
- **Official Classification & Championship Standings**: Complete official session classifications (with points, retirements, and pit stop counts) and season constructor standings dynamically loaded from the Ergast API.
- **Driver Headshots in Summary Banner**: The driver banner automatically fetches official F1 portrait photos as circular headshots with team-coloured ring borders.

### 📱 Application Platform & Infrastructure

- **Real-Time Live Timing Mode** ([Issue #84](https://github.com/parekhrohan21/fastf1_pitwall/issues/84)): Stream live timing and telemetry via FastF1 SignalR WebSocket client with disk packet recording and auto-refresh intervals during active F1 race weekends.
- **Post-Race Debrief PDF Exporter** ([Issue #122](https://github.com/parekhrohan21/fastf1_pitwall/issues/122)): Capture the entire visual state of your analysis (Lap Time History, Tyre Stints, Gap to Leader, Position History) and export it as a clean, broadcast-style PDF report for easy offline sharing.
- **Dynamic Constructor Theming & Light/Dark Mode** ([Issue #112](https://github.com/parekhrohan21/fastf1_pitwall/issues/112)): Automatically recolours cards, banners, and charts to match team liveries, with an instant toggle between midnight dark mode and light mode.
- **Connection Diagnostics & Anti-Bot Bypass** ([Issue #100](https://github.com/parekhrohan21/fastf1_pitwall/issues/100), [Issue #105](https://github.com/parekhrohan21/fastf1_pitwall/issues/105)): TLS impersonation (`curl_cffi`) and sidebar diagnostics to bypass CloudFront/Cloudflare 403 blocks.
- **Modular Architecture & Code Hygiene** ([Issue #82](https://github.com/parekhrohan21/fastf1_pitwall/issues/82), [Issue #164](https://github.com/parekhrohan21/fastf1_pitwall/issues/164), [Issue #177](https://github.com/parekhrohan21/fastf1_pitwall/issues/177)): Refactored into clean `src/` modules (`src/data/`, `src/charts/`, `src/ui/`), purged duplicate code from `app.py`, and added comprehensive architectural commentary detailing the 11-stage render pipeline.
- **Automated Pytest Test Suite** ([Issue #83](https://github.com/parekhrohan21/fastf1_pitwall/issues/83)): Comprehensive test coverage with **116 automated pytest unit and integration tests** across 18 dedicated modules.

---

## 📚 How to Use the Dashboard

> **Note:** On first load, the dashboard automatically defaults to the most recent completed Grand Prix of the current season and selects the session winner (or fastest driver in practice) as Driver 1.

1. **Sidebar → Season, Grand Prix & Session**: Pick a year (2018 – present), Grand Prix event, and session type (Race, Qualifying, Sprint, FP1, FP2, or FP3).
2. **Click ⬇️ Load Session(s)**: The first load downloads data from the F1 timing API (~10–30 seconds). Subsequent loads are instantaneous from the local disk cache.
3. **Session Info Banner**: Inspect the circuit name, country flag, round number, session type icon (🏆 Race, ⏱ Qualifying, ⚡ Sprint, 🔧 Practice), and event date.
4. **Select Drivers and Laps**: Pick a primary driver and select *Fastest* or a specific lap number. Tick **👥 Compare with Driver 2** to enable head-to-head comparison mode across all charts.
5. **Driver Summary Banner & Session Statistics**: Review official driver headshots, team logo badges, tyre status, weather strip, and session statistics (Grid, Finish, Status, Best Lap, Race Pace, Top Speed).
6. **Lap Time History & Compound Filter**: Inspect race pace with compound-coloured markers, pit-out flags, and flag bands. Use the multiselect compound filter above the chart to isolate tyre stints.
7. **Fuel-Adjusted Pace Analysis**: Remove fuel load penalties with the interactive sensitivity slider and expand the **Simulated Qualifying Leaderboard** for true pace rankings.
8. **Tyre Stints & Pit Stop Summary**: View Gantt-style horizontal stint timelines and pit stop durations.
9. **Pit Strategy & Undercut / Overcut Simulator**: In compare mode, automatically detect adjacent pit cycles (±3 laps), calculate pre/post pit gaps, and evaluate strategy outcomes.
10. **Pit Lane Transit Loss Breakdown**: Analyze speed-limiter transit duration, in-lap entry push deltas, out-lap cold tyre warm-up deltas, and sector splits on stacked bar charts and classified leaderboards.
11. **Tyre Degradation Modeling & Fuel Burn Decoupler**: Review OLS and quadratic regressions. Toggle the **Fuel Burn Decoupler** to isolate True Mechanical Tyre Wear from car weight loss, inspect true vs raw degradation rates, and check thermal cliff predictions in the full-field urgency matrix.
12. **Driver Consistency Index**: Inspect driver lap time variance per stint, Consistency Score (0–100%), Clean Air Pace vs. Traffic Deficit (+s/lap), and violin/boxplots.
13. **Track Temperature & Weather Correlation**: Overlay track temperature on driver pace with auto-detected rain crossover windows.
14. **Track Evolution & Grip Improvement Ramp Index**: In Practice and Qualifying sessions, review driver fixed-effects pace normalisation, Track Ramp Rate (ms/min), Total Track Grip Gain (s), and track condition classification banners.
15. **Braking Efficiency & Trail-Braking Analysis**: Select any turn from the corner dropdown to analyze braking distance before apex, peak deceleration ($G$), trail-braking release points, and brake-to-throttle transition times (ms) on stacked telemetry subplots.
16. **Corner Exit Traction & Throttle Aggression Analysis**: Select any corner to evaluate throttle pick-up points, distance to 100% full throttle, throttle ramp rate (%/m), hesitation wheelspin lifts, exit acceleration ($G$), and Traction Aggression Score (0–100), with automatic flat-out corner detection.
17. **Gear Shift Strategy & RPM Power Bands**: Inspect engine RPM curves with annotated shift markers, tactical short-shifts (< 11,000 RPM at > 60% throttle), redline shifts, and percentage gear usage distributions (Gears 1 to 8).
18. **Multi-Year Historical Lap Comparison**: In compare mode, select a second season and Grand Prix to compare cars across technical regulation eras on a 500-point distance grid.
19. **High-Resolution Telemetry & Dynamic Channel Filter**: Inspect telemetry waveforms. Use the **Telemetry Channels** multiselect to toggle channels (`Speed`, `Throttle`, `Brake`, `RPM`, `Gear`, `DRS`) on/off and reorder them with dynamic figure scaling.
20. **Export Telemetry Data (CSV, Parquet, JSON)**: Expand the export panel beneath the telemetry charts to download high-frequency data with sector splits and lap metadata.
21. **Speed Delta & Continuous Time Delta per Meter**: In compare mode, identify exact track coordinates where time is gained or lost along the lap.
22. **Speed Trap & Intermediate Velocity Radar Breakdown**: Inspect the 4-axis polar radar comparing speeds across ST, I1, I2, and FL, benchmark constructor and power unit aerodynamic efficiency, and review the classified speed trap table.
23. **Intra-Team Teammate Battle & Qualifying Delta Matrix**: Toggle between Qualifying Lap Delta and Race Pace Delta to review diverging teammate gap bars, sector dominance tallies, and classified matrix tables.
24. **Multi-Driver Grid Analysis & Heatmaps**: Select 3 to 20 drivers across the field to render colour-coded heatmaps for Sector Split Deltas, Lap-by-Lap Pace, and Top Speed.
25. **Track Maps, Corner Analysis & Animated Race Replay**: Switch between speed heat-maps, AWS-style mini-sector dominance maps, driver input pedal traces, 4-subplot corner analysis, or run the multi-car animated race replay.
26. **Official Classification & Championship Standings**: Review complete official session classifications and seasonal drivers' and constructors' championship standings.
27. **Real-Time Live Timing Mode**: Toggle live timing in the sidebar during active race weekends to record WebSocket packets and stream live timing.
28. **Post-Race Debrief PDF Exporter**: Click **Generate PDF Report** in the sidebar to export a broadcast-quality printable PDF debrief.

---

## 📁 Project Structure

```
fastf1_pitwall/
├── app.py                      # Main Streamlit entry point, layout orchestration & 11-stage render pipeline
├── src/                        # Modular source package
│   ├── data/
│   │   └── loader.py           # FastF1 session caching, proxy/TLS bypass, statistical builders,
│   │                           # robust regression, metric extractors & telemetry exporters (CSV/Parquet/JSON)
│   ├── charts/
│   │   ├── plotly.py           # Interactive Plotly figures (History, stints, maps, replays, corners, braking,
│   │   │                       # traction exits, track evolution, gears, radars, teammate matrix, pit loss)
│   │   └── matplotlib.py       # Static Matplotlib telemetry charts & dynamic channel filtering
│   └── ui/
│       ├── styles.py           # CSS design system, team/compound constants, PWA manifest & dark/light toggler
│       └── components.py       # Reusable UI sections, KPI metric cards, map tabs, teammate matrix,
│                               # pit loss breakdown, traction sections & telemetry export panels
├── tests/                      # Automated Pytest suite (116 tests across 18 dedicated modules)
│   ├── test_traction_exit.py           # Corner exit traction, throttle ramp rate, flat-out corners & aggression score
│   ├── test_track_evolution.py         # Theil-Sen ramp rate, grip gain, flyer filtering & knockout bias removal
│   ├── test_pit_transit_loss.py        # Pit lane transit duration, in-lap/out-lap deltas & sector warm-up
│   ├── test_teammate_battle.py         # Teammate head-to-head battle, qualifying & race pace deltas
│   ├── test_fuel_decoupled_tyre_deg.py # Pure mechanical tyre degradation & fuel burn decoupler
│   ├── test_speed_trap.py              # Speed trap, intermediate velocity & polar radar metrics
│   ├── test_gear_shifts.py             # Powertrain dynamics, shift detection & gear distributions
│   ├── test_braking_analysis.py        # Braking dynamics, trail-braking & deceleration G-force metrics
│   ├── test_telemetry_export.py        # CSV, Apache Parquet & JSON export serialization
│   ├── test_telemetry_channels.py      # Dynamic channel toggle configuration & figure scaling
│   ├── test_tyre_crossover.py          # Quadratic degradation regression & cliff lap prediction
│   ├── test_consistency.py             # Driver Consistency Index & stint pace distributions
│   ├── test_weather_correlation.py     # Track temperature correlation & rain crossover detection
│   ├── test_multi_year_comparison.py   # 500-pt distance grid cross-era telemetry comparisons
│   ├── test_corner_analysis.py         # Corner telemetry (braking, apex, steering angle, DRS)
│   ├── test_grid_heatmap.py            # Multi-driver heatmap matrix data wrangling
│   ├── test_live_timing.py             # SignalR live timing stream recorder
│   └── test_data_wrangling.py          # Session lap filtering & summary statistics
├── .github/workflows/test.yml  # GitHub Actions CI workflow running pytest on every push / PR to main
├── .devcontainer/              # GitHub Codespaces & VS Code Dev Container definitions
│   └── devcontainer.json
├── requirements.txt            # Pinned Python package dependencies
├── Dockerfile                  # Containerisation definition with inline build and execution comments
├── .dockerignore               # Docker build context exclusions
├── .gitignore                  # Git repository exclusions (cache, bytecode, test artifacts)
├── README.md                   # User documentation, feature guide & architecture index
├── AGENT.md                    # AI developer guidelines, architectural decisions & review checklist
└── DOCS.md                     # Comprehensive technical developer manual & pipeline architecture
```

---

## 🧑‍💻 Contributing & Development Workflow

To ensure code stability and maintain a clean git history, all code changes (fixes or feature requests) must follow this systematic branch-and-PR development workflow:

### Step 1 — Create a GitHub Issue
Document the bug or feature request in a GitHub Issue:
```bash
gh issue create --title "<type>: <short summary>" --body "<description and details>" --label "<bug/enhancement/documentation>"
```

### Step 2 — Create a Feature or Fix Branch
Switch to a clean `main` branch, pull remote changes, and checkout a dedicated feature/fix branch:
```bash
git checkout main
git pull
git checkout -b <prefix>/<short-description>  # e.g., feat/issue-155-corner-exit-traction or fix/session-error
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
All **116 unit and integration tests** across 18 test modules must pass cleanly.

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

## ⚠️ Known Limitations & Troubleshooting

| Problem | Cause & Diagnostic | Solution / Fix |
|---|---|---|
| **First load is slow** | Downloading ~50-100MB of telemetry from the official F1 CDN. | Expected behaviour. All subsequent loads are cached to disk and load in milliseconds. |
| **Active / Ongoing Sessions** | Static timing data is only finalized by F1 after session completion. | Toggle **🔴 Real-Time Live Timing Mode** in the sidebar to stream live SignalR WebSocket packets during live sessions. |
| **"Session data unavailable"** | Recent or newly announced sessions may not have finalized timing files yet. | Try an older completed race, or click **Load Session(s)** again (bad cache entries are cleared automatically). |
| **Port 8501 already in use** | A previous Streamlit instance is still bound to the port. | Run `lsof -i :8501` and kill the process, or run Streamlit on a different port using `streamlit run app.py --server.port 8502`. |
| **Docker daemon not reachable** | Docker Desktop is not running on your host. | Launch Docker Desktop (`open -a Docker` on macOS), wait 30 seconds for the engine to initialize, and retry. |
| **F1 API HTTP 403 blocks (CloudFront/Cloudflare)** | F1 CDN anti-bot blocks on cloud hosting providers. | Handled automatically via TLS impersonation (`curl_cffi`). If blocks persist, set the `F1_PROXY` environment variable or Streamlit secret to route requests through a proxy. |
| **Verify API connectivity or TLS status** | Network firewall or CDN blocking. | Expand **🛠️ Diagnostics & Debug Info** at the bottom of the sidebar and click **Run Connection Test** to verify connectivity. |
| **Plotly deprecation warning on `use_container_width`** | Running an older codebase version. | The codebase uses `width='stretch'` / `width='content'` throughout. Update to the latest version of the repository. |
| **Top bar keeps the old theme** | Browser cached stylesheet edge case. | Toggle the dark/light mode button in the sidebar once more — CSS injection re-applies on every rerun. |

---

## 📜 Solved Issues & Changelog

All development on FastF1 Pit Wall is tracked transparently via GitHub Issues and Pull Requests following a rigorous branch-and-PR workflow. Below is the complete chronological index of active roadmap issues and resolved issues.

### 🔮 Active Roadmap & Open Issues

| Issue | Title | Category | Scope & Planned Capability | Status |
|:---:|---|---|---|:---:|
| **[#172](https://github.com/parekhrohan21/fastf1_pitwall/issues/172)** | `docs: add DECISIONS.md to document Architectural choices and AI implementation decisions` | Architecture & Governance | Standardised Architecture Decision Records (ADRs) cataloguing key algorithmic choices, mathematical rationale, engineering trade-offs, and rejected alternatives. | Open |
| **[#171](https://github.com/parekhrohan21/fastf1_pitwall/issues/171)** | `feat: Automated Session Brag Video Generation via Latent Space Telemetry Embeddings` | Telemetry & Video | Dimensionality reduction (PCA / manifold embedding) projecting 9D telemetry into fluid camera tracking reels, HUD telemetry overlays, and exportable MP4 brag videos. | Open |
| **[#157](https://github.com/parekhrohan21/fastf1_pitwall/issues/157)** | `feat: Clean Air vs Dirty Air Pace Impact & Overtaking Analysis` | Telemetry & Strategy | Aerodynamic wake analysis quantifying lap time penalty and tyre degradation rate when following within 1.5s vs clean air. | Open |
| **[#156](https://github.com/parekhrohan21/fastf1_pitwall/issues/156)** | `feat: Full Grand Prix Weekend Multi-Session Progression Tracker` | Grid Analytics | Cross-session pace evolution and setup refinement tracking across FP1, FP2, FP3, Qualifying, and Race sessions. | Open |

---

### ✅ Resolved Issues Index

| Issue / PR | Title | Category | Key Capability Delivered |
|:---:|---|---|---|
| **[#183](https://github.com/parekhrohan21/fastf1_pitwall/issues/183)** | `docs: update README with recent features, architecture updates, and full resolved issues index` | Documentation | Comprehensive synchronization of README documentation covering all recent features (#148–#155, #164, #177), 116 tests across 18 modules, and Docker setup. |
| **[#155 Follow-up](https://github.com/parekhrohan21/fastf1_pitwall/commit/3a0b5f3)** | `fix: flat-out corners and snap pick-ups in traction analysis` | Corner Dynamics | Added `FLAT_OUT_THROTTLE_PCT` (85%) within $\pm 10$m of apex to identify flat-out corners without computing spurious traction scores; measured snap pick-up ramps from preceding sample. |
| **[#182](https://github.com/parekhrohan21/fastf1_pitwall/pull/182)** / **[#155](https://github.com/parekhrohan21/fastf1_pitwall/issues/155)** | `feat: Corner Exit Traction & Throttle Pick-Up Aggression Analysis` | Corner Dynamics | Corner exit throttle pick-up points, distance to 100% throttle, spatial ramp rate (%/m), temporal gradient (%/s), hesitation lifts ($\ge 3.5\%$), oversteer corrections, exit acceleration ($G$), and 0–100 Traction Aggression Score. |
| **[#181](https://github.com/parekhrohan21/fastf1_pitwall/pull/181)** | `docs: synchronize README documentation and resolve runtime pipeline defects` | Documentation & UI | Synchronized README documentation, fixed sidebar diagnostic button labels, and resolved runtime layout rendering edge-cases. |
| **[#180](https://github.com/parekhrohan21/fastf1_pitwall/pull/180)** / **[#177](https://github.com/parekhrohan21/fastf1_pitwall/issues/177)** | `docs: add app.py architecture commentary and close README gaps` | Architecture & Docs | Added comprehensive module docstring to `app.py` detailing the 11-stage render pipeline, rerun execution model, caching rules, and inline commentary across all 46 section dividers. |
| **[#179](https://github.com/parekhrohan21/fastf1_pitwall/pull/179)** / **[#154](https://github.com/parekhrohan21/fastf1_pitwall/issues/154)** | `feat: Track Evolution & Grip Improvement Ramp Index` | Track Analytics | Whole-field sensor modeling for Practice & Qualifying; driver fixed-effects pace normalisation removing knockout bias; Theil-Sen seeded robust regression (`_robust_linear_fit`); Track Ramp Rate (ms/min) and Total Track Grip Gain (s). |
| **[#176](https://github.com/parekhrohan21/fastf1_pitwall/pull/176)** / **[#164](https://github.com/parekhrohan21/fastf1_pitwall/issues/164)** | `refactor: repository cleanup, remove redundant code and AI slop, and streamline file tree` | Maintenance / Refactor | Purged 2,021 lines of duplicate functions from `app.py`, removed tracked bytecode and scratch files, and strengthened `.gitignore` and `.dockerignore` for optimal Docker builds and Streamlit memory efficiency. |
| **[#175](https://github.com/parekhrohan21/fastf1_pitwall/pull/175)** | `docs: update README, DOCS.md, and AGENT.md manual documentation` | Documentation | Synchronized user manual, developer documentation, and agent instructions. |
| **[#174](https://github.com/parekhrohan21/fastf1_pitwall/pull/174)** | `docs: sync README, DOCS.md, and AGENT.md with active roadmap issues (#171, #172)` | Documentation | Synchronized active roadmap tables, developer manual roadmap, and agent guidelines with newly opened GitHub issues (#171, #172). |
| **[#173](https://github.com/parekhrohan21/fastf1_pitwall/pull/173)** / **[#153](https://github.com/parekhrohan21/fastf1_pitwall/issues/153)** | `feat: Pit Lane Transit Loss & In-Lap / Out-Lap Performance Breakdown` | Strategy & Pit Stops | Micro-sector decomposition of pit lane transit duration ($t_{\text{pit\_lane}}$), in-lap push delta ($\Delta t_{\text{in}}$), out-lap cold tyre warm-up ($\Delta t_{\text{out}}$), net pit loss, sector warm-up splits, and full-field efficiency leaderboard. |
| **[#170](https://github.com/parekhrohan21/fastf1_pitwall/pull/170)** | `docs: update README and documentation files sync` | Documentation | Synchronized test counts and PR indices across user and developer documentation. |
| **[#169](https://github.com/parekhrohan21/fastf1_pitwall/pull/169)** / **[#152](https://github.com/parekhrohan21/fastf1_pitwall/issues/152)** | `feat: Intra-Team Teammate Battle & Qualifying Delta Matrix` | Leaderboards & Analytics | Grid-wide teammate comparison across all 10 constructors with diverging qualifying & race pace delta bars, sector dominance (S1/S2/S3), and classified matrix table. |
| **[#168](https://github.com/parekhrohan21/fastf1_pitwall/pull/168)** | `docs: synchronize README, AGENT.md, and DOCS.md documentation` | Documentation | Comprehensive documentation and agentic guidelines audit synchronizing test counts, roadmap items, and architecture decision records. |
| **[#167](https://github.com/parekhrohan21/fastf1_pitwall/pull/167)** / **[#151](https://github.com/parekhrohan21/fastf1_pitwall/issues/151)** | `feat: Fuel-Corrected Pure Tyre Degradation & Fuel Burn Decoupler` | Tyre Modeling & Strategy | Decoupling fuel mass burn-off (lap-by-lap weight reduction) from compound wear to isolate pure tyre degradation curves, unmasked thermal cliff laps, and fuel masking offsets. |
| **[#166](https://github.com/parekhrohan21/fastf1_pitwall/pull/166)** / **[#150](https://github.com/parekhrohan21/fastf1_pitwall/issues/150)** | `feat: Speed Trap & Intermediate Velocity Radar Breakdown` | Telemetry / Radar | 4-axis polar velocity radar (`ST`, `I1`, `I2`, `FL`), constructor/engine benchmarks, classified Speed Trap Leaderboard, and DRS gain deltas. |
| **[#163](https://github.com/parekhrohan21/fastf1_pitwall/pull/163)** / **[#149](https://github.com/parekhrohan21/fastf1_pitwall/issues/149)** | `feat: Gear Shift Strategy & RPM Power Band Optimization` | Powertrain Dynamics | Dual-subplot engine RPM curve with shift markers, gear usage distribution (Gears 1–8), and tactical short-shift detection. |
| **[#162](https://github.com/parekhrohan21/fastf1_pitwall/pull/162)** / **[#148](https://github.com/parekhrohan21/fastf1_pitwall/issues/148)** | `feat: Braking Efficiency & Trail-Braking Zone Analysis` | Corner Dynamics | Longitudinal deceleration ($G$), braking distance, trail-braking release point, and 3-subplot braking dynamics profile. |
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

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 live timing stream and the Ergast-compatible [Jolpica F1 API](https://github.com/jolpica/jolpica-f1). Pit Wall is an independent community project and is not affiliated with Formula 1 or the FIA.

**For educational and non-commercial use only.**
