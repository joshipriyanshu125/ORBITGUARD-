import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.models.agent import (
    TaskPlan,
    AgentCommandRequest,
    AgentCommandResponse,
    AgentStepTrace,
    AgentInvestigationMemory
)
from app.agents.planner import task_planner
from app.agents.specialized import (
    MonitoringAgent,
    PredictionAgent,
    CollisionAssessmentAgent,
    MissionPlanningAgent,
    IntelligenceReportingAgent
)
from app.db.repositories.agent_memory_repo import agent_memory_repo
from app.models.maneuver import BurnDirection
from app.core.logging import logger


class AgentOrchestrator:
    """
    Week 8 Deliverable: Autonomous AI Agent Orchestrator.
    - Coordinates five specialized aerospace agents.
    - Manages task planning, tool calling, and inter-agent data flow.
    - Enforces persistent MongoDB memory retention across sessions.
    - Enforces strict Human-in-the-Loop approval checkpoints for orbital burns.
    """

    def __init__(self):
        self.monitoring_agent = MonitoringAgent()
        self.prediction_agent = PredictionAgent()
        self.collision_agent = CollisionAssessmentAgent()
        self.mission_planning_agent = MissionPlanningAgent()
        self.reporting_agent = IntelligenceReportingAgent()

    async def run_investigation(
        self,
        query: str,
        target_norad_id: Optional[int] = None,
        session_id: Optional[str] = None,
        custom_plan: Optional[TaskPlan] = None
    ) -> AgentCommandResponse:
        """
        Execute an autonomous multi-agent investigation workflow.
        """
        sess_id = session_id or f"SESS-{uuid.uuid4().hex[:10].upper()}"
        target_id = target_norad_id or 25544

        logger.info(f"[Orchestrator] Starting autonomous investigation session {sess_id} for target {target_id}...")

        # 1. Generate task plan if not provided
        plan = custom_plan or task_planner.generate_plan(query=query, target_norad_id=target_id)

        traces: List[AgentStepTrace] = []
        monitoring_out: Dict[str, Any] = {}
        prediction_out: Dict[str, Any] = {}
        assessment_out: Dict[str, Any] = {}
        planning_out: Optional[Dict[str, Any]] = None
        pending_proposal_dict: Optional[Dict[str, Any]] = None
        pending_proposal_id: Optional[str] = None
        approval_checkpoint_active: bool = False

        # 2. Sequential execution of planned task steps
        for step in plan.steps:
            step.status = "RUNNING"

            if step.agent_name == "MonitoringAgent":
                res = await self.monitoring_agent.execute(norad_id=target_id)
                monitoring_out = res["output"]
                traces.append(res["trace"])
                step.output = monitoring_out
                step.status = "COMPLETED"

            elif step.agent_name == "PredictionAgent":
                res = await self.prediction_agent.execute(norad_id=target_id, duration_hours=24.0)
                prediction_out = res["output"]
                traces.append(res["trace"])
                step.output = prediction_out
                step.status = "COMPLETED"

            elif step.agent_name == "CollisionAssessmentAgent":
                # Secondary defaults to Fengyun debris benchmark if unspecified
                sec_id = 39872
                res = await self.collision_agent.execute(
                    primary_norad_id=target_id,
                    secondary_norad_id=sec_id,
                    miss_distance_km=0.85,
                    relative_velocity_kms=14.2,
                    lead_time_hours=18.0
                )
                assessment_out = res["output"]
                traces.append(res["trace"])
                step.output = assessment_out
                step.status = "COMPLETED"

            elif step.agent_name == "MissionPlanningAgent":
                # Check if assessment warrants maneuver planning
                conj_id = assessment_out.get("event_id", f"CONJ-{target_id}-39872")
                curr_miss = assessment_out.get("miss_distance_km", 0.85)

                res = await self.mission_planning_agent.execute(
                    conjunction_id=conj_id,
                    target_norad_id=target_id,
                    current_miss_km=curr_miss,
                    desired_miss_km=8.0,
                    direction=BurnDirection.RADIAL
                )
                planning_out = res["output"]
                traces.append(res["trace"])
                step.output = planning_out
                step.status = "COMPLETED"

                approval_checkpoint_active = True
                pending_proposal_dict = res.get("proposal")
                pending_proposal_id = planning_out.get("proposal_id")

            elif step.agent_name == "IntelligenceReportingAgent":
                res = await self.reporting_agent.execute(
                    query=query,
                    session_id=sess_id,
                    monitoring_data=monitoring_out,
                    prediction_data=prediction_out,
                    assessment_data=assessment_out,
                    planning_data=planning_out
                )
                traces.append(res["trace"])
                step.output = res["output"]
                step.status = "COMPLETED"
                findings_summary = res["summary"]

        # 3. Save into Persistent Memory
        memory_record = AgentInvestigationMemory(
            session_id=sess_id,
            target_norad_id=target_id,
            query=query,
            plan=plan,
            agent_trace=traces,
            findings_summary=findings_summary,
            approval_checkpoint_reached=approval_checkpoint_active,
            maneuver_proposal_id=pending_proposal_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        await agent_memory_repo.save_memory(memory_record)
        logger.info(f"[Orchestrator] Investigation session {sess_id} committed to persistent memory.")

        return AgentCommandResponse(
            session_id=sess_id,
            query=query,
            plan=plan,
            findings_summary=findings_summary,
            approval_required=approval_checkpoint_active,
            pending_proposal_id=pending_proposal_id,
            pending_proposal=pending_proposal_dict,
            trace=traces
        )


agent_orchestrator = AgentOrchestrator()
