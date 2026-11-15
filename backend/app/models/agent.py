from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def now_utc():
    return datetime.now(timezone.utc)


class AgentStepTrace(BaseModel):
    agent: str
    action: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    status: str = "COMPLETED"
    timestamp: datetime = Field(default_factory=now_utc)


class TaskStep(BaseModel):
    step_id: int
    agent_name: str
    action: str
    description: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, SKIPPED, FAILED
    output: Optional[Dict[str, Any]] = None


class TaskPlan(BaseModel):
    plan_id: str
    goal: str
    target_norad_id: Optional[int] = None
    steps: List[TaskStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class AgentInvestigationMemory(BaseModel):
    session_id: str
    target_norad_id: Optional[int] = None
    query: str
    plan: Optional[TaskPlan] = None
    agent_trace: List[AgentStepTrace] = Field(default_factory=list)
    findings_summary: str
    approval_checkpoint_reached: bool = False
    maneuver_proposal_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(populate_by_name=True)


class AgentCommandRequest(BaseModel):
    query: str = Field(..., description="Natural language operator request")
    target_norad_id: Optional[int] = Field(default=None, description="Optional target satellite NORAD ID")
    session_id: Optional[str] = None
    auto_execute: bool = Field(default=True, description="Whether to execute the generated plan immediately")


class AgentCommandResponse(BaseModel):
    session_id: str
    query: str
    plan: Optional[TaskPlan] = None
    findings_summary: str
    approval_required: bool = False
    pending_proposal_id: Optional[str] = None
    pending_proposal: Optional[Dict[str, Any]] = None
    trace: List[AgentStepTrace] = Field(default_factory=list)
    disclaimer: str = (
        "Analytical/illustrative assessment based on public TLE/OMM data, "
        "not certified operational flight-dynamics commands. Explicit human-in-the-loop "
        "authorization is strictly required for all recommended maneuvers."
    )
