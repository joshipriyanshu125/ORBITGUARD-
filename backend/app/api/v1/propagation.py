from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from app.models.satellite import OrbitPropagationResponse
from app.db.repositories.satellite_repo import satellite_repo
from app.services.sgp4_engine import sgp4_engine

router = APIRouter()


@router.get("/satellites/{norad_id}/orbit", response_model=OrbitPropagationResponse)
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
