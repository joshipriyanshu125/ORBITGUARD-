"""
Week 12 – Agent Reliability Tests.
Tests orchestrator consistency, error recovery, tool registry completeness,
memory persistence, and approval workflow state machine.
"""
import pytest
from datetime import datetime, timezone

from app.agents.orchestrator import agent_orchestrator, AgentOrchestrator
from app.agents.planner import task_planner, TaskPlanner
from app.agents.specialized import (
    MonitoringAgent,
    PredictionAgent,
    CollisionAssessmentAgent,
    MissionPlanningAgent,
    IntelligenceReportingAgent,
)
from app.agents.tools import tool_registry, ToolRegistry
from app.db.repositories.agent_memory_repo import agent_memory_repo
from app.db.repositories.maneuver_repo import maneuver_repo
from app.models.maneuver import ApprovalStatus, BurnDirection


# ------ Orchestrator Consistency ------
async def test_orchestrator_repeated_execution_consistency():
    """
    Run orchestrator multiple times with the same goal and verify consistent output structure.
    """
    query = "Assess collision risk for ISS"
    results = []
    
    for i in range(3):
        result = await agent_orchestrator.run_investigation(
            query=query,
            target_norad_id=25544,
            session_id=f"CONSISTENCY-TEST-{i}"
        )
        results.append(result)
    
    for i, r in enumerate(results):
        assert r.session_id == f"CONSISTENCY-TEST-{i}"
        assert r.query == query
        assert r.plan is not None
        assert r.plan.steps is not None
        assert len(r.plan.steps) >= 3, f"Run {i}: Expected >=3 steps, got {len(r.plan.steps)}"
        assert r.findings_summary is not None
        assert len(r.findings_summary) > 0
        assert r.trace is not None
        assert len(r.trace) >= 3
    
    step_counts = [len(r.plan.steps) for r in results]
    assert len(set(step_counts)) == 1, f"Inconsistent step counts: {step_counts}"


# ------ Error Recovery ------
async def test_agent_error_recovery_invalid_norad():
    """
    Pass an invalid NORAD ID and verify graceful handling without crashing.
    """
    result = await agent_orchestrator.run_investigation(
        query="Check satellite status",
        target_norad_id=9999999,
        session_id="ERROR-RECOVERY-TEST"
    )
    
    assert result is not None
    assert result.session_id == "ERROR-RECOVERY-TEST"
    assert result.findings_summary is not None
    assert result.trace is not None
    assert len(result.trace) >= 3


async def test_tool_error_recovery_missing_satellite():
    """
    Call tool registry functions with non-existent satellite and verify fallback behavior.
    """
    telemetry = await tool_registry.query_satellite_telemetry(norad_id=1)
    assert telemetry is not None
    assert "norad_id" in telemetry
    
    prop = await tool_registry.propagate_trajectory(norad_id=1, duration_hours=1.0)
    assert prop is not None
    assert "points_count" in prop
    assert prop["points_count"] == 0
    assert prop["start_time"] is None


# ------ Tool Registry Completeness ------
def test_tool_registry_completeness():
    """
    Verify all 6 tool functions exist in the registry and are callable.
    """
    tools = [
        "query_satellite_telemetry",
        "propagate_trajectory",
        "screen_close_encounters",
        "assess_collision_risk",
        "plan_avoidance_maneuver",
        "query_memory_history",
    ]
    
    for tool_name in tools:
        assert hasattr(tool_registry, tool_name), f"Tool '{tool_name}' missing from registry"
        func = getattr(tool_registry, tool_name)
        assert callable(func), f"Tool '{tool_name}' is not callable"


async def test_tool_registry_execution(async_client):
    """
    Execute tools and verify structured output.
    """
    await async_client.post("/api/catalog/sync?groups=stations")
    telemetry = await tool_registry.query_satellite_telemetry(25544)
    assert isinstance(telemetry, dict)
    assert "norad_id" in telemetry
    
    prop = await tool_registry.propagate_trajectory(25544, duration_hours=1.0)
    assert isinstance(prop, dict)
    assert "points_count" in prop
    
    assessment = await tool_registry.assess_collision_risk(
        primary_norad_id=25544,
        secondary_norad_id=39872,
        lead_time_hours=18.0
    )
    assert isinstance(assessment, dict)
    assert "event_id" in assessment


# ------ Memory Persistence ------
async def test_memory_persistence_and_retrieval():
    """
    Store an investigation in memory, then retrieve and verify integrity.
    """
    result = await agent_orchestrator.run_investigation(
        query="Check debris threat",
        target_norad_id=25544,
        session_id="MEMORY-PERSIST-TEST"
    )
    assert result is not None
    
    memories = await agent_memory_repo.list_memories(target_norad_id=25544, limit=10)
    assert isinstance(memories, list)
    
    found = False
    for mem in memories:
        if isinstance(mem, dict) and mem.get("session_id") == "MEMORY-PERSIST-TEST":
            found = True
            assert mem["target_norad_id"] == 25544
            assert mem["query"] == "Check debris threat"
            break
    
    assert found, "Memory record 'MEMORY-PERSIST-TEST' not found after save"


# ------ Approval Workflow State Machine ------
async def test_approval_workflow_state_machine():
    """
    Test approval workflow: proposals start in PENDING state with human approval checkpoint.
    """
    plan = await tool_registry.plan_avoidance_maneuver(
        conjunction_id="CONJ-STATE-MACHINE",
        target_norad_id=25544,
        desired_miss_km=8.0,
        current_miss_km=1.0,
        burn_epoch=datetime.now(timezone.utc),
        direction=BurnDirection.PROGRADE
    )
    assert plan["approval_status"] == "PENDING"
    assert plan["requires_human_approval"] is True
    assert plan.get("proposal_id") is not None


# ------ Task Planner & Specialized Agents ------
def test_task_planner_and_specialized_agents():
    """
    Verify task planner decomposition and agent instantiations.
    """
    plan = task_planner.generate_plan("Plan collision avoidance maneuver", target_norad_id=25544)
    assert len(plan.steps) >= 4
    agent_names = [s.agent_name for s in plan.steps]
    assert "MonitoringAgent" in agent_names
    assert "PredictionAgent" in agent_names
    assert "CollisionAssessmentAgent" in agent_names
    assert "MissionPlanningAgent" in agent_names
    assert "IntelligenceReportingAgent" in agent_names

    agents = [
        MonitoringAgent(),
        PredictionAgent(),
        CollisionAssessmentAgent(),
        MissionPlanningAgent(),
        IntelligenceReportingAgent(),
    ]
    for agent in agents:
        assert agent.name is not None
        assert agent.role is not None
