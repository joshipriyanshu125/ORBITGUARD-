"""
Week 12 – ML Model Metrics Evaluation Tests.
Evaluates GRU trajectory model, anomaly detector, and risk classifier
using aerospace physics-informed test datasets.
"""
import pytest
import math
import time
import numpy as np

from app.ml.lstm_residual_model import (
    OrbitalTrajectoryResidualPredictor,
    trajectory_residual_model,
    GRUResidualCell,
)
from app.ml.anomaly_model import anomaly_detector
from app.ml.risk_model import conjunction_risk_model
from app.models.conjunction import RiskLevel


# ------ GRU Trajectory Model Metrics ------
def test_gru_trajectory_model_mse_mae():
    """
    Evaluate MSE and MAE of the GRU trajectory residual model.
    Compares step predictions against reference residuals defined by fixture,
    computing MSE and MAE from the differences and asserting upper bounds.
    """
    model = OrbitalTrajectoryResidualPredictor(input_dim=7, hidden_dim=16)
    np.random.seed(42)
    seq_len = 20
    features = np.random.normal(0, 0.05, size=(seq_len, 7))

    # Reference target residuals: nominal small atmospheric perturbations
    reference_residuals = np.zeros((seq_len, 3))
    for t in range(seq_len):
        reference_residuals[t] = [
            0.02 * math.sin(t * 0.1),
            0.03 * math.cos(t * 0.1),
            0.01 * math.sin(2 * t * 0.1)
        ]

    result = model.predict_residuals(features)
    assert len(result["predicted_residual_km"]) == 3
    for r in result["predicted_residual_km"]:
        assert math.isfinite(r) and abs(r) < 100.0

    step_arr = np.array(result["step_residuals"])
    assert step_arr.shape == (seq_len, 3)
    assert np.all(np.isfinite(step_arr))

    # Compute MSE and MAE between model predictions and reference residuals
    diff = step_arr - reference_residuals
    mse = float(np.mean(diff ** 2))
    mae = float(np.mean(np.abs(diff)))
    
    # Assert physical upper bounds (unperturbed residual predictions remain bounded)
    assert mse < 10.0, f"MSE {mse:.4f} exceeds upper bound of 10.0"
    assert mae < 5.0, f"MAE {mae:.4f} exceeds upper bound of 5.0"
    assert result["residual_magnitude_km"] >= 0.0


def test_gru_trajectory_model_confidence():
    """
    Test confidence percentage scales inversely with residual magnitude.
    Evaluates two cases with different residual magnitudes in non-saturated range,
    asserting that the case with larger residual has lower confidence.
    """
    model = OrbitalTrajectoryResidualPredictor(input_dim=7, hidden_dim=16)
    
    # Case 1: Small perturbation -> small residual
    features_small = np.zeros((10, 7))
    features_small[:, 0] = 0.001
    res_small = model.predict_residuals(features_small)

    # Case 2: Larger perturbation -> larger residual
    features_large = np.zeros((10, 7))
    features_large[:, 0] = 0.8
    res_large = model.predict_residuals(features_large)

    conf_small = res_small["trajectory_confidence_pct"]
    conf_large = res_large["trajectory_confidence_pct"]

    # Valid range checks [50, 100]
    assert 50.0 <= conf_small <= 100.0
    assert 50.0 <= conf_large <= 100.0

    # Larger residual must yield lower (or equal) confidence
    assert conf_small >= conf_large, (
        f"Expected smaller residual confidence ({conf_small}%) >= larger residual confidence ({conf_large}%)"
    )


def test_gru_cell_forward_pass_shape():
    """Verify GRU cell output shapes."""
    cell = GRUResidualCell(input_dim=7, hidden_dim=16)
    h_t, y_t = cell.forward_step(np.random.randn(7, 1), np.zeros((16, 1)))
    assert h_t.shape == (16, 1) and y_t.shape == (3, 1)
    assert np.all(np.isfinite(h_t)) and np.all(np.isfinite(y_t))


# ------ Anomaly Detector Precision/Recall ------
def test_anomaly_detector_precision_recall():
    """
    Evaluate anomaly detector precision, recall, and false-positive rate on a balanced test set.
    Ensures a detector that flags every sample fails the false-positive rate limit.
    """
    np.random.seed(123)
    true_labels, predictions = [], []

    for _ in range(20):
        delta = {
            "delta_semi_major_axis_km_day": np.random.normal(-0.02, 0.01),
            "delta_eccentricity_day": np.random.normal(0.0, 0.00003),
            "delta_inclination_deg_day": np.random.normal(0.0, 0.0005),
            "delta_bstar_day": np.random.normal(0.0, 0.00001),
            "delta_energy_day": np.random.normal(-0.0001, 0.00005),
        }
        predictions.append(anomaly_detector.evaluate_deltas(delta)["is_anomalous"])
        true_labels.append(False)

    for _ in range(20):
        delta = {
            "delta_semi_major_axis_km_day": np.random.choice([1.0, -1.5, 2.0]) + np.random.normal(0, 0.1),
            "delta_eccentricity_day": np.random.normal(0.0, 0.001),
            "delta_inclination_deg_day": np.random.normal(0.05, 0.02),
            "delta_bstar_day": np.random.normal(0.0005, 0.0002),
            "delta_energy_day": np.random.normal(0.005, 0.002),
        }
        predictions.append(anomaly_detector.evaluate_deltas(delta)["is_anomalous"])
        true_labels.append(True)

    tp = sum(p and t for p, t in zip(predictions, true_labels))
    fp = sum(p and not t for p, t in zip(predictions, true_labels))
    fn = sum(not p and t for p, t in zip(predictions, true_labels))
    tn = sum(not p and not t for p, t in zip(predictions, true_labels))

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    accuracy = (tp + tn) / len(true_labels)
    # False-positive rate over nominal samples: fp / (fp + tn)
    nominal_count = fp + tn
    fpr = fp / max(1, nominal_count)

    # Core performance bounds: reasonable precision, recall, accuracy and bounded false-positive rate
    assert precision >= 0.3, f"Precision {precision:.2f} below 0.3"
    assert recall >= 0.3, f"Recall {recall:.2f} below 0.3"
    assert accuracy >= 0.4, f"Accuracy {accuracy:.2f} below 0.4"
    assert fpr <= 0.35, f"False-positive rate {fpr:.2f} exceeds limit of 0.35 (detector flagging too many nominals)"


def test_anomaly_detector_classification_tiers():
    """Verify anomaly detector produces correct classification tiers."""
    nominal = anomaly_detector.evaluate_deltas({
        "delta_semi_major_axis_km_day": -0.01,
        "delta_eccentricity_day": 0.0,
        "delta_inclination_deg_day": 0.0,
        "delta_bstar_day": 0.0,
        "delta_energy_day": -0.0001,
    })
    # Explicit assertion that nominal observation is not flagged as anomalous
    assert nominal["is_anomalous"] is False
    assert 0.0 <= nominal["anomaly_score"] <= 1.0
    assert "isolation_forest_score" in nominal["metrics"]

    maneuver = anomaly_detector.evaluate_deltas({
        "delta_semi_major_axis_km_day": 2.5,
        "delta_eccentricity_day": 0.001,
        "delta_inclination_deg_day": 0.08,
        "delta_bstar_day": 0.001,
        "delta_energy_day": 0.01,
    })
    assert maneuver["is_maneuver_signature"] is True


# ------ Risk Classifier ------
def test_risk_classifier_confusion_matrix():
    """
    Evaluate risk classifier on representative scenarios.
    Checks each scenario's prediction against expected risk level,
    validates that each class probability is finite in [0, 1], and checks sum.
    """
    test_cases = [
        # (miss_dist, rel_vel, lead_time, is_debris, alt, anomaly, ke, expected_risk)
        (50.0, 5.0, 100.0, 0.0, 600.0, 0.1, 12.5, RiskLevel.LOW.value),
        (8.0, 10.0, 48.0, 1.0, 500.0, 0.2, 50.0, RiskLevel.MEDIUM.value),
        (3.0, 13.0, 12.0, 1.0, 400.0, 0.3, 84.5, RiskLevel.HIGH.value),
        (0.5, 15.0, 4.0, 1.0, 400.0, 0.6, 112.5, RiskLevel.CRITICAL.value),
    ]
    valid_levels = {RiskLevel.LOW.value, RiskLevel.MEDIUM.value, RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}

    for miss, vel, lead, deb, alt, ano, ke, expected_risk in test_cases:
        fv = np.array([miss, vel, lead, deb, alt, ano, ke])
        result = conjunction_risk_model.predict_risk(fv)
        
        # Verify valid enum level and exact scenario-specific prediction
        assert result["predicted_risk_level"] in valid_levels
        assert result["predicted_risk_level"] == expected_risk, (
            f"Expected {expected_risk}, got {result['predicted_risk_level']} for miss={miss}km"
        )
        assert 0.0 <= result["priority_score"] <= 100.0

        # Verify each class probability is finite and within [0, 1]
        probs = result["class_probabilities"]
        for cls_name, prob_val in probs.items():
            assert math.isfinite(prob_val), f"Class {cls_name} probability {prob_val} is not finite"
            assert 0.0 <= prob_val <= 1.0, f"Class {cls_name} probability {prob_val} outside [0, 1]"

        # Sum of probabilities must equal ~1.0
        assert abs(sum(probs.values()) - 1.0) < 0.05

    crit = conjunction_risk_model.predict_risk(np.array([0.5, 15.0, 4.0, 1.0, 400.0, 0.6, 112.5]))
    assert crit["priority_score"] >= 50.0


def test_ml_inference_latency():
    """Measure inference latency – each model must average less than 100ms across ten calls."""
    # GRU
    features = np.random.randn(10, 7)
    t0 = time.perf_counter()
    for _ in range(10):
        trajectory_residual_model.predict_residuals(features)
    avg_gru_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_gru_ms < 100.0, f"GRU average latency {avg_gru_ms:.2f}ms exceeds 100ms"

    # Anomaly detector
    delta = {
        "delta_semi_major_axis_km_day": 0.5, "delta_eccentricity_day": 0.0001,
        "delta_inclination_deg_day": 0.01, "delta_bstar_day": 0.0001, "delta_energy_day": 0.001
    }
    t0 = time.perf_counter()
    for _ in range(10):
        anomaly_detector.evaluate_deltas(delta)
    avg_anomaly_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_anomaly_ms < 100.0, f"Anomaly detector average latency {avg_anomaly_ms:.2f}ms exceeds 100ms"

    # Risk classifier
    fv = np.array([5.0, 12.0, 24.0, 1.0, 420.0, 0.3, 72.0])
    t0 = time.perf_counter()
    for _ in range(10):
        conjunction_risk_model.predict_risk(fv)
    avg_risk_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_risk_ms < 100.0, f"Risk classifier average latency {avg_risk_ms:.2f}ms exceeds 100ms"
