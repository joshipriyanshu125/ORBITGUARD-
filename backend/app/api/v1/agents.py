from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional

from app.models.agent import (
    AgentCommandRequest,
    AgentCommandResponse,
    TaskPlan
)
from app.models.maneuver import (
    ManeuverDecisionRequest,
    ApprovalStatus
)
from app.agents.orchestrator import agent_orchestrator
from app.agents.planner import task_planner
from app.db.repositories.agent_memory_repo import agent_memory_repo
from app.db.repositories.maneuver_repo import maneuver_repo
from app.core.logging import logger

router = APIRouter()


@router.post("/agents/command", response_model=AgentCommandResponse)
@router.post("/agents/orchestrate", response_model=AgentCommandResponse)
async def dispatch_agent_command(payload: Dict[str, Any] = Body(...)):
    """
    Week 8 Deliverable: Autonomous AI Command Bar Endpoint.
    - Dispatches multi-agent workflow coordinated by Agent Orchestrator.
    - Employs 5 specialized agents (Monitoring, Prediction, Collision, Mission Planning, Reporting).
    - Performs real tool calling and task planning.
    - Persists session traces into MongoDB agent memory.
    - Locks any generated avoidance burn into an Approval Checkpoint.
    """
    try:
        query_text = payload.get("query") or payload.get("goal") or "Analyze orbital collision risk"
        target_id = payload.get("target_norad_id")
        session_id = payload.get("session_id")
        response = await agent_orchestrator.run_investigation(
            query=query_text,
            target_norad_id=target_id,
            session_id=session_id
        )
        return response
    except Exception as e:
        logger.error(f"Error executing agent workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Agent orchestration failed: {str(e)}")


@router.post("/agents/plan", response_model=TaskPlan)
async def generate_investigation_plan(
    query: str = Query(..., description="Operator query or scenario description"),
    target_norad_id: Optional[int] = Query(default=None, description="Optional target NORAD ID")
):
    """
    Week 8 Deliverable: Task Planning Endpoint.
    Generates a structured execution plan across the 5 specialized agents.
    """
    plan = task_planner.generate_plan(query=query, target_norad_id=target_norad_id)
    return plan


@router.get("/agents/memory", response_model=List[Dict[str, Any]])
async def list_agent_memories(
    target_norad_id: Optional[int] = Query(default=None, description="Filter by target satellite NORAD ID"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Week 8 Deliverable: Persistent Memory Retrieval.
    Lists past multi-agent investigation sessions and execution traces from MongoDB.
    """
    memories = await agent_memory_repo.list_memories(target_norad_id=target_norad_id, limit=limit)
    return memories


@router.get("/agents/memory/{session_id}")
async def get_agent_session_memory(session_id: str):
    """
    Week 8 Deliverable: Retrieve specific agent investigation session by ID.
    """
    memory = await agent_memory_repo.get_memory(session_id=session_id)
    if not memory:
        raise HTTPException(status_code=404, detail=f"Agent memory session {session_id} not found.")
    return memory


@router.get("/agents/proposals", response_model=List[Dict[str, Any]])
@router.get("/agents/proposals/pending", response_model=List[Dict[str, Any]])
async def list_maneuver_proposals(
    status: Optional[str] = Query(default=None, description="Filter by PENDING, APPROVED, REJECTED"),
    target_norad_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100)
):
    """
    Week 8 Deliverable: Maneuver Proposals & Approval Checkpoint Queue.
    Lists collision avoidance burns awaiting or processed by Human-In-The-Loop operators.
    """
    proposals = await maneuver_repo.list_proposals(
        approval_status=status,
        target_norad_id=target_norad_id,
        limit=limit
    )
    return proposals


@router.post("/agents/proposals/{proposal_id}/decision")
async def submit_human_approval_decision(
    proposal_id: str,
    decision_payload: ManeuverDecisionRequest
):
    """
    Week 8 Deliverable: Human-in-the-Loop Approval Checkpoint Gate.
    Authorizes or rejects a planned avoidance maneuver burn.
    Requires explicit operator name and decision tag (APPROVED / REJECTED).
    """
    updated = await maneuver_repo.record_decision(
        proposal_id=proposal_id,
        operator_name=decision_payload.operator_name,
        decision=decision_payload.decision,
        notes=decision_payload.notes
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Maneuver proposal {proposal_id} not found.")

    return {
        "status": "success",
        "proposal_id": proposal_id,
        "decision": decision_payload.decision.value,
        "reviewed_by": decision_payload.operator_name,
        "reviewed_at": updated.get("reviewed_at"),
        "message": f"Maneuver proposal {proposal_id} successfully updated to {decision_payload.decision.value}."
    }
