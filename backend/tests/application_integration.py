import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_application_api_flow(async_client: AsyncClient):
    """
    Weeks 10-11 Deliverable: UI and Backend API Integration Verification.
    Verifies that all API endpoints driving the 5 application modules are operational:
    1. Mission Control Dashboard: /api/health, /api/catalog
    2. 3D Orbital Explorer: /api/propagation/{norad_id}/orbit
    3. AI Intelligence Center: /api/agents/orchestrate, /api/agents/proposals/pending
    4. Collision Risk Center: /api/collision/calculate-probability, /api/collision/explainability-report
    5. Simulation Laboratory: /api/simulation/scenarios/presets, /api/simulation/scenarios/run
    """
    # 1. Mission Control Dashboard APIs
    health_res = await async_client.get("/api/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] in ["healthy", "online"]

    # Sync stations fixture to mock DB for propagation & catalog test
    sync_res = await async_client.post("/api/catalog/sync?groups=stations")
    assert sync_res.status_code == 200

    catalog_res = await async_client.get("/api/catalog?limit=10")
    assert catalog_res.status_code == 200
    catalog_data = catalog_res.json()
    assert "data" in catalog_data or "items" in catalog_data or isinstance(catalog_data, list)

    # 2. 3D Orbital Explorer SGP4 Propagation API
    # Propagate orbit for ISS (25544)
    orbit_res = await async_client.get("/api/propagation/25544/orbit?duration_hours=2.0&step_seconds=300")
    assert orbit_res.status_code == 200
    orbit_data = orbit_res.json()
    assert "points" in orbit_data
    assert len(orbit_data["points"]) > 5
    first_pt = orbit_data["points"][0]
    assert "latitude_deg" in first_pt or "lat" in first_pt
    assert "longitude_deg" in first_pt or "lon" in first_pt
    assert "altitude_km" in first_pt or "alt_km" in first_pt

    # 3. AI Intelligence Center Multi-Agent Orchestration & HITL Approvals
    orch_res = await async_client.post(
        "/api/agents/orchestrate",
        json={
            "goal": "Screen ISS conjunctions and formulate avoidance burn proposal",
            "target_norad_id": 25544
        }
    )
    assert orch_res.status_code == 200
    orch_data = orch_res.json()
    assert "session_id" in orch_data
    assert "findings_summary" in orch_data
    assert "trace" in orch_data

    proposals_res = await async_client.get("/api/agents/proposals/pending")
    assert proposals_res.status_code == 200
    assert isinstance(proposals_res.json(), list)

    # 4. Collision Risk Center Probability & Explainability APIs
    prob_res = await async_client.post(
        "/api/collision/calculate-probability",
        json={
            "primary_r": [6800.0, 0.0, 0.0],
            "primary_v": [0.0, 7.6, 0.0],
            "secondary_r": [6800.35, 0.28, 0.15],
            "secondary_v": [0.0, -6.6, 0.0],
            "hard_body_radius_m": 15.0
        }
    )
    assert prob_res.status_code == 200
    prob_data = prob_res.json()
    assert "miss_distance_km" in prob_data
    assert prob_data["miss_distance_km"] > 0.0
    assert "nasa_cara_tier" in prob_data

    report_res = await async_client.post(
        "/api/collision/explainability-report",
        json={
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 39872,
            "secondary_name": "FENGYUN 1C DEBRIS",
            "tca": "2026-11-20T12:00:00Z",
            "miss_distance_km": 0.45,
            "relative_velocity_kms": 14.2,
            "collision_probability": 0.00035,
            "nasa_cara_tier": "RED_ALERT",
            "b_plane_xi_km": 0.28,
            "b_plane_zeta_km": 0.35,
            "recommended_burn_direction": "PROGRADE",
            "delta_v_ms": 0.85,
            "fuel_mass_kg": 118.0
        }
    )
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert "report_text" in report_data
    assert "COLLISION RISK ASSESSMENT" in report_data["report_text"]

    # 5. Simulation Laboratory APIs
    presets_res = await async_client.get("/api/simulation/scenarios/presets")
    assert presets_res.status_code == 200
    presets_data = presets_res.json()
    assert "presets" in presets_data
    assert len(presets_data["presets"]) >= 4

    run_sim_res = await async_client.post(
        "/api/simulation/scenarios/run",
        json={
            "scenario_id": "TEST-INTEGRATION-001",
            "scenario_type": "IMMINENT_DEBRIS_COLLISION",
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 39872,
            "secondary_name": "FENGYUN 1C DEBRIS",
            "initial_miss_distance_km": 0.45,
            "relative_velocity_kms": 14.2,
            "lead_time_hours": 24.0,
            "spacecraft_dry_mass_kg": 420000.0,
            "spacecraft_propellant_mass_kg": 2500.0,
            "thruster_isp_seconds": 310.0
        }
    )
    assert run_sim_res.status_code == 200
    sim_data = run_sim_res.json()
    assert len(sim_data["candidates_evaluated"]) == 5
    assert len(sim_data["fuel_comparison_table"]) == 5
    assert "trajectory_comparison" in sim_data
    assert "executive_engineering_debrief" in sim_data
