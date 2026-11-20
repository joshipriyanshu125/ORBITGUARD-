from fastapi import APIRouter, HTTPException
from typing import List

from app.models.simulation import (
    HypotheticalScenarioRequest,
    HypotheticalScenarioResponse,
    ManeuverCandidate,
    TrajectoryComparisonResult,
    ScenarioType
)
from app.services.simulation_engine import simulation_engine
from app.core.logging import logger

from pydantic import BaseModel, Field

router = APIRouter()


class GenerateCandidatesRequest(BaseModel):
    initial_miss_distance_km: float = Field(..., ge=0.01)
    desired_miss_distance_km: float = Field(..., ge=1.0)
    relative_velocity_kms: float = Field(..., ge=0.1)
    lead_time_hours: float = Field(..., ge=1.0)
    semi_major_axis_km: float = Field(..., ge=6400.0)
    spacecraft_dry_mass_kg: float = Field(..., ge=1.0)
    spacecraft_propellant_mass_kg: float = Field(..., ge=0.1)
    thruster_isp_seconds: float = Field(..., ge=50.0)


class TrajectoryComparisonRequest(BaseModel):
    delta_v_radial_ms: float = Field(default=0.0)
    delta_v_in_track_ms: float = Field(default=0.0)
    delta_v_cross_track_ms: float = Field(default=0.0)
    initial_miss_distance_km: float = Field(..., ge=0.01)
    semi_major_axis_km: float = Field(..., ge=6400.0)
    lead_time_hours: float = Field(..., ge=1.0)
    spacecraft_dry_mass_kg: float = Field(..., gt=0)
    spacecraft_propellant_mass_kg: float = Field(..., ge=0)
    thruster_isp_seconds: float = Field(..., gt=0)
    num_steps: int = Field(default=24, ge=5, le=100)


@router.post("/simulation/candidates", response_model=List[ManeuverCandidate])
async def generate_maneuver_candidates(payload: GenerateCandidatesRequest):
    """
    Week 9 Deliverable: Candidate Maneuver Generation.
    Generates diverse collision avoidance maneuver candidates (Prograde Phasing,
    Retrograde Phasing, Radial Boost, Normal Cross-Track, Optimal Hohmann)
    with Tsiolkovsky propellant mass estimates and efficiency rankings.
    """
    candidates = simulation_engine.generate_candidate_maneuvers(
        initial_miss_km=payload.initial_miss_distance_km,
        desired_miss_km=payload.desired_miss_distance_km,
        relative_velocity_kms=payload.relative_velocity_kms,
        lead_time_hours=payload.lead_time_hours,
        semi_major_axis_km=payload.semi_major_axis_km,
        spacecraft_dry_mass_kg=payload.spacecraft_dry_mass_kg,
        spacecraft_propellant_mass_kg=payload.spacecraft_propellant_mass_kg,
        thruster_isp_seconds=payload.thruster_isp_seconds
    )
    return candidates


@router.post("/simulation/compare-trajectories", response_model=TrajectoryComparisonResult)
async def compare_simulated_trajectories(payload: TrajectoryComparisonRequest):
    """
    Week 9 Deliverable: Trajectory Comparison.
    Simulates baseline unperturbed orbit vs post-burn trajectory via Clohessy-Wiltshire dynamics.
    Outputs radial, in-track, and cross-track relative separations across time.
    """
    custom_candidate = simulation_engine.evaluate_custom_maneuver(
        delta_v_radial_ms=payload.delta_v_radial_ms,
        delta_v_in_track_ms=payload.delta_v_in_track_ms,
        delta_v_cross_track_ms=payload.delta_v_cross_track_ms,
        initial_miss_km=payload.initial_miss_distance_km,
        semi_major_axis_km=payload.semi_major_axis_km,
        lead_time_hours=payload.lead_time_hours,
        spacecraft_dry_mass_kg=payload.spacecraft_dry_mass_kg,
        spacecraft_propellant_mass_kg=payload.spacecraft_propellant_mass_kg,
        thruster_isp_seconds=payload.thruster_isp_seconds
    )

    result = simulation_engine.compare_trajectories(
        candidate=custom_candidate,
        initial_miss_km=payload.initial_miss_distance_km,
        semi_major_axis_km=payload.semi_major_axis_km,
        lead_time_hours=payload.lead_time_hours,
        num_steps=payload.num_steps
    )
    return result


@router.post("/simulation/scenarios/run", response_model=HypotheticalScenarioResponse)
async def run_hypothetical_scenario(payload: HypotheticalScenarioRequest):
    """
    Week 9 Deliverable: 'What-If' Simulation Laboratory.
    Tests hypothetical aerospace collision scenarios:
    - IMMINENT_DEBRIS_COLLISION: High-velocity close approach
    - LOW_THRUST_ELECTRIC_PHASING: Long horizon electric propulsion
    - SECONDARY_CONJUNCTION_HAZARD: Conjunction cloud injection screening
    - FUEL_CONSTRAINED_EMERGENCY: Strict propellant budget optimization
    """
    try:
        response = simulation_engine.test_hypothetical_scenario(payload)
        return response
    except Exception as e:
        logger.error(f"Error executing hypothetical simulation scenario: {e}")
        raise HTTPException(status_code=500, detail=f"Simulation scenario failed: {str(e)}")


@router.get("/simulation/scenarios/presets")
async def get_scenario_presets():
    """
    Returns the supported simulation scenario types. No satellite parameters are
    prefilled; callers must supply a real conjunction and spacecraft properties.
    """
    return {
        "presets": [
            {
                "scenario_type": ScenarioType.IMMINENT_DEBRIS_COLLISION.value,
                "title": "Imminent Close Approach",
                "description": "Evaluate avoidance options for a high relative-velocity close approach."
            },
            {
                "scenario_type": ScenarioType.FUEL_CONSTRAINED_EMERGENCY.value,
                "title": "Propellant-Constrained Avoidance",
                "description": "Evaluate avoidance options under a maximum propellant budget."
            },
            {
                "scenario_type": ScenarioType.LOW_THRUST_ELECTRIC_PHASING.value,
                "title": "Low-Thrust Electric Phasing",
                "description": "Evaluate a high-specific-impulse phasing profile over a long lead time."
            },
            {
                "scenario_type": ScenarioType.SECONDARY_CONJUNCTION_HAZARD.value,
                "title": "Secondary Conjunction Hazard",
                "description": "Evaluate whether candidate burns could create new conjunction risk."
            }
        ]
    }
