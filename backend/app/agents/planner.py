import uuid
from typing import Optional, List
from datetime import datetime, timezone
from app.models.agent import TaskPlan, TaskStep
from app.core.logging import logger


class TaskPlanner:
    """
    Autonomous Task Planner for ORBITGUARD AI.
    Deconstructs high-level aerospace operator queries or collision alarms
    into actionable multi-step execution plans across specialized agents.
    """

    @staticmethod
    def generate_plan(query: str, target_norad_id: Optional[int] = None) -> TaskPlan:
        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
        target_id = target_norad_id or 25544  # Default to ISS if unspecified
        q_lower = query.lower()

        logger.info(f"TaskPlanner generating execution plan for target NORAD ID {target_id}...")

        steps: List[TaskStep] = [
            TaskStep(
                step_id=1,
                agent_name="MonitoringAgent",
                action="INSPECT_TELEMETRY",
                description=f"Inspect orbital elements, altitude parameters, and telemetry state for NORAD ID {target_id}."
            ),
            TaskStep(
                step_id=2,
                agent_name="PredictionAgent",
                action="PROPAGATE_TRAJECTORY",
                description=f"Propagate SGP4 trajectory over a 24-hour horizon to predict close-approach ephemerides."
            ),
            TaskStep(
                step_id=3,
                agent_name="CollisionAssessmentAgent",
                action="EVALUATE_COLLISION_PROBABILITY",
                description="Evaluate 3D miss distance, LVLH RIC decomposition, Foster 2D collision probability, and NASA CARA tier."
            )
        ]

        # Check if query requests maneuver or if an avoidance action might be needed
        wants_maneuver = any(w in q_lower for w in ["maneuver", "avoid", "burn", "plan", "collision", "danger", "threat"])
        if wants_maneuver:
            steps.append(TaskStep(
                step_id=4,
                agent_name="MissionPlanningAgent",
                action="PLAN_AVOIDANCE_BURN",
                description="Plan collision avoidance maneuver (CAM), compute delta-V and propellant, and establish Approval Checkpoint."
            ))

        # Always end with Mission Intelligence debrief
        next_id = len(steps) + 1
        steps.append(TaskStep(
            step_id=next_id,
            agent_name="IntelligenceReportingAgent",
            action="SYNTHESIZE_MISSION_REPORT",
            description="Synthesize executive aerospace debrief, verify audit trail, and enforce HITL safety governance."
        ))

        return TaskPlan(
            plan_id=plan_id,
            goal=query,
            target_norad_id=target_id,
            steps=steps,
            created_at=datetime.now(timezone.utc)
        )


task_planner = TaskPlanner()
