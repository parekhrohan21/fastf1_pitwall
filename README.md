# 🏎 Pit Wall — F1 Telemetry Dashboard

A **Streamlit + FastF1** dashboard for exploring lap telemetry from any Formula 1 session since 2018.

Select a season, Grand Prix, session, driver, and lap — then instantly visualise **Speed**, **Throttle**, and **Brake** traces, alongside lap time and sector splits. Supports head-to-head driver comparison.

---

## Features

- 📅 Any session from **2018 → present** (Race, Qualifying, Sprint, Practice)
- 📈 Three-panel telemetry chart (Speed km/h · Throttle % · Brake on/off)
- ⏱  Lap summary card (lap time, S1/S2/S3, tyre compound & age)
- 👥 **Driver comparison** — overlay two drivers on the same chart
- ⚡ FastF1 disk cache keeps repeated loads instant
- 🐳 Docker-ready

---

## Quick Start (Local)

### 1. Install dependencies

```bash
cd fastf1_pitwall
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Docker

### Build

```bash
docker build -t pitwall .
```

### Run

```bash
docker run -p 8501:8501 pitwall
```

To persist the FastF1 cache between container restarts:

```bash
docker run -p 8501:8501 -v $(pwd)/cache:/app/cache pitwall
```

Open **http://localhost:8501**.

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

## Example Usage

1. Sidebar → **Season: 2023**, **Grand Prix: Monaco Grand Prix**, **Session: Race (R)**
2. Click **⬇️ Load Session** (first load ~30 s, subsequent loads instant from cache)
3. Pick **Driver: HAM**, **Lap: Fastest**
4. Charts render showing Hamilton's fastest Monaco race lap telemetry

---

## Data & Licencing

Telemetry data is sourced via [FastF1](https://docs.fastf1.dev) from the official F1 timing stream and Ergast API. For educational / non-commercial use only.
