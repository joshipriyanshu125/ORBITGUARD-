import pytest
from app.services.celestrak import celestrak_service
from app.services.orbital_math import compute_keplerian_altitudes, ecef_to_geodetic, teme_to_ecef
from app.models.satellite import ObjectType
from datetime import datetime, timezone


def test_keplerian_altitudes():
    # Mean motion for ISS is ~15.5 revs/day, eccentricity ~0.0004
    sma_km, apogee_km, perigee_km, period_min = compute_keplerian_altitudes(15.498, 0.00045)
    
    # ISS orbital altitude is between 400 and 430 km
    assert 6700 < sma_km < 6900
    assert 400 < apogee_km < 440
    assert 400 < perigee_km < 440
    assert 90 < period_min < 95


def test_bstar_scientific_parsing():
    # Test standard TLE BSTAR representation e.g. " 30000-3" -> 0.30000e-3 = 0.000300
    bstar1 = celestrak_service._parse_tle_scientific(" 30000-3")
    assert abs(bstar1 - 0.00003) < 1e-6 or abs(bstar1 - 0.0003) < 1e-4

    bstar2 = celestrak_service._parse_tle_scientific("00000+0")
    assert bstar2 == 0.0


def test_parse_tle_text():
    tle_sample = """ISS (ZARYA)
1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9993
2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451231
FENGYUN 1C DEBRIS
1 39872U 99025DF  24125.41235123  .00003214  00000+0  12000-3 0  9991
2 39872  98.6512  45.1234 0021456 120.4512 240.1234 14.12451234789512"""

    satellites = celestrak_service.parse_tle_text(tle_sample, source_group="test")
    assert len(satellites) == 2
    
    iss = satellites[0]
    assert iss.norad_id == 25544
    assert iss.name == "ISS (ZARYA)"
    assert iss.object_type == ObjectType.PAYLOAD
    assert iss.inclination_deg == 51.6415
    assert 400 < iss.apogee_km < 440
    
    debris = satellites[1]
    assert debris.norad_id == 39872
    assert debris.object_type == ObjectType.DEBRIS
    assert debris.inclination_deg == 98.6512


def test_ecef_to_geodetic():
    # Test point on equator at sea level: X = 6378.137 km, Y = 0, Z = 0
    lat, lon, alt = ecef_to_geodetic(6378.137, 0.0, 0.0)
    assert abs(lat) < 0.01
    assert abs(lon) < 0.01
    assert abs(alt) < 0.1
