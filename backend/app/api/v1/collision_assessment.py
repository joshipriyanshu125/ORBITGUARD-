from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from pydantic import BaseModel, Field

from app.models.collision_assessment import (
    CollisionAssessmentResult,
    ConjunctionRankingResponse,
    ExplainabilityReport
)
from app.services.collision_assessment import collision_assessment_engine
from app.services.sgp4_engine import sgp4_engine
from app.db.repositories.conjunction_repo import conjunction_repo
from app.db.repositories.satellite_repo import satellite_repo

router = APIRouter()


async def _propagate_catalog_state(norad_id: int, at: datetime):
    """Return real ECI position/velocity and BSTAR for a cataloged object at a given epoch."""
    sat = await satellite_repo.get_by_norad_id(norad_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite {norad_id} not found in catalog.")
    try:
        satrec = sgp4_engine.build_satrec(sat["tle_line1"], sat["tle_line2"])
        point = sgp4_engine.propagate_single(satrec, at)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not propagate satellite {norad_id}: {exc}")
    if point is None:
        raise HTTPException(status_code=422, detail=f"SGP4 propagation failed for satellite {norad_id} at TCA.")
    r = np.array([point.x_km, point.y_km, point.z_km], dtype=np.float64)
    v = np.array([point.vx_kms, point.vy_kms, point.vz_kms], dtype=np.float64)
    return r, v, float(sat.get("bstar") or 0.0)


class ConjunctionRankingRequest(BaseModel):
    events: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Explicit list of conjunction event dicts to rank. If omitted, evaluates events stored in database."
    )


@router.post("/collision-assessment/evaluate", response_model=CollisionAssessmentResult)
@router.post("/collision/calculate-probability")
async def evaluate_collision_encounter(payload: Dict[str, Any] = Body(...)):
    """
    Week 7 Deliverable: Collision Assessment Evaluation Endpoint.
    - Calculates 3D Euclidean, LVLH (RIC), and B-plane miss distances.
    - Incorporates available covariance and drag growth uncertainty.
    - Computes analytical Foster 2D and Monte Carlo collision probabilities.
    - Synthesizes an explainability report with sensitivity analysis and HITL directive.
    """
    p_norad = payload.get("primary_norad_id")
    s_norad = payload.get("secondary_norad_id")
    if p_norad is None or s_norad is None:
        raise HTTPException(status_code=400, detail="primary_norad_id and secondary_norad_id are required.")
    ev_id = payload.get("event_id") or f"CONJ-{p_norad}-{s_norad}-{int(datetime.now(timezone.utc).timestamp())}"
    tca_val = payload.get("tca")
    tca = datetime.fromisoformat(tca_val) if tca_val and isinstance(tca_val, str) else datetime.now(timezone.utc)

    r1_raw = payload.get("primary_position_eci") or payload.get("primary_r")
    v1_raw = payload.get("primary_velocity_eci") or payload.get("primary_v")
    r2_raw = payload.get("secondary_position_eci") or payload.get("secondary_r")
    v2_raw = payload.get("secondary_velocity_eci") or payload.get("secondary_v")
    if not all([r1_raw, v1_raw, r2_raw, v2_raw]):
        raise HTTPException(
            status_code=400,
            detail="ECI position and velocity vectors are required for both objects."
        )

    r1 = np.array(r1_raw, dtype=np.float64)
    v1 = np.array(v1_raw, dtype=np.float64)
    r2 = np.array(r2_raw, dtype=np.float64)
    v2 = np.array(v2_raw, dtype=np.float64)

    result = collision_assessment_engine.assess_collision(
        event_id=ev_id,
        primary_norad_id=p_norad,
        primary_name=payload.get("primary_name") or f"NORAD {p_norad}",
        secondary_norad_id=s_norad,
        secondary_name=payload.get("secondary_name") or f"NORAD {s_norad}",
        secondary_type=payload.get("secondary_type", "DEBRIS"),
        r1_eci=r1,
        v1_eci=v1,
        r2_eci=r2,
        v2_eci=v2,
        tca=tca,
        lead_time_hours=float(payload.get("lead_time_hours", 24.0)),
        hard_body_radius_m=float(payload.get("hard_body_radius_m", 15.0)),
        bstar_primary=float(payload.get("bstar_primary", 0.0)),
        bstar_secondary=float(payload.get("bstar_secondary", 0.0))
    )
    # Also attach top-level convenience fields for the UI calculator
    res_dict = result.model_dump()
    res_dict["miss_distance_km"] = result.geometry.miss_distance_km
    res_dict["collision_probability"] = result.probabilistic.collision_probability
    res_dict["foster_pc_sci"] = result.probabilistic.collision_probability_sci
    res_dict["nasa_cara_tier"] = result.probabilistic.nasa_cara_tier.value
    res_dict["b_plane_xi_km"] = result.geometry.b_plane_x_km
    res_dict["b_plane_zeta_km"] = result.geometry.b_plane_z_km
    return res_dict


@router.post("/collision-assessment/rank", response_model=ConjunctionRankingResponse)
async def rank_conjunction_encounters(payload: ConjunctionRankingRequest):
    """
    Week 7 Deliverable: Multi-criteria Conjunction Event Ranking.
    Ranks conjunction encounters based on Urgency Priority Index (UPI) incorporating
    collision probability, miss distance, radial overlap, time to TCA, and object pedigree.
    """
    candidate_events = payload.events

    if not candidate_events:
        # Pull latest screened conjunctions from MongoDB database
        stored = await conjunction_repo.list_conjunctions(limit=50)
        candidate_events = stored

    if not candidate_events:
        return ConjunctionRankingResponse(
            status="success",
            total_events_evaluated=0,
            immediate_action_count=0,
            urgent_triage_count=0,
            elevated_watch_count=0,
            routine_count=0,
            ranked_queue=[]
        )

    return collision_assessment_engine.rank_conjunction_events(candidate_events)


@router.get("/collision-assessment/report/{event_id}", response_model=ExplainabilityReport)
async def get_collision_explainability_report(event_id: str):
    """
    Week 7 Deliverable: Conjunction Explainability Report Endpoint.
    Retrieves a stored conjunction and re-propagates both objects to its TCA
    to build the assessment from real catalog ephemerides.
    """
    conj = await conjunction_repo.get_by_event_id(event_id)
    if not conj:
        raise HTTPException(status_code=404, detail=f"Conjunction event {event_id} not found.")

    p_id = int(conj["primary_norad_id"])
    s_id = int(conj["secondary_norad_id"])
    p_name = conj.get("primary_name") or f"NORAD {p_id}"
    s_name = conj.get("secondary_name") or f"NORAD {s_id}"
    s_type = conj.get("secondary_type", "UNKNOWN")

    tca_raw = conj.get("tca")
    tca = datetime.fromisoformat(tca_raw) if isinstance(tca_raw, str) else tca_raw
    if tca.tzinfo is None:
        tca = tca.replace(tzinfo=timezone.utc)

    r1, v1, bstar1 = await _propagate_catalog_state(p_id, tca)
    r2, v2, bstar2 = await _propagate_catalog_state(s_id, tca)
    lead_time = max(0.1, (tca - datetime.now(timezone.utc)).total_seconds() / 3600.0)

    assessment = collision_assessment_engine.assess_collision(
        event_id=event_id,
        primary_norad_id=p_id,
        primary_name=p_name,
        secondary_norad_id=s_id,
        secondary_name=s_name,
        secondary_type=s_type,
        r1_eci=r1,
        v1_eci=v1,
        r2_eci=r2,
        v2_eci=v2,
        tca=tca,
        lead_time_hours=lead_time,
        hard_body_radius_m=15.0,
        bstar_primary=bstar1,
        bstar_secondary=bstar2
    )

    return assessment.explainability_report


@router.post("/collision/explainability-report")
async def generate_explainability_report_from_payload(payload: Dict[str, Any] = Body(...)):
    """
    Week 7 & 10 Deliverable: Direct explainability report synthesis for frontend UI.
    Uses caller-supplied ECI vectors when present, otherwise real catalog TLE propagation.
    """
    p_id = payload.get("primary_norad_id")
    s_id = payload.get("secondary_norad_id")
    if p_id is None or s_id is None:
        raise HTTPException(status_code=400, detail="primary_norad_id and secondary_norad_id are required.")
    p_id, s_id = int(p_id), int(s_id)

    p_name = payload.get("primary_name") or f"NORAD {p_id}"
    s_name = payload.get("secondary_name") or f"NORAD {s_id}"
    s_type = payload.get("secondary_type", "UNKNOWN")

    tca_val = payload.get("tca")
    tca = datetime.fromisoformat(tca_val) if isinstance(tca_val, str) else datetime.now(timezone.utc)
    if tca.tzinfo is None:
        tca = tca.replace(tzinfo=timezone.utc)

    vectors = [
        payload.get("primary_position_eci"), payload.get("primary_velocity_eci"),
        payload.get("secondary_position_eci"), payload.get("secondary_velocity_eci")
    ]
    if all(vectors):
        r1, v1 = np.array(vectors[0], dtype=np.float64), np.array(vectors[1], dtype=np.float64)
        r2, v2 = np.array(vectors[2], dtype=np.float64), np.array(vectors[3], dtype=np.float64)
        bstar1 = float(payload.get("bstar_primary", 0.0))
        bstar2 = float(payload.get("bstar_secondary", 0.0))
    else:
        r1, v1, bstar1 = await _propagate_catalog_state(p_id, tca)
        r2, v2, bstar2 = await _propagate_catalog_state(s_id, tca)

    lead_time = max(0.1, (tca - datetime.now(timezone.utc)).total_seconds() / 3600.0)
    ev_id = payload.get("event_id") or f"REPORT-{p_id}-{s_id}"
    assessment = collision_assessment_engine.assess_collision(
        event_id=ev_id,
        primary_norad_id=p_id,
        primary_name=p_name,
        secondary_norad_id=s_id,
        secondary_name=s_name,
        secondary_type=s_type,
        r1_eci=r1,
        v1_eci=v1,
        r2_eci=r2,
        v2_eci=v2,
        tca=tca,
        lead_time_hours=lead_time,
        hard_body_radius_m=float(payload.get("hard_body_radius_m", 15.0)),
        bstar_primary=bstar1,
        bstar_secondary=bstar2
    )

    report = assessment.explainability_report
    return {
        "event_id": ev_id,
        "report_text": f"COLLISION RISK ASSESSMENT & EXPLAINABILITY REPORT [{ev_id}]\n"
                       f"Primary: {p_name} (NORAD {p_id}) vs Secondary: {s_name} (NORAD {s_id})\n"
                       f"Executive Summary: {report.executive_summary}\n\n"
                       f"Physical Geometry: {report.geometry_explanation}\n\n"
                       f"Uncertainty Breakdown: {report.uncertainty_explanation}\n\n"
                       f"Probabilistic CARA Risk: {report.probabilistic_explanation}\n\n"
                       f"Human-in-the-Loop Directive: {report.hitl_recommendation}",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
