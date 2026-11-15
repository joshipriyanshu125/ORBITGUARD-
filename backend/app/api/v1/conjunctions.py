from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.models.conjunction import ConjunctionResponse, ConjunctionBase, RiskLevel, ConjunctionStatus
from app.db.repositories.satellite_repo import satellite_repo
from app.db.repositories.conjunction_repo import conjunction_repo
from app.services.conjunction_engine import conjunction_screening_engine
from app.services.socrates_service import socrates_service
from app.core.logging import logger

router = APIRouter()


class ScreenConjunctionsRequest(BaseModel):
    primary_norad_id: int = Field(default=25544, description="Target satellite NORAD Catalog ID (e.g. 25544 for ISS)")
    horizon_hours: float = Field(default=48.0, ge=1.0, le=168.0, description="Screening time horizon in hours")
    threshold_km: float = Field(default=25.0, ge=0.5, le=100.0, description="Close approach distance threshold in km")
    altitude_margin_km: float = Field(default=50.0, ge=10.0, le=200.0, description="Broad-phase altitude buffer in km")


@router.post("/conjunctions/screen")
async def screen_close_approaches(payload: ScreenConjunctionsRequest):
    """
    Run full two-phase close approach screening:
    1. Broad-phase radial shell filtering against cataloged objects and debris.
    2. Narrow-phase high-precision SGP4 propagation and TCA minimization.
    Detected encounters are persisted to MongoDB.
    """
    primary = await satellite_repo.get_by_norad_id(payload.primary_norad_id)
    if not primary:
        raise HTTPException(
            status_code=404,
            detail=f"Primary satellite {payload.primary_norad_id} not found in catalog. Sync catalog first."
        )

    # 1. Broad-phase spatial candidate retrieval
    candidates = await satellite_repo.find_orbital_shell_candidates(
        min_perigee=primary["perigee_km"] - payload.altitude_margin_km,
        max_apogee=primary["apogee_km"] + payload.altitude_margin_km,
        exclude_norad_id=payload.primary_norad_id
    )

    if not candidates:
        return {
            "status": "success",
            "primary_norad_id": payload.primary_norad_id,
            "primary_name": primary["name"],
            "candidates_screened": 0,
            "conjunctions_detected": 0,
            "items": [],
            "message": "No overlapping orbital shell candidates found in catalog."
        }

    # Filter further with broad-phase mathematical shell filter
    filtered_candidates = conjunction_screening_engine.broad_phase_filter(
        primary_apogee_km=primary["apogee_km"],
        primary_perigee_km=primary["perigee_km"],
        candidates=candidates,
        altitude_margin_km=payload.altitude_margin_km
    )

    # 2. Narrow-phase fine TCA minimization
    detected_events: List[ConjunctionBase] = []
    now = datetime.now(timezone.utc)

    for cand in filtered_candidates:
        events = conjunction_screening_engine.screen_pair(
            primary=primary,
            secondary=cand,
            start_time=now,
            horizon_hours=payload.horizon_hours,
            threshold_km=payload.threshold_km
        )
        for ev in events:
            await conjunction_repo.upsert_conjunction(ev)
            detected_events.append(ev)

    logger.info(
        f"Screening complete for {primary['name']}: {len(detected_events)} "
        f"conjunctions detected out of {len(filtered_candidates)} candidates."
    )

    return {
        "status": "success",
        "primary_norad_id": payload.primary_norad_id,
        "primary_name": primary["name"],
        "candidates_screened": len(filtered_candidates),
        "conjunctions_detected": len(detected_events),
        "items": detected_events
    }


@router.get("/conjunctions")
async def list_conjunctions(
    primary_norad_id: Optional[int] = Query(None, description="Filter by primary NORAD ID"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by LOW, MEDIUM, HIGH, CRITICAL"),
    status: Optional[ConjunctionStatus] = Query(None, description="Filter by DETECTED, AWAITING_APPROVAL, etc."),
    max_miss_distance_km: Optional[float] = Query(None, ge=0.1, description="Maximum miss distance in km"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500)
):
    """Query persisted close approaches with multi-criteria filtering."""
    items = await conjunction_repo.list_conjunctions(
        primary_norad_id=primary_norad_id,
        risk_level=risk_level.value if risk_level else None,
        status=status.value if status else None,
        max_miss_distance_km=max_miss_distance_km,
        skip=skip,
        limit=limit
    )
    total = await conjunction_repo.count_conjunctions(
        primary_norad_id=primary_norad_id,
        risk_level=risk_level.value if risk_level else None,
        status=status.value if status else None
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items
    }


@router.get("/conjunctions/{event_id}", response_model=ConjunctionResponse)
async def get_conjunction_detail(event_id: str):
    """Retrieve details of a specific conjunction event."""
    item = await conjunction_repo.get_by_event_id(event_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Conjunction event {event_id} not found.")
    return item


@router.post("/conjunctions/socrates/compare")
async def compare_with_socrates(
    primary_norad_id: Optional[int] = Query(None, description="Optional target NORAD ID to benchmark")
):
    """
    Compare ORBITGUARD SGP4 conjunction screening results against CelesTrak SOCRATES
    ground-truth assessments, returning accuracy and concordance metrics.
    """
    # 1. Retrieve current conjunctions from database
    stored_events_dicts = await conjunction_repo.list_conjunctions(
        primary_norad_id=primary_norad_id,
        limit=100
    )
    
    stored_events: List[ConjunctionBase] = []
    for d in stored_events_dicts:
        try:
            stored_events.append(ConjunctionBase(**d))
        except Exception:
            continue

    # 2. Fetch SOCRATES reports
    socrates_records = await socrates_service.fetch_socrates_conjunctions()

    # 3. Benchmark comparison
    comparison_result = socrates_service.compare_screening_with_socrates(
        screened_events=stored_events,
        socrates_records=socrates_records
    )

    return {
        "status": "success",
        "benchmark_source": "CelesTrak SOCRATES",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": comparison_result
    }
