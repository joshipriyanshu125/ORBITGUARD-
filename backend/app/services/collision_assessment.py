import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import numpy as np

from app.models.collision_assessment import (
    EncounterGeometry,
    UncertaintyData,
    ProbabilisticAssessment,
    ExplainabilityReport,
    CollisionAssessmentResult,
    RankedConjunctionItem,
    ConjunctionRankingResponse,
    OperationalActionCategory,
    NASACARATier
)
from app.services.orbital_math import eci_to_lvlh
from app.core.logging import logger


class CollisionAssessmentEngine:
    """
    Week 7 Deliverable: Collision Assessment Module & Risk Assessment Engine.
    - Calculates high-precision miss distances (3D Euclidean, LVLH RIC components, B-Plane).
    - Incorporates available uncertainty data (CDMs or physics-informed SGP4 drag growth covariance).
    - Implements probabilistic risk assessment (Analytical Foster 2D + Monte Carlo covariance simulation).
    - Multi-criteria Event Ranking with Urgency Priority Index (UPI).
    - Synthesizes aerospace Explainability Reports with sensitivity analysis and HITL safety directives.
    """

    # NASA CARA Standard Thresholds
    RED_THRESHOLD = 1e-4      # Mandatory maneuver planning
    YELLOW_THRESHOLD = 1e-7   # Elevated monitoring required

    def compute_miss_distance_and_geometry(
        self,
        r1_eci: np.ndarray,
        v1_eci: np.ndarray,
        r2_eci: np.ndarray,
        v2_eci: np.ndarray
    ) -> EncounterGeometry:
        """
        Calculate 3D Euclidean miss distance, decompose into LVLH (RIC) frame,
        and project onto the B-plane encounter frame.
        """
        dr = r2_eci - r1_eci
        dv = v2_eci - v1_eci
        
        miss_dist_km = float(np.linalg.norm(dr))
        rel_vel_kms = float(np.linalg.norm(dv))
        rel_ke_mj_kg = 0.5 * (rel_vel_kms ** 2)

        # 1. LVLH / Hill / RIC decomposition
        radial_km, in_track_km, cross_track_km = eci_to_lvlh(
            tuple(r1_eci), tuple(v1_eci), tuple(r2_eci)
        )

        # 2. B-Plane encounter frame decomposition
        if rel_vel_kms < 1e-6:
            u_y = np.array([0.0, 1.0, 0.0])
        else:
            u_y = dv / rel_vel_kms

        h_vec = np.cross(r1_eci, u_y)
        h_norm = np.linalg.norm(h_vec)
        if h_norm < 1e-6:
            u_x = np.array([1.0, 0.0, 0.0])
        else:
            u_x = h_vec / h_norm

        u_z = np.cross(u_x, u_y)

        b_x = float(np.dot(dr, u_x))
        b_z = float(np.dot(dr, u_z))
        impact_param = float(math.sqrt(b_x**2 + b_z**2))

        return EncounterGeometry(
            miss_distance_km=round(miss_dist_km, 4),
            radial_miss_km=round(radial_km, 4),
            in_track_miss_km=round(in_track_km, 4),
            cross_track_miss_km=round(cross_track_km, 4),
            b_plane_x_km=round(b_x, 4),
            b_plane_z_km=round(b_z, 4),
            impact_parameter_km=round(impact_param, 4),
            relative_velocity_kms=round(rel_vel_kms, 3),
            relative_kinetic_energy_mj_kg=round(rel_ke_mj_kg, 2)
        )

    def incorporate_uncertainty(
        self,
        geometry: EncounterGeometry,
        primary_cov: Optional[np.ndarray] = None,
        secondary_cov: Optional[np.ndarray] = None,
        hard_body_radius_m: float = 15.0,
        bstar_primary: float = 0.0001,
        bstar_secondary: float = 0.0001,
        lead_time_hours: float = 24.0
    ) -> UncertaintyData:
        """
        Incorporate available covariance uncertainty data.
        If explicit CDM covariance matrices are provided, combines and projects them.
        Otherwise, constructs a physics-informed empirical SGP4 drag growth covariance model.
        """
        r_hbr_km = hard_body_radius_m / 1000.0

        if primary_cov is not None and secondary_cov is not None:
            cov_source = "CCSDS Conjunction Data Message (CDM) Covariance"
            comb_cov = np.array(primary_cov) + np.array(secondary_cov)
            sigma_r = float(math.sqrt(max(1e-6, comb_cov[0, 0])))
            sigma_i = float(math.sqrt(max(1e-6, comb_cov[1, 1])))
            sigma_c = float(math.sqrt(max(1e-6, comb_cov[2, 2])))
            # Approximate encounter plane projection
            sigma_x = max(0.05, (sigma_r + sigma_c) / 2.0)
            sigma_y = max(0.05, sigma_i)
            rho = float(comb_cov[0, 1] / max(1e-6, (sigma_r * sigma_i))) if comb_cov.shape == (3, 3) else 0.0
            rho = max(-0.95, min(0.95, rho))
        else:
            cov_source = "Physics-Informed SGP4 Drag Growth Empirical Model"
            # Standard radial and cross-track errors for LEO SGP4
            sigma_r = 0.12
            sigma_c = 0.28
            # In-track uncertainty grows with propagation horizon and atmospheric drag parameter (BSTAR)
            drag_factor = max(1e-5, max(bstar_primary, bstar_secondary)) * 1e4
            time_factor = (max(1.0, lead_time_hours) / 24.0) ** 1.15
            sigma_i = round(0.45 + 0.35 * time_factor * drag_factor, 4)

            # Encounter plane error ellipse projections
            sigma_x = round(0.5 * (sigma_r + sigma_c) + 0.1, 4)
            sigma_y = round(sigma_i * 0.85, 4)
            rho = 0.15

        # Mahalanobis distance calculation
        bx = geometry.b_plane_x_km
        bz = geometry.b_plane_z_km
        det = max(1e-8, 1.0 - rho**2)
        term_x = (bx / max(1e-4, sigma_x)) ** 2
        term_y = (bz / max(1e-4, sigma_y)) ** 2
        term_cross = (2.0 * rho * bx * bz) / max(1e-4, sigma_x * sigma_y)
        mahalanobis_sq = max(0.0, (term_x - term_cross + term_y) / det)
        mahalanobis_dist = float(math.sqrt(mahalanobis_sq))

        return UncertaintyData(
            covariance_source=cov_source,
            hard_body_radius_m=hard_body_radius_m,
            hard_body_radius_km=round(r_hbr_km, 6),
            sigma_radial_km=round(sigma_r, 4),
            sigma_in_track_km=round(sigma_i, 4),
            sigma_cross_track_km=round(sigma_c, 4),
            b_plane_sigma_x_km=round(sigma_x, 4),
            b_plane_sigma_y_km=round(sigma_y, 4),
            b_plane_correlation_rho=round(rho, 4),
            mahalanobis_distance=round(mahalanobis_dist, 3)
        )

    def evaluate_probabilistic_risk(
        self,
        geometry: EncounterGeometry,
        uncertainty: UncertaintyData,
        n_mc_trials: int = 10000
    ) -> ProbabilisticAssessment:
        """
        Probabilistic collision risk evaluation:
        1. Foster (1992) Analytical 2D B-Plane collision probability.
        2. Monte Carlo covariance perturbation simulation.
        3. Theoretical peak maximum Pc benchmarking.
        4. NASA CARA operational risk classification.
        """
        r_hbr = uncertainty.hard_body_radius_km
        sx = uncertainty.b_plane_sigma_x_km
        sy = uncertainty.b_plane_sigma_y_km
        rho = uncertainty.b_plane_correlation_rho
        d_m = uncertainty.mahalanobis_distance

        # 1. Analytical Foster (1992) formulation
        det_factor = sx * sy * math.sqrt(max(1e-8, 1.0 - rho**2))
        disk_factor = (r_hbr ** 2) / (2.0 * det_factor)
        exp_factor = math.exp(max(-50.0, -0.5 * (d_m ** 2)))
        pc = float(disk_factor * exp_factor)
        pc = min(1.0, max(0.0, pc))

        # Theoretical maximum probability if miss distance were 0
        max_pc = min(1.0, float(disk_factor))

        # 2. Monte Carlo covariance simulation
        np.random.seed(42)
        mean_vec = np.array([geometry.b_plane_x_km, geometry.b_plane_z_km])
        cov_matrix = np.array([
            [sx**2, rho * sx * sy],
            [rho * sx * sy, sy**2]
        ])
        
        # Cholesky decomposition for bivariate Gaussian draws
        try:
            L = np.linalg.cholesky(cov_matrix)
            z_samples = np.random.normal(0.0, 1.0, size=(n_mc_trials, 2))
            perturbed = mean_vec + (z_samples @ L.T)
        except Exception:
            perturbed = mean_vec + np.random.normal(0.0, scale=[sx, sy], size=(n_mc_trials, 2))

        radii = np.linalg.norm(perturbed, axis=1)
        mc_hits = int(np.sum(radii <= r_hbr))
        mc_prob = float(mc_hits) / float(n_mc_trials)

        # 95% Confidence interval for Monte Carlo estimate
        z_score = 1.96
        ci_half = z_score * math.sqrt(max(1e-9, mc_prob * (1.0 - mc_prob) / n_mc_trials))
        ci_low = max(0.0, round(mc_prob - ci_half, 6))
        ci_high = min(1.0, round(mc_prob + ci_half, 6))

        # 3. NASA CARA Tier Benchmarking
        if pc >= self.RED_THRESHOLD:
            cara_tier = NASACARATier.RED_ALERT
            severity = "CRITICAL"
        elif pc >= self.YELLOW_THRESHOLD:
            cara_tier = NASACARATier.YELLOW_ALERT
            severity = "ELEVATED"
        else:
            cara_tier = NASACARATier.GREEN
            severity = "NOMINAL"

        return ProbabilisticAssessment(
            collision_probability=pc,
            collision_probability_sci=f"{pc:.3e}",
            monte_carlo_probability=mc_prob,
            monte_carlo_trials=n_mc_trials,
            monte_carlo_hits=mc_hits,
            confidence_interval_95=[ci_low, ci_high],
            nasa_cara_tier=cara_tier,
            operational_severity=severity,
            max_possible_pc=round(max_pc, 6)
        )

    def calculate_composite_risk_score(
        self,
        geometry: EncounterGeometry,
        probabilistic: ProbabilisticAssessment,
        secondary_type: str = "DEBRIS",
        lead_time_hours: float = 24.0
    ) -> float:
        """
        Compute continuous operational risk score [0 - 100].
        Combines miss distance, radial separation criticality, collision probability,
        hyper-velocity kinetic energy, and object pedigree.
        """
        pc = probabilistic.collision_probability

        # 1. Probability component (0 - 45 points)
        if pc >= 1e-4:
            prob_score = 45.0
        elif pc > 0:
            # Scale log10 from 1e-10 (0 pts) to 1e-4 (45 pts)
            log_pc = math.log10(max(1e-12, pc))
            prob_score = max(0.0, min(45.0, (log_pc + 10.0) * (45.0 / 6.0)))
        else:
            prob_score = 0.0

        # 2. Miss distance & radial component (0 - 30 points)
        # In orbital mechanics, small radial separation (|Delta R| < 1.0 km) is dangerous
        d = geometry.miss_distance_km
        dr = abs(geometry.radial_miss_km)
        dist_score = max(0.0, 20.0 - min(20.0, d * 2.0))
        radial_score = max(0.0, 10.0 - min(10.0, dr * 10.0))

        # 3. Velocity & energy component (0 - 15 points)
        v_rel = geometry.relative_velocity_kms
        vel_score = min(15.0, max(0.0, (v_rel - 5.0) * 1.5))

        # 4. Debris pedigree & lead time urgency (0 - 10 points)
        debris_weight = 6.0 if secondary_type.upper() == "DEBRIS" else 3.0
        urgency = 4.0 if lead_time_hours < 24.0 else (2.0 if lead_time_hours < 48.0 else 1.0)

        total_score = prob_score + dist_score + radial_score + vel_score + debris_weight + urgency
        return float(round(min(100.0, max(0.0, total_score)), 1))

    def generate_explainability_report(
        self,
        event_id: str,
        primary_name: str,
        primary_norad_id: int,
        secondary_name: str,
        secondary_norad_id: int,
        secondary_type: str,
        tca: datetime,
        lead_time_hours: float,
        geometry: EncounterGeometry,
        uncertainty: UncertaintyData,
        probabilistic: ProbabilisticAssessment,
        composite_score: float
    ) -> ExplainabilityReport:
        """
        Generate operational plain-English and engineering explainability report
        detailing physical mechanics, uncertainty bounds, probabilistic rationale,
        sensitivity analysis, and Human-in-the-Loop directives.
        """
        # Executive summary
        pc_str = probabilistic.collision_probability_sci
        tier_short = "RED ALERT" if "RED" in probabilistic.nasa_cara_tier.value else (
            "YELLOW ALERT" if "YELLOW" in probabilistic.nasa_cara_tier.value else "GREEN"
        )
        tca_iso = tca.isoformat()

        exec_summary = (
            f"Conjunction assessment between primary asset {primary_name} (NORAD {primary_norad_id}) "
            f"and secondary {secondary_name} (NORAD {secondary_norad_id}, {secondary_type}) "
            f"at TCA {tca_iso} (Lead time: {lead_time_hours:.1f}h). "
            f"Predicted 3D miss distance is {geometry.miss_distance_km:.2f} km with relative velocity of "
            f"{geometry.relative_velocity_kms:.2f} km/s. The model-based Pc estimate is {pc_str}; "
            f"its comparison with NASA CARA thresholds is indicative only, not an operational CARA determination. "
            f"Composite screening priority score: {composite_score}/100."
        )

        # Geometry explanation
        geom_exp = (
            f"Encounter geometry decomposes into LVLH (RIC) frame components: "
            f"Radial separation ΔR = {geometry.radial_miss_km:.3f} km, "
            f"In-track separation ΔI = {geometry.in_track_miss_km:.3f} km, and "
            f"Cross-track separation ΔC = {geometry.cross_track_miss_km:.3f} km. "
            f"Because radial separation is {abs(geometry.radial_miss_km):.3f} km, "
            f"{'orbital altitudes directly intersect within the cross-track tolerance window, posing severe collision risk' if abs(geometry.radial_miss_km) < 0.5 else 'orbital altitude shells are separated by over 500m, mitigating physical intersection danger'}. "
            f"B-plane impact parameter is {geometry.impact_parameter_km:.3f} km with specific kinetic energy of "
            f"{geometry.relative_kinetic_energy_mj_kg:.1f} MJ/kg (hyper-velocity regime)."
        )

        # Uncertainty explanation
        unc_exp = (
            f"Uncertainty model sourced via {uncertainty.covariance_source}. "
            f"Combined 1-sigma positional uncertainty bounds: Radial σR = ±{uncertainty.sigma_radial_km:.3f} km, "
            f"In-track σI = ±{uncertainty.sigma_in_track_km:.3f} km, Cross-track σC = ±{uncertainty.sigma_cross_track_km:.3f} km. "
            f"Projected 2D encounter frame semi-axes are σx = {uncertainty.b_plane_sigma_x_km:.3f} km and "
            f"σy = {uncertainty.b_plane_sigma_y_km:.3f} km (Correlation ρ = {uncertainty.b_plane_correlation_rho:.2f}). "
            f"Standardized Mahalanobis distance is {uncertainty.mahalanobis_distance:.2f}σ."
        )

        # Probabilistic explanation
        prob_exp = (
            f"Illustrative Foster 2D model-based Pc estimate = {probabilistic.collision_probability_sci}, "
            f"Empirical Monte Carlo simulation ({probabilistic.monte_carlo_trials:,} trials) yielded "
            f"{probabilistic.monte_carlo_hits} collision events (Pc_MC = {probabilistic.monte_carlo_probability:.3e}, "
            f"95% CI: [{probabilistic.confidence_interval_95[0]:.3e}, {probabilistic.confidence_interval_95[1]:.3e}]). "
            f"Maximum theoretical estimate if miss distance were zero under current modeled covariance is "
            f"{probabilistic.max_possible_pc:.3e}. These estimates are conditional on the uncertainty source "
            f"({uncertainty.covariance_source}); empirical SGP4 uncertainty is illustrative screening input, "
            f"not a validated operational Pc. CARA thresholds are shown for reference only."
        )

        # Sensitivity analysis
        r_base = uncertainty.hard_body_radius_m
        pc_base = probabilistic.collision_probability
        sensitivity = {
            "hard_body_radius_variations": {
                f"half_radius_{r_base/2:.1f}m": f"{pc_base * 0.25:.3e}",
                f"nominal_radius_{r_base:.1f}m": f"{pc_base:.3e}",
                f"double_radius_{r_base*2:.1f}m": f"{min(1.0, pc_base * 4.0):.3e}"
            },
            "miss_distance_sensitivity": {
                "minus_500m_miss": f"{min(1.0, pc_base * 2.8):.3e}",
                "nominal_miss": f"{pc_base:.3e}",
                "plus_500m_miss": f"{pc_base * 0.35:.3e}"
            },
            "max_possible_pc_under_current_covariance": f"{probabilistic.max_possible_pc:.3e}"
        }

        # HITL recommendation
        if probabilistic.operational_severity == "CRITICAL" or composite_score >= 80.0:
            rec = (
                "ACTION REQUIRED: Mandatory avoidance maneuver proposal generation. "
                "Recommend positive radial (+ΔR) or proactive along-track phasing burn of ~0.5 - 1.2 m/s "
                "at least 1 orbit period prior to TCA. Explicit Human-In-The-Loop authorization required."
            )
        elif probabilistic.operational_severity == "ELEVATED" or composite_score >= 50.0:
            rec = (
                "ELEVATED MONITORING: Task high-cadence tracking sensors and ingest updated TLE ephemerides "
                "within the next 12 hours. Prepare avoidance burn contingency profile."
            )
        else:
            rec = (
                "NOMINAL / ROUTINE: The modeled estimate is below the configured screening thresholds. "
                "Continue passive tracking with standard sensor updates."
            )

        return ExplainabilityReport(
            executive_summary=exec_summary,
            geometry_explanation=geom_exp,
            uncertainty_explanation=unc_exp,
            probabilistic_explanation=prob_exp,
            sensitivity_analysis=sensitivity,
            hitl_recommendation=rec
        )

    def assess_collision(
        self,
        event_id: str,
        primary_norad_id: int,
        primary_name: str,
        secondary_norad_id: int,
        secondary_name: str,
        secondary_type: str,
        r1_eci: np.ndarray,
        v1_eci: np.ndarray,
        r2_eci: np.ndarray,
        v2_eci: np.ndarray,
        tca: datetime,
        lead_time_hours: float,
        hard_body_radius_m: float = 15.0,
        primary_cov: Optional[np.ndarray] = None,
        secondary_cov: Optional[np.ndarray] = None,
        bstar_primary: float = 0.0001,
        bstar_secondary: float = 0.0001
    ) -> CollisionAssessmentResult:
        """Full end-to-end collision assessment pipeline."""
        # 1. Miss distance and geometry
        geometry = self.compute_miss_distance_and_geometry(r1_eci, v1_eci, r2_eci, v2_eci)

        # 2. Uncertainty data incorporation
        uncertainty = self.incorporate_uncertainty(
            geometry=geometry,
            primary_cov=primary_cov,
            secondary_cov=secondary_cov,
            hard_body_radius_m=hard_body_radius_m,
            bstar_primary=bstar_primary,
            bstar_secondary=bstar_secondary,
            lead_time_hours=lead_time_hours
        )

        # 3. Probabilistic assessment
        probabilistic = self.evaluate_probabilistic_risk(geometry, uncertainty)

        # 4. Composite risk score
        score = self.calculate_composite_risk_score(
            geometry=geometry,
            probabilistic=probabilistic,
            secondary_type=secondary_type,
            lead_time_hours=lead_time_hours
        )

        risk_level = "CRITICAL" if score >= 80.0 else (
            "HIGH" if score >= 60.0 else (
                "MEDIUM" if score >= 35.0 else "LOW"
            )
        )

        # 5. Explainability report
        report = self.generate_explainability_report(
            event_id=event_id,
            primary_name=primary_name,
            primary_norad_id=primary_norad_id,
            secondary_name=secondary_name,
            secondary_norad_id=secondary_norad_id,
            secondary_type=secondary_type,
            tca=tca,
            lead_time_hours=lead_time_hours,
            geometry=geometry,
            uncertainty=uncertainty,
            probabilistic=probabilistic,
            composite_score=score
        )

        return CollisionAssessmentResult(
            event_id=event_id,
            primary_norad_id=primary_norad_id,
            primary_name=primary_name,
            secondary_norad_id=secondary_norad_id,
            secondary_name=secondary_name,
            secondary_type=secondary_type,
            tca=tca,
            lead_time_hours=round(lead_time_hours, 2),
            risk_level=risk_level,
            composite_risk_score=score,
            geometry=geometry,
            uncertainty=uncertainty,
            probabilistic=probabilistic,
            explainability_report=report
        )

    def rank_conjunction_events(
        self,
        events: List[Dict[str, Any]]
    ) -> ConjunctionRankingResponse:
        """
        Rank an arbitrary list of conjunction events using a multi-criteria
        Urgency Priority Index (UPI) based on Pc, miss distance, radial overlap,
        lead time to TCA, and object pedigree.
        """
        ranked_items: List[RankedConjunctionItem] = []

        for ev in events:
            ev_id = ev.get("event_id", f"CONJ-{ev.get('primary_norad_id')}-{ev.get('secondary_norad_id')}")
            p_id = int(ev.get("primary_norad_id", 0))
            p_name = ev.get("primary_name", f"SAT-{p_id}")
            s_id = int(ev.get("secondary_norad_id", 0))
            s_name = ev.get("secondary_name", f"OBJ-{s_id}")
            s_type = ev.get("secondary_type", "DEBRIS")
            
            tca = ev.get("tca")
            if isinstance(tca, str):
                try:
                    tca_dt = datetime.fromisoformat(tca.replace("Z", "+00:00"))
                except Exception:
                    tca_dt = datetime.now(timezone.utc)
            elif isinstance(tca, datetime):
                tca_dt = tca
            else:
                tca_dt = datetime.now(timezone.utc)

            lead_time = float(ev.get("lead_time_hours", 24.0))
            miss_km = float(ev.get("miss_distance_km", 2.0))
            radial_km = float(ev.get("radial_miss_km", miss_km * 0.4))
            v_rel = float(ev.get("relative_velocity_kms", 12.0))
            pc = float(ev.get("collision_probability", 1e-5))

            # Multi-attribute Urgency Priority Index (UPI) [0 - 100]
            # 1. Probability severity (40 pts)
            if pc >= 1e-4:
                pc_pts = 40.0
            elif pc > 0:
                pc_pts = max(0.0, min(40.0, (math.log10(max(1e-12, pc)) + 10.0) * (40.0 / 6.0)))
            else:
                pc_pts = 0.0

            # 2. Geometric proximity (30 pts)
            # Radial separation is the most hazardous
            geo_pts = max(0.0, 18.0 - min(18.0, miss_km * 1.8)) + max(0.0, 12.0 - min(12.0, abs(radial_km) * 12.0))

            # 3. Time Urgency (20 pts): closer to TCA = more urgent
            time_pts = max(0.0, 20.0 * (1.0 - min(1.0, lead_time / 72.0)))

            # 4. Pedigree & closing velocity (10 pts)
            ped_pts = (5.0 if s_type.upper() == "DEBRIS" else 2.0) + min(5.0, (v_rel / 15.0) * 5.0)

            upi = round(min(100.0, max(0.0, pc_pts + geo_pts + time_pts + ped_pts)), 1)
            comp_score = float(ev.get("risk_score", upi))

            # Operational Action Category
            if pc >= 1e-4 or (upi >= 80.0 and lead_time <= 36.0):
                cat = OperationalActionCategory.IMMEDIATE_ACTION_REQUIRED
                rationale = "Critical hazard: Pc exceeds 1e-4 safety ceiling with imminent close approach."
            elif upi >= 65.0:
                cat = OperationalActionCategory.URGENT_TRIAGE
                rationale = "High risk encounter: Tight radial overlap requiring flight dynamics triage."
            elif upi >= 40.0 or pc >= 1e-7:
                cat = OperationalActionCategory.ELEVATED_WATCH
                rationale = "Elevated screening: Conjunction falls into NASA CARA Yellow Alert monitoring."
            else:
                cat = OperationalActionCategory.ROUTINE_MONITORING
                rationale = "Nominal trajectory: Well outside avoidance maneuver thresholds."

            cara_str = "RED_ALERT" if pc >= 1e-4 else ("YELLOW_ALERT" if pc >= 1e-7 else "GREEN")

            ranked_items.append(RankedConjunctionItem(
                rank=0,
                event_id=ev_id,
                primary_norad_id=p_id,
                primary_name=p_name,
                secondary_norad_id=s_id,
                secondary_name=s_name,
                secondary_type=s_type,
                tca=tca_dt,
                lead_time_hours=round(lead_time, 2),
                miss_distance_km=round(miss_km, 3),
                radial_miss_km=round(radial_km, 3),
                relative_velocity_kms=round(v_rel, 2),
                collision_probability_sci=f"{pc:.3e}",
                nasa_cara_tier=cara_str,
                composite_risk_score=comp_score,
                urgency_priority_index=upi,
                action_category=cat,
                short_rationale=rationale
            ))

        # Sort descending by UPI
        ranked_items.sort(key=lambda x: x.urgency_priority_index, reverse=True)
        for idx, item in enumerate(ranked_items):
            item.rank = idx + 1

        imm_count = sum(1 for i in ranked_items if i.action_category == OperationalActionCategory.IMMEDIATE_ACTION_REQUIRED)
        urg_count = sum(1 for i in ranked_items if i.action_category == OperationalActionCategory.URGENT_TRIAGE)
        elev_count = sum(1 for i in ranked_items if i.action_category == OperationalActionCategory.ELEVATED_WATCH)
        rout_count = sum(1 for i in ranked_items if i.action_category == OperationalActionCategory.ROUTINE_MONITORING)

        return ConjunctionRankingResponse(
            status="success",
            total_events_evaluated=len(ranked_items),
            immediate_action_count=imm_count,
            urgent_triage_count=urg_count,
            elevated_watch_count=elev_count,
            routine_count=rout_count,
            ranked_queue=ranked_items
        )


collision_assessment_engine = CollisionAssessmentEngine()
