from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def now_utc():
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConjunctionStatus(str, Enum):
    DETECTED = "DETECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"


class ConjunctionBase(BaseModel):
    event_id: str = Field(..., description="Unique deterministic conjunction ID")
    primary_norad_id: int
    primary_name: str
    secondary_norad_id: int
    secondary_name: str
    secondary_type: str = "DEBRIS"
    tca: datetime = Field(..., description="Time of Closest Approach")
    miss_distance_km: float = Field(..., description="Predicted minimum distance at TCA")
    relative_velocity_kms: float = Field(..., description="Relative velocity at TCA")
    primary_position_eci: List[float] = Field(default_factory=list)
    secondary_position_eci: List[float] = Field(default_factory=list)
    ml_anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    status: ConjunctionStatus = Field(default=ConjunctionStatus.DETECTED)
    analysis_summary: Optional[str] = None


class ConjunctionInDB(ConjunctionBase):
    id: Optional[str] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(populate_by_name=True)


class ConjunctionResponse(ConjunctionBase):
    created_at: datetime
    disclaimer: str = (
        "Analytical/illustrative assessment based on public TLE/OMM data, "
        "not certified operational flight-dynamics commands."
    )
