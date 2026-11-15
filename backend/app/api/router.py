from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.propagation import router as propagation_router
from app.api.v1.conjunctions import router as conjunctions_router
from app.api.v1.ml import router as ml_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router, tags=["System Health"])
api_router.include_router(catalog_router, tags=["Satellite Catalog"])
api_router.include_router(propagation_router, tags=["Orbital Propagation"])
api_router.include_router(conjunctions_router, tags=["Conjunction Screening"])
api_router.include_router(ml_router, tags=["Machine Learning Intelligence"])
