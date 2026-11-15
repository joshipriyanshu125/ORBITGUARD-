# ORBITGUARD AI – Dataset Architecture & Placement Guide

This directory (`backend/data/`) is the central repository for offline datasets, historical orbital ephemerides, conjunction data messages (CDMs), and space weather indices.

---

## 1. Directory Structure

```text
backend/data/
├── tle/                  <-- Raw TLE / OMM catalog files (Space-Track, CelesTrak)
│   ├── stations.txt      <-- Space stations & crewed vehicles (ISS, Tiangong)
│   ├── active.txt        <-- Active payloads (Starlink, OneWeb, GPS, etc.)
│   └── debris/           <-- Fragmentation clouds (Fengyun-1C, Cosmos-2251, Iridium-33)
│       ├── fengyun-1c-debris.txt
│       └── cosmos-2251-debris.txt
├── conjunctions/         <-- Conjunction assessment archives
│   ├── socrates/         <-- SOCRATES 7-day screening CSV dumps
│   │   └── socrates_latest.csv
│   └── cdm/              <-- NASA/ESA Conjunction Data Messages (JSON / KVN format)
│       └── sample_cdm.json
├── space_weather/        <-- Atmospheric drag & density drivers for Model 1 GRU residuals
│   ├── f107_solar_flux.csv  <-- Daily 10.7 cm solar radio flux (NOAA SWPC)
│   └── geomagnetic_ap.csv   <-- Planetary geomagnetic Ap indices
└── physical_catalogs/    <-- Spacecraft dimensions & Hard Body Radius (HBR) for Model 4
    └── discos_hbr.json   <-- ESA DISCOS spacecraft cross-sections & masses
```

---

## 2. Where to Source Datasets

### A. TLE & OMM Orbital Catalogs
* **CelesTrak (Recommended for immediate use – Public, no registration):**
  * Direct downloads: `https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle`
  * Active satellites: `https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json`
  * Major debris clouds: `https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=tle`
* **Space-Track.org (Official US Space Force Catalog – Free registration):**
  * URL: `https://www.space-track.org/`
  * Historical TLE search across any epoch range for precise anomaly evaluation.

### B. Historical Conjunctions & Close Approaches
* **CelesTrak SOCRATES (Satellite Orbital Conjunction Reports Assessing Threatening Encounters in Space):**
  * URL: `https://celestrak.org/SOCRATES/`
  * Export: CSV dumps of Top 10 minimum range encounters. Place in `backend/data/conjunctions/socrates/`.
* **NASA CARA (Conjunction Assessment Risk Analysis) Sample CDMs:**
  * URL: `https://www.nasa.gov/conjunction-assessment-risk-analysis/`
  * Format: CCSDS Conjunction Data Message (CDM) standard with covariance matrices.

### C. Atmospheric Drag & Solar Activity (For Trajectory Residuals)
* **NOAA Space Weather Prediction Center (SWPC):**
  * URL: `https://www.swpc.noaa.gov/products/daily-solar-data`
  * Tracks $F_{10.7}$ solar flux and $A_p$ index, which directly drive thermospheric density variations modeled by Model 1 (GRU Neural Residual Predictor).

---

## 3. How ORBITGUARD Uses These Files

1. **Autonomous Fallback:** If offline or during testing, ORBITGUARD automatically falls back to internal fixtures. Placing `.txt` or `.csv` files into the directories above allows the data ingestion pipeline to index millions of real orbital states without network calls.
2. **Catalog Ingestion:** Call `POST /api/catalog/sync?groups=stations,fengyun-1c-debris` to populate MongoDB Atlas from these sources.
3. **Model Evaluation:** The datasets feed feature extraction (`features.py`), anomaly baseline evaluation (`anomaly_model.py`), and B-plane encounter verification (`collision_probability.py`).
