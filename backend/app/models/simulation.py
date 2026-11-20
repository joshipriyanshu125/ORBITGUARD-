from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def now_utc():
    return datetime.now(timezone.utc)


class ManeuverType(str, Enum):
    PROGRADE_PHASING = "PROGRADE_PHASING"
    RETROGRADE_PHASING = "RETROGRADE_PHASING"
    RADIAL_BOOST = "RADIAL_BOOST"
    RADIAL_DROP = "RADIAL_DROP"
    OUT_OF_PLANE_NORMAL = "OUT_OF_PLANE_NORMAL"
    OPTIMAL_HOHMANN_PHASING = "OPTIMAL_HOHMANN_PHASING"


class ScenarioType(str, Enum):
    IMMINENT_DEBRIS_COLLISION = "IMMINENT_DEBRIS_COLLISION"
    LOW_THRUST_ELECTRIC_PHASING = "LOW_THRUST_ELECTRIC_PHASING"
    SECONDARY_CONJUNCTION_HAZARD = "SECONDARY_CONJUNCTION_HAZARD"
    FUEL_CONSTRAINED_EMERGENCY = "FUEL_CONSTRAINED_EMERGENCY"
    CUSTOM_OPERATOR_SIMULATION = "CUSTOM_OPERATOR_SIMULATION"


class ManeuverCandidate(BaseModel):
    candidate_id: str
    name: str
    maneuver_type: ManeuverType
    burn_direction: str  # PROGRADE, RETROGRADE, RADIAL, NORMAL
    delta_v_ms: float = Field(..., description="Burn velocity impulse in m/s")
    delta_v_vector_lvlh: List[float] = Field(default_factory=list, description="[dv_radial, dv_in_track, dv_cross_track] in m/s")
    burn_epoch: datetime
    lead_time_to_tca_hours: float
    projected_miss_distance_km: float
    post_maneuver_collision_prob: float
    post_maneuver_collision_prob_sci: str
    post_maneuver_cara_tier: str
    fuel_mass_kg: float = Field(..., description="Propellant mass consumed via Tsiolkovsky rocket equation")
    fuel_efficiency_km_per_kg: float = Field(..., description="Miss distance gain per kg of fuel")
    residual_fuel_budget_kg: float = Field(..., description="Remaining usable propellant mass")
    secondary_conjunction_risk: str = "NOT_ASSESSED"
    recommendation_rank: int = 1
    tradeoff_rationale: str


class TrajectoryComparisonPoint(BaseModel):
    time: datetime
    time_offset_seconds: float
    baseline_eci: List[float]
    maneuvered_eci: List[float]
    separation_delta_km: float
    radial_delta_km: float
    in_track_delta_km: float
    cross_track_delta_km: float
    baseline_altitude_km: float
    maneuvered_altitude_km: float


class TrajectoryComparisonResult(BaseModel):
    candidate_id: str
    maneuver_name: str
    delta_v_ms: float
    tca: datetime
    baseline_miss_distance_km: float
    post_burn_miss_distance_km: float
    miss_distance_gain_km: float
    max_spatial_separation_km: float
    tca_radial_separation_km: float
    tca_in_track_separation_km: float
    tca_cross_track_separation_km: float
    trajectory_points: List[TrajectoryComparisonPoint]


class HypotheticalScenarioRequest(BaseModel):
    scenario_id: Optional[str] = None
    scenario_type: ScenarioType = ScenarioType.IMMINENT_DEBRIS_COLLISION
    primary_norad_id: int = Field(..., description="Primary satellite NORAD ID")
    primary_name: str = Field(...)
    secondary_norad_id: int = Field(..., description="Secondary object NORAD ID")
    secondary_name: str = Field(...)
    semi_major_axis_km: float = Field(..., ge=6400.0, description="Primary orbit semi-major axis in km")
    initial_miss_distance_km: float = Field(..., ge=0.01)
    relative_velocity_kms: float = Field(..., ge=0.1)
    lead_time_hours: float = Field(..., ge=1.0)
    spacecraft_dry_mass_kg: float = Field(..., gt=0, description="Spacecraft dry mass in kg")
    spacecraft_propellant_mass_kg: float = Field(..., ge=0, description="Available propellant mass in kg")
    thruster_isp_seconds: float = Field(..., gt=0, description="Specific impulse Isp in seconds")
    max_fuel_budget_kg: Optional[float] = Field(default=None, description="Max allowed propellant for CAM")


class HypotheticalScenarioResponse(BaseModel):
    scenario_id: str
    scenario_type: ScenarioType
    scenario_name: str
    scenario_description: str
    simulation_timestamp: datetime = Field(default_factory=now_utc)
    baseline_encounter: Dict[str, Any]
    candidates_evaluated: List[ManeuverCandidate]
    optimal_candidate: ManeuverCandidate
    fuel_comparison_table: List[Dict[str, Any]]
    trajectory_comparison: TrajectoryComparisonResult
    secondary_risk_check: Dict[str, Any]
    executive_engineering_debrief: str
