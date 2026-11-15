import pytest
from datetime import datetime, timezone, timedelta
from app.services.conjunction_engine import conjunction_screening_engine
from app.models.conjunction import RiskLevel, ConjunctionStatus
from httpx import AsyncClient


def test_broad_phase_filtering():
    # Primary: ISS at 415-422 km
    p_apogee = 422.0
    p_perigee = 415.0

    candidates = [
        {"norad_id": 1, "name": "LEO-1", "perigee_km": 410.0, "apogee_km": 430.0},  # Intersects
        {"norad_id": 2, "name": "LEO-2", "perigee_km": 460.0, "apogee_km": 480.0},  # Within 50km margin
        {"norad_id": 3, "name": "GEO-1", "perigee_km": 35780.0, "apogee_km": 35800.0}, # Out of bounds
        {"norad_id": 4, "name": "VLEO", "perigee_km": 200.0, "apogee_km": 250.0},   # Out of bounds
    ]

    filtered = conjunction_screening_engine.broad_phase_filter(
        primary_apogee_km=p_apogee,
        primary_perigee_km=p_perigee,
        candidates=candidates,
        altitude_margin_km=50.0
    )

    passed_ids = [c["norad_id"] for c in filtered]
    assert 1 in passed_ids
    assert 2 in passed_ids
    assert 3 not in passed_ids
    assert 4 not in passed_ids


def test_risk_classification():
    # Critical risk (< 1.0 km)
    lvl_crit, score_crit = conjunction_screening_engine.compute_risk_classification(0.4, 12.0)
    assert lvl_crit == RiskLevel.CRITICAL
    assert score_crit >= 90.0

    # High risk (1.0 - 3.0 km)
    lvl_high, score_high = conjunction_screening_engine.compute_risk_classification(2.1, 10.0)
    assert lvl_high == RiskLevel.HIGH
    assert 70.0 <= score_high < 90.0

    # Medium risk (3.0 - 10.0 km)
    lvl_med, score_med = conjunction_screening_engine.compute_risk_classification(7.5, 9.0)
    assert lvl_med == RiskLevel.MEDIUM
    assert 40.0 <= score_med < 70.0

    # Low risk (> 10.0 km)
    lvl_low, score_low = conjunction_screening_engine.compute_risk_classification(20.0, 5.0)
    assert lvl_low == RiskLevel.LOW
    assert score_low < 40.0


@pytest.mark.asyncio
async def test_conjunction_screening_api(async_client: AsyncClient):
    # First sync catalog with sample data
    sync_resp = await async_client.post("/api/catalog/sync?groups=stations")
    assert sync_resp.status_code == 200

    # Screen ISS (25544) with broad 100km threshold
    screen_resp = await async_client.post(
        "/api/conjunctions/screen",
        json={
            "primary_norad_id": 25544,
            "horizon_hours": 12.0,
            "threshold_km": 50.0,
            "altitude_margin_km": 50.0
        }
    )
    assert screen_resp.status_code == 200
    screen_data = screen_resp.json()
    assert screen_data["status"] == "success"
    assert "candidates_screened" in screen_data

    # Query conjunction list endpoint
    list_resp = await async_client.get("/api/conjunctions")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert "items" in list_data
    assert "total" in list_data
