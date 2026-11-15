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


class AgentInvestigationMemory(BaseModel):
    session_id: str
    target_norad_id: Optional[int] = None
    query: str
    agent_trace: List[AgentStepTrace] = Field(default_factory=list)
    findings_summary: str
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(populate_by_name=True)


class AgentCommandRequest(BaseModel):
    query: str = Field(..., description="Natural language operator request")
    target_norad_id: Optional[int] = Field(default=None, description="Optional target satellite NORAD ID")
    session_id: Optional[str] = None


class AgentCommandResponse(BaseModel):
    session_id: str
    query: str
    findings_summary: str
    trace: List[AgentStepTrace]
    disclaimer: str = (
        "Analytical/illustrative assessment based on public TLE/OMM data, "
        "not certified operational flight-dynamics commands."
    )
