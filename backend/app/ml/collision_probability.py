import math
from typing import Dict, Any, Tuple, List, Optional
import numpy as np


class CollisionProbabilityEstimator:
    """
    Model 4 – Collision Probability Estimation.
    Implements:
    1. Foster (1992) / Akella-Alfriend 2D B-Plane Encounter Frame Analytical Formulation.
    2. Monte Carlo Covariance Perturbation Simulation (N = 10,000 trials).
    3. NASA CARA (Conjunction Assessment Risk Analysis) Threshold Benchmarking.
    """

    # NASA CARA Standard Thresholds
    RED_THRESHOLD = 1e-4      # Maneuver planning mandatory
    YELLOW_THRESHOLD = 1e-7   # Elevated monitoring required

    def compute_b_plane_encounter_coordinates(
        self,
        r1_eci: np.ndarray,
        v1_eci: np.ndarray,
        r2_eci: np.ndarray,
        v2_eci: np.ndarray
    ) -> Tuple[float, float, float, np.ndarray]:
        """
        Construct the B-plane encounter frame perpendicular to relative velocity:
        - Unit vector u_y along relative velocity v_rel = v1 - v2
        - Unit vector u_x along (r1 x v_rel) / ||r1 x v_rel|| (in encounter plane)
        - Unit vector u_z completes orthogonal frame (u_z = u_x x u_y)
        Returns:
            (x_encounter_km, z_encounter_km, v_rel_mag, projection_matrix)
        """
        dr = r2_eci - r1_eci
        dv = v2_eci - v1_eci
        v_rel_mag = float(np.linalg.norm(dv))

        if v_rel_mag < 1e-6:
            return float(dr[0]), float(dr[1]), 1.0, np.eye(3)

        u_y = dv / v_rel_mag  # Along relative velocity

        # Cross with primary position vector
        h_vec = np.cross(r1_eci, u_y)
        h_norm = np.linalg.norm(h_vec)
        if h_norm < 1e-6:
            u_x = np.array([1.0, 0.0, 0.0])
        else:
            u_x = h_vec / h_norm

        u_z = np.cross(u_x, u_y)

        # Projections on 2D encounter plane
        x_enc = float(np.dot(dr, u_x))
        z_enc = float(np.dot(dr, u_z))

        proj_matrix = np.vstack([u_x, u_z])  # Shape (2, 3)
        return x_enc, z_enc, v_rel_mag, proj_matrix

    def compute_foster_probability(
        self,
        miss_distance_km: float,
        hard_body_radius_m: float = 15.0,
        sigma_x_km: float = 0.8,
        sigma_y_km: float = 0.5,
        correlation_rho: float = 0.0
    ) -> Dict[str, Any]:
        """
        Analytical Foster 2D Encounter Frame Collision Probability:
        P_c = (R_HBR^2 / (2 * sigma_x * sigma_y * sqrt(1 - rho^2))) * exp(-Mahalanobis / 2)
        """
        # Convert HBR from meters to km
        r_hbr_km = hard_body_radius_m / 1000.0

        det_term = sigma_x_km * sigma_y_km * math.sqrt(max(1e-8, 1.0 - correlation_rho**2))
        
        # Mahalanobis distance squared (assuming centered encounter at miss_distance along major axis)
        # For general miss distance d:
        d2 = miss_distance_km ** 2
        sig2 = 0.5 * (sigma_x_km**2 + sigma_y_km**2)
        exp_arg = -0.5 * d2 / max(1e-6, sig2)

        # Integral of 2D Gaussian over disk of radius r_hbr
        disk_area_factor = (r_hbr_km ** 2) / (2.0 * det_term)
        pc = disk_area_factor * math.exp(max(-50.0, exp_arg))
        pc = min(1.0, max(0.0, pc))

        # NASA CARA classification
        if pc >= self.RED_THRESHOLD:
            nasa_tier = "RED_ALERT (P_c >= 1e-4) - Mandatory Maneuver Planning"
            severity = "CRITICAL"
        elif pc >= self.YELLOW_THRESHOLD:
            nasa_tier = "YELLOW_ALERT (1e-7 <= P_c < 1e-4) - Active Screening"
            severity = "ELEVATED"
        else:
            nasa_tier = "GREEN (P_c < 1e-7) - Acceptable Risk"
            severity = "NOMINAL"

        return {
            "method": "Foster 2D Encounter Frame (NASA CARA Standard)",
            "collision_probability": pc,
            "collision_probability_sci": f"{pc:.3e}",
            "hard_body_radius_m": hard_body_radius_m,
            "uncertainty_sigma_km": [sigma_x_km, sigma_y_km],
            "nasa_cara_tier": nasa_tier,
            "operational_severity": severity
        }

    def run_monte_carlo_simulation(
        self,
        miss_distance_km: float,
        hard_body_radius_m: float = 15.0,
        sigma_km: float = 0.6,
        n_trials: int = 10000
    ) -> Dict[str, Any]:
        """
        Monte Carlo simulation:
        Perturbs encounter positions using 3D Gaussian covariance draws.
        Directly measures empirical collision frequency.
        """
        np.random.seed(42)
        r_hbr_km = hard_body_radius_m / 1000.0

        # Mean separation along X axis
        mean_offset = np.array([miss_distance_km, 0.0, 0.0])
        # Generate 3D perturbations
        perturbations = np.random.normal(loc=0.0, scale=sigma_km, size=(n_trials, 3))
        perturbed_positions = mean_offset + perturbations

        # Calculate distances to origin
        distances = np.linalg.norm(perturbed_positions, axis=1)
        collisions = np.sum(distances <= r_hbr_km)

        mc_prob = float(collisions) / float(n_trials)

        return {
            "method": "Monte Carlo Covariance Perturbation",
            "trials": n_trials,
            "collision_hits": int(collisions),
            "mc_probability": mc_prob,
            "mc_probability_sci": f"{mc_prob:.3e}",
            "statistical_error": round(math.sqrt(max(1e-9, mc_prob * (1.0 - mc_prob) / n_trials)), 6)
        }

    def generate_b_plane_ellipse(
        self,
        center_x: float = 0.0,
        center_y: float = 0.0,
        sigma_x: float = 0.8,
        sigma_y: float = 0.5,
        num_points: int = 60
    ) -> List[Dict[str, float]]:
        """
        Generate 1-sigma, 2-sigma, and 3-sigma covariance error ellipse points
        on the B-plane encounter frame for frontend 2D/3D visualization.
        """
        angles = np.linspace(0, 2 * np.pi, num_points)
        points = []
        for a in angles:
            points.append({
                "x_1sigma": round(center_x + sigma_x * math.cos(a), 4),
                "y_1sigma": round(center_y + sigma_y * math.sin(a), 4),
                "x_3sigma": round(center_x + 3.0 * sigma_x * math.cos(a), 4),
                "y_3sigma": round(center_y + 3.0 * sigma_y * math.sin(a), 4)
            })
        return points


collision_probability_estimator = CollisionProbabilityEstimator()
