from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import settings
from app.db import mongodb

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint exposing system readiness and operational disclaimers."""
    db_status = "connected" if mongodb.client is not None else "disconnected"
    db_mode = "mock_in_memory" if mongodb.is_mock_db else "mongodb_atlas"
    
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_status,
            "engine": db_mode,
            "name": settings.MONGODB_DB_NAME
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": settings.SYSTEM_DISCLAIMER
    }
