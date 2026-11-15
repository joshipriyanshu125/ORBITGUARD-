import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.services.celestrak import celestrak_service
from app.services.sgp4_engine import sgp4_engine


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "ORBITGUARD AI"
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_catalog_sync_and_retrieval(async_client: AsyncClient):
    # 1. Trigger catalog sync with stations group
    sync_resp = await async_client.post("/api/catalog/sync?groups=stations")
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["status"] == "success"
    assert sync_data["synced_total"] > 0

    # 2. List satellites
    list_resp = await async_client.get("/api/satellites?limit=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] > 0
    assert len(list_data["items"]) > 0

    # Find ISS
    iss_item = next((item for item in list_data["items"] if item["norad_id"] == 25544), None)
    assert iss_item is not None
    assert iss_item["norad_id"] == 25544

    # 3. Retrieve single satellite
    sat_resp = await async_client.get("/api/satellites/25544")
    assert sat_resp.status_code == 200
    sat_data = sat_resp.json()
    assert sat_data["norad_id"] == 25544
    assert "disclaimer" in sat_data

    # 4. Check orbit propagation endpoint
    orbit_resp = await async_client.get("/api/satellites/25544/orbit?duration_hours=2.0&step_seconds=300")
    assert orbit_resp.status_code == 200
    orbit_data = orbit_resp.json()
    assert orbit_data["norad_id"] == 25544
    assert orbit_data["point_count"] > 10
    assert len(orbit_data["points"]) == orbit_data["point_count"]
    first_pt = orbit_data["points"][0]
    assert "latitude_deg" in first_pt
    assert "longitude_deg" in first_pt
    assert "altitude_km" in first_pt
    assert "disclaimer" in orbit_data

    # 5. Non-existent satellite returns 404
    not_found_resp = await async_client.get("/api/satellites/9999999")
    assert not_found_resp.status_code == 404


def test_root_and_system_disclaimer():
    assert settings.PROJECT_NAME == "ORBITGUARD AI"
    assert "analytical and illustrative orbital assessments" in settings.SYSTEM_DISCLAIMER
    assert "Explicit human-in-the-loop authorization is required" in settings.SYSTEM_DISCLAIMER


def test_catalog_station_fixtures():
    satellites = celestrak_service.get_offline_sample_data("stations")
    assert len(satellites) > 0
    iss = next((s for s in satellites if s.norad_id == 25544), None)
    assert iss is not None
    assert iss.norad_id == 25544
    assert iss.name == "ISS (ZARYA)"
    assert 400.0 < iss.apogee_km < 440.0


def test_satellite_orbit_propagation_service():
    satellites = celestrak_service.get_offline_sample_data("stations")
    iss = next(s for s in satellites if s.norad_id == 25544)
    res = sgp4_engine.propagate_orbit_path(
        norad_id=iss.norad_id,
        name=iss.name,
        tle_line1=iss.tle_line1,
        tle_line2=iss.tle_line2,
        epoch=iss.epoch,
        start_time=iss.epoch,
        duration_hours=2.0,
        step_seconds=300
    )
    points = res.points
    assert len(points) > 10
    first_pt = points[0]
    assert first_pt.latitude_deg is not None
    assert first_pt.longitude_deg is not None
    assert first_pt.altitude_km is not None
    assert 400.0 < first_pt.altitude_km < 450.0
