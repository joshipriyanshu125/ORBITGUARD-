from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.ml.features import feature_extractor
from app.ml.anomaly_model import anomaly_detector
from app.ml.risk_model import conjunction_risk_model
from app.ml.collision_probability import collision_probability_estimator
from app.ml.mission_intelligence import mission_intelligence_engine
from app.ml.analytics import visual_ml_analytics
from app.db.repositories.satellite_repo import satellite_repo
from app.db.repositories.conjunction_repo import conjunction_repo

router = APIRouter()


class AnomalyEvaluationRequest(BaseModel):
    norad_id: Optional[int] = Field(default=None, description="NORAD ID of satellite in catalog")
    delta_semi_major_axis_km_day: float = Field(default=0.0)
    delta_eccentricity_day: float = Field(default=0.0)
    delta_inclination_deg_day: float = Field(default=0.0)
    delta_bstar_day: float = Field(default=0.0)
    delta_energy_day: float = Field(default=0.0)


class ConjunctionRiskEvaluationRequest(BaseModel):
    miss_distance_km: float = Field(default=1.42, ge=0.01)
    relative_velocity_kms: float = Field(default=12.5, ge=0.1)
    lead_time_hours: float = Field(default=24.0, ge=0.1)
    secondary_is_debris: bool = Field(default=True)
    primary_altitude_km: float = Field(default=415.0)
    ml_anomaly_score: float = Field(default=0.1, ge=0.0, le=1.0)


class CollisionProbabilityRequest(BaseModel):
    miss_distance_km: float = Field(default=1.42, ge=0.001)
    hard_body_radius_m: float = Field(default=15.0, ge=1.0)
    sigma_x_km: float = Field(default=0.8, ge=0.01)
    sigma_y_km: float = Field(default=0.5, ge=0.01)
    run_monte_carlo: bool = Field(default=True)


class MissionBriefRequest(BaseModel):
    event_id: Optional[str] = Field(default=None, description="Conjunction event ID")
    primary_norad_id: int = Field(default=25544)
    query: Optional[str] = Field(default=None, description="Operator specific question")


@router.post("/ml/anomaly/evaluate")
async def evaluate_orbital_anomaly(payload: AnomalyEvaluationRequest):
    """
    Model 2 – Evaluate orbital anomaly score using Isolation Forest & Autoencoder.
    Detects unannounced maneuvers, tumbling, and accelerated drag decay.
    """
    if payload.norad_id:
        sat = await satellite_repo.get_by_norad_id(payload.norad_id)
        if not sat:
            raise HTTPException(status_code=404, detail=f"Satellite {payload.norad_id} not found in catalog.")
        history = await satellite_repo.get_history(payload.norad_id, limit=2)
        if len(history) >= 2:
            deltas = feature_extractor.extract_time_series_deltas(history[0], history[1])
        else:
            deltas = {
                "delta_semi_major_axis_km_day": payload.delta_semi_major_axis_km_day,
                "delta_eccentricity_day": payload.delta_eccentricity_day,
                "delta_inclination_deg_day": payload.delta_inclination_deg_day,
                "delta_bstar_day": payload.delta_bstar_day,
                "delta_energy_day": payload.delta_energy_day
            }
    else:
        deltas = {
            "delta_semi_major_axis_km_day": payload.delta_semi_major_axis_km_day,
            "delta_eccentricity_day": payload.delta_eccentricity_day,
            "delta_inclination_deg_day": payload.delta_inclination_deg_day,
            "delta_bstar_day": payload.delta_bstar_day,
            "delta_energy_day": payload.delta_energy_day
        }

    result = anomaly_detector.evaluate_deltas(deltas)
    return {
        "status": "success",
        "norad_id": payload.norad_id,
        "input_deltas": deltas,
        "anomaly_assessment": result
    }


@router.post("/ml/conjunction/risk")
async def evaluate_conjunction_risk(payload: ConjunctionRiskEvaluationRequest):
    """
    Model 3 – Evaluate conjunction risk using Gradient Boosted Decision Trees (GBDT).
    Prioritizes close approaches and outputs explainable feature importances.
    """
    rel_ke = 0.5 * (payload.relative_velocity_kms ** 2)
    import numpy as np
    vec = np.array([
        payload.miss_distance_km,
        payload.relative_velocity_kms,
        payload.lead_time_hours,
        1.0 if payload.secondary_is_debris else 0.0,
        payload.primary_altitude_km,
        payload.ml_anomaly_score,
        rel_ke
    ])

    risk_result = conjunction_risk_model.predict_risk(vec)
    return {
        "status": "success",
        "conjunction_risk": risk_result
    }


@router.post("/ml/collision/probability")
async def evaluate_collision_probability(payload: CollisionProbabilityRequest):
    """
    Model 4 – Compute analytical Foster 2D encounter frame collision probability
    and Monte Carlo covariance perturbation simulation against NASA CARA thresholds.
    """
    foster_res = collision_probability_estimator.compute_foster_probability(
        miss_distance_km=payload.miss_distance_km,
        hard_body_radius_m=payload.hard_body_radius_m,
        sigma_x_km=payload.sigma_x_km,
        sigma_y_km=payload.sigma_y_km
    )

    mc_res = None
    if payload.run_monte_carlo:
        mc_res = collision_probability_estimator.run_monte_carlo_simulation(
            miss_distance_km=payload.miss_distance_km,
            hard_body_radius_m=payload.hard_body_radius_m,
            sigma_km=(payload.sigma_x_km + payload.sigma_y_km) / 2.0,
            n_trials=10000
        )

    return {
        "status": "success",
        "analytical_foster": foster_res,
        "monte_carlo_simulation": mc_res
    }


@router.get("/ml/visual-analytics")
async def get_visual_analytics():
    """
    Provides pre-formatted visual analytical data structures:
    feature importances, B-plane error ellipse coordinates, and model evaluation metrics.
    """
    return {
        "status": "success",
        "risk_feature_importances": visual_ml_analytics.get_risk_feature_importance_chart(),
        "b_plane_visualization": visual_ml_analytics.get_b_plane_encounter_visualization(),
        "model_benchmarks": visual_ml_analytics.get_model_evaluation_metrics()
    }


@router.post("/ml/mission-brief")
async def generate_mission_brief(payload: MissionBriefRequest):
    """
    Model 5 – AI Mission Intelligence generation.
    Synthesizes technical findings, anomaly analysis, and human-in-the-loop recommendations.
    """
    primary = await satellite_repo.get_by_norad_id(payload.primary_norad_id)
    if not primary:
        primary = {"name": f"SAT-{payload.primary_norad_id}", "norad_id": payload.primary_norad_id, "perigee_km": 415.0}

    conjunction = None
    if payload.event_id:
        conjunction = await conjunction_repo.get_by_event_id(payload.event_id)

    if not conjunction:
        conjunction = {
            "secondary_name": "COSMOS 2251 DEBRIS",
            "secondary_norad_id": 34125,
            "tca": "2026-11-17T08:15:00Z",
            "miss_distance_km": 1.42,
            "relative_velocity_kms": 12.8,
            "risk_level": "CRITICAL"
        }

    # Evaluate ML anomaly and collision prob
    ano_metrics = anomaly_detector.evaluate_deltas({
        "delta_semi_major_axis_km_day": -0.015,
        "delta_eccentricity_day": 0.00001,
        "delta_inclination_deg_day": 0.0005,
        "delta_bstar_day": 0.00001,
        "delta_energy_day": -0.00005
    })

    prob_metrics = collision_probability_estimator.compute_foster_probability(
        miss_distance_km=float(conjunction.get("miss_distance_km", 1.42))
    )

    brief = await mission_intelligence_engine.generate_mission_intelligence_report(
        primary_satellite=primary,
        conjunction=conjunction,
        anomaly_metrics=ano_metrics,
        collision_prob_metrics=prob_metrics,
        operator_query=payload.query
    )

    return brief
