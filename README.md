# ORBITGUARD AI 🛰️
### Autonomous Space Intelligence & Collision Avoidance System

> **Statutory Aerospace Notice:** ORBITGUARD AI provides analytical and illustrative orbital assessments based on public TLE/OMM ephemeris data. This platform does not provide certified operational flight-dynamics commands. Explicit **human-in-the-loop (HITL)** authorization is strictly required for all recommended maneuvers.

---

## 1. System Overview
**ORBITGUARD AI** is an autonomous space intelligence platform designed to protect operational orbital assets from space debris and hyper-velocity collisions (~7.5+ km/s in LEO). It incorporates:
- **Real-Time Data Ingestion:** Automated synchronization with CelesTrak GP/OMM and TLE element feeds.
- **SGP4 Orbital Propagator:** High-precision WGS-72/84 analytical propagation, converting TEME coordinates into ECI (J2000), ECEF, and Geodetic coordinates (lat/lon/alt).
- **Two-Phase Conjunction Screening:** Broad-phase orbital shell/apogee-perigee filtering + narrow-phase close approach refinement (Time of Closest Approach `TCA`, Euclidean miss distance in km, relative velocity).
- **5-Agent Autonomous Brain:** Specialized agents (Monitoring, Prediction, Collision Assessment, Mission Planning, Intelligence Reporting) coordinated via persistent MongoDB memory and backed by real backend tools.
- **Human-in-the-Loop Safety Gate:** Strict approval enforcement preventing any simulated avoidance burn from transitioning without operator authorization.

---

## 2. Architecture & Tech Stack

```
               [ CelesTrak GP/OMM / TLE Feeds ]
                              │
                              ▼
        ┌───────────────────────────────────────────┐
        │        FastAPI Backend Engine             │
        │  • Ingestion Service (CelesTrak)          │
        │  • SGP4 Ephemeris Propagator (WGS-72/84)  │
        │  • Broad & Narrow Phase Conjunction Engine│
        │  • ML Anomaly & Risk Scorer               │
        │  • 5-Agent Autonomous Brain               │
        │  • WebSocket Alert Stream                 │
        └─────────────────────┬─────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       [ MongoDB Atlas / Local ]     [ CesiumJS 3D Earth UI ]
    • Satellites Catalog          • Propagated 3D Orbits
    • TLE History                 • Conjunction Corridors
    • Conjunctions                • Autonomous Command Bar
    • Maneuver Proposals (HITL)   • Approval / Reject Panel
    • Agent Memory & Traces
```

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SGP4, NumPy, SciPy, Motor, Pydantic v2.
- **Database:** MongoDB (Atlas, Local, or in-memory fallback).
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + CesiumJS (3D Earth).

---

## 3. API Reference (Phase 1 Implemented & Verified)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service health metadata & operational disclaimer |
| `GET` | `/api/health` | System health status, database engine state, and uptime |
| `POST`| `/api/catalog/sync` | Ingests live CelesTrak groups (`stations`, `active`, `debris`) into MongoDB |
| `GET` | `/api/satellites` | Lists orbital catalog with pagination, type, and search filters |
| `GET` | `/api/satellites/{norad_id}` | Detailed orbital elements & apogee/perigee geometries |
| `GET` | `/api/satellites/{norad_id}/history` | Historical TLE records for time-series anomaly modeling |
| `GET` | `/api/satellites/{norad_id}/orbit` | SGP4 propagated 3D ECI & Geodetic points (lat/lon/alt) over horizon |

---

## 4. Local Quickstart (No Docker Required)

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend dashboard)

### Backend Setup
```bash
cd backend

# Create virtual environment and install dependencies
uv venv
uv pip install -e ".[dev]"

# Run test suite (9 unit & integration tests)
.venv\Scripts\pytest -v

# Start development server
.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access Swagger UI interactive documentation at: `http://localhost:8000/docs`

---

## 5. Environment Variables (`.env.example`)
```ini
PORT=8000
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000"]
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=orbitguard_db
CELESTRAK_BASE_URL=https://celestrak.org/NORAD/elements/gp.php
GEMINI_API_KEY=
CESIUM_ION_TOKEN=
```
