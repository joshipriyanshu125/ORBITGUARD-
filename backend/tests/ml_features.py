import pytest
from datetime import datetime, timezone, timedelta
from app.ml.features import feature_extractor


def test_specific_orbital_energy():
    # Energy E = -mu / (2*a)
    # For a = 7000 km, E should be approx -398600.4418 / 14000 = -28.47 km^2/s^2
    energy = feature_extractor.compute_specific_orbital_energy(7000.0)
    assert abs(energy - (-28.4714)) < 0.01


def test_j2_secular_drift_rates():
    # ISS orbit: a ~ 6800 km, e ~ 0.0004, i ~ 51.64 deg, mm ~ 15.5 rev/day
    drifts = feature_extractor.compute_nodal_precession_rates(
        semi_major_axis_km=6800.0,
        eccentricity=0.0004,
        inclination_deg=51.64,
        mean_motion_rev_day=15.5
    )
    # ISS RAAN precesses westward at ~ -5.0 deg/day
    raan_drift = drifts["raan_drift_deg_day"]
    assert -6.5 < raan_drift < -4.0

    # Perigee precesses eastward at ~ 3-4 deg/day
    arg_p_drift = drifts["arg_perigee_drift_deg_day"]
    assert 2.0 < arg_p_drift < 6.0


def test_time_series_deltas_extraction():
    epoch1 = {
        "epoch": datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
        "apogee_km": 420.0,
        "perigee_km": 415.0,
        "eccentricity": 0.0004,
        "inclination": 51.64,
        "bstar": 0.0001
    }
    epoch2 = {
        "epoch": datetime(2024, 5, 5, 12, 0, 0, tzinfo=timezone.utc), # 1 day later
        "apogee_km": 420.5, # Station-keeping boost (+0.5 km)
        "perigee_km": 415.5,
        "eccentricity": 0.00042,
        "inclination": 51.641,
        "bstar": 0.00011
    }

    deltas = feature_extractor.extract_time_series_deltas(epoch2, epoch1)
    assert deltas["dt_days"] == 1.0
    assert abs(deltas["delta_semi_major_axis_km_day"] - 0.5) < 1e-3
    assert deltas["delta_eccentricity_day"] > 0
    assert deltas["delta_energy_day"] > 0
