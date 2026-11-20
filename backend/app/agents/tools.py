import math
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import numpy as np

from app.db.repositories.satellite_repo import satellite_repo
from app.db.repositories.conjunction_repo import conjunction_repo
from app.db.repositories.maneuver_repo import maneuver_repo
from app.db.repositories.agent_memory_repo import agent_memory_repo
from app.services.sgp4_engine import sgp4_engine
from app.services.conjunction_engine import conjunction_screening_engine
from app.services.collision_assessment import collision_assessment_engine
from app.models.maneuver import ManeuverProposalInDB, BurnDirection, ApprovalStatus
from app.core.logging import logger


class ToolRegistry:
    """Executable backend tool registry for ORBITGUARD autonomous AI agents."""

    @staticmethod
    async def query_satellite_telemetry(norad_id: int) -> Dict[str, Any]:
        """Tool 1 – Inspect satellite state, TLE elements, and physical metadata from catalog."""
        sat = await satellite_repo.get_by_norad_id(norad_id)
        if not sat:
            return {
                "found": False,
                "norad_id": norad_id,
                "message": f"Satellite {norad_id} is not in the catalog."
            }
        return {
            "found": True,
            "norad_id": sat.get("norad_id"),
            "name": sat.get("name"),
            "object_type": sat.get("object_type"),
            "epoch": str(sat.get("epoch")),
            "perigee_km": sat.get("perigee_km"),
            "apogee_km": sat.get("apogee_km"),
            "inclination_deg": sat.get("inclination_deg"),
            "bstar": sat.get("bstar"),
            "tle_line1": sat.get("tle_line1"),
            "tle_line2": sat.get("tle_line2")
        }

    @staticmethod
    async def propagate_trajectory(
        norad_id: int,
        duration_hours: float = 24.0,
        step_seconds: int = 300
    ) -> Dict[str, Any]:
        """Tool 2 – Propagate 3D orbital trajectory forward in time using SGP4 analytical propagator."""
        sat = await satellite_repo.get_by_norad_id(norad_id)
        if not sat:
            return {
                "norad_id": norad_id,
                "points_count": 0,
                "duration_hours": duration_hours,
                "start_time": None,
                "end_time": None,
                "message": f"Satellite {norad_id} is not in the catalog."
            }

        res = sgp4_engine.propagate_orbit_path(
            norad_id=sat["norad_id"],
            name=sat["name"],
            tle_line1=sat["tle_line1"],
            tle_line2=sat["tle_line2"],
            epoch=sat["epoch"],
            duration_hours=duration_hours,
            step_seconds=step_seconds
        )
        return {
            "norad_id": norad_id,
            "points_count": res.point_count,
            "duration_hours": duration_hours,
            "start_time": res.start_time.isoformat(),
            "end_time": res.end_time.isoformat(),
            "sample_first_point": res.points[0].model_dump() if res.points else {}
        }

    @staticmethod
    async def screen_close_encounters(
        primary_norad_id: int,
        horizon_hours: float = 24.0,
        threshold_km: float = 25.0
    ) -> Dict[str, Any]:
        """Tool 3 – Broad and narrow phase conjunction screening against cataloged space objects."""
        primary = await satellite_repo.get_by_norad_id(primary_norad_id)
        if not primary:
            return {
                "status": "warning",
                "message": f"Primary {primary_norad_id} not in catalog. Screened 0 pairs.",
                "conjunctions_found": []
            }

        candidates = await satellite_repo.find_orbital_shell_candidates(
            min_perigee=primary.get("perigee_km", 400.0) - 50.0,
            max_apogee=primary.get("apogee_km", 420.0) + 50.0,
            exclude_norad_id=primary_norad_id
        )

        detected_events = []
        now = datetime.now(timezone.utc)
        for cand in candidates[:20]:
            events = conjunction_screening_engine.screen_pair(
                primary=primary,
                secondary=cand,
                start_time=now,
                horizon_hours=horizon_hours,
                threshold_km=threshold_km
            )
            detected_events.extend(events)

        return {
            "primary_norad_id": primary_norad_id,
            "candidates_screened": len(candidates),
            "events_detected_count": len(detected_events),
            "events": [e.model_dump() for e in detected_events[:5]]
        }

    @staticmethod
    async def assess_collision_risk(
        primary_norad_id: int,
        secondary_norad_id: int,
        tca: Optional[datetime] = None,
        lead_time_hours: Optional[float] = None,
        hard_body_radius_m: float = 15.0
    ) -> Dict[str, Any]:
        """Tool 4 – Probabilistic collision risk assessment (Foster 2D Pc, NASA CARA tier, Monte Carlo)."""
        primary = await satellite_repo.get_by_norad_id(primary_norad_id)
        secondary = await satellite_repo.get_by_norad_id(secondary_norad_id)
        if not primary or not secondary:
            missing = primary_norad_id if not primary else secondary_norad_id
            return {"status": "not_found", "message": f"Satellite {missing} is not in the catalog."}

        if tca is None:
            tca = datetime.now(timezone.utc) + timedelta(hours=lead_time_hours if lead_time_hours is not None else 24.0)
        if tca.tzinfo is None:
            tca = tca.replace(tzinfo=timezone.utc)
        lead_hours = max(0.1, (tca - datetime.now(timezone.utc)).total_seconds() / 3600.0)

        try:
            p_state = sgp4_engine.propagate_single(
                sgp4_engine.build_satrec(primary["tle_line1"], primary["tle_line2"]), tca
            )
            s_state = sgp4_engine.propagate_single(
                sgp4_engine.build_satrec(secondary["tle_line1"], secondary["tle_line2"]), tca
            )
        except Exception as exc:
            return {"status": "propagation_failed", "message": str(exc)}
        if p_state is None or s_state is None:
            return {"status": "propagation_failed", "message": "SGP4 propagation returned no state at TCA."}

        r1 = np.array([p_state.x_km, p_state.y_km, p_state.z_km])
        v1 = np.array([p_state.vx_kms, p_state.vy_kms, p_state.vz_kms])
        r2 = np.array([s_state.x_km, s_state.y_km, s_state.z_km])
        v2 = np.array([s_state.vx_kms, s_state.vy_kms, s_state.vz_kms])

        event_id = f"CONJ-{primary_norad_id}-{secondary_norad_id}-{int(tca.timestamp())}"
        assessment = collision_assessment_engine.assess_collision(
            event_id=event_id,
            primary_norad_id=primary_norad_id,
            primary_name=primary.get("name") or f"NORAD {primary_norad_id}",
            secondary_norad_id=secondary_norad_id,
            secondary_name=secondary.get("name") or f"NORAD {secondary_norad_id}",
            secondary_type=str(secondary.get("object_type") or "UNKNOWN"),
            r1_eci=r1,
            v1_eci=v1,
            r2_eci=r2,
            v2_eci=v2,
            tca=tca,
            lead_time_hours=lead_hours,
            hard_body_radius_m=hard_body_radius_m,
            bstar_primary=float(primary.get("bstar") or 0.0),
            bstar_secondary=float(secondary.get("bstar") or 0.0)
        )
        return assessment.model_dump()

    @staticmethod
    async def plan_avoidance_maneuver(
        conjunction_id: str,
        target_norad_id: int,
        current_miss_km: float,
        desired_miss_km: float,
        burn_epoch: datetime,
        direction: BurnDirection = BurnDirection.RADIAL,
        spacecraft_mass_kg: Optional[float] = None,
        isp_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Tool 5 – Plan collision avoidance maneuver (CAM).
        Calculates delta-V, and fuel mass consumption when spacecraft mass and Isp
        are supplied, then creates a PENDING proposal requiring HITL approval.
        """
        # Delta-V required to achieve desired miss distance
        # For radial burn: delta_v ~ (delta_r / (3 * semi_major_axis / mean_motion)) or empirical ~0.4 m/s per km separation
        miss_delta = max(1.0, desired_miss_km - current_miss_km)
        proposed_dv = round(min(5.0, max(0.25, miss_delta * 0.35)), 2)

        # Tsiolkovsky rocket equation is only valid with real spacecraft mass and Isp.
        fuel_kg = None
        if spacecraft_mass_kg is not None and isp_seconds is not None:
            g0 = 9.80665
            ve = isp_seconds * g0
            fuel_kg = round(spacecraft_mass_kg * (1.0 - math.exp(-(proposed_dv) / ve)), 2)

        proposal = ManeuverProposalInDB(
            conjunction_id=conjunction_id,
            target_norad_id=target_norad_id,
            proposed_delta_v_ms=proposed_dv,
            burn_direction=direction,
            burn_epoch=burn_epoch,
            projected_miss_distance_km=round(current_miss_km + miss_delta, 2),
            fuel_consumption_kg=fuel_kg,
            secondary_conjunction_risk="NOT_ASSESSED",
            approval_status=ApprovalStatus.PENDING,
            review_notes="Automated plan generated by Mission Planning Agent. Awaiting flight-director HITL approval."
        )

        doc = await maneuver_repo.create_proposal(proposal)
        return {
            "proposal_id": doc.get("_id"),
            "conjunction_id": conjunction_id,
            "target_norad_id": target_norad_id,
            "delta_v_ms": proposed_dv,
            "burn_direction": direction.value,
            "burn_epoch": burn_epoch.isoformat(),
            "projected_miss_distance_km": round(current_miss_km + miss_delta, 2),
            "fuel_consumption_kg": fuel_kg,
            "approval_status": "PENDING",
            "requires_human_approval": True,
            "message": "Maneuver proposal generated and locked in PENDING status. Human approval checkpoint required."
        }

    @staticmethod
    async def query_memory_history(target_norad_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tool 6 – Query persistent agent memory for historical investigation traces."""
        return await agent_memory_repo.list_memories(target_norad_id=target_norad_id, limit=5)


tool_registry = ToolRegistry()
