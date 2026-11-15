import pytest
import math
from datetime import datetime, timezone
from app.services.orbital_math import (
    gmst_angle,
    teme_to_ecef,
    teme_to_ecef_full,
    ecef_to_geodetic,
    geodetic_to_ecef,
    teme_to_eci_j2000,
    eci_to_lvlh,
    compute_keplerian_altitudes,
    EARTH_RADIUS_EQUATORIAL_KM
)


def test_gmst_angle_range():
    dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    theta = gmst_angle(dt)
    assert 0.0 <= theta <= 2.0 * math.pi


def test_geodetic_ecef_roundtrip():
    # Test point: Kennedy Space Center (lat ~ 28.57 deg N, lon ~ -80.65 deg, alt 0.05 km)
    orig_lat, orig_lon, orig_alt = 28.5729, -80.6490, 0.05
    
    x, y, z = geodetic_to_ecef(orig_lat, orig_lon, orig_alt)
    assert abs(math.sqrt(x**2 + y**2 + z**2) - (EARTH_RADIUS_EQUATORIAL_KM + orig_alt)) < 25.0

    calc_lat, calc_lon, calc_alt = ecef_to_geodetic(x, y, z)
    assert abs(calc_lat - orig_lat) < 1e-4
    assert abs(calc_lon - orig_lon) < 1e-4
    assert abs(calc_alt - orig_alt) < 1e-3


def test_teme_to_ecef_full_velocity():
    dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    r_teme = (6800.0, 0.0, 0.0)
    v_teme = (0.0, 7.6, 0.0)

    (xe, ye, ze), (vxe, vye, vze) = teme_to_ecef_full(r_teme, v_teme, dt)
    # Position magnitude must be conserved under rotation
    r_mag = math.sqrt(xe**2 + ye**2 + ze**2)
    assert abs(r_mag - 6800.0) < 1e-6


def test_teme_to_eci_j2000():
    dt = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    r_teme = (4500.0, 3200.0, 4100.0)
    x_j, y_j, z_j = teme_to_eci_j2000(r_teme, dt)

    orig_norm = math.sqrt(sum(c**2 for c in r_teme))
    j2000_norm = math.sqrt(x_j**2 + y_j**2 + z_j**2)
    assert abs(orig_norm - j2000_norm) < 1e-3


def test_eci_to_lvlh_frame():
    # Primary satellite in circular orbit along X, velocity along Y
    r_prim = (7000.0, 0.0, 0.0)
    v_prim = (0.0, 7.5, 0.0)
    
    # Secondary satellite displaced 2 km Radially (+X) and 5 km In-Track (+Y)
    r_sec = (7002.0, 5.0, 0.0)

    radial, in_track, cross_track = eci_to_lvlh(r_prim, v_prim, r_sec)
    assert abs(radial - 2.0) < 1e-3
    assert abs(in_track - 5.0) < 1e-3
    assert abs(cross_track - 0.0) < 1e-3
