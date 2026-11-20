from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.models.satellite import OrbitPropagationResponse
from app.db.repositories.satellite_repo import satellite_repo
from app.services.sgp4_engine import sgp4_engine

router = APIRouter()


class CatalogPositionsRequest(BaseModel):
    norad_ids: List[int] = Field(..., min_length=1, max_length=500)


@router.post("/propagation/positions")
async def get_current_positions(payload: CatalogPositionsRequest):
    """Return real SGP4 sub-satellite positions for a batch of catalog objects at the same epoch."""
    epoch = datetime.now(timezone.utc)
    satellites = await satellite_repo.get_by_norad_ids(payload.norad_ids)

    items = []
    for sat in satellites:
        try:
            satrec = sgp4_engine.build_satrec(sat["tle_line1"], sat["tle_line2"])
            point = sgp4_engine.propagate_single(satrec, epoch)
        except Exception:
            continue
        if point is None:
            continue
        items.append({
            "norad_id": sat["norad_id"],
            "name": sat.get("name"),
            "object_type": sat.get("object_type"),
            "timestamp": point.timestamp.isoformat(),
            "lat": point.latitude_deg,
            "lon": point.longitude_deg,
            "alt_km": point.altitude_km
        })

    return {"timestamp": epoch.isoformat(), "count": len(items), "items": items}


@router.get("/satellites/{norad_id}/position")
@router.get("/propagation/{norad_id}/current")
async def get_current_position(
    norad_id: int,
    at: Optional[datetime] = Query(default=None, description="Evaluation epoch in UTC (defaults to now)")
):
    """Return the real SGP4 state vector and sub-satellite point for a cataloged object."""
    sat = await satellite_repo.get_by_norad_id(norad_id)
    if not sat:
        raise HTTPException(
            status_code=404,
            detail=f"Satellite with NORAD ID {norad_id} not found in catalog. Sync catalog first."
        )

    epoch = at or datetime.now(timezone.utc)
    try:
        satrec = sgp4_engine.build_satrec(sat["tle_line1"], sat["tle_line2"])
        point = sgp4_engine.propagate_single(satrec, epoch)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to propagate state for NORAD ID {norad_id}: {str(e)}"
        )

    if point is None:
        raise HTTPException(status_code=422, detail=f"SGP4 propagation failed for NORAD ID {norad_id}.")

    velocity_kms = (point.vx_kms ** 2 + point.vy_kms ** 2 + point.vz_kms ** 2) ** 0.5
    return {
        "norad_id": sat["norad_id"],
        "name": sat["name"],
        "timestamp": point.timestamp.isoformat(),
        "lat": point.latitude_deg,
        "lon": point.longitude_deg,
        "alt_km": point.altitude_km,
        "x_eci": point.x_km,
        "y_eci": point.y_km,
        "z_eci": point.z_km,
        "vx": point.vx_kms,
        "vy": point.vy_kms,
        "vz": point.vz_kms,
        "velocity_kms": round(velocity_kms, 4)
    }


@router.get("/satellites/{norad_id}/orbit", response_model=OrbitPropagationResponse)
@router.get("/propagation/{norad_id}/orbit", response_model=OrbitPropagationResponse)
async def get_propagated_orbit(
    norad_id: int,
    duration_hours: float = Query(default=24.0, ge=1.0, le=168.0, description="Propagation horizon in hours (max 7 days)"),
    step_seconds: int = Query(default=120, ge=10, le=3600, description="Propagation time step in seconds"),
    start_time: Optional[datetime] = Query(default=None, description="Propagation start ISO datetime (defaults to current UTC)")
):
    """
    Propagate the orbit of a cataloged satellite using the SGP4 analytical propagator.
    Returns 3D ECI coordinates (km), velocities (km/s), and geodetic positions (lat, lon, alt)
    for CesiumJS 3D Earth trajectory rendering.
    """
    sat = await satellite_repo.get_by_norad_id(norad_id)
    if not sat:
        raise HTTPException(
            status_code=404,
            detail=f"Satellite with NORAD ID {norad_id} not found in catalog. Sync catalog first."
        )

    try:
        orbit_data = sgp4_engine.propagate_orbit_path(
            norad_id=sat["norad_id"],
            name=sat["name"],
            tle_line1=sat["tle_line1"],
            tle_line2=sat["tle_line2"],
            epoch=sat["epoch"],
            start_time=start_time,
            duration_hours=duration_hours,
            step_seconds=step_seconds
        )
        return orbit_data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to propagate orbit for NORAD ID {norad_id}: {str(e)}"
        )
