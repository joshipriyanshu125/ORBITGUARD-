import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import logger
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.services.ingestion_scheduler import ingestion_scheduler
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB and build indexes
    logger.info("Initializing ORBITGUARD AI backend service...")
    await connect_to_mongo()
    ingestion_scheduler.start()
    yield
    # Shutdown: Stop scheduler and close MongoDB connection
    logger.info("Shutting down ORBITGUARD AI backend service...")
    ingestion_scheduler.stop()
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Autonomous Space Intelligence & Collision Avoidance System. "
        "Continuously monitors orbital objects, propagates trajectories with SGP4, "
        "detects dangerous close approaches, and evaluates collision risks."
    ),
    lifespan=lifespan
)

# Configure CORS for Vercel frontend and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach API routes
app.include_router(api_router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": settings.SYSTEM_DISCLAIMER
    }
