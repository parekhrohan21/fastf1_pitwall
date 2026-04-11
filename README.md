# 🏎 Pit Wall — F1 Telemetry Dashboard

A professional-grade **Streamlit + FastF1** dashboard with a custom McLaren/iOS 7 flat style design for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **6 telemetry channels** alongside track maps, full race replays, and detailed lap/weather summaries.

---

## 🚀 Key Features

- **Any Session**: Supports data from 2018 → present (Race, Qualifying, Sprint, Practice 1/2/3).
- **6-Channel Telemetry**: View combined or separate traces for Speed (km/h), Throttle (%), Brake (On/Off), RPM, Gear, and DRS.
- **Head-to-Head Comparison**: Overlay two drivers on the primary charts, plus a **Speed Delta (Δ)** chart showing where time is gained/lost.
- **Interactive Track Map**: A Plotly-powered map coloured by speed, with secondary driver path overlays.
- **Animated Race Replay**: Watch a full animated replay of the session plotting all drivers on the track with a scrubbable timeline.
- **Rich Dashboard Context**: Includes custom tyre visualizations (compound, age, freshness) and a detailed weather strip (air/track temp, humidity, rainfall, track status).
- **Premium Aesthetics**: A custom built, fully responsive UI inspired by McLaren Papaya and iOS 7 flat/frosted glass aesthetics. Now features the premium **Inter** font, seamless keyframe animations (fade-ins, slide-ups), glassmorphism interactive hovers, and dynamic adaptation to both **Light** and **Dark** mode device themes natively (including fully transparent overlay rendering for static Matplotlib telemetry charts).
- **Native UI Compatibility**: Full support for Streamlit's native overlays (e.g. settings menus, sidebar navigation icons) and system-animated run indicators without custom CSS overlapping or breakage. Material Symbols icons (sidebar collapse arrow, toolbar buttons) are explicitly preserved via targeted CSS font rules.
- **Gap to Leader Chart**: Interactive Plotly chart showing every driver's time gap to the race leader lap-by-lap. Selected driver(s) are highlighted in team colour against a faded field, with ▼ pit lap markers and a final gap stat card per driver.
- **Mobile PWA Ready**: The dashboard acts as a native mobile application. Pin it to your iOS or Android home screen for a fullscreen, address-bar-free app experience powered by an injected embedded Web Manifest!
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
7. **Gap to Leader** — Scroll to the Gap to Leader section to see every driver's time gap per lap vs the leader. Your selected driver(s) are highlighted; pit stops are marked with ▼ triangles. A stat card shows the final gap and peak deficit.
8. **Track Map & Replay** — Scroll to the Track Map tabs to view the speed heat-map or build the full multi-car Race Replay animation!

---

## ⚠️ Known Limitations & Troubleshooting

| Problem | Fix |
|---|---|
| First load is slow | Expected behavior (FastF1 is downloading ~50-100MB of telemetry). Subsequent loads are cached. |
| Session fails to load | Some recent/future sessions may not be published fully yet. Try an older completed race. |
| Port 8501 already in use | Run `lsof -i :8501` and kill the process, or run Streamlit on a different port using `streamlit run app.py --server.port 8502` |
| Docker fails to connect API | The Docker Daemon is not running. Launch the Docker Desktop explicitly first using `open -a Docker`, wait 30 seconds for the engine to initialize, and try again. |
| Sidebar shows `keyboard_double_arrow_left` text | The custom font CSS is overriding Streamlit's icon font. Ensure you are running the latest version of the app — this was patched via explicit `Material Symbols` CSS restoration. |
| Plotly config deprecation warning | Triggered by Plotly 6.x when using width as a direct argument. The codebase has been updated to use `use_container_width=True` to maintain compatibility with Streamlit without throwing Plotly warnings. |

---

## ⚖️ Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
