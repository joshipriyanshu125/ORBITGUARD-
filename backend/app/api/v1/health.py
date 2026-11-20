from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import settings
from app.db import mongodb
from app.db.repositories.satellite_repo import satellite_repo
from app.db.repositories.conjunction_repo import conjunction_repo
from app.services.ingestion_scheduler import ingestion_scheduler

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint exposing system readiness and live catalog counts."""
    db_status = "connected" if mongodb.client is not None else "disconnected"
    db_mode = "mock_in_memory" if mongodb.is_mock_db else "mongodb_atlas"

    try:
        satellite_count = await satellite_repo.count_satellites()
        conjunction_count = await conjunction_repo.count_conjunctions()
    except Exception:
        satellite_count = 0
        conjunction_count = 0

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_status,
            "engine": db_mode,
            "name": settings.MONGODB_DB_NAME
        },
        "catalog": {
            "satellites": satellite_count,
            "conjunctions": conjunction_count
        },
        "ingestion_scheduler": {
            "running": ingestion_scheduler._is_running,
            "interval_hours": ingestion_scheduler.interval_hours,
            "groups": ingestion_scheduler.groups
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": settings.SYSTEM_DISCLAIMER
    }
