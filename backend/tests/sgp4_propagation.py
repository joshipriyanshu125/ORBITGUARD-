import pytest
from datetime import datetime, timezone, timedelta
from app.services.sgp4_engine import sgp4_engine


def test_sgp4_single_propagation():
    line1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9993"
    line2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451231"
    
    satrec = sgp4_engine.build_satrec(line1, line2)
    now = datetime(2024, 5, 4, 12, 17, 43, tzinfo=timezone.utc)
    
    pt = sgp4_engine.propagate_single(satrec, now)
    assert pt is not None
    assert pt.x_km != 0.0
    assert pt.y_km != 0.0
    assert pt.z_km != 0.0
    
    # Velocity in LEO should be roughly 7.5 - 7.8 km/s
    speed = (pt.vx_kms ** 2 + pt.vy_kms ** 2 + pt.vz_kms ** 2) ** 0.5
    assert 7.4 < speed < 7.9
    
    # Altitude should be in typical LEO range ~ 400-430 km
    assert 400.0 < pt.altitude_km < 440.0
    assert -90.0 <= pt.latitude_deg <= 90.0
    assert -180.0 <= pt.longitude_deg <= 180.0


def test_sgp4_discards_non_finite_state(monkeypatch):
    """NaN geodetic output must not reach JSON (it breaks the batch positions endpoint)."""
    import app.services.sgp4_engine as engine_module

    line1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9993"
    line2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451231"
    satrec = sgp4_engine.build_satrec(line1, line2)
    monkeypatch.setattr(engine_module, "ecef_to_geodetic", lambda *_: (float("nan"), 0.0, 400.0))

    assert sgp4_engine.propagate_single(satrec, datetime(2024, 5, 4, 12, 17, 43, tzinfo=timezone.utc)) is None


def test_sgp4_orbit_path_generation():
    line1 = "1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9993"
    line2 = "2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451231"
    
    epoch = datetime(2024, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    orbit_resp = sgp4_engine.propagate_orbit_path(
        norad_id=25544,
        name="ISS (ZARYA)",
        tle_line1=line1,
        tle_line2=line2,
        epoch=epoch,
        start_time=epoch,
        duration_hours=2.0,
        step_seconds=300  # 5 min steps
    )
    
    assert orbit_resp.norad_id == 25544
    assert orbit_resp.point_count > 20
    assert len(orbit_resp.points) == orbit_resp.point_count
    assert "Analytical/illustrative" in orbit_resp.disclaimer
