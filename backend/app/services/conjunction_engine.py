from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sgp4.api import Satrec, WGS72, jday

from app.models.conjunction import ConjunctionBase, RiskLevel, ConjunctionStatus
from app.services.orbital_math import eci_to_lvlh
from app.services.sgp4_engine import sgp4_engine
from app.core.logging import logger


class ConjunctionScreeningEngine:
    """
    Two-phase Conjunction Assessment & Close-Approach Screening Engine.
    Phase 1: Broad-phase radial shell / apogee-perigee altitude filtering.
    Phase 2: Narrow-phase time-step ephemeris propagation & fine TCA minimization.
    """

    def broad_phase_filter(
        self,
        primary_apogee_km: float,
        primary_perigee_km: float,
        candidates: List[Dict[str, Any]],
        altitude_margin_km: float = 50.0
    ) -> List[Dict[str, Any]]:
        """
        Broad-phase spatial filter: Screen candidates based on radial shell intersection.
        Two orbits cannot intersect if primary perigee - margin > candidate apogee
        or candidate perigee - margin > primary apogee.
        """
        passed: List[Dict[str, Any]] = []
        p_min = primary_perigee_km - altitude_margin_km
        p_max = primary_apogee_km + altitude_margin_km

        for cand in candidates:
            c_perigee = cand.get("perigee_km", 0.0)
            c_apogee = cand.get("apogee_km", 0.0)
            
            # Intersection test
            if c_perigee <= p_max and c_apogee >= p_min:
                passed.append(cand)

        logger.info(
            f"Broad-phase filter: {len(passed)} of {len(candidates)} candidates passed "
            f"for shell [{p_min:.1f}, {p_max:.1f}] km"
        )
        return passed

    def _propagate_position_velocity(
        self,
        satrec: Satrec,
        dt: datetime
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Evaluate position and velocity in TEME (ECI) at given UTC datetime."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
        err, r, v = satrec.sgp4(jd, fr)
        if err != 0:
            return None
        return np.array(r, dtype=np.float64), np.array(v, dtype=np.float64)

    def _fine_minimize_tca(
        self,
        satrec1: Satrec,
        satrec2: Satrec,
        window_start: datetime,
        window_end: datetime,
        sub_step_seconds: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Fine-grained local minimum search within a coarse close approach interval.
        Performs 1-second grid search to pinpoint exact TCA and miss distance.
        """
        best_tca = window_start
        min_dist = float("inf")
        best_r1: Optional[np.ndarray] = None
        best_v1: Optional[np.ndarray] = None
        best_r2: Optional[np.ndarray] = None
        best_v2: Optional[np.ndarray] = None

        current = window_start
        step = timedelta(seconds=sub_step_seconds)

        while current <= window_end:
            pv1 = self._propagate_position_velocity(satrec1, current)
            pv2 = self._propagate_position_velocity(satrec2, current)

            if pv1 is not None and pv2 is not None:
                r1, v1 = pv1
                r2, v2 = pv2
                dist = float(np.linalg.norm(r1 - r2))
                if dist < min_dist:
                    min_dist = dist
                    best_tca = current
                    best_r1 = r1
                    best_v1 = v1
                    best_r2 = r2
                    best_v2 = v2

            current += step

        if best_r1 is None or best_r2 is None:
            return None

        rel_vel = float(np.linalg.norm(best_v1 - best_v2))
        return {
            "tca": best_tca,
            "miss_distance_km": round(min_dist, 3),
            "relative_velocity_kms": round(rel_vel, 3),
            "r1": best_r1.tolist(),
            "v1": best_v1.tolist(),
            "r2": best_r2.tolist(),
            "v2": best_v2.tolist(),
        }

    def compute_risk_classification(
        self,
        miss_distance_km: float,
        relative_velocity_kms: float
    ) -> Tuple[RiskLevel, float]:
        """
        Classify operational conjunction risk into LOW, MEDIUM, HIGH, CRITICAL
        and compute continuous risk score [0 - 100].
        """
        if miss_distance_km <= 1.0:
            level = RiskLevel.CRITICAL
            base_score = 90.0 + min(10.0, (1.0 - miss_distance_km) * 10.0)
        elif miss_distance_km <= 3.0:
            level = RiskLevel.HIGH
            base_score = 70.0 + (3.0 - miss_distance_km) * 10.0
        elif miss_distance_km <= 10.0:
            level = RiskLevel.MEDIUM
            base_score = 40.0 + (10.0 - miss_distance_km) * 4.0
        else:
            level = RiskLevel.LOW
            base_score = max(5.0, 30.0 - (miss_distance_km - 10.0) * 0.5)

        # Scale slightly with high hyper-velocity encounters (> 10 km/s)
        vel_weight = min(5.0, max(0.0, (relative_velocity_kms - 8.0) * 0.8))
        total_score = min(100.0, round(base_score + vel_weight, 1))

        return level, total_score

    def screen_pair(
        self,
        primary: Dict[str, Any],
        secondary: Dict[str, Any],
        start_time: datetime,
        horizon_hours: float = 48.0,
        coarse_step_seconds: int = 60,
        threshold_km: float = 25.0
    ) -> List[ConjunctionBase]:
        """
        Screen a primary satellite against a secondary object over a given time horizon.
        Returns list of detected close approach encounters.
        """
        try:
            satrec1 = sgp4_engine.build_satrec(primary["tle_line1"], primary["tle_line2"])
            satrec2 = sgp4_engine.build_satrec(secondary["tle_line1"], secondary["tle_line2"])
        except Exception as e:
            logger.warning(f"Failed to build satrec for screening pair: {e}")
            return []

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time = start_time.astimezone(timezone.utc)

        end_time = start_time + timedelta(hours=horizon_hours)
        step = timedelta(seconds=coarse_step_seconds)

        coarse_events: List[Tuple[datetime, float]] = []
        current = start_time
        prev_dist = float("inf")
        curr_dist = float("inf")
        was_decreasing = False

        # Coarse sweep
        while current <= end_time:
            pv1 = self._propagate_position_velocity(satrec1, current)
            pv2 = self._propagate_position_velocity(satrec2, current)

            if pv1 is not None and pv2 is not None:
                dist = float(np.linalg.norm(pv1[0] - pv2[0]))
                
                # Check for inflection point / local minimum under threshold
                if dist < threshold_km:
                    if dist > curr_dist and was_decreasing:
                        # Local minimum was at current - step
                        inflection_time = current - step
                        coarse_events.append((inflection_time, curr_dist))
                    was_decreasing = dist < curr_dist
                else:
                    was_decreasing = False

                prev_dist = curr_dist
                curr_dist = dist

            current += step

        conjunctions: List[ConjunctionBase] = []

        # Refine coarse local minima with fine sub-step minimization
        for event_time, _ in coarse_events:
            w_start = event_time - timedelta(seconds=coarse_step_seconds)
            w_end = event_time + timedelta(seconds=coarse_step_seconds)
            
            refined = self._fine_minimize_tca(satrec1, satrec2, w_start, w_end, sub_step_seconds=1.0)
            if not refined:
                continue

            miss_km = refined["miss_distance_km"]
            if miss_km <= threshold_km:
                tca = refined["tca"]
                rel_vel = refined["relative_velocity_kms"]
                r1 = refined["r1"]
                v1 = refined["v1"]
                r2 = refined["r2"]

                # Calculate LVLH relative coordinates
                radial, in_track, cross_track = eci_to_lvlh(r1, v1, r2)
                
                # Deterministic event_id: CONJ-PRIMARY-SECONDARY-YYYYMMDDTHHMMSS
                tca_slug = tca.strftime("%Y%m%dT%H%M%S")
                event_id = f"CONJ-{primary['norad_id']}-{secondary['norad_id']}-{tca_slug}"

                risk_lvl, risk_sc = self.compute_risk_classification(miss_km, rel_vel)
                
                status = ConjunctionStatus.AWAITING_APPROVAL if risk_lvl in [RiskLevel.HIGH, RiskLevel.CRITICAL] else ConjunctionStatus.DETECTED

                summary = (
                    f"Predicted close approach between {primary.get('name')} and {secondary.get('name')}. "
                    f"Miss distance: {miss_km} km at {tca.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
                    f"Relative velocity: {rel_vel} km/s. "
                    f"LVLH RIC offset: [R: {radial:.2f} km, I: {in_track:.2f} km, C: {cross_track:.2f} km]."
                )

                conj = ConjunctionBase(
                    event_id=event_id,
                    primary_norad_id=primary["norad_id"],
                    primary_name=primary["name"],
                    secondary_norad_id=secondary["norad_id"],
                    secondary_name=secondary["name"],
                    secondary_type=secondary.get("object_type", "DEBRIS"),
                    tca=tca,
                    miss_distance_km=miss_km,
                    relative_velocity_kms=rel_vel,
                    primary_position_eci=r1,
                    secondary_position_eci=r2,
                    risk_score=risk_sc,
                    risk_level=risk_lvl,
                    status=status,
                    analysis_summary=summary
                )
                conjunctions.append(conj)

        return conjunctions


conjunction_screening_engine = ConjunctionScreeningEngine()
