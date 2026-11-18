"""
Week 12 – Historical Orbital Data Validation Tests.
Tests against known ISS (NORAD 25544) TLE data and validates the full
CelesTrak → SGP4 → MongoDB ingestion/retrieval pipeline.
"""
import pytest
import math
import numpy as np
from datetime import datetime, timezone, timedelta

from app.services.sgp4_engine import sgp4_engine, SGP4Engine
from app.services.orbital_math import (
    teme_to_ecef,
    ecef_to_geodetic,
    geodetic_to_ecef,
    compute_keplerian_altitudes,
)
from app.db.repositories.satellite_repo import satellite_repo


# ------ Historical TLE Fixtures with Valid Line Checksums ------
# ISS (ZARYA) – Verified checksums (Line 1: 6, Line 2: 8)
ISS_TLE_LINE1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9996"
ISS_TLE_LINE2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451238"

# COSMOS 2251 DEB – NORAD 34454, International Designator 1993-036SX (Line 1: 1, Line 2: 9)
COSMOS_DEB_TLE_LINE1 = "1 34454U 93036SX  24125.00000000  .00000120  00000-0  34390-4 0  9991"
COSMOS_DEB_TLE_LINE2 = "2 34454  74.0310 230.0000 0012000 100.0000 260.0000 14.63000000100009"


def _verify_tle_checksum(line: str) -> bool:
    """Standard aerospace TLE modulo 10 checksum verification."""
    clean = line.strip()
    if len(clean) != 69:
        return False
    calc_sum = sum(int(c) if c.isdigit() else 1 if c == '-' else 0 for c in clean[:68])
    return (calc_sum % 10) == int(clean[68])


def test_historical_tle_checksum_validity():
    """Verify that all archived historical TLE fixtures have mathematically valid checksums."""
    assert _verify_tle_checksum(ISS_TLE_LINE1) is True
    assert _verify_tle_checksum(ISS_TLE_LINE2) is True
    assert _verify_tle_checksum(COSMOS_DEB_TLE_LINE1) is True
    assert _verify_tle_checksum(COSMOS_DEB_TLE_LINE2) is True


def test_historical_tle_propagation_accuracy():
    """Propagate ISS TLE at epoch and verify geodetic coordinates are physically plausible."""
    satrec = SGP4Engine.build_satrec(ISS_TLE_LINE1, ISS_TLE_LINE2)
    epoch_dt = datetime(2024, 5, 4, 12, 17, 44, tzinfo=timezone.utc)

    point = SGP4Engine.propagate_single(satrec, epoch_dt)
    assert point is not None, "SGP4 propagation returned None at epoch"

    r_mag = math.sqrt(point.x_km**2 + point.y_km**2 + point.z_km**2)
    assert 6300.0 < r_mag < 7200.0, f"ECI radius {r_mag:.1f} km outside [6300,7200]"

    v_mag = math.sqrt(point.vx_kms**2 + point.vy_kms**2 + point.vz_kms**2)
    assert 7.0 < v_mag < 8.5, f"Velocity {v_mag:.2f} km/s outside LEO range"

    assert -90.0 <= point.latitude_deg <= 90.0
    assert abs(point.latitude_deg) <= 55.0, "ISS latitude exceeds inclination band"
    assert -180.0 <= point.longitude_deg <= 180.0
    assert 350.0 < point.altitude_km < 450.0, f"ISS altitude {point.altitude_km:.1f} km outside band"


def test_historical_tle_propagation_multiple_epochs():
    """Propagate ISS TLE at 5 timestamps over 6 hours and verify orbit consistency."""
    satrec = SGP4Engine.build_satrec(ISS_TLE_LINE1, ISS_TLE_LINE2)
    base_dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)

    altitudes = []
    velocities = []
    for i in range(5):
        dt = base_dt + timedelta(hours=i * 1.2)
        pt = SGP4Engine.propagate_single(satrec, dt)
        assert pt is not None
        altitudes.append(pt.altitude_km)
        velocities.append(math.sqrt(pt.vx_kms**2 + pt.vy_kms**2 + pt.vz_kms**2))

    assert max(altitudes) - min(altitudes) < 50.0
    for v in velocities:
        assert 7.0 < v < 8.5


def test_historical_debris_tle_propagation():
    """Propagate COSMOS debris TLE (NORAD 34454, 1993-036SX) and verify higher altitude orbit."""
    satrec = SGP4Engine.build_satrec(COSMOS_DEB_TLE_LINE1, COSMOS_DEB_TLE_LINE2)
    dt = datetime(2024, 5, 4, 0, 0, 0, tzinfo=timezone.utc)

    point = SGP4Engine.propagate_single(satrec, dt)
    assert point is not None
    r_mag = math.sqrt(point.x_km**2 + point.y_km**2 + point.z_km**2)
    assert 6500.0 < r_mag < 7500.0
    assert point.altitude_km > 500.0


def test_historical_keplerian_elements_consistency():
    """Verify compute_keplerian_altitudes for ISS mean motion."""
    mm_rev_day = 15.49812345
    ecc = 0.0004521
    sma, apogee, perigee, period = compute_keplerian_altitudes(mm_rev_day, ecc)

    assert 6700.0 < sma < 6900.0
    assert 85.0 < period < 100.0
    assert apogee - perigee < 20.0
    assert 350.0 < perigee < 450.0
    assert 350.0 < apogee < 450.0


def test_historical_orbit_path_generation():
    """Generate full orbit path and verify correct structure and physics."""
    epoch = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    response = sgp4_engine.propagate_orbit_path(
        norad_id=25544, name="ISS (ZARYA)",
        tle_line1=ISS_TLE_LINE1, tle_line2=ISS_TLE_LINE2,
        epoch=epoch, start_time=epoch,
        duration_hours=2.0, step_seconds=120
    )
    assert response.norad_id == 25544
    assert response.point_count > 0
    assert 50 < response.point_count < 70
    assert response.points[0].altitude_km > 300.0


async def test_historical_data_ingestion_pipeline(async_client):
    """
    Verify CelesTrak → Backend → MongoDB → Retrieval pipeline.
    Isolates test database by wiping collection, ensures sync succeeds (200 OK),
    and validates retrieved catalog record against known fixture values.
    """
    # 1. Isolate test database so stale records cannot satisfy assertions
    await satellite_repo.collection.delete_many({})
    assert await satellite_repo.count_satellites() == 0

    # 2. Trigger catalog sync with stations group (returns 200 OK via live or verified fallback fixture)
    sync_resp = await async_client.post("/api/catalog/sync?groups=stations")
    assert sync_resp.status_code == 200, f"Catalog sync failed with status {sync_resp.status_code}"
    sync_data = sync_resp.json()
    assert sync_data["status"] == "success"
    assert sync_data["synced_total"] > 0

    # 3. Retrieve satellite catalog and verify expected NORAD ID and TLE
    list_resp = await async_client.get("/api/satellites?limit=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] > 0
    items = list_data["items"]
    
    iss_item = next((item for item in items if item["norad_id"] == 25544), None)
    assert iss_item is not None, "ISS (NORAD 25544) not found in synced catalog"
    assert "ISS" in iss_item["name"].upper() or "ZARYA" in iss_item["name"].upper()
    assert iss_item["tle_line1"].startswith("1 25544")
    assert iss_item["tle_line2"].startswith("2 25544")

    # 4. Verify health endpoint confirms connected database status
    health_resp = await async_client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["database"]["status"] == "connected"
