import pytest
import math
from datetime import datetime, timezone
from httpx import AsyncClient

from app.models.simulation import ManeuverType, ScenarioType
from app.services.simulation_engine import simulation_engine, EARTH_MU, EARTH_RADIUS_KM, G0_M_S2
from app.models.simulation import HypotheticalScenarioRequest


def test_clohessy_wiltshire_dynamics():
    """
    Test Hill-Clohessy-Wiltshire relative motion equations:
    - Secular along-track drift for in-track burn: dy ~ -3 * dvt * dt
    - Cross-track harmonic isolation
    - Zero burn leaves zero displacement
    """
    sma = 6800.0  # km (~422 km altitude)
    n = math.sqrt(EARTH_MU / (sma ** 3))

    # 1. Zero burn
    dr0, dy0, dz0 = simulation_engine.compute_clohessy_wiltshire_perturbation(sma, 0.0, 0.0, 0.0, 3600.0)
    assert dr0 == 0.0
    assert dy0 == 0.0
    assert dz0 == 0.0

    # 2. In-track prograde burn (+1 m/s) over 1 full orbit (T = 2*pi/n)
    period = 2.0 * math.pi / n
    dr_t, dy_t, dz_t = simulation_engine.compute_clohessy_wiltshire_perturbation(sma, 0.0, 1.0, 0.0, period)
    # At t = period: sin(n*T) = 0, cos(n*T) = 1
    # dr = (2*dvt/n)*(1 - 1) = 0
    # dy = -3 * dvt * T
    expected_dy = (1.0 / 1000.0) * (-3.0 * n * period) / n  # in km
    assert abs(dr_t) < 1e-4
    assert abs(dy_t - expected_dy) < 1e-3
    assert dz_t == 0.0

    # 3. Pure cross-track burn (+2 m/s)
    # dz = (dvn/n) * sin(nt), dr = 0, dy = 0
    dr_n, dy_n, dz_n = simulation_engine.compute_clohessy_wiltshire_perturbation(sma, 0.0, 0.0, 2.0, period / 4.0)
    assert dr_n == 0.0
    assert dy_n == 0.0
    assert dz_n > 0.0


def test_tsiolkovsky_fuel_computation():
    """
    Test Tsiolkovsky Rocket Equation propellant mass consumption:
    delta_m = m_total * (1 - exp(-delta_v / (Isp * g0)))
    """
    # 1. Zero delta-v
    fuel0 = simulation_engine.calculate_propellant_consumption(420000.0, 0.0, 310.0)
    assert fuel0 == 0.0

    # 2. ISS scale: 420,000 kg, dv = 1.0 m/s, Isp = 310 s
    ve = 310.0 * G0_M_S2
    expected_fuel = 420000.0 * (1.0 - math.exp(-1.0 / ve))
    calculated_fuel = simulation_engine.calculate_propellant_consumption(420000.0, 1.0, 310.0)
    assert abs(calculated_fuel - round(expected_fuel, 3)) < 0.01

    # 3. SmallSat: 500 kg, dv = 5.0 m/s, Isp = 220 s
    small_fuel = simulation_engine.calculate_propellant_consumption(500.0, 5.0, 220.0)
    assert small_fuel > 0.0
    assert small_fuel < 500.0


def test_candidate_maneuver_generation():
    """
    Test candidate maneuver generation:
    - 5 diverse candidates produced (Prograde, Retrograde, Radial, Normal, Hohmann)
    - Ranked by composite score
    - Valid CARA collision risk reductions
    """
    candidates = simulation_engine.generate_candidate_maneuvers(
        initial_miss_km=0.45,
        desired_miss_km=8.0,
        relative_velocity_kms=14.2,
        lead_time_hours=24.0,
        semi_major_axis_km=6800.0,
        spacecraft_dry_mass_kg=420000.0,
        spacecraft_propellant_mass_kg=2500.0,
        thruster_isp_seconds=310.0
    )

    assert len(candidates) == 5
    types = {c.maneuver_type for c in candidates}
    assert ManeuverType.PROGRADE_PHASING in types
    assert ManeuverType.RETROGRADE_PHASING in types
    assert ManeuverType.RADIAL_BOOST in types
    assert ManeuverType.OUT_OF_PLANE_NORMAL in types
    assert ManeuverType.OPTIMAL_HOHMANN_PHASING in types

    ranks = [c.recommendation_rank for c in candidates]
    assert ranks == [1, 2, 3, 4, 5]

    assert candidates[0].post_maneuver_collision_prob < 1e-4

    for c in candidates:
        assert c.delta_v_ms > 0.0
        assert c.fuel_mass_kg > 0.0
        assert c.projected_miss_distance_km > 0.45
        assert c.residual_fuel_budget_kg <= 2500.0
        assert c.fuel_efficiency_km_per_kg > 0.0
        assert 0.0 <= c.post_maneuver_collision_prob <= 1.0
        assert len(c.delta_v_vector_lvlh) == 3


def test_trajectory_comparison():
    """
    Test trajectory comparison between unperturbed baseline and post-burn orbit.
    """
    candidates = simulation_engine.generate_candidate_maneuvers(
        initial_miss_km=0.50,
        desired_miss_km=8.0,
        relative_velocity_kms=12.0,
        lead_time_hours=12.0,
        semi_major_axis_km=6800.0,
        spacecraft_dry_mass_kg=1000.0,
        spacecraft_propellant_mass_kg=100.0,
        thruster_isp_seconds=300.0
    )
    cand = candidates[0]

    result = simulation_engine.compare_trajectories(
        candidate=cand,
        initial_miss_km=0.50,
        semi_major_axis_km=6800.0,
        lead_time_hours=12.0,
        num_steps=12
    )

    assert result.candidate_id == cand.candidate_id
    assert result.miss_distance_gain_km > 0.0
    assert len(result.trajectory_points) == 13
    assert result.trajectory_points[0].time_offset_seconds == 0.0
    assert result.trajectory_points[0].separation_delta_km == 0.0

    final_pt = result.trajectory_points[-1]
    assert final_pt.time_offset_seconds == 12.0 * 3600.0
    assert final_pt.separation_delta_km > 0.0
    assert abs(final_pt.baseline_altitude_km - (6800.0 - EARTH_RADIUS_KM)) < 0.1


def test_hypothetical_scenario_execution():
    """
    Test hypothetical scenario execution across scenario types:
    - Imminent debris close encounter
    - Fuel constrained emergency
    - Low-thrust electric phasing
    """
    # 1. Imminent debris scenario
    req_debris = HypotheticalScenarioRequest(
        scenario_id="TEST-SCEN-DEBRIS",
        scenario_type=ScenarioType.IMMINENT_DEBRIS_COLLISION,
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        initial_miss_distance_km=0.35,
        relative_velocity_kms=14.5,
        lead_time_hours=24.0,
        spacecraft_dry_mass_kg=420000.0,
        spacecraft_propellant_mass_kg=2500.0,
        thruster_isp_seconds=310.0
    )
    res_debris = simulation_engine.test_hypothetical_scenario(req_debris)
    assert res_debris.scenario_id == "TEST-SCEN-DEBRIS"
    assert res_debris.scenario_type == ScenarioType.IMMINENT_DEBRIS_COLLISION
    assert len(res_debris.candidates_evaluated) == 5
    assert res_debris.optimal_candidate.recommendation_rank == 1
    assert len(res_debris.fuel_comparison_table) == 5
    assert res_debris.trajectory_comparison.miss_distance_gain_km > 0.0
    assert "PASSED" in res_debris.secondary_risk_check["status"]
    assert "ENGINEERING DEBRIEF" in res_debris.executive_engineering_debrief

    # 2. Fuel constrained scenario
    req_fuel = HypotheticalScenarioRequest(
        scenario_id="TEST-SCEN-FUEL",
        scenario_type=ScenarioType.FUEL_CONSTRAINED_EMERGENCY,
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=41234,
        secondary_name="COSMOS 1408 DEBRIS",
        initial_miss_distance_km=0.40,
        relative_velocity_kms=13.0,
        lead_time_hours=18.0,
        spacecraft_dry_mass_kg=1200.0,
        spacecraft_propellant_mass_kg=15.0,
        thruster_isp_seconds=285.0,
        max_fuel_budget_kg=2.0
    )
    res_fuel = simulation_engine.test_hypothetical_scenario(req_fuel)
    assert res_fuel.scenario_type == ScenarioType.FUEL_CONSTRAINED_EMERGENCY
    assert any("within_budget" in entry for entry in res_fuel.fuel_comparison_table)


@pytest.mark.asyncio
async def test_simulation_api_endpoints(async_client: AsyncClient):
    """
    Test Week 9 Simulation Laboratory REST API endpoints:
    - POST /api/simulation/candidates
    - POST /api/simulation/compare-trajectories
    - POST /api/simulation/scenarios/run
    - GET /api/simulation/scenarios/presets
    """
    # 1. Preset scenarios
    res_presets = await async_client.get("/api/simulation/scenarios/presets")
    assert res_presets.status_code == 200
    presets_data = res_presets.json()
    presets = presets_data.get("presets", [])
    assert len(presets) >= 4
    preset_types = [p["scenario_type"] for p in presets]
    assert ScenarioType.IMMINENT_DEBRIS_COLLISION.value in preset_types

    # 2. Candidate generation endpoint
    res_cand = await async_client.post(
        "/api/simulation/candidates",
        json={
            "initial_miss_distance_km": 0.45,
            "desired_miss_distance_km": 8.0,
            "relative_velocity_kms": 14.2,
            "lead_time_hours": 24.0,
            "spacecraft_dry_mass_kg": 420000.0,
            "spacecraft_propellant_mass_kg": 2500.0,
            "thruster_isp_seconds": 310.0
        }
    )
    assert res_cand.status_code == 200
    candidates = res_cand.json()
    assert len(candidates) == 5
    assert candidates[0]["recommendation_rank"] == 1

    # 3. Trajectory comparison endpoint
    res_traj = await async_client.post(
        "/api/simulation/compare-trajectories",
        json={
            "delta_v_radial_ms": 0.0,
            "delta_v_in_track_ms": 0.85,
            "delta_v_cross_track_ms": 0.0,
            "initial_miss_distance_km": 0.45,
            "semi_major_axis_km": 6800.0,
            "lead_time_hours": 24.0,
            "num_steps": 12
        }
    )
    assert res_traj.status_code == 200
    traj_data = res_traj.json()
    assert traj_data["miss_distance_gain_km"] > 0.0
    assert len(traj_data["trajectory_points"]) == 13

    # 4. Run scenario endpoint
    res_run = await async_client.post(
        "/api/simulation/scenarios/run",
        json={
            "scenario_id": "API-RUN-001",
            "scenario_type": "IMMINENT_DEBRIS_COLLISION",
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 39872,
            "secondary_name": "FENGYUN 1C DEBRIS",
            "initial_miss_distance_km": 0.40,
            "relative_velocity_kms": 14.2,
            "lead_time_hours": 24.0,
            "spacecraft_dry_mass_kg": 420000.0,
            "spacecraft_propellant_mass_kg": 2500.0,
            "thruster_isp_seconds": 310.0
        }
    )
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["scenario_id"] == "API-RUN-001"
    assert len(run_data["candidates_evaluated"]) == 5
    assert run_data["optimal_candidate"]["candidate_id"] is not None
    assert len(run_data["fuel_comparison_table"]) == 5
    assert "trajectory_comparison" in run_data
    assert "secondary_risk_check" in run_data
    assert "executive_engineering_debrief" in run_data
