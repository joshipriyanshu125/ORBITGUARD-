from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class OperationalActionCategory(str, Enum):
    IMMEDIATE_ACTION_REQUIRED = "IMMEDIATE_ACTION_REQUIRED"
    URGENT_TRIAGE = "URGENT_TRIAGE"
    ELEVATED_WATCH = "ELEVATED_WATCH"
    ROUTINE_MONITORING = "ROUTINE_MONITORING"


class NASACARATier(str, Enum):
    RED_ALERT = "RED_ALERT (Pc >= 1e-4) - Mandatory Maneuver Planning"
    YELLOW_ALERT = "YELLOW_ALERT (1e-7 <= Pc < 1e-4) - Elevated Screening"
    GREEN = "GREEN (Pc < 1e-7) - Nominal Risk"


class EncounterGeometry(BaseModel):
    miss_distance_km: float = Field(..., description="Total 3D Euclidean miss distance at TCA")
    radial_miss_km: float = Field(..., description="Radial separation in LVLH frame (Delta R)")
    in_track_miss_km: float = Field(..., description="In-track separation in LVLH frame (Delta I)")
    cross_track_miss_km: float = Field(..., description="Cross-track separation in LVLH frame (Delta C)")
    b_plane_x_km: float = Field(..., description="Encounter B-plane coordinate along horizontal axis")
    b_plane_z_km: float = Field(..., description="Encounter B-plane coordinate along vertical axis")
    impact_parameter_km: float = Field(..., description="B-plane impact parameter sqrt(x^2 + z^2)")
    relative_velocity_kms: float = Field(..., description="Relative encounter velocity at TCA (km/s)")
    relative_kinetic_energy_mj_kg: float = Field(..., description="Specific kinetic energy 0.5 * v^2 (MJ/kg)")


class UncertaintyData(BaseModel):
    covariance_source: str = Field(..., description="Source of uncertainty (e.g., CDM, SGP4_EMPIRICAL_DRAG)")
    hard_body_radius_m: float = Field(..., description="Combined hard body radius R_primary + R_secondary (meters)")
    hard_body_radius_km: float = Field(..., description="Combined hard body radius in kilometers")
    sigma_radial_km: float = Field(..., description="1-sigma uncertainty along radial axis")
    sigma_in_track_km: float = Field(..., description="1-sigma uncertainty along in-track axis")
    sigma_cross_track_km: float = Field(..., description="1-sigma uncertainty along cross-track axis")
    b_plane_sigma_x_km: float = Field(..., description="Projected 1-sigma uncertainty along B-plane X axis")
    b_plane_sigma_y_km: float = Field(..., description="Projected 1-sigma uncertainty along B-plane Y axis")
    b_plane_correlation_rho: float = Field(default=0.0, description="Correlation coefficient in B-plane [-1, 1]")
    mahalanobis_distance: float = Field(..., description="Standardized Mahalanobis distance in encounter plane")


class ProbabilisticAssessment(BaseModel):
    collision_probability: float = Field(..., description="Analytical Foster 2D collision probability (Pc)")
    collision_probability_sci: str = Field(..., description="Scientific notation representation of Pc")
    monte_carlo_probability: float = Field(..., description="Empirical collision probability from MC simulation")
    monte_carlo_trials: int = Field(default=10000, description="Number of Monte Carlo trials drawn")
    monte_carlo_hits: int = Field(default=0, description="Collision hits recorded in MC simulation")
    confidence_interval_95: List[float] = Field(default_factory=list, description="95% confidence interval [low, high]")
    nasa_cara_tier: NASACARATier
    operational_severity: str = Field(..., description="NOMINAL, ELEVATED, HIGH, or CRITICAL")
    max_possible_pc: float = Field(..., description="Theoretical maximum Pc if miss distance were 0 under current covariance")


class ExplainabilityReport(BaseModel):
    executive_summary: str
    geometry_explanation: str
    uncertainty_explanation: str
    probabilistic_explanation: str
    sensitivity_analysis: Dict[str, Any]
    hitl_recommendation: str


class CollisionAssessmentResult(BaseModel):
    event_id: str
    primary_norad_id: int
    primary_name: str
    secondary_norad_id: int
    secondary_name: str
    secondary_type: str = "DEBRIS"
    tca: datetime
    lead_time_hours: float
    risk_level: str
    composite_risk_score: float = Field(..., ge=0.0, le=100.0)
    geometry: EncounterGeometry
    uncertainty: UncertaintyData
    probabilistic: ProbabilisticAssessment
    explainability_report: ExplainabilityReport
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RankedConjunctionItem(BaseModel):
    rank: int
    event_id: str
    primary_norad_id: int
    primary_name: str
    secondary_norad_id: int
    secondary_name: str
    secondary_type: str
    tca: datetime
    lead_time_hours: float
    miss_distance_km: float
    radial_miss_km: float
    relative_velocity_kms: float
    collision_probability_sci: str
    nasa_cara_tier: str
    composite_risk_score: float
    urgency_priority_index: float
    action_category: OperationalActionCategory
    short_rationale: str


class ConjunctionRankingResponse(BaseModel):
    status: str = "success"
    total_events_evaluated: int
    immediate_action_count: int
    urgent_triage_count: int
    elevated_watch_count: int
    routine_count: int
    ranked_queue: List[RankedConjunctionItem]
