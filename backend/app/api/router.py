from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.propagation import router as propagation_router
from app.api.v1.conjunctions import router as conjunctions_router
from app.api.v1.ml import router as ml_router
from app.api.v1.collision_assessment import router as collision_assessment_router
from app.api.v1.agents import router as agents_router
from app.api.v1.simulation import router as simulation_router

api_router = APIRouter(prefix="/api")
root_router = APIRouter()

routers = [
    (health_router, "System Health"),
    (catalog_router, "Satellite Catalog"),
    (propagation_router, "Orbital Propagation"),
    (conjunctions_router, "Conjunction Screening"),
    (ml_router, "Machine Learning Intelligence"),
    (collision_assessment_router, "Collision Assessment Module"),
    (agents_router, "Autonomous AI Multi-Agent Brain"),
    (simulation_router, "Simulation Laboratory & Engine"),
]

for r, tag in routers:
    api_router.include_router(r, tags=[tag])
    root_router.include_router(r, tags=[tag], include_in_schema=False)
