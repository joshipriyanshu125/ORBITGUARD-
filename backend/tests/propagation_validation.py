"""
Week 12 – Orbital Propagation Validation Tests.
Validates SGP4 propagation, Kepler's third law, coordinate transforms,
and multi-orbit propagation stability.
"""
import pytest
import math
import numpy as np
from datetime import datetime, timezone, timedelta

from app.services.sgp4_engine import sgp4_engine, SGP4Engine
from app.services.orbital_math import (
    teme_to_ecef, ecef_to_geodetic, geodetic_to_ecef,
    teme_to_ecef_full, teme_to_eci_j2000, eci_to_lvlh,
    compute_keplerian_altitudes, EARTH_MU, EARTH_RADIUS_EQUATORIAL_KM,
)


# ISS TLE with verified modulo 10 checksums (Line 1: 6, Line 2: 8)
ISS_L1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9996"
ISS_L2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451238"

# Tiangong Space Station TLE with verified modulo 10 checksums (Line 1: 7, Line 2: 7)
TIANGONG_L1 = "1 48274U 21035A   24125.48912345  .00021456  00000+0  38000-3 0  9997"
TIANGONG_L2 = "2 48274  41.4721 178.5412 0006123  88.3412 271.8541 15.61234512165417"


def test_sgp4_known_epoch_validation():
    """Propagate ISS TLE at known epoch; verify radius and velocity match expectations."""
    satrec = SGP4Engine.build_satrec(ISS_L1, ISS_L2)
    pt = SGP4Engine.propagate_single(satrec, datetime(2024, 5, 4, 12, 17, 44, tzinfo=timezone.utc))
    assert pt is not None

    r = math.sqrt(pt.x_km**2 + pt.y_km**2 + pt.z_km**2)
    assert abs(r - (EARTH_RADIUS_EQUATORIAL_KM + 408.0)) < 80.0

    v = math.sqrt(pt.vx_kms**2 + pt.vy_kms**2 + pt.vz_kms**2)
    assert abs(v - math.sqrt(EARTH_MU / r)) < 0.5


def test_circular_orbit_period_consistency():
    """Verify propagated period matches Kepler's Third Law: T = 2π√(a³/μ)."""
    mm = 15.49812345
    n = mm * (2.0 * math.pi / 86400.0)
    a = (EARTH_MU / (n ** 2)) ** (1.0 / 3.0)
    kepler_min = 2.0 * math.pi * math.sqrt(a**3 / EARTH_MU) / 60.0
    mm_min = 1440.0 / mm
    assert abs(kepler_min - mm_min) < 0.1

    sma, _, _, period = compute_keplerian_altitudes(mm, 0.0004521)
    assert abs(sma - a) < 0.01 and abs(period - mm_min) < 0.1


def test_coordinate_transform_roundtrip_accuracy():
    """
    TEME → ECEF → Geodetic → ECEF roundtrip within 0.01 km.
    Validates ECEF coordinates against an independent astronomical reference derived
    from the GMST rotation angle at May 4, 2024 12:00:00 UTC (theta ≈ 0.7567 rad).
    An unrotated/unchanged TEME vector would differ by ~3694 km and fail this assertion.
    """
    dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    x_teme, y_teme, z_teme = 4000.0, 3000.0, 4000.0

    x_e, y_e, z_e = teme_to_ecef(x_teme, y_teme, z_teme, dt)

    # Independent reference derived from GMST angle (theta ≈ 0.756749 rad)
    # ref_x = cos(theta)*4000 + sin(theta)*3000 = 4967.971 km
    # ref_y = -sin(theta)*4000 + cos(theta)*3000 = -565.032 km
    # ref_z = 4000.0 km
    assert abs(x_e - 4967.971) < 0.1, f"x_ecef {x_e:.3f} deviates from expected 4967.971"
    assert abs(y_e - (-565.032)) < 0.1, f"y_ecef {y_e:.3f} deviates from expected -565.032"
    assert abs(z_e - 4000.0) < 0.001, f"z_ecef {z_e:.3f} deviates from expected 4000.0"

    # Geodetic roundtrip verification
    lat, lon, alt = ecef_to_geodetic(x_e, y_e, z_e)
    xr, yr, zr = geodetic_to_ecef(lat, lon, alt)
    assert math.sqrt((x_e - xr)**2 + (y_e - yr)**2 + (z_e - zr)**2) < 0.01
    assert -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and alt > 0.0


def test_ecef_velocity_transform():
    """
    TEME → ECEF full transform preserves position magnitude and compares velocity
    against a trusted reference incorporating Earth rotation transport omega x r.
    """
    dt = datetime(2024, 6, 15, 8, 30, 0, tzinfo=timezone.utc)
    r_teme = (4000.0, 3000.0, 4000.0)
    v_teme = (0.0, 7.6, 0.0)

    r_ecef, v_ecef = teme_to_ecef_full(r_teme, v_teme, dt)

    # Position magnitude preserved under rotation
    r_orig = math.sqrt(4000**2 + 3000**2 + 4000**2)
    r_new = math.sqrt(sum(c**2 for c in r_ecef))
    assert abs(r_orig - r_new) < 0.001

    # Compare velocity components against trusted reference with Earth rotation
    # v_ecef = R_z(theta)*v - omega_E x r_ecef -> vx ≈ 4.055 km/s, vy ≈ 6.084 km/s, vz = 0.0
    assert abs(v_ecef[0] - 4.055) < 0.01, f"v_ecef_x {v_ecef[0]:.3f} km/s ≠ 4.055"
    assert abs(v_ecef[1] - 6.084) < 0.01, f"v_ecef_y {v_ecef[1]:.3f} km/s ≠ 6.084"
    assert abs(v_ecef[2] - 0.0) < 0.001, f"v_ecef_z {v_ecef[2]:.3f} km/s ≠ 0.0"
    assert 5.0 < math.sqrt(sum(c**2 for c in v_ecef)) < 10.0


def test_propagation_stability_over_multiple_orbits():
    """Propagate ISS over 10 orbits (~15 h); altitude must stay within [300, 500] km."""
    satrec = SGP4Engine.build_satrec(ISS_L1, ISS_L2)
    start = datetime(2024, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    altitudes = []
    for step in range(0, int(10 * 92.9), 10):
        pt = SGP4Engine.propagate_single(satrec, start + timedelta(minutes=step))
        assert pt is not None
        altitudes.append(pt.altitude_km)
    for alt in altitudes:
        assert 300.0 < alt < 500.0
    assert np.std(altitudes) < 20.0


def test_j2000_precession_transform():
    """
    TEME → J2000 verifies both direction and vector length against an independent
    astronomical reference for May 4, 2024 accounting for 24.34 years of equinox precession.
    """
    dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    r_j = teme_to_eci_j2000((6778.0, 0.0, 0.0), dt)

    # Position magnitude must be preserved
    r_mag = math.sqrt(sum(c**2 for c in r_j))
    assert abs(r_mag - 6778.0) < 0.01

    # Direction components accounting for precession rotation matrix P:
    # J2000 x ≈ 6777.881, y ≈ -36.893, z ≈ -16.030
    assert abs(r_j[0] - 6777.881) < 0.1, f"J2000 x {r_j[0]:.3f} ≠ 6777.881"
    assert abs(r_j[1] - (-36.893)) < 0.1, f"J2000 y {r_j[1]:.3f} ≠ -36.893"
    assert abs(r_j[2] - (-16.030)) < 0.1, f"J2000 z {r_j[2]:.3f} ≠ -16.030"


def test_lvlh_frame_decomposition():
    """ECI → LVLH for 1 km radial offset yields ~1 km radial separation."""
    dr, di, dc = eci_to_lvlh((6778.0, 0.0, 0.0), (0.0, 7.66, 0.0), (6779.0, 0.0, 0.0))
    assert abs(dr - 1.0) < 0.01 and abs(di) < 0.01 and abs(dc) < 0.01


def test_batch_propagation_consistency():
    """
    Batch propagation with two distinct satellites (ISS and Tiangong) and three
    distinct timestamps. Verifies every returned position matches single propagation
    and asserts expected dimensions (2 satellites × 3 timestamps × 3 coordinates)
    to detect swapped axes.
    """
    satrec_iss = SGP4Engine.build_satrec(ISS_L1, ISS_L2)
    satrec_tg = SGP4Engine.build_satrec(TIANGONG_L1, TIANGONG_L2)
    satrecs = [satrec_iss, satrec_tg]

    base_dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    target_times = [
        base_dt,
        base_dt + timedelta(hours=1),
        base_dt + timedelta(hours=2),
    ]

    # Perform batch propagation
    positions, velocities = SGP4Engine.batch_propagate_positions(satrecs, target_times)

    # Assert exact expected dimensions (n_sats, n_times, 3)
    assert positions.shape == (2, 3, 3), f"Positions shape {positions.shape} != (2, 3, 3)"
    assert velocities.shape == (2, 3, 3), f"Velocities shape {velocities.shape} != (2, 3, 3)"

    # Verify each satellite at each timestamp against independent single-propagation
    for s_idx, satrec in enumerate(satrecs):
        for t_idx, dt in enumerate(target_times):
            single = SGP4Engine.propagate_single(satrec, dt)
            assert single is not None, f"Single propagation failed for sat {s_idx} at time {t_idx}"
            
            for c_idx, attr in enumerate(["x_km", "y_km", "z_km"]):
                single_val = getattr(single, attr)
                batch_val = positions[s_idx, t_idx, c_idx]
                assert abs(batch_val - single_val) < 0.001, (
                    f"Mismatch at sat {s_idx}, time {t_idx}, coord {attr}: batch={batch_val:.4f}, single={single_val:.4f}"
                )
