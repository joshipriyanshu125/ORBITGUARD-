import math
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

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
    initial_miss_distance_km: float = Field(default=0.45, ge=0.01)
    desired_miss_distance_km: float = Field(default=8.0, ge=1.0)
    relative_velocity_kms: float = Field(default=14.2, ge=0.1)
    lead_time_hours: float = Field(default=24.0, ge=1.0)
    semi_major_axis_km: float = Field(default=6800.0, ge=6400.0)
    spacecraft_dry_mass_kg: float = Field(default=420000.0, ge=1.0)
    spacecraft_propellant_mass_kg: float = Field(default=2500.0, ge=0.1)
    thruster_isp_seconds: float = Field(default=310.0, ge=50.0)


class TrajectoryComparisonRequest(BaseModel):
    delta_v_radial_ms: float = Field(default=0.0)
    delta_v_in_track_ms: float = Field(default=0.85)
    delta_v_cross_track_ms: float = Field(default=0.0)
    initial_miss_distance_km: float = Field(default=0.45)
    semi_major_axis_km: float = Field(default=6800.0)
    lead_time_hours: float = Field(default=24.0)
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
    total_dv = math.sqrt(payload.delta_v_radial_ms**2 + payload.delta_v_in_track_ms**2 + payload.delta_v_cross_track_ms**2)
    mock_candidate = ManeuverCandidate(
        candidate_id="SIM-CUSTOM-COMPARE",
        name="Custom Operator Maneuver",
        maneuver_type="PROGRADE_PHASING",
        burn_direction="PROGRADE" if payload.delta_v_in_track_ms >= 0 else "RETROGRADE",
        delta_v_ms=round(total_dv, 3),
        delta_v_vector_lvlh=[payload.delta_v_radial_ms, payload.delta_v_in_track_ms, payload.delta_v_cross_track_ms],
        burn_epoch=datetime.now(timezone.utc),
        lead_time_to_tca_hours=payload.lead_time_hours,
        projected_miss_distance_km=round(payload.initial_miss_distance_km + total_dv * 6.0, 2),
        post_maneuver_collision_prob=1e-8,
        post_maneuver_collision_prob_sci="1.000e-08",
        post_maneuver_cara_tier="GREEN",
        fuel_mass_kg=12.5,
        fuel_efficiency_km_per_kg=0.85,
        residual_fuel_budget_kg=2487.5,
        tradeoff_rationale="Simulated custom comparison profile."
    )

    result = simulation_engine.compare_trajectories(
        candidate=mock_candidate,
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
    Returns standard aerospace scenario presets ready for one-click simulation laboratory execution.
    """
    return {
        "presets": [
            {
                "scenario_type": ScenarioType.IMMINENT_DEBRIS_COLLISION.value,
                "title": "Imminent Debris Cloud Encounter (ISS vs Fengyun-1C)",
                "description": "Critical close approach (< 0.5 km) with 14.2 km/s relative speed at T-24h.",
                "default_params": {
                    "primary_norad_id": 25544,
                    "primary_name": "ISS (ZARYA)",
                    "secondary_norad_id": 39872,
                    "secondary_name": "FENGYUN 1C DEBRIS",
                    "initial_miss_distance_km": 0.42,
                    "lead_time_hours": 24.0
                }
            },
            {
                "scenario_type": ScenarioType.FUEL_CONSTRAINED_EMERGENCY.value,
                "title": "Strict Propellant Budget Emergency Maneuver",
                "description": "Collision avoidance restricted to max 25 kg propellant mass.",
                "default_params": {
                    "primary_norad_id": 25544,
                    "primary_name": "ISS (ZARYA)",
                    "secondary_norad_id": 34125,
                    "secondary_name": "COSMOS 2251 DEBRIS",
                    "initial_miss_distance_km": 0.65,
                    "lead_time_hours": 18.0,
                    "max_fuel_budget_kg": 25.0
                }
            },
            {
                "scenario_type": ScenarioType.LOW_THRUST_ELECTRIC_PHASING.value,
                "title": "Continuous Low-Thrust Electric Propulsion Phasing",
                "description": "High-efficiency electric propulsion phasing (Isp = 1500s) over 72h lead time.",
                "default_params": {
                    "primary_norad_id": 48274,
                    "primary_name": "STARLINK-2541",
                    "secondary_norad_id": 20451,
                    "secondary_name": "SL-16 DEBRIS",
                    "initial_miss_distance_km": 0.85,
                    "lead_time_hours": 72.0,
                    "thruster_isp_seconds": 1500.0,
                    "spacecraft_dry_mass_kg": 260.0,
                    "spacecraft_propellant_mass_kg": 50.0
                }
            },
            {
                "scenario_type": ScenarioType.SECONDARY_CONJUNCTION_HAZARD.value,
                "title": "Avoidance Burn Secondary Conjunction Injection Screening",
                "description": "Simulate candidate avoidance burns that risk injecting the asset into secondary debris tracks.",
                "default_params": {
                    "primary_norad_id": 25544,
                    "primary_name": "ISS (ZARYA)",
                    "secondary_norad_id": 43205,
                    "secondary_name": "IRIDIUM 33 DEBRIS",
                    "initial_miss_distance_km": 0.50,
                    "lead_time_hours": 24.0
                }
            }
        ]
    }
