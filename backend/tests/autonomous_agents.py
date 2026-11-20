import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from app.agents.tools import tool_registry
from app.agents.planner import task_planner
from app.agents.specialized import (
    MonitoringAgent,
    PredictionAgent,
    CollisionAssessmentAgent,
    MissionPlanningAgent,
    IntelligenceReportingAgent
)
from app.agents.orchestrator import agent_orchestrator
from app.db.repositories.agent_memory_repo import agent_memory_repo
from app.db.repositories.maneuver_repo import maneuver_repo
from app.models.maneuver import ManeuverProposalInDB, BurnDirection, ApprovalStatus


@pytest.mark.asyncio
async def test_tool_calling_registry(async_client: AsyncClient):
    await async_client.post("/api/catalog/sync?groups=stations")

    # 1. Query satellite telemetry
    sat_res = await tool_registry.query_satellite_telemetry(25544)
    assert sat_res["norad_id"] == 25544
    assert "name" in sat_res

    # 2. Trajectory propagation tool
    prop_res = await tool_registry.propagate_trajectory(25544, duration_hours=6.0)
    assert prop_res["points_count"] > 10
    assert prop_res["duration_hours"] == 6.0

    # 3. Collision risk tool
    risk_res = await tool_registry.assess_collision_risk(
        primary_norad_id=25544,
        secondary_norad_id=39872,
        lead_time_hours=18.0
    )
    assert "geometry" in risk_res
    assert "probabilistic" in risk_res
    assert risk_res["geometry"]["miss_distance_km"] > 0.0

    # 4. Maneuver planning tool
    plan_res = await tool_registry.plan_avoidance_maneuver(
        conjunction_id="CONJ-TEST-TOOL-1",
        target_norad_id=25544,
        desired_miss_km=8.0,
        current_miss_km=0.75,
        burn_epoch=datetime.now(timezone.utc),
        direction=BurnDirection.RADIAL,
        spacecraft_mass_kg=420000.0,
        isp_seconds=310.0
    )
    assert plan_res["approval_status"] == "PENDING"
    assert plan_res["requires_human_approval"] is True
    assert plan_res["delta_v_ms"] > 0.0
    assert plan_res["fuel_consumption_kg"] > 0.0


@pytest.mark.asyncio
async def test_five_specialized_agents_execution(async_client: AsyncClient):
    await async_client.post("/api/catalog/sync?groups=stations")

    # 1. Monitoring Agent
    mon_agent = MonitoringAgent()
    mon_out = await mon_agent.execute(norad_id=25544)
    assert mon_out["trace"].agent == "MonitoringAgent"
    assert mon_out["trace"].action == "INSPECT_TELEMETRY"
    assert mon_out["output"]["telemetry_health"] == "CATALOG_STATE_ONLY"

    # 2. Prediction Agent
    pred_agent = PredictionAgent()
    pred_out = await pred_agent.execute(norad_id=25544, duration_hours=12.0)
    assert pred_out["trace"].agent == "PredictionAgent"
    assert pred_out["output"]["prediction_horizon_hours"] == 12.0

    # 3. Collision Assessment Agent
    col_agent = CollisionAssessmentAgent()
    col_out = await col_agent.execute(
        primary_norad_id=25544,
        secondary_norad_id=39872,
        lead_time_hours=18.0
    )
    assert col_out["trace"].agent == "CollisionAssessmentAgent"
    assert col_out["output"]["status"] == "ASSESSED"
    assert "collision_probability_sci" in col_out["output"]
    assert isinstance(col_out["output"]["requires_maneuver_planning"], bool)

    # 4. Mission Planning Agent
    plan_agent = MissionPlanningAgent()
    plan_out = await plan_agent.execute(
        conjunction_id="CONJ-AGENT-TEST",
        target_norad_id=25544,
        current_miss_km=0.65,
        desired_miss_km=10.0,
        burn_epoch=datetime.now(timezone.utc),
        direction=BurnDirection.RADIAL
    )
    assert plan_out["trace"].agent == "MissionPlanningAgent"
    assert plan_out["output"]["approval_status"] == "PENDING"
    assert plan_out["output"]["approval_checkpoint_enforced"] is True

    # 5. Intelligence Reporting Agent
    rep_agent = IntelligenceReportingAgent()
    rep_out = await rep_agent.execute(
        query="Investigate threat to ISS",
        session_id="SESS-TEST-1",
        monitoring_data=mon_out["output"],
        prediction_data=pred_out["output"],
        assessment_data=col_out["output"],
        planning_data=plan_out["output"]
    )
    assert rep_out["trace"].agent == "IntelligenceReportingAgent"
    assert "MISSION INTELLIGENCE BRIEFING" in rep_out["summary"]
    assert "SAFETY DIRECTIVE" in rep_out["summary"]


def test_task_planner_decomposition():
    # Plan with maneuver requirement
    plan_with_burn = task_planner.generate_plan(
        query="Investigate collision danger for ISS and plan avoidance maneuver",
        target_norad_id=25544
    )
    assert len(plan_with_burn.steps) == 5
    agent_names = [s.agent_name for s in plan_with_burn.steps]
    assert agent_names == [
        "MonitoringAgent",
        "PredictionAgent",
        "CollisionAssessmentAgent",
        "MissionPlanningAgent",
        "IntelligenceReportingAgent"
    ]

    # Plan without burn keyword
    plan_monitor_only = task_planner.generate_plan(
        query="Check ISS current orbit and telemetry status",
        target_norad_id=25544
    )
    assert len(plan_monitor_only.steps) == 4
    assert "MissionPlanningAgent" not in [s.agent_name for s in plan_monitor_only.steps]


@pytest.mark.asyncio
async def test_agent_orchestrator_end_to_end(async_client: AsyncClient):
    await async_client.post("/api/catalog/sync?groups=stations")
    sess_id = "SESS-ORCHESTRATOR-TEST"
    resp = await agent_orchestrator.run_investigation(
        query="Investigate collision hazard for ISS with Fengyun debris and plan avoidance burn",
        target_norad_id=25544,
        session_id=sess_id
    )

    assert resp.session_id == sess_id
    assert len(resp.trace) >= 3
    assert resp.approval_required == (resp.pending_proposal_id is not None)
    assert "MISSION INTELLIGENCE BRIEFING" in resp.findings_summary

    # Verify persistent memory was saved and mirrors the approval state
    mem = await agent_memory_repo.get_memory(sess_id)
    assert mem is not None
    assert mem["session_id"] == sess_id
    assert mem["approval_checkpoint_reached"] is resp.approval_required


@pytest.mark.asyncio
async def test_approval_checkpoint_human_gate():
    # Create proposal in PENDING state
    proposal = ManeuverProposalInDB(
        conjunction_id="CONJ-HITL-GATE-TEST",
        target_norad_id=25544,
        proposed_delta_v_ms=0.85,
        burn_direction=BurnDirection.RADIAL,
        burn_epoch=datetime.now(timezone.utc),
        projected_miss_distance_km=9.5,
        fuel_consumption_kg=125.0,
        approval_status=ApprovalStatus.PENDING
    )
    created = await maneuver_repo.create_proposal(proposal)
    prop_id = created["_id"]

    # Verify it starts PENDING
    stored = await maneuver_repo.get_by_id(prop_id)
    assert stored["approval_status"] == ApprovalStatus.PENDING.value
    assert stored["reviewed_by"] is None

    # Submit Human-In-The-Loop Approval decision
    updated = await maneuver_repo.record_decision(
        proposal_id=prop_id,
        operator_name="Flight Director Marcus Vance",
        decision=ApprovalStatus.APPROVED,
        notes="Authorized 0.85 m/s radial burn at orbit node 42."
    )
    assert updated["approval_status"] == ApprovalStatus.APPROVED.value
    assert updated["reviewed_by"] == "Flight Director Marcus Vance"
    assert updated["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_autonomous_ai_api_endpoints(async_client: AsyncClient):
    # 1. Command bar endpoint
    cmd_resp = await async_client.post(
        "/api/agents/command",
        json={
            "query": "Evaluate ISS close encounter and propose avoidance maneuver",
            "target_norad_id": 25544
        }
    )
    assert cmd_resp.status_code == 200
    cmd_data = cmd_resp.json()
    assert "session_id" in cmd_data
    assert "findings_summary" in cmd_data
    assert len(cmd_data["trace"]) > 0
    assert "disclaimer" in cmd_data

    # 2. Task plan endpoint
    plan_resp = await async_client.post(
        "/api/agents/plan?query=Screen%20ISS%20collision%20risk&target_norad_id=25544"
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert "steps" in plan_data
    assert len(plan_data["steps"]) >= 4

    # 3. Persistent memory list
    mem_resp = await async_client.get("/api/agents/memory?limit=10")
    assert mem_resp.status_code == 200
    mem_list = mem_resp.json()
    assert isinstance(mem_list, list)

    # 4. Maneuver proposals list
    prop_resp = await async_client.get("/api/agents/proposals")
    assert prop_resp.status_code == 200
    prop_list = prop_resp.json()
    assert isinstance(prop_list, list)

    # 5. Submit approval decision endpoint
    if prop_list:
        target_prop = prop_list[0]
        prop_id = target_prop["_id"]
        dec_resp = await async_client.post(
            f"/api/agents/proposals/{prop_id}/decision",
            json={
                "operator_name": "Commander Sarah Chen",
                "decision": "APPROVED",
                "notes": "Verified secondary clearances. Burn authorized."
            }
        )
        assert dec_resp.status_code == 200
        dec_data = dec_resp.json()
        assert dec_data["decision"] == "APPROVED"
        assert dec_data["reviewed_by"] == "Commander Sarah Chen"
