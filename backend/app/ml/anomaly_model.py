from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from app.core.logging import logger


class OrbitalAnomalyDetector:
    """
    Model 2 – Orbital Anomaly Detection (Isolation Forest + Autoencoder).
    Detects unannounced maneuvers, station-keeping burns, unexpected drag spikes,
    and rapid orbital decay from temporal TLE parameter derivatives.
    """

    def __init__(self):
        self.scaler = StandardScaler()
        # Isolation Forest for tree-based outlier isolation
        self.isolation_forest = IsolationForest(
            n_estimators=30,
            contamination=0.08,
            random_state=42
        )
        # Neural Autoencoder (Symmetric 5 -> 2 -> 5 bottleneck)
        self.autoencoder = MLPRegressor(
            hidden_layer_sizes=(6, 2, 6),
            activation='tanh',
            solver='adam',
            max_iter=35,
            tol=1e-2,
            random_state=42
        )
        self._is_trained = False
        self._init_baseline_model()

    def _init_baseline_model(self):
        """Train on synthetic physics-based baseline nominal orbits + perturbation anomalies."""
        np.random.seed(42)
        n_nominal = 80
        # Nominal: small natural drag decay and gravitational precession
        da = np.random.normal(loc=-0.02, scale=0.015, size=n_nominal)
        de = np.random.normal(loc=0.0, scale=0.00005, size=n_nominal)
        di = np.random.normal(loc=0.0, scale=0.001, size=n_nominal)
        dbstar = np.random.normal(loc=0.0, scale=0.00002, size=n_nominal)
        denergy = np.random.normal(loc=-0.0001, scale=0.00008, size=n_nominal)

        nominal_data = np.column_stack([da, de, di, dbstar, denergy])

        # Synthesize 15 anomaly examples (maneuvers and drag surges)
        n_anomaly = 15
        da_ano = np.random.choice([0.8, -1.2, 1.5, -2.0], size=n_anomaly) + np.random.normal(0, 0.1, n_anomaly)
        de_ano = np.random.normal(0, 0.001, size=n_anomaly)
        di_ano = np.random.normal(0.05, 0.02, size=n_anomaly)
        dbstar_ano = np.random.normal(0.0005, 0.0002, size=n_anomaly)
        denergy_ano = da_ano * 0.004

        anomaly_data = np.column_stack([da_ano, de_ano, di_ano, dbstar_ano, denergy_ano])

        X_train = np.vstack([nominal_data, anomaly_data])
        X_scaled = self.scaler.fit_transform(X_train)

        self.isolation_forest.fit(X_scaled)
        self.autoencoder.fit(X_scaled, X_scaled)
        self._is_trained = True
        logger.info("Orbital Anomaly Detector (Isolation Forest + Autoencoder) initialized.")

    def evaluate_deltas(self, delta_dict: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluate a single temporal delta observation.
        Returns composite anomaly score, reconstruction error, and operational flags.
        """
        features = np.array([
            delta_dict.get("delta_semi_major_axis_km_day", 0.0),
            delta_dict.get("delta_eccentricity_day", 0.0),
            delta_dict.get("delta_inclination_deg_day", 0.0),
            delta_dict.get("delta_bstar_day", 0.0),
            delta_dict.get("delta_energy_day", 0.0)
        ]).reshape(1, -1)

        X_scaled = self.scaler.transform(features)

        # 1. Isolation Forest score (raw decision function inverted)
        iso_score = float(-self.isolation_forest.decision_function(X_scaled)[0])
        # Sigmoid calibration to [0, 1]
        iso_calibrated = 1.0 / (1.0 + np.exp(-3.0 * iso_score))

        # 2. Autoencoder reconstruction loss (MSE)
        reconstruction = self.autoencoder.predict(X_scaled)
        mse = float(np.mean((X_scaled - reconstruction) ** 2))
        ae_score = min(1.0, mse / 4.0)

        # Composite anomaly score (ensemble blend)
        composite_score = round(0.5 * iso_calibrated + 0.5 * ae_score, 3)

        # Operational diagnostics
        da = float(delta_dict.get("delta_semi_major_axis_km_day", 0.0))
        dbstar = float(delta_dict.get("delta_bstar_day", 0.0))
        denergy = float(delta_dict.get("delta_energy_day", 0.0))

        is_maneuver = bool(abs(da) > 0.25 or abs(denergy) > 0.001)
        is_drag_spike = bool(abs(dbstar) > 0.00015)
        is_decaying = bool(da < -0.5)

        classification = "NOMINAL"
        if composite_score >= 0.75:
            classification = "CRITICAL_ANOMALY"
        elif composite_score >= 0.50:
            classification = "SUSPECT_ANOMALY"
        elif composite_score >= 0.30:
            classification = "ELEVATED_DRIFT"

        return {
            "anomaly_score": float(composite_score),
            "classification": classification,
            "is_anomalous": bool(composite_score >= 0.50),
            "is_maneuver_signature": bool(is_maneuver),
            "is_drag_spike": bool(is_drag_spike),
            "is_rapid_decay": bool(is_decaying),
            "metrics": {
                "isolation_forest_score": round(float(iso_calibrated), 3),
                "autoencoder_reconstruction_mse": round(float(mse), 4)
            }
        }


anomaly_detector = OrbitalAnomalyDetector()
