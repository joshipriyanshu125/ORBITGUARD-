import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient

from app.services.collision_assessment import collision_assessment_engine
from app.models.collision_assessment import (
    EncounterGeometry,
    UncertaintyData,
    ProbabilisticAssessment,
    OperationalActionCategory,
    NASACARATier
)


def test_miss_distance_and_lvlh_b_plane_calculation():
    # Primary: ISS at [6800, 0, 0] moving along Y at [0, 7.6, 0]
    r1 = np.array([6800.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.6, 0.0])

    # Secondary: [6800.8, 1.2, 0.5] moving head-on at [0, -7.4, 0]
    r2 = np.array([6800.8, 1.2, 0.5])
    v2 = np.array([0.0, -7.4, 0.0])

    geom = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2, v2)

    # 1. Euclidean miss distance norm
    expected_dist = float(np.linalg.norm(r2 - r1))
    assert abs(geom.miss_distance_km - expected_dist) < 1e-3
    assert 1.4 < geom.miss_distance_km < 1.6

    # 2. LVLH RIC components
    assert abs(geom.radial_miss_km - 0.8) < 1e-2  # Radial separation along X
    assert abs(geom.in_track_miss_km - 1.2) < 1e-2 # In-track along Y
    assert abs(geom.cross_track_miss_km - 0.5) < 1e-2 # Cross-track along Z

    # 3. Relative dynamics
    assert abs(geom.relative_velocity_kms - 15.0) < 1e-2  # 7.6 - (-7.4) = 15.0 km/s
    assert geom.relative_kinetic_energy_mj_kg > 100.0   # 0.5 * 15^2 = 112.5 MJ/kg

    # 4. B-plane encounter frame
    assert abs(geom.impact_parameter_km - math_norm(geom.b_plane_x_km, geom.b_plane_z_km)) < 1e-3
    assert geom.impact_parameter_km > 0.0


def math_norm(x: float, y: float) -> float:
    return float(np.sqrt(x**2 + y**2))


def test_uncertainty_incorporation_cdm_and_sgp4():
    r1 = np.array([6800.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.6, 0.0])
    r2 = np.array([6801.0, 0.5, 0.0])
    v2 = np.array([0.0, -7.4, 0.0])
    geom = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2, v2)

    # 1. Physics-informed SGP4 empirical drag growth model
    unc_sgp4 = collision_assessment_engine.incorporate_uncertainty(
        geometry=geom,
        hard_body_radius_m=20.0,
        bstar_primary=0.00015,
        bstar_secondary=0.00030,
        lead_time_hours=48.0
    )
    assert "SGP4 Drag Growth" in unc_sgp4.covariance_source
    assert unc_sgp4.hard_body_radius_km == 0.02
    assert unc_sgp4.sigma_radial_km > 0.05
    assert unc_sgp4.sigma_in_track_km > unc_sgp4.sigma_radial_km  # In-track error dominates
    assert unc_sgp4.mahalanobis_distance >= 0.0

    # 2. Explicit CDM covariance integration
    cov1 = np.diag([0.01, 0.25, 0.04])  # 3x3 variance
    cov2 = np.diag([0.02, 0.36, 0.05])
    unc_cdm = collision_assessment_engine.incorporate_uncertainty(
        geometry=geom,
        primary_cov=cov1,
        secondary_cov=cov2,
        hard_body_radius_m=25.0
    )
    assert "CDM" in unc_cdm.covariance_source
    assert unc_cdm.hard_body_radius_km == 0.025
    assert abs(unc_cdm.sigma_radial_km - np.sqrt(0.01 + 0.02)) < 1e-3


def test_probabilistic_risk_assessment_foster_and_monte_carlo():
    r1 = np.array([6800.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.6, 0.0])

    # Very close encounter (miss = 0.03 km, HBR = 25m)
    r2_crit = np.array([6800.02, 0.02, 0.01])
    v2_crit = np.array([0.0, -7.4, 0.0])
    geom_crit = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2_crit, v2_crit)
    unc_crit = collision_assessment_engine.incorporate_uncertainty(geom_crit, hard_body_radius_m=25.0)

    prob_crit = collision_assessment_engine.evaluate_probabilistic_risk(geom_crit, unc_crit, n_mc_trials=5000)

    assert prob_crit.collision_probability > 1e-4
    assert prob_crit.nasa_cara_tier == NASACARATier.RED_ALERT
    assert prob_crit.operational_severity == "CRITICAL"
    assert prob_crit.monte_carlo_hits > 0
    assert prob_crit.max_possible_pc >= prob_crit.collision_probability
    assert len(prob_crit.confidence_interval_95) == 2

    # Distant encounter (miss = 30 km)
    r2_safe = np.array([6825.0, 15.0, 5.0])
    geom_safe = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2_safe, v2_crit)
    unc_safe = collision_assessment_engine.incorporate_uncertainty(geom_safe, hard_body_radius_m=10.0)

    prob_safe = collision_assessment_engine.evaluate_probabilistic_risk(geom_safe, unc_safe, n_mc_trials=1000)
    assert prob_safe.collision_probability < 1e-7
    assert prob_safe.nasa_cara_tier == NASACARATier.GREEN
    assert prob_safe.operational_severity == "NOMINAL"
    assert prob_safe.monte_carlo_hits == 0


def test_event_ranking_multi_criteria_upi():
    now = datetime.now(timezone.utc)
    events = [
        {
            "event_id": "EVT-CRITICAL",
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 39872,
            "secondary_name": "FENGYUN 1C DEBRIS",
            "secondary_type": "DEBRIS",
            "tca": (now + timedelta(hours=8)).isoformat(),
            "lead_time_hours": 8.0,
            "miss_distance_km": 0.25,
            "radial_miss_km": 0.05,
            "relative_velocity_kms": 14.5,
            "collision_probability": 4.2e-4,
            "risk_score": 96.0
        },
        {
            "event_id": "EVT-SAFE",
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 99999,
            "secondary_name": "DISTANT COLD OBJECT",
            "secondary_type": "PAYLOAD",
            "tca": (now + timedelta(hours=96)).isoformat(),
            "lead_time_hours": 96.0,
            "miss_distance_km": 35.0,
            "radial_miss_km": 8.5,
            "relative_velocity_kms": 6.2,
            "collision_probability": 1.2e-9,
            "risk_score": 15.0
        },
        {
            "event_id": "EVT-ELEVATED",
            "primary_norad_id": 48274,
            "primary_name": "STARLINK-2541",
            "secondary_norad_id": 34125,
            "secondary_name": "COSMOS 2251 DEBRIS",
            "secondary_type": "DEBRIS",
            "tca": (now + timedelta(hours=36)).isoformat(),
            "lead_time_hours": 36.0,
            "miss_distance_km": 2.1,
            "radial_miss_km": 0.4,
            "relative_velocity_kms": 11.2,
            "collision_probability": 2.5e-6,
            "risk_score": 68.0
        }
    ]

    ranking_resp = collision_assessment_engine.rank_conjunction_events(events)

    assert ranking_resp.total_events_evaluated == 3
    assert ranking_resp.ranked_queue[0].event_id == "EVT-CRITICAL"
    assert ranking_resp.ranked_queue[0].rank == 1
    assert ranking_resp.ranked_queue[0].action_category == OperationalActionCategory.IMMEDIATE_ACTION_REQUIRED

    assert ranking_resp.ranked_queue[-1].event_id == "EVT-SAFE"
    assert ranking_resp.ranked_queue[-1].rank == 3
    assert ranking_resp.ranked_queue[-1].action_category == OperationalActionCategory.ROUTINE_MONITORING

    assert ranking_resp.immediate_action_count == 1
    assert ranking_resp.routine_count == 1


def test_explainability_report_synthesis():
    now = datetime.now(timezone.utc)
    r1 = np.array([6800.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.6, 0.0])
    r2 = np.array([6800.4, 0.8, 0.2])
    v2 = np.array([0.0, -7.2, 0.0])

    assessment = collision_assessment_engine.assess_collision(
        event_id="CONJ-TEST-EXPLAIN-1",
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        secondary_type="DEBRIS",
        r1_eci=r1,
        v1_eci=v1,
        r2_eci=r2,
        v2_eci=v2,
        tca=now + timedelta(hours=18),
        lead_time_hours=18.0,
        hard_body_radius_m=20.0
    )

    report = assessment.explainability_report

    # 1. Executive summary
    assert "ISS (ZARYA)" in report.executive_summary
    assert "FENGYUN 1C DEBRIS" in report.executive_summary
    assert "NASA CARA" in report.executive_summary

    # 2. Physics & geometry breakdown
    assert "LVLH (RIC)" in report.geometry_explanation
    assert "Radial separation" in report.geometry_explanation

    # 3. Uncertainty audit
    assert "Uncertainty model" in report.uncertainty_explanation
    assert "Mahalanobis" in report.uncertainty_explanation

    # 4. Probabilistic explanation
    assert "Foster" in report.probabilistic_explanation
    assert "Monte Carlo" in report.probabilistic_explanation

    # 5. Sensitivity analysis
    assert "hard_body_radius_variations" in report.sensitivity_analysis
    assert "miss_distance_sensitivity" in report.sensitivity_analysis
    assert "max_possible_pc_under_current_covariance" in report.sensitivity_analysis

    # 6. HITL Directive
    assert "Human-In-The-Loop" in report.hitl_recommendation


@pytest.mark.asyncio
async def test_collision_assessment_api_endpoints(async_client: AsyncClient):
    # 1. Evaluate endpoint
    eval_resp = await async_client.post(
        "/api/collision-assessment/evaluate",
        json={
            "primary_norad_id": 25544,
            "primary_name": "ISS (ZARYA)",
            "secondary_norad_id": 39872,
            "secondary_name": "FENGYUN 1C DEBRIS",
            "secondary_type": "DEBRIS",
            "primary_position_eci": [6800.0, 0.0, 0.0],
            "primary_velocity_eci": [0.0, 7.6, 0.0],
            "secondary_position_eci": [6800.5, 0.6, 0.3],
            "secondary_velocity_eci": [0.0, -7.4, 0.0],
            "lead_time_hours": 16.0,
            "hard_body_radius_m": 18.0
        }
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["primary_norad_id"] == 25544
    assert "geometry" in eval_data
    assert "uncertainty" in eval_data
    assert "probabilistic" in eval_data
    assert "explainability_report" in eval_data
    assert eval_data["geometry"]["miss_distance_km"] > 0.0

    # 2. Ranking endpoint returns only stored events; never a synthetic benchmark queue
    rank_resp = await async_client.post(
        "/api/collision-assessment/rank",
        json={}
    )
    assert rank_resp.status_code == 200
    rank_data = rank_resp.json()
    assert rank_data["status"] == "success"
    assert len(rank_data["ranked_queue"]) == rank_data["total_events_evaluated"]
    if rank_data["ranked_queue"]:
        assert rank_data["ranked_queue"][0]["rank"] == 1

    # 3. Unknown explainability report is a real 404, not a fabricated event
    report_resp = await async_client.get("/api/collision-assessment/report/CONJ-TEST-SAMPLE")
    assert report_resp.status_code == 404
