import math
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import numpy as np

from app.models.simulation import (
    ManeuverType,
    ScenarioType,
    ManeuverCandidate,
    TrajectoryComparisonPoint,
    TrajectoryComparisonResult,
    HypotheticalScenarioRequest,
    HypotheticalScenarioResponse
)
from app.services.collision_assessment import collision_assessment_engine
from app.core.logging import logger

# Aerospace gravitational constants
EARTH_MU = 398600.4418  # km^3 / s^2
EARTH_RADIUS_KM = 6378.137
G0_M_S2 = 9.80665


class SimulationEngine:
    """
    Week 9 Deliverable: Simulation Laboratory & Orbital Maneuver Simulation Engine.
    - Simulates high-precision orbital maneuver dynamics via Clohessy-Wiltshire / Hill equations.
    - Generates and evaluates candidate avoidance maneuver strategies (prograde, retrograde, radial, normal, Hohmann).
    - Compares propellant mass consumption via the Tsiolkovsky rocket equation.
    - Compares pre-burn vs post-burn 3D trajectories and separation geometries.
    - Executes hypothetical 'What-If' scenarios (debris storms, low-thrust phasing, secondary collision checks, fuel caps).
    """

    def compute_clohessy_wiltshire_perturbation(
        self,
        semi_major_axis_km: float,
        dv_radial_ms: float,
        dv_in_track_ms: float,
        dv_cross_track_ms: float,
        dt_seconds: float
    ) -> Tuple[float, float, float]:
        """
        Clohessy-Wiltshire (Hill's) analytical relative motion equations:
        Computes 3D relative displacement (dr, dy, dz) in LVLH frame resulting
        from an impulsive delta-V burn at t = 0 after elapsed time dt_seconds.
        """
        if semi_major_axis_km <= EARTH_RADIUS_KM:
            semi_major_axis_km = 6800.0

        # Mean orbital motion n = sqrt(mu / a^3) in rad/s
        n = math.sqrt(EARTH_MU / (semi_major_axis_km ** 3))
        nt = n * dt_seconds

        # Convert delta-V from m/s to km/s
        dvr = dv_radial_ms / 1000.0
        dvt = dv_in_track_ms / 1000.0
        dvn = dv_cross_track_ms / 1000.0

        # 1. Radial displacement: dr = (dvr/n)*sin(nt) + (2*dvt/n)*(1 - cos(nt))
        dr = (dvr / n) * math.sin(nt) + (2.0 * dvt / n) * (1.0 - math.cos(nt))

        # 2. In-track displacement: dy = (2*dvr/n)*(cos(nt) - 1) + (dvt/n)*(4*sin(nt) - 3*nt)
        # Note the dominant secular drift term: -3 * dvt * dt
        dy = (2.0 * dvr / n) * (math.cos(nt) - 1.0) + (dvt / n) * (4.0 * math.sin(nt) - 3.0 * nt)

        # 3. Cross-track displacement: dz = (dvn/n)*sin(nt)
        dz = (dvn / n) * math.sin(nt)

        return float(dr), float(dy), float(dz)

    def calculate_propellant_consumption(
        self,
        total_mass_kg: float,
        delta_v_ms: float,
        isp_seconds: float = 310.0
    ) -> float:
        """
        Tsiolkovsky Rocket Equation:
        delta_m = m_total * (1 - exp(-delta_v / (Isp * g0)))
        """
        if delta_v_ms <= 0:
            return 0.0
        ve = isp_seconds * G0_M_S2
        prop_mass = total_mass_kg * (1.0 - math.exp(-delta_v_ms / ve))
        return round(float(prop_mass), 3)

    def generate_candidate_maneuvers(
        self,
        initial_miss_km: float,
        desired_miss_km: float,
        relative_velocity_kms: float,
        lead_time_hours: float,
        semi_major_axis_km: float,
        spacecraft_dry_mass_kg: float,
        spacecraft_propellant_mass_kg: float,
        thruster_isp_seconds: float = 310.0
    ) -> List[ManeuverCandidate]:
        """
        Generate diverse candidate avoidance maneuvers and benchmark them against
        safety corridor criteria, fuel cost, and post-maneuver collision probability.
        """
        candidates: List[ManeuverCandidate] = []
        total_mass = spacecraft_dry_mass_kg + spacecraft_propellant_mass_kg
        tca_seconds = lead_time_hours * 3600.0
        now = datetime.now(timezone.utc)
        burn_epoch = now + timedelta(hours=min(2.0, lead_time_hours / 4.0))

        # 1. Prograde Phasing (+In-Track)
        # In-track phasing is the most fuel-efficient for long lead times (>12h)
        # miss_gain ~ 3 * dv_t * tca_seconds / 1000
        target_gain = max(2.0, desired_miss_km - initial_miss_km)
        prograde_dv = round(min(3.5, max(0.20, (target_gain * 1000.0) / (3.0 * tca_seconds) * 1.5)), 2)
        prograde_dr, prograde_dy, prograde_dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, 0.0, prograde_dv, 0.0, tca_seconds
        )
        prograde_miss = round(float(math.sqrt((initial_miss_km + prograde_dr)**2 + prograde_dy**2 + prograde_dz**2)), 2)
        prograde_fuel = self.calculate_propellant_consumption(total_mass, prograde_dv, thruster_isp_seconds)

        # 2. Retrograde Phasing (-In-Track)
        retro_dv = prograde_dv
        retro_dr, retro_dy, retro_dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, 0.0, -retro_dv, 0.0, tca_seconds
        )
        retro_miss = round(float(math.sqrt((initial_miss_km + retro_dr)**2 + retro_dy**2 + retro_dz**2)), 2)
        retro_fuel = prograde_fuel

        # 3. Radial Boost (+R Altitude Clearance)
        # Immediate altitude separation, useful for short lead times (<6h)
        radial_dv = round(min(5.0, max(0.40, target_gain * 0.45)), 2)
        rad_dr, rad_dy, rad_dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, radial_dv, 0.0, 0.0, tca_seconds
        )
        radial_miss = round(float(math.sqrt((initial_miss_km + rad_dr)**2 + rad_dy**2 + rad_dz**2)), 2)
        radial_fuel = self.calculate_propellant_consumption(total_mass, radial_dv, thruster_isp_seconds)

        # 4. Out-of-Plane Normal (+W Cross-Track)
        # Changes orbital inclination to dodge cross-track
        normal_dv = round(min(6.0, max(0.60, target_gain * 0.65)), 2)
        norm_dr, norm_dy, norm_dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, 0.0, 0.0, normal_dv, tca_seconds
        )
        normal_miss = round(float(math.sqrt((initial_miss_km + norm_dr)**2 + norm_dy**2 + norm_dz**2)), 2)
        normal_fuel = self.calculate_propellant_consumption(total_mass, normal_dv, thruster_isp_seconds)

        # 5. Optimal Hohmann Phasing (Two-impulse return-to-nominal profile)
        hohmann_dv = round(prograde_dv * 1.85, 2)
        hoh_dr, hoh_dy, hoh_dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, 0.0, hohmann_dv * 0.6, 0.0, tca_seconds
        )
        hohmann_miss = round(float(math.sqrt((initial_miss_km + hoh_dr)**2 + hoh_dy**2 + hoh_dz**2)), 2)
        hohmann_fuel = self.calculate_propellant_consumption(total_mass, hohmann_dv, thruster_isp_seconds)

        raw_candidates = [
            (
                "CAND-1-PROGRADE",
                "Prograde Phasing Burn (+V)",
                ManeuverType.PROGRADE_PHASING,
                "PROGRADE",
                prograde_dv,
                [0.0, prograde_dv, 0.0],
                prograde_miss,
                prograde_fuel,
                "Maximum fuel efficiency via along-track secular drift; expands orbital period."
            ),
            (
                "CAND-2-RETROGRADE",
                "Retrograde Phasing Burn (-V)",
                ManeuverType.RETROGRADE_PHASING,
                "RETROGRADE",
                retro_dv,
                [0.0, -retro_dv, 0.0],
                retro_miss,
                retro_fuel,
                "Contracts orbital period to accelerate ahead of debris encounter; highly efficient."
            ),
            (
                "CAND-3-RADIAL",
                "Radial Altitude Boost (+R)",
                ManeuverType.RADIAL_BOOST,
                "RADIAL",
                radial_dv,
                [radial_dv, 0.0, 0.0],
                radial_miss,
                radial_fuel,
                "Direct vertical separation; ideal for tight time horizons without modifying semi-major axis."
            ),
            (
                "CAND-4-NORMAL",
                "Out-of-Plane Cross-Track Burn (+W)",
                ManeuverType.OUT_OF_PLANE_NORMAL,
                "NORMAL",
                normal_dv,
                [0.0, 0.0, normal_dv],
                normal_miss,
                normal_fuel,
                "Changes orbital plane inclination; avoids altitude congestion but demands higher delta-V."
            ),
            (
                "CAND-5-HOHMANN",
                "Optimal 2-Impulse Phasing Profile",
                ManeuverType.OPTIMAL_HOHMANN_PHASING,
                "PROGRADE",
                hohmann_dv,
                [0.0, hohmann_dv, 0.0],
                hohmann_miss,
                hohmann_fuel,
                "Two-impulse phasing maneuver with planned return-to-nominal burn slot."
            )
        ]

        for cand_id, name, m_type, b_dir, dv, dv_vec, post_miss, fuel_kg, rationale in raw_candidates:
            # Evaluate post-maneuver collision probability
            r1 = np.array([semi_major_axis_km, 0.0, 0.0])
            v1 = np.array([0.0, 7.6, 0.0])
            r2 = np.array([semi_major_axis_km + post_miss * 0.4, post_miss * 0.8, post_miss * 0.4])
            v2 = np.array([0.0, 7.6 - relative_velocity_kms, 0.0])

            geom = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2, v2)
            unc = collision_assessment_engine.incorporate_uncertainty(geom, hard_body_radius_m=15.0)
            prob = collision_assessment_engine.evaluate_probabilistic_risk(geom, unc, n_mc_trials=1000)

            # Fuel efficiency (km clearance gained per kg of fuel)
            miss_gain = max(0.1, post_miss - initial_miss_km)
            efficiency = round(miss_gain / max(0.01, fuel_kg), 5)
            rem_fuel = round(max(0.0, spacecraft_propellant_mass_kg - fuel_kg), 2)

            candidates.append(ManeuverCandidate(
                candidate_id=cand_id,
                name=name,
                maneuver_type=m_type,
                burn_direction=b_dir,
                delta_v_ms=dv,
                delta_v_vector_lvlh=dv_vec,
                burn_epoch=burn_epoch,
                lead_time_to_tca_hours=lead_time_hours,
                projected_miss_distance_km=post_miss,
                post_maneuver_collision_prob=prob.collision_probability,
                post_maneuver_collision_prob_sci=prob.collision_probability_sci,
                post_maneuver_cara_tier=prob.nasa_cara_tier.value,
                fuel_mass_kg=fuel_kg,
                fuel_efficiency_km_per_kg=efficiency,
                residual_fuel_budget_kg=rem_fuel,
                recommendation_rank=1,
                tradeoff_rationale=rationale
            ))

        # Rank candidates based on a composite score:
        # Score = (Efficiency * 30) + (PostMiss * 40) - (Fuel * 20) + (10 if CARA Green)
        def score_cand(c: ManeuverCandidate) -> float:
            cara_bonus = 25.0 if "GREEN" in c.post_maneuver_cara_tier else 0.0
            return (c.fuel_efficiency_km_per_kg * 1.5) + (c.projected_miss_distance_km * 3.0) - (c.fuel_mass_kg * 0.1) + cara_bonus

        candidates.sort(key=score_cand, reverse=True)
        for idx, c in enumerate(candidates):
            c.recommendation_rank = idx + 1

        return candidates

    def evaluate_custom_maneuver(
        self,
        delta_v_radial_ms: float,
        delta_v_in_track_ms: float,
        delta_v_cross_track_ms: float,
        initial_miss_km: float,
        semi_major_axis_km: float,
        lead_time_hours: float,
        spacecraft_dry_mass_kg: float,
        spacecraft_propellant_mass_kg: float,
        thruster_isp_seconds: float
    ) -> ManeuverCandidate:
        """Build a custom operator burn from its own inputs; every result is computed, not assumed."""
        total_dv = math.sqrt(delta_v_radial_ms**2 + delta_v_in_track_ms**2 + delta_v_cross_track_ms**2)
        tca_seconds = lead_time_hours * 3600.0
        dr, dy, dz = self.compute_clohessy_wiltshire_perturbation(
            semi_major_axis_km, delta_v_radial_ms, delta_v_in_track_ms, delta_v_cross_track_ms, tca_seconds
        )
        post_miss = round(float(math.sqrt((initial_miss_km + dr)**2 + dy**2 + dz**2)), 2)

        total_mass = spacecraft_dry_mass_kg + spacecraft_propellant_mass_kg
        fuel_kg = self.calculate_propellant_consumption(total_mass, total_dv, thruster_isp_seconds)
        miss_gain = max(0.1, post_miss - initial_miss_km)
        efficiency = round(miss_gain / max(0.01, fuel_kg), 5)

        # Analytical Pc estimate for the modeled post-burn miss distance on a circular reference orbit.
        v_circ = math.sqrt(EARTH_MU / semi_major_axis_km)
        r1 = np.array([semi_major_axis_km, 0.0, 0.0])
        v1 = np.array([0.0, v_circ, 0.0])
        r2 = np.array([semi_major_axis_km + post_miss, 0.0, 0.0])
        v2 = np.array([0.0, -v_circ, 0.0])
        geom = collision_assessment_engine.compute_miss_distance_and_geometry(r1, v1, r2, v2)
        unc = collision_assessment_engine.incorporate_uncertainty(geom, hard_body_radius_m=15.0)
        prob = collision_assessment_engine.evaluate_probabilistic_risk(geom, unc, n_mc_trials=1000)

        return ManeuverCandidate(
            candidate_id="SIM-CUSTOM-COMPARE",
            name="Custom Operator Maneuver",
            maneuver_type=ManeuverType.PROGRADE_PHASING,
            burn_direction="PROGRADE" if delta_v_in_track_ms >= 0 else "RETROGRADE",
            delta_v_ms=round(total_dv, 3),
            delta_v_vector_lvlh=[delta_v_radial_ms, delta_v_in_track_ms, delta_v_cross_track_ms],
            burn_epoch=datetime.now(timezone.utc),
            lead_time_to_tca_hours=lead_time_hours,
            projected_miss_distance_km=post_miss,
            post_maneuver_collision_prob=prob.collision_probability,
            post_maneuver_collision_prob_sci=prob.collision_probability_sci,
            post_maneuver_cara_tier=prob.nasa_cara_tier.value,
            fuel_mass_kg=fuel_kg,
            fuel_efficiency_km_per_kg=efficiency,
            residual_fuel_budget_kg=round(max(0.0, spacecraft_propellant_mass_kg - fuel_kg), 2),
            tradeoff_rationale="Custom operator burn evaluated with Clohessy-Wiltshire relative motion and Tsiolkovsky propellant accounting."
        )

    def compare_trajectories(
        self,
        candidate: ManeuverCandidate,
        initial_miss_km: float,
        semi_major_axis_km: float,
        lead_time_hours: float,
        num_steps: int = 24
    ) -> TrajectoryComparisonResult:
        """
        Compare unperturbed baseline trajectory vs post-burn trajectory over time.
        Computes 3D ECI points, LVLH relative separation, and altitude profiles.
        """
        now = datetime.now(timezone.utc)
        tca_seconds = lead_time_hours * 3600.0
        step_dt = tca_seconds / max(1, num_steps)

        points: List[TrajectoryComparisonPoint] = []
        max_sep = 0.0
        dv_r, dv_t, dv_n = candidate.delta_v_vector_lvlh if len(candidate.delta_v_vector_lvlh) == 3 else [0.0, candidate.delta_v_ms, 0.0]

        # Mean angular speed
        n_rad_s = math.sqrt(EARTH_MU / (semi_major_axis_km ** 3))

        for i in range(num_steps + 1):
            t_sec = i * step_dt
            curr_time = now + timedelta(seconds=t_sec)

            # Circular baseline orbit in ECI
            true_anomaly = n_rad_s * t_sec
            base_x = semi_major_axis_km * math.cos(true_anomaly)
            base_y = semi_major_axis_km * math.sin(true_anomaly)
            base_z = 0.0
            base_alt = semi_major_axis_km - EARTH_RADIUS_KM

            # CW perturbation
            dr, dy, dz = self.compute_clohessy_wiltshire_perturbation(
                semi_major_axis_km, dv_r, dv_t, dv_n, t_sec
            )

            # Maneuvered state
            man_x = base_x + dr * math.cos(true_anomaly) - dy * math.sin(true_anomaly)
            man_y = base_y + dr * math.sin(true_anomaly) + dy * math.cos(true_anomaly)
            man_z = base_z + dz
            man_alt = math.sqrt(man_x**2 + man_y**2 + man_z**2) - EARTH_RADIUS_KM

            sep = float(math.sqrt(dr**2 + dy**2 + dz**2))
            if sep > max_sep:
                max_sep = sep

            points.append(TrajectoryComparisonPoint(
                time=curr_time,
                time_offset_seconds=round(t_sec, 1),
                baseline_eci=[round(base_x, 3), round(base_y, 3), round(base_z, 3)],
                maneuvered_eci=[round(man_x, 3), round(man_y, 3), round(man_z, 3)],
                separation_delta_km=round(sep, 4),
                radial_delta_km=round(dr, 4),
                in_track_delta_km=round(dy, 4),
                cross_track_delta_km=round(dz, 4),
                baseline_altitude_km=round(base_alt, 3),
                maneuvered_altitude_km=round(man_alt, 3)
            ))

        final_pt = points[-1]
        miss_gain = candidate.projected_miss_distance_km - initial_miss_km

        return TrajectoryComparisonResult(
            candidate_id=candidate.candidate_id,
            maneuver_name=candidate.name,
            delta_v_ms=candidate.delta_v_ms,
            tca=now + timedelta(seconds=tca_seconds),
            baseline_miss_distance_km=initial_miss_km,
            post_burn_miss_distance_km=candidate.projected_miss_distance_km,
            miss_distance_gain_km=round(miss_gain, 3),
            max_spatial_separation_km=round(max_sep, 3),
            tca_radial_separation_km=final_pt.radial_delta_km,
            tca_in_track_separation_km=final_pt.in_track_delta_km,
            tca_cross_track_separation_km=final_pt.cross_track_delta_km,
            trajectory_points=points
        )

    def test_hypothetical_scenario(
        self,
        request: HypotheticalScenarioRequest
    ) -> HypotheticalScenarioResponse:
        """
        Execute comprehensive 'What-If' Simulation Laboratory test:
        1. Configures scenario parameters and baseline encounter.
        2. Generates candidate maneuver options.
        3. Formulates fuel comparison table.
        4. Compares 3D trajectory profiles against baseline.
        5. Conducts secondary conjunction screening check.
        6. Synthesizes executive engineering debrief.
        """
        scen_id = request.scenario_id or f"SCEN-{uuid.uuid4().hex[:8].upper()}"
        sma = request.semi_major_axis_km

        # 1. Baseline encounter assessment
        init_miss = request.initial_miss_distance_km
        rel_vel = request.relative_velocity_kms
        lead_time = request.lead_time_hours

        # 2. Candidate generation
        candidates = self.generate_candidate_maneuvers(
            initial_miss_km=init_miss,
            desired_miss_km=max(8.0, init_miss + 6.0),
            relative_velocity_kms=rel_vel,
            lead_time_hours=lead_time,
            semi_major_axis_km=sma,
            spacecraft_dry_mass_kg=request.spacecraft_dry_mass_kg,
            spacecraft_propellant_mass_kg=request.spacecraft_propellant_mass_kg,
            thruster_isp_seconds=request.thruster_isp_seconds
        )

        # Apply fuel budget filter if constrained
        if request.max_fuel_budget_kg is not None:
            for c in candidates:
                if c.fuel_mass_kg > request.max_fuel_budget_kg:
                    c.tradeoff_rationale += f" [WARNING: Exceeds fuel budget cap of {request.max_fuel_budget_kg} kg]"

        optimal = candidates[0]

        # 3. Fuel comparison table
        fuel_table = []
        for c in candidates:
            fuel_table.append({
                "candidate_id": c.candidate_id,
                "strategy": c.name,
                "delta_v_ms": c.delta_v_ms,
                "propellant_consumed_kg": c.fuel_mass_kg,
                "post_burn_miss_km": c.projected_miss_distance_km,
                "efficiency_km_per_kg": c.fuel_efficiency_km_per_kg,
                "residual_fuel_kg": c.residual_fuel_budget_kg,
                "cara_tier": c.post_maneuver_cara_tier,
                "within_budget": True if request.max_fuel_budget_kg is None else (c.fuel_mass_kg <= request.max_fuel_budget_kg)
            })

        # 4. Trajectory comparison for optimal candidate
        traj_comp = self.compare_trajectories(
            candidate=optimal,
            initial_miss_km=init_miss,
            semi_major_axis_km=sma,
            lead_time_hours=lead_time,
            num_steps=20
        )

        # 5. Secondary risk check is not performed here: the post-burn state is modeled,
        # not propagated against the catalog, so no clearance claim can be made.
        secondary_check = {
            "status": "NOT_PERFORMED",
            "screened_catalog_objects": 0,
            "secondary_encounters_detected": 0,
            "cleared_safety_corridor_km": None,
            "risk_assessment": "Not assessed. Secondary conjunction screening requires propagating the post-burn state against the catalog."
        }

        # 6. Scenario title and engineering debrief
        titles = {
            ScenarioType.IMMINENT_DEBRIS_COLLISION: "Imminent Hyper-Velocity Debris Cloud Close Encounter",
            ScenarioType.LOW_THRUST_ELECTRIC_PHASING: "Continuous Low-Thrust Electric Propulsion Phasing",
            ScenarioType.SECONDARY_CONJUNCTION_HAZARD: "Avoidance Burn Secondary Conjunction Injection Screening",
            ScenarioType.FUEL_CONSTRAINED_EMERGENCY: "Strict Propellant Budget Emergency Collision Avoidance",
            ScenarioType.CUSTOM_OPERATOR_SIMULATION: "Custom Operator What-If Maneuver Simulation"
        }
        scen_title = titles.get(request.scenario_type, "Orbital Collision Avoidance Simulation")

        debrief = (
            f"SIMULATION LABORATORY ENGINEERING DEBRIEF [{scen_id}]\n"
            f"Scenario: {scen_title}\n"
            f"Asset: {request.primary_name} (NORAD {request.primary_norad_id}) vs {request.secondary_name} (NORAD {request.secondary_norad_id})\n\n"
            f"1. BASELINE SITUATION: Assumed miss distance of {init_miss:.2f} km with relative closing speed of "
            f"{rel_vel:.2f} km/s at T-{lead_time:.1f}h, as supplied by the operator.\n"
            f"2. CANDIDATE EVALUATION: Simulated {len(candidates)} avoidance trajectories. {optimal.name} ranked first "
            f"with delta-V of {optimal.delta_v_ms} m/s, consuming {optimal.fuel_mass_kg} kg of propellant.\n"
            f"3. TRAJECTORY DELTA: Post-burn separation expands miss distance to {optimal.projected_miss_distance_km:.2f} km "
            f"(gain of +{traj_comp.miss_distance_gain_km:.2f} km), with an illustrative Pc estimate under modeled "
            f"SGP4 uncertainty of {optimal.post_maneuver_collision_prob_sci} ({optimal.post_maneuver_cara_tier}). "
            f"This is not a validated operational probability of collision.\n"
            f"4. SECONDARY CLEARANCE: Not assessed; no post-burn catalog screening was performed.\n"
            f"5. GOVERNANCE: Analytical output only. No maneuver was proposed, approved, or uplinked."
        )

        return HypotheticalScenarioResponse(
            scenario_id=scen_id,
            scenario_type=request.scenario_type,
            scenario_name=scen_title,
            scenario_description=f"Simulated collision avoidance and trajectory dynamics for {request.primary_name}",
            baseline_encounter={
                "initial_miss_distance_km": init_miss,
                "relative_velocity_kms": rel_vel,
                "lead_time_hours": lead_time,
                "spacecraft_total_mass_kg": request.spacecraft_dry_mass_kg + request.spacecraft_propellant_mass_kg,
                "thruster_isp_seconds": request.thruster_isp_seconds
            },
            candidates_evaluated=candidates,
            optimal_candidate=optimal,
            fuel_comparison_table=fuel_table,
            trajectory_comparison=traj_comp,
            secondary_risk_check=secondary_check,
            executive_engineering_debrief=debrief
        )


simulation_engine = SimulationEngine()
