# 🏎 Pit Wall — F1 Telemetry Dashboard

A **Streamlit + FastF1** dashboard for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **Speed**, **Throttle**, and **Brake** traces alongside lap time and sector splits. Supports head-to-head driver comparison.

---

## Features

- 📅 Any session from **2018 → present** (Race, Qualifying, Sprint, Practice 1/2/3)
- 📈 Three-panel telemetry chart — Speed (km/h) · Throttle (%) · Brake (On/Off)
- ⏱  Lap summary cards — lap time, S1 / S2 / S3 splits, tyre compound & age
- 👥 **Driver comparison** — overlay two drivers on the same chart with different colours
- ⚡ FastF1 disk cache keeps repeated loads instant
- 🐳 Docker-ready with optional cache volume mount

---

## Prerequisites

| Without Docker | With Docker |
|---|---|
| Python 3.10+ | Docker Desktop installed & running |
| pip | No Python needed locally |

---

## Running Locally (Without Docker)

### Step 1 — Clone the repo

```bash
git clone https://github.com/your-username/fastf1_pitwall.git
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

Open **http://localhost:8501** in your browser. The app will hot-reload when you save changes to `app.py`.

---

## Running with Docker

### Step 1 — Build the image

```bash
cd fastf1_pitwall
docker build -t pitwall .
```

### Step 2 — Run the container

```bash
docker run -p 8501:8501 pitwall
```

Open **http://localhost:8501**.

### (Optional) Persist the cache between restarts

FastF1 caches downloaded telemetry to disk. Mount a local folder so you don't re-download data every time the container restarts:

```bash
docker run -p 8501:8501 -v $(pwd)/cache:/app/cache pitwall
```

### Stop the container

```bash
docker ps                        # find the container ID
docker stop <container-id>
```

---

## How to Use the Dashboard

Once the app is open in your browser:

1. **Sidebar → Season** — pick a year (2018 – present)
2. **Sidebar → Grand Prix** — pick any event from that season's calendar
3. **Sidebar → Session** — choose Race, Qualifying, Sprint, FP1, FP2, or FP3
4. **Click ⬇️ Load Session** — first load may take ~30 seconds; subsequent loads are instant from cache
5. **Driver 1** — select any driver from the session
6. **Lap** — choose *Fastest* or a specific lap number
7. The telemetry chart (Speed · Throttle · Brake) and lap summary cards will render automatically

### Head-to-Head Comparison

8. Tick **👥 Compare with Driver 2**
9. Select a second driver and their lap
10. Both drivers' telemetry will be overlaid on the same chart with distinct colours and a legend

---

## Example Walkthrough

| Step | Action |
|---|---|
| Season | 2023 |
| Grand Prix | Monaco Grand Prix |
| Session | Race (R) |
| Click | ⬇️ Load Session |
| Driver 1 | VER — Lap: Fastest |
| Compare | ✅ enabled |
| Driver 2 | ALO — Lap: Fastest |

You'll see Verstappen's and Alonso's fastest Monaco race laps overlaid — great for spotting braking points and throttle application differences.

---

## Project Structure

```
fastf1_pitwall/
├── app.py            # Main Streamlit application
├── requirements.txt  # Python dependencies
├── Dockerfile        # Docker image (python:3.11-slim, port 8501)
├── .dockerignore
└── cache/            # FastF1 telemetry cache (auto-created, gitignored)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Session fails to load | Some 2026 sessions may not be published yet — try a completed 2025 race |
| No telemetry for a lap | Pit laps or very slow laps are filtered out; choose a different lap |
| Port 8501 already in use | Run `lsof -i :8501` and kill the process, or use `--server.port 8502` |
| Docker cache not persisting | Mount the cache volume: `-v $(pwd)/cache:/app/cache` |

---

## Data & Licensing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and the Ergast API.  
**For educational / non-commercial use only.**
