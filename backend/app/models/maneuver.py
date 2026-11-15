from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def now_utc():
    return datetime.now(timezone.utc)


class BurnDirection(str, Enum):
    PROGRADE = "PROGRADE"
    RETROGRADE = "RETROGRADE"
    NORMAL = "NORMAL"
    RADIAL = "RADIAL"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ManeuverProposalBase(BaseModel):
    conjunction_id: str
    target_norad_id: int
    proposed_delta_v_ms: float = Field(..., description="Burn magnitude in m/s")
    burn_direction: BurnDirection
    burn_epoch: datetime
    projected_miss_distance_km: float
    fuel_consumption_kg: Optional[float] = None
    secondary_conjunction_risk: str = "NONE_DETECTED"
    approval_status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None


class ManeuverProposalInDB(ManeuverProposalBase):
    id: Optional[str] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(populate_by_name=True)


class ManeuverDecisionRequest(BaseModel):
    operator_name: str
    decision: ApprovalStatus  # APPROVED or REJECTED
    notes: Optional[str] = None
