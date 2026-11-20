import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

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
from app.db.repositories.conjunction_repo import conjunction_repo
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

        # Resolve the target from the request or the most recent stored conjunction.
        conjunction = None
        target_id = target_norad_id
        if target_id is not None:
            stored = await conjunction_repo.list_conjunctions(primary_norad_id=target_id, limit=1)
            conjunction = stored[0] if stored else None
        else:
            stored = await conjunction_repo.list_conjunctions(limit=1)
            if stored:
                conjunction = stored[0]
                target_id = conjunction["primary_norad_id"]

        if target_id is None:
            raise ValueError(
                "No target NORAD ID was provided and no stored conjunction is available. "
                "Sync the catalog and run conjunction screening first."
            )

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
        findings_summary: str = ""
        conjunction_tca: Optional[datetime] = None

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
                if conjunction:
                    conj_tca = conjunction.get("tca")
                    if isinstance(conj_tca, str):
                        conj_tca = datetime.fromisoformat(conj_tca)
                    if conj_tca is not None and conj_tca.tzinfo is None:
                        conj_tca = conj_tca.replace(tzinfo=timezone.utc)
                    conjunction_tca = conj_tca
                    lead_hours = None
                    if conj_tca is not None:
                        lead_hours = max(0.1, (conj_tca - datetime.now(timezone.utc)).total_seconds() / 3600.0)
                    res = await self.collision_agent.execute(
                        primary_norad_id=target_id,
                        secondary_norad_id=conjunction["secondary_norad_id"],
                        tca=conj_tca,
                        lead_time_hours=lead_hours
                    )
                    assessment_out = res["output"]
                    traces.append(res["trace"])
                    step.output = assessment_out
                    step.status = "COMPLETED" if assessment_out.get("status") == "ASSESSED" else "FAILED"
                else:
                    assessment_out = {
                        "status": "NO_CONJUNCTION",
                        "message": f"No stored conjunction involves NORAD {target_id}. Run conjunction screening first.",
                        "requires_maneuver_planning": False
                    }
                    step.output = assessment_out
                    step.status = "SKIPPED"

            elif step.agent_name == "MissionPlanningAgent":
                if not assessment_out.get("requires_maneuver_planning") or not assessment_out.get("event_id"):
                    step.output = {
                        "status": "NOT_REQUIRED",
                        "message": assessment_out.get("message") or "No assessed conjunction warrants maneuver planning."
                    }
                    step.status = "SKIPPED"
                    continue

                conj_id = assessment_out["event_id"]
                curr_miss = assessment_out["miss_distance_km"]
                now = datetime.now(timezone.utc)
                burn_epoch = now + timedelta(minutes=10)
                if conjunction_tca and conjunction_tca - timedelta(hours=2) > now:
                    burn_epoch = conjunction_tca - timedelta(hours=2)

                res = await self.mission_planning_agent.execute(
                    conjunction_id=conj_id,
                    target_norad_id=target_id,
                    current_miss_km=curr_miss,
                    desired_miss_km=8.0,
                    burn_epoch=burn_epoch,
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
