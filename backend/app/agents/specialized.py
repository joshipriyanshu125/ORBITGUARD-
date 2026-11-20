from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.agents.tools import tool_registry
from app.models.agent import AgentStepTrace
from app.models.maneuver import BurnDirection
from app.core.logging import logger


class BaseSpecializedAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def _create_trace(
        self,
        action: str,
        input_data: Optional[Dict[str, Any]],
        output_data: Optional[Dict[str, Any]],
        status: str = "COMPLETED"
    ) -> AgentStepTrace:
        return AgentStepTrace(
            agent=self.name,
            action=action,
            input_data=input_data,
            output_data=output_data,
            status=status,
            timestamp=datetime.now(timezone.utc)
        )


class MonitoringAgent(BaseSpecializedAgent):
    """Agent 1 – Orbital Monitoring & Telemetry Inspection Agent."""

    def __init__(self):
        super().__init__(name="MonitoringAgent", role="Orbital Telemetry & Catalog Monitoring")

    async def execute(self, norad_id: int) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Inspecting orbital catalog state for NORAD ID {norad_id}...")
        telemetry = await tool_registry.query_satellite_telemetry(norad_id)
        
        found = telemetry.get("found", False)
        output = {
            "found": found,
            "satellite_name": telemetry.get("name"),
            "norad_id": norad_id,
            "object_type": telemetry.get("object_type"),
            "apogee_km": telemetry.get("apogee_km"),
            "perigee_km": telemetry.get("perigee_km"),
            "bstar_drag": telemetry.get("bstar"),
            "telemetry_health": "CATALOG_STATE_ONLY" if found else "UNKNOWN",
            "monitoring_status": "ACTIVE_MONITORING" if found else "NOT_IN_CATALOG"
        }
        trace = self._create_trace("INSPECT_TELEMETRY", {"norad_id": norad_id}, output)
        return {"output": output, "trace": trace}


class PredictionAgent(BaseSpecializedAgent):
    """Agent 2 – Ephemeris Propagation & Orbit Prediction Agent."""

    def __init__(self):
        super().__init__(name="PredictionAgent", role="SGP4 Orbital Propagation & Trajectory Prediction")

    async def execute(self, norad_id: int, duration_hours: float = 24.0) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Propagating trajectory for NORAD ID {norad_id} over {duration_hours}h...")
        prop_data = await tool_registry.propagate_trajectory(norad_id, duration_hours=duration_hours)
        
        points_count = prop_data.get("points_count") or 0
        output = {
            "norad_id": norad_id,
            "propagator_engine": "SGP4 (WGS-72/84 Analytical)",
            "prediction_horizon_hours": duration_hours,
            "trajectory_points_computed": points_count,
            "ephemeris_validity": "COMPUTED" if points_count > 0 else "UNAVAILABLE",
            "start_time": prop_data.get("start_time"),
            "end_time": prop_data.get("end_time")
        }
        trace = self._create_trace("PROPAGATE_TRAJECTORY", {"norad_id": norad_id, "horizon_hours": duration_hours}, output)
        return {"output": output, "trace": trace}


class CollisionAssessmentAgent(BaseSpecializedAgent):
    """Agent 3 – Conjunction Screening & Probabilistic Collision Assessment Agent."""

    def __init__(self):
        super().__init__(name="CollisionAssessmentAgent", role="Conjunction Screening & Probabilistic Risk Assessment")

    async def execute(
        self,
        primary_norad_id: int,
        secondary_norad_id: int,
        tca: Optional[datetime] = None,
        lead_time_hours: Optional[float] = None
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Assessing collision threat between {primary_norad_id} and {secondary_norad_id}...")
        assessment = await tool_registry.assess_collision_risk(
            primary_norad_id=primary_norad_id,
            secondary_norad_id=secondary_norad_id,
            tca=tca,
            lead_time_hours=lead_time_hours
        )

        if assessment.get("status") in ("not_found", "propagation_failed"):
            output = {
                "status": assessment["status"],
                "message": assessment.get("message"),
                "requires_maneuver_planning": False
            }
            trace = self._create_trace("EVALUATE_COLLISION_PROBABILITY", {"primary": primary_norad_id, "secondary": secondary_norad_id}, output, status="FAILED")
            return {"output": output, "trace": trace, "full_assessment": assessment}

        prob = assessment.get("probabilistic", {})
        geom = assessment.get("geometry", {})
        score = assessment.get("composite_risk_score", 0.0)

        output = {
            "status": "ASSESSED",
            "event_id": assessment.get("event_id"),
            "primary_norad_id": primary_norad_id,
            "secondary_norad_id": secondary_norad_id,
            "miss_distance_km": geom.get("miss_distance_km"),
            "radial_separation_km": geom.get("radial_miss_km"),
            "relative_velocity_kms": geom.get("relative_velocity_kms"),
            "collision_probability_sci": prob.get("collision_probability_sci"),
            "nasa_cara_tier": prob.get("nasa_cara_tier"),
            "operational_severity": prob.get("operational_severity"),
            "composite_risk_score": score,
            "requires_maneuver_planning": score >= 70.0 or prob.get("operational_severity") == "CRITICAL"
        }
        trace = self._create_trace("EVALUATE_COLLISION_PROBABILITY", {"primary": primary_norad_id, "secondary": secondary_norad_id}, output)
        return {"output": output, "trace": trace, "full_assessment": assessment}


class MissionPlanningAgent(BaseSpecializedAgent):
    """Agent 4 – Collision Avoidance Maneuver (CAM) Planning & Approval Checkpoint Agent."""

    def __init__(self):
        super().__init__(name="MissionPlanningAgent", role="Collision Avoidance Maneuver Planning & HITL Gate")

    async def execute(
        self,
        conjunction_id: str,
        target_norad_id: int,
        current_miss_km: float,
        desired_miss_km: float,
        burn_epoch: datetime,
        direction: BurnDirection = BurnDirection.RADIAL,
        spacecraft_mass_kg: Optional[float] = None,
        isp_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Planning collision avoidance maneuver for NORAD ID {target_norad_id}...")
        plan_res = await tool_registry.plan_avoidance_maneuver(
            conjunction_id=conjunction_id,
            target_norad_id=target_norad_id,
            desired_miss_km=desired_miss_km,
            current_miss_km=current_miss_km,
            burn_epoch=burn_epoch,
            direction=direction,
            spacecraft_mass_kg=spacecraft_mass_kg,
            isp_seconds=isp_seconds
        )

        output = {
            "proposal_id": plan_res.get("proposal_id"),
            "target_norad_id": target_norad_id,
            "conjunction_id": conjunction_id,
            "delta_v_ms": plan_res.get("delta_v_ms"),
            "burn_direction": plan_res.get("burn_direction"),
            "fuel_consumption_kg": plan_res.get("fuel_consumption_kg"),
            "projected_miss_distance_km": plan_res.get("projected_miss_distance_km"),
            "approval_status": "PENDING",
            "approval_checkpoint_enforced": True,
            "action_directive": "AWAITING_HUMAN_IN_THE_LOOP_AUTHORIZATION"
        }
        trace = self._create_trace("PLAN_AVOIDANCE_BURN", {"conjunction_id": conjunction_id, "target": target_norad_id}, output)
        return {"output": output, "trace": trace, "proposal": plan_res}


class IntelligenceReportingAgent(BaseSpecializedAgent):
    """Agent 5 – Aerospace Mission Intelligence & Audit Reporting Agent."""

    def __init__(self):
        super().__init__(name="IntelligenceReportingAgent", role="Aerospace Mission Intelligence & Debrief Synthesis")

    async def execute(
        self,
        query: str,
        session_id: str,
        monitoring_data: Dict[str, Any],
        prediction_data: Dict[str, Any],
        assessment_data: Dict[str, Any],
        planning_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Synthesizing operational mission briefing for session {session_id}...")
        
        p_found = monitoring_data.get("found", False)
        p_name = monitoring_data.get("satellite_name") or "UNKNOWN"
        p_id = monitoring_data.get("norad_id")
        miss_km = assessment_data.get("miss_distance_km")
        pc_str = assessment_data.get("collision_probability_sci")
        severity = assessment_data.get("operational_severity") or "NOT_ASSESSED"
        score = assessment_data.get("composite_risk_score")

        asset_clause = (
            f"Primary {p_name} (NORAD {p_id}) is present in the catalog.\n"
            if p_found else
            f"Primary NORAD {p_id} is not present in the catalog; no orbital state was available.\n"
        )
        if miss_km is None:
            assessment_clause = f"COLLISION ASSESSMENT: {assessment_data.get('message') or 'No conjunction assessment was performed.'}"
        else:
            assessment_clause = (
                f"COLLISION ASSESSMENT: Miss distance is {miss_km} km with evaluated Pc = {pc_str} "
                f"({severity}, composite priority {score}/100)."
            )

        maneuver_clause = ""
        if planning_data and planning_data.get("approval_checkpoint_enforced"):
            dv = planning_data.get("delta_v_ms")
            prop_id = planning_data.get("proposal_id")
            fuel = planning_data.get("fuel_consumption_kg")
            maneuver_clause = (
                f"\n\nMANEUVER PROPOSAL GENERATED (APPROVAL GATE ACTIVE):\n"
                f"- Proposal ID: {prop_id}\n"
                f"- Recommended Burn: {planning_data.get('burn_direction')} delta-V of {dv} m/s\n"
                f"- Estimated Propellant Consumption: {fuel} kg\n"
                f"- Projected Miss Distance Post-Burn: {planning_data.get('projected_miss_distance_km')} km\n"
                f"- Approval Status: PENDING (Explicit Human-in-the-Loop authorization strictly required before execution)."
            )

        summary = (
            f"MISSION INTELLIGENCE BRIEFING [Session: {session_id}]\n"
            f"Query: \"{query}\"\n\n"
            f"1. ASSET STATUS: {asset_clause}"
            f"2. ORBIT PREDICTION: {prediction_data.get('trajectory_points_computed', 0)} SGP4 trajectory points "
            f"computed over {prediction_data.get('prediction_horizon_hours', 24)}h "
            f"({prediction_data.get('ephemeris_validity', 'UNAVAILABLE')}).\n"
            f"3. {assessment_clause}"
            f"{maneuver_clause}\n\n"
            f"SAFETY DIRECTIVE: Analytical output only. No automated orbital burn shall be commanded "
            f"without operator sign-off."
        )

        output = {
            "session_id": session_id,
            "briefing_text": summary,
            "severity": severity,
            "composite_score": score,
            "audit_compliance": "ANALYTICAL_NOT_CERTIFIED"
        }
        trace = self._create_trace("SYNTHESIZE_MISSION_REPORT", {"session_id": session_id}, output)
        return {"output": output, "trace": trace, "summary": summary}
