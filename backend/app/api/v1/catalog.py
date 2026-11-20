from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from app.models.satellite import SatelliteResponse, ObjectType
from app.db.repositories.satellite_repo import satellite_repo
from app.services.celestrak import celestrak_service
from app.core.logging import logger

router = APIRouter()


@router.post("/catalog/sync")
async def sync_catalog(
    groups: List[str] = Query(
        default=["stations", "fengyun-1c-debris"],
        description="CelesTrak groups to sync (e.g. stations, active, cosmos-2251-debris, fengyun-1c-debris)"
    )
):
    """
    Fetch live or cached orbital data from CelesTrak and synchronize with the MongoDB catalog.
    """
    total_synced = 0
    group_results = {}

    for group in groups:
        try:
            records = await celestrak_service.fetch_group(group_name=group)
            synced_in_group = 0
            for record in records:
                await satellite_repo.upsert_satellite(record)
                synced_in_group += 1
            
            group_results[group] = synced_in_group
            total_synced += synced_in_group
            logger.info(f"Synchronized {synced_in_group} objects for group '{group}'")
        except Exception as e:
            logger.error(f"Error syncing group '{group}': {e}")
            group_results[group] = f"Error: {str(e)}"

    total_catalog = await satellite_repo.count_satellites()

    return {
        "status": "success",
        "synced_total": total_synced,
        "catalog_size": total_catalog,
        "groups": group_results,
        "message": f"Synchronized {total_synced} orbital objects to MongoDB catalog."
    }


@router.get("/satellites")
@router.get("/catalog")
async def list_satellites(
    object_type: Optional[ObjectType] = Query(None, description="Filter by PAYLOAD, DEBRIS, ROCKET_BODY"),
    search: Optional[str] = Query(None, description="Filter by name regex or NORAD ID"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000)
):
    """List satellites and debris in the catalog with pagination and filtering."""
    query_str = search or q
    results = await satellite_repo.list_satellites(
        object_type=object_type.value if object_type else None,
        search=query_str,
        skip=skip,
        limit=limit
    )
    total_count = await satellite_repo.count_satellites(
        object_type=object_type.value if object_type else None
    )

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "items": results
    }


@router.get("/satellites/{norad_id}", response_model=SatelliteResponse)
@router.get("/catalog/{norad_id}", response_model=SatelliteResponse)
async def get_satellite(norad_id: int):
    """Retrieve full details of a specific satellite by NORAD ID."""
    sat = await satellite_repo.get_by_norad_id(norad_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found in catalog.")
    return sat


@router.get("/satellites/{norad_id}/history")
async def get_satellite_history(norad_id: int, limit: int = Query(50, ge=1, le=200)):
    """Retrieve historical TLE epochs for a satellite (used for ML anomaly detection)."""
    sat = await satellite_repo.get_by_norad_id(norad_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found.")
    
    history = await satellite_repo.get_history(norad_id, limit=limit)
    return {
        "norad_id": norad_id,
        "name": sat.get("name"),
        "history_count": len(history),
        "history": history
    }
