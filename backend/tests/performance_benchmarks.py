"""
Week 12 – System Performance Benchmarks.
Measures API response times, concurrent request handling, SGP4 throughput,
collision assessment computation time, and simulation engine throughput.
"""
import pytest
import time
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta

from app.services.sgp4_engine import sgp4_engine, SGP4Engine
from app.services.collision_assessment import collision_assessment_engine
from app.services.simulation_engine import simulation_engine
from app.models.simulation import (
    HypotheticalScenarioRequest,
    ScenarioType,
)


# ISS TLE with verified modulo 10 checksums (Line 1: 6, Line 2: 8)
ISS_L1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9996"
ISS_L2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451238"


# ------ API Response Times ------
async def test_api_response_times(async_client):
    """
    Measure response latency for all major API endpoints.
    Each endpoint call has an effective 2-second deadline enforced via asyncio.wait_for.
    """
    endpoints = [
        ("GET", "/"),
        ("GET", "/api/health"),
        ("GET", "/api/satellites"),
        ("GET", "/api/satellites?limit=10"),
    ]
    
    for method, path in endpoints:
        start = time.perf_counter()
        if method == "GET":
            # Enforce strict 2-second timeout on request execution
            resp = await asyncio.wait_for(async_client.get(path), timeout=2.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}"
        assert elapsed_ms < 2000, f"{method} {path} took {elapsed_ms:.0f}ms (>2000ms)"


async def test_concurrent_request_handling(async_client):
    """
    Simulate 10 concurrent API requests and verify all complete successfully.
    """
    async def fetch(path):
        return await async_client.get(path)
    
    tasks = [fetch("/api/health") for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    for resp in results:
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ------ SGP4 Propagation Throughput ------
def test_sgp4_propagation_throughput():
    """
    Measure propagations/second for bulk SGP4 computation.
    Should handle at least 100 propagation steps/second.
    """
    satrec = SGP4Engine.build_satrec(ISS_L1, ISS_L2)
    base_dt = datetime(2024, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    
    num_points = 500
    start = time.perf_counter()
    for i in range(num_points):
        dt = base_dt + timedelta(seconds=i * 60)
        pt = SGP4Engine.propagate_single(satrec, dt)
        assert pt is not None
    elapsed = time.perf_counter() - start
    
    throughput = num_points / elapsed
    assert throughput >= 100.0, f"SGP4 throughput {throughput:.0f} pts/s below 100 pts/s minimum"


def test_sgp4_batch_propagation_throughput():
    """
    Measure batch propagation throughput for multiple satellites × multiple times.
    Verifies that all values in both positions and velocity outputs are finite.
    """
    satrec = SGP4Engine.build_satrec(ISS_L1, ISS_L2)
    n_sats = 5
    n_times = 50
    satrecs = [satrec] * n_sats
    times = [datetime(2024, 5, 4, tzinfo=timezone.utc) + timedelta(minutes=i * 10) for i in range(n_times)]
    
    start = time.perf_counter()
    positions, velocities = SGP4Engine.batch_propagate_positions(satrecs, times)
    elapsed = time.perf_counter() - start
    
    total_props = n_sats * n_times
    assert positions.shape == (n_sats, n_times, 3)
    assert velocities.shape == (n_sats, n_times, 3)
    throughput = total_props / elapsed
    assert throughput >= 50.0, f"Batch throughput {throughput:.0f} props/s below 50 props/s"

    # Require all values in both positions and velocity outputs to be finite (no NaNs, no infinities)
    assert np.all(np.isfinite(positions)), "Non-finite values found in batch propagation positions"
    assert np.all(np.isfinite(velocities)), "Non-finite values found in batch propagation velocities"


# ------ Collision Assessment Computation Time ------
def test_collision_assessment_computation_time():
    """
    Measure time for a full collision assessment pipeline (Foster 2D + Monte Carlo).
    Should complete within 2 seconds.
    """
    r1 = np.array([6800.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.6, 0.0])
    r2 = np.array([6800.5, 0.8, 0.3])
    v2 = np.array([0.0, -6.0, 0.0])
    tca = datetime.now(timezone.utc) + timedelta(hours=18)
    
    start = time.perf_counter()
    result = collision_assessment_engine.assess_collision(
        event_id="PERF-TEST-001",
        primary_norad_id=25544,
        primary_name="ISS",
        secondary_norad_id=39872,
        secondary_name="DEBRIS",
        secondary_type="DEBRIS",
        r1_eci=r1,
        v1_eci=v1,
        r2_eci=r2,
        v2_eci=v2,
        tca=tca,
        lead_time_hours=18.0,
        hard_body_radius_m=15.0
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert result is not None
    assert result.geometry is not None
    assert result.uncertainty is not None
    assert result.probabilistic is not None
    assert result.explainability_report is not None
    assert elapsed_ms < 2000, f"Collision assessment took {elapsed_ms:.0f}ms (>2000ms)"


def test_collision_ranking_throughput():
    """
    Measure event ranking throughput for a batch of conjunction events.
    """
    events = []
    for i in range(20):
        events.append({
            "event_id": f"CONJ-BENCH-{i}",
            "primary_norad_id": 25544,
            "secondary_norad_id": 30000 + i,
            "miss_distance_km": 0.5 + i * 0.3,
            "radial_miss_km": 0.2 + i * 0.1,
            "relative_velocity_kms": 12.0 + (i % 5),
            "collision_probability": 1e-5 / (1 + i),
            "lead_time_hours": 6 + i * 2,
            "secondary_type": "DEBRIS",
        })
    
    start = time.perf_counter()
    ranking = collision_assessment_engine.rank_conjunction_events(events)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert ranking is not None
    assert ranking.total_events_evaluated == 20
    assert len(ranking.ranked_queue) == 20
    assert ranking.ranked_queue[0].rank == 1
    assert elapsed_ms < 500, f"Ranking 20 events took {elapsed_ms:.0f}ms (>500ms)"


# ------ Simulation Engine Throughput ------
def test_simulation_engine_throughput():
    """
    Measure candidate maneuver generation and trajectory comparison throughput independently.
    Applies dedicated timers and budgets to both phases.
    """
    # 1. Candidate maneuver generation benchmark
    start_gen = time.perf_counter()
    candidates = simulation_engine.generate_candidate_maneuvers(
        initial_miss_km=1.0,
        desired_miss_km=10.0,
        relative_velocity_kms=13.5,
        lead_time_hours=18.0,
        semi_major_axis_km=6800.0,
        spacecraft_dry_mass_kg=4000.0,
        spacecraft_propellant_mass_kg=200.0,
        thruster_isp_seconds=310.0
    )
    elapsed_gen_ms = (time.perf_counter() - start_gen) * 1000
    assert len(candidates) == 5
    assert elapsed_gen_ms < 3000, f"Candidate generation took {elapsed_gen_ms:.0f}ms (>3000ms budget)"

    # 2. Independent trajectory comparison benchmark
    start_comp = time.perf_counter()
    comparison = simulation_engine.compare_trajectories(
        candidate=candidates[0],
        initial_miss_km=1.0,
        semi_major_axis_km=6800.0,
        lead_time_hours=18.0,
        num_steps=24
    )
    elapsed_comp_ms = (time.perf_counter() - start_comp) * 1000
    assert comparison is not None
    assert len(comparison.trajectory_points) == 25
    assert elapsed_comp_ms < 1000, f"Trajectory comparison took {elapsed_comp_ms:.0f}ms (>1000ms budget)"
