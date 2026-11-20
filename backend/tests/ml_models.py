import pytest
import numpy as np
from datetime import datetime, timezone
from app.ml.lstm_residual_model import trajectory_residual_model
from app.ml.anomaly_model import anomaly_detector
from app.ml.risk_model import conjunction_risk_model
from app.ml.mission_intelligence import mission_intelligence_engine
from app.ml.analytics import visual_ml_analytics
from app.models.conjunction import ConjunctionBase, RiskLevel
from app.db.repositories.conjunction_repo import conjunction_repo
from httpx import AsyncClient


def test_gru_trajectory_residual_model():
    # Sequence of 10 residual states: [dx, dy, dz, vx, vy, vz, bstar]
    seq = np.random.normal(loc=0.0, scale=0.05, size=(10, 7))
    result = trajectory_residual_model.predict_residuals(seq)
    
    assert "predicted_residual_km" in result
    assert len(result["predicted_residual_km"]) == 3
    assert result["residual_magnitude_km"] >= 0.0
    assert result["trajectory_confidence_pct"] > 0.0


def test_anomaly_detector_nominal_vs_maneuver():
    # 1. Nominal small decay
    nominal_deltas = {
        "delta_semi_major_axis_km_day": -0.015,
        "delta_eccentricity_day": 0.00001,
        "delta_inclination_deg_day": 0.0002,
        "delta_bstar_day": 0.00001,
        "delta_energy_day": -0.00005
    }
    nom_res = anomaly_detector.evaluate_deltas(nominal_deltas)
    assert nom_res["anomaly_score"] < 0.50
    assert not nom_res["is_anomalous"]
    assert not nom_res["is_maneuver_signature"]

    # 2. Large unannounced impulsive maneuver (+1.5 km altitude boost)
    maneuver_deltas = {
        "delta_semi_major_axis_km_day": 1.5,
        "delta_eccentricity_day": 0.001,
        "delta_inclination_deg_day": 0.05,
        "delta_bstar_day": 0.00002,
        "delta_energy_day": 0.006
    }
    man_res = anomaly_detector.evaluate_deltas(maneuver_deltas)
    assert man_res["anomaly_score"] >= 0.50
    assert man_res["is_anomalous"]
    assert man_res["is_maneuver_signature"]


def test_conjunction_risk_classification():
    # Critical encounter: miss = 0.5 km, vel = 14.5 km/s
    crit_vec = np.array([0.5, 14.5, 12.0, 1.0, 420.0, 0.6, 0.5 * 14.5**2])
    crit_res = conjunction_risk_model.predict_risk(crit_vec)
    assert crit_res["predicted_risk_level"] in [RiskLevel.CRITICAL.value, RiskLevel.HIGH.value]
    assert crit_res["priority_score"] >= 70.0
    assert "miss_distance_km" in crit_res["feature_contributions"]

    # Safe encounter: miss = 25 km, vel = 6.0 km/s
    safe_vec = np.array([25.0, 6.0, 72.0, 0.0, 420.0, 0.05, 0.5 * 6.0**2])
    safe_res = conjunction_risk_model.predict_risk(safe_vec)
    assert safe_res["predicted_risk_level"] == RiskLevel.LOW.value
    assert safe_res["priority_score"] < 50.0


def test_visual_ml_analytics():
    importances = visual_ml_analytics.get_risk_feature_importance_chart()
    assert len(importances) == len(conjunction_risk_model.FEATURE_NAMES)
    assert importances[0]["importance"] >= importances[-1]["importance"]

    b_plane = visual_ml_analytics.get_b_plane_encounter_visualization(1.42, 0.8, 0.5)
    assert "ellipse_points" in b_plane
    assert len(b_plane["ellipse_points"]) > 0

    benchmarks = visual_ml_analytics.get_model_evaluation_metrics()
    assert "model_1_lstm_residual" in benchmarks
    assert "model_2_anomaly_detector" in benchmarks
    assert "model_3_risk_prioritization" in benchmarks
    assert "model_4_collision_probability" in benchmarks
    assert "model_5_mission_intelligence" in benchmarks


def test_ml_pipeline_and_mission_brief_generation():
    # 1. Anomaly model evaluation
    deltas = {"delta_semi_major_axis_km_day": -0.02, "delta_energy_day": -0.0001}
    ano_res = anomaly_detector.evaluate_deltas(deltas)
    assert "anomaly_score" in ano_res
    assert "is_anomalous" in ano_res

    # 2. Risk model evaluation
    rel_ke = 0.5 * (13.0 ** 2)
    risk_vec = np.array([1.2, 13.0, 24.0, 1.0, 420.0, 0.45, rel_ke])
    risk_res = conjunction_risk_model.predict_risk(risk_vec)
    assert risk_res["predicted_risk_level"] in [RiskLevel.CRITICAL.value, RiskLevel.HIGH.value]
    assert "priority_score" in risk_res

    # 3. Visual analytics payload
    chart = visual_ml_analytics.get_risk_feature_importance_chart()
    assert len(chart) > 0
    assert "feature" in chart[0]

    # 4. Mission brief expert report synthesis
    brief = mission_intelligence_engine._generate_deterministic_brief(
        p_name="ISS (ZARYA)",
        p_id=25544,
        s_name="FENGYUN 1C DEBRIS",
        s_id=39872,
        tca="2026-11-16T14:22:15Z",
        miss_km=1.42,
        rel_vel=13.85,
        risk_lvl="HIGH",
        ano_score=ano_res["anomaly_score"],
        ano_diag="NOMINAL",
        pc_sci="1.240e-04",
        cara_tier="RED_ALERT",
        operator_query="Is there collision danger for ISS?"
    )
    assert "executive_summary" in brief
    assert "technical_findings" in brief
    assert "recommended_action" in brief


@pytest.mark.asyncio
async def test_ml_api_endpoints(async_client: AsyncClient):
    # 1. Anomaly evaluate endpoint
    ano_resp = await async_client.post(
        "/api/ml/anomaly/evaluate",
        json={
            "delta_semi_major_axis_km_day": -0.015,
            "delta_eccentricity_day": 0.00001,
            "delta_inclination_deg_day": 0.0002,
            "delta_bstar_day": 0.00001,
            "delta_energy_day": -0.00005
        }
    )
    assert ano_resp.status_code == 200
    ano_data = ano_resp.json()
    assert ano_data["status"] == "success"
    assert "anomaly_assessment" in ano_data

    # Anomaly evaluation with unknown norad_id returns 404
    ano_not_found = await async_client.post(
        "/api/ml/anomaly/evaluate",
        json={"norad_id": 9999999}
    )
    assert ano_not_found.status_code == 404

    # 2. Conjunction risk endpoint
    risk_resp = await async_client.post(
        "/api/ml/conjunction/risk",
        json={
            "miss_distance_km": 1.42,
            "relative_velocity_kms": 12.5,
            "lead_time_hours": 24.0,
            "secondary_is_debris": True,
            "primary_altitude_km": 415.0,
            "ml_anomaly_score": 0.1
        }
    )
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["status"] == "success"
    assert "conjunction_risk" in risk_data

    # 3. Collision probability endpoint
    prob_resp = await async_client.post(
        "/api/ml/collision/probability",
        json={
            "miss_distance_km": 1.42,
            "hard_body_radius_m": 15.0,
            "sigma_x_km": 0.8,
            "sigma_y_km": 0.5,
            "run_monte_carlo": True
        }
    )
    assert prob_resp.status_code == 200
    prob_data = prob_resp.json()
    assert prob_data["status"] == "success"
    assert "analytical_foster" in prob_data
    assert "monte_carlo_simulation" in prob_data

    # 4. Visual analytics endpoint
    vis_resp = await async_client.get("/api/ml/visual-analytics")
    assert vis_resp.status_code == 200
    vis_data = vis_resp.json()
    assert vis_data["status"] == "success"
    assert "risk_feature_importances" in vis_data
    assert "b_plane_visualization" in vis_data
    assert "model_benchmarks" in vis_data

    # 5. Mission brief endpoint requires a cataloged asset and a stored conjunction
    await async_client.post("/api/catalog/sync?groups=stations")
    await conjunction_repo.upsert_conjunction(ConjunctionBase(
        event_id="CONJ-ML-TEST",
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        secondary_type="DEBRIS",
        tca=datetime.now(timezone.utc),
        miss_distance_km=1.42,
        relative_velocity_kms=12.8,
        risk_level=RiskLevel.CRITICAL
    ))

    brief_resp = await async_client.post(
        "/api/ml/mission-brief",
        json={
            "event_id": "CONJ-ML-TEST",
            "primary_norad_id": 25544,
            "query": "Assess collision threat with Chinese Fengyun debris"
        }
    )
    assert brief_resp.status_code == 200
    brief_data = brief_resp.json()
    assert "executive_summary" in brief_data
    assert "technical_findings" in brief_data

    missing_brief = await async_client.post(
        "/api/ml/mission-brief",
        json={"event_id": "CONJ-UNKNOWN", "primary_norad_id": 25544}
    )
    assert missing_brief.status_code == 404
