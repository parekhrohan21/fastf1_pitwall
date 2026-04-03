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
- **Premium Aesthetics**: A custom built, fully responsive UI inspired by McLaren Papaya and iOS 7 flat/frosted glass aesthetics that dynamically adapts to both **Light** and **Dark** mode device themes natively.
- **Native UI Compatibility**: Full support for Streamlit's native overlays (e.g. settings menus, sidebar navigation icons) and system-animated run indicators without custom CSS overlapping or breakage.
- **High Performance**: FastF1 caching combined with Streamlit session state keeps the heavy data processing instant after the first load.

---

## 🛠 Prerequisites

| Without Docker | With Docker |
|---|---|
| Python 3.11+ | Docker Desktop installed & running |
| pip | No Python needed locally |

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

## 📚 How to Use the Dashboard

1. **Sidebar → Season** — pick a year (2018 – present)
2. **Sidebar → Grand Prix** — pick any event from that season's calendar
3. **Sidebar → Session** — choose Race, Qualifying, Sprint, FP1, FP2, or FP3
4. **Click ⬇️ Load Session** — The first load streams the data from the F1 API and takes ~10-30 seconds. Afterwards, it is cached down to milliseconds.
5. **Select Drivers and Laps** — Pick a driver and select *Fastest* or a specific lap number.
6. **Compare Drivers** — Tick **👥 Compare with Driver 2** to overlay traces and generate the Speed Delta chart.
7. **Track Map & Replacements** — Scroll down to the Track Map tabs to view the speed heat-map or build the full multi-car Race Replay animation!

---

## ⚠️ Known Limitations & Troubleshooting

| Problem | Fix |
|---|---|
| First load is slow | Expected behavior (FastF1 is downloading ~50-100MB of telemetry). Subsequent loads are cached. |
| Session fails to load | Some recent/future sessions may not be published fully yet. Try an older completed race. |
| Port 8501 already in use | Run `lsof -i :8501` and kill the process, or run Streamlit on a different port using `streamlit run app.py --server.port 8502` |
| Docker fails to connect API | The Docker Daemon is not running. Launch the Docker Desktop explicitly first using `open -a Docker`, wait 30 seconds for the engine to initialize, and try again. |

---

## ⚖️ Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
