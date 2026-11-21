from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import numpy as np
from sgp4.api import Satrec, WGS72
from sgp4.api import jday

from app.models.satellite import OrbitPoint, OrbitPropagationResponse
from app.services.orbital_math import (
    teme_to_ecef,
    ecef_to_geodetic,
    compute_keplerian_altitudes,
)
from app.core.logging import logger


class SGP4Engine:
    """High-performance SGP4 orbital propagator with ECI/ECEF/Geodetic coordinate transformations."""

    @staticmethod
    def build_satrec(tle_line1: str, tle_line2: str) -> Satrec:
        """Construct an SGP4 Satrec object from TLE lines."""
        return Satrec.twoline2rv(tle_line1.strip(), tle_line2.strip(), WGS72)

    @staticmethod
    def propagate_single(
        satrec: Satrec,
        dt: datetime
    ) -> Optional[OrbitPoint]:
        """Propagate a satellite to a single datetime, returning ECI and Geodetic coordinates."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
        error_code, r_teme, v_teme = satrec.sgp4(jd, fr)

        if error_code != 0:
            # Satrec error code (e.g. decayed orbit, eccentricity out of range)
            return None

        x, y, z = r_teme
        vx, vy, vz = v_teme

        # Coordinate transformation: TEME -> ECEF -> Geodetic
        x_ecef, y_ecef, z_ecef = teme_to_ecef(x, y, z, dt)
        lat_deg, lon_deg, alt_km = ecef_to_geodetic(x_ecef, y_ecef, z_ecef)
        # Degenerate elements can yield NaN with error_code 0; NaN is not JSON-safe.
        if not np.all(np.isfinite([lat_deg, lon_deg, alt_km])):
            return None

        return OrbitPoint(
            timestamp=dt,
            x_km=float(x),
            y_km=float(y),
            z_km=float(z),
            vx_kms=float(vx),
            vy_kms=float(vy),
            vz_kms=float(vz),
            latitude_deg=float(lat_deg),
            longitude_deg=float(lon_deg),
            altitude_km=float(alt_km),
        )

    def propagate_orbit_path(
        self,
        norad_id: int,
        name: str,
        tle_line1: str,
        tle_line2: str,
        epoch: datetime,
        start_time: Optional[datetime] = None,
        duration_hours: float = 24.0,
        step_seconds: int = 120
    ) -> OrbitPropagationResponse:
        """
        Propagate orbit over a duration and return trajectory points for 3D visualization.
        """
        satrec = self.build_satrec(tle_line1, tle_line2)
        
        now = datetime.now(timezone.utc)
        start = start_time if start_time else now
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
            
        end = start + timedelta(hours=duration_hours)
        
        # Calculate steps
        total_seconds = int((end - start).total_seconds())
        step_seconds = max(10, step_seconds)  # Guard minimum step
        
        points: List[OrbitPoint] = []
        current = start
        
        while current <= end:
            pt = self.propagate_single(satrec, current)
            if pt is not None:
                points.append(pt)
            current += timedelta(seconds=step_seconds)
            
        return OrbitPropagationResponse(
            norad_id=norad_id,
            name=name,
            epoch=epoch,
            start_time=start,
            end_time=end,
            step_seconds=step_seconds,
            point_count=len(points),
            points=points,
        )

    @staticmethod
    def batch_propagate_positions(
        satrecs: List[Satrec],
        target_datetimes: List[datetime]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Vectorized batch propagation for conjunction screening.
        Returns:
            positions: ndarray of shape (len(satrecs), len(target_datetimes), 3) in km
            velocities: ndarray of shape (len(satrecs), len(target_datetimes), 3) in km/s
        """
        n_sats = len(satrecs)
        n_times = len(target_datetimes)
        
        positions = np.zeros((n_sats, n_times, 3), dtype=np.float64)
        velocities = np.zeros((n_sats, n_times, 3), dtype=np.float64)

        for t_idx, dt in enumerate(target_datetimes):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
            for s_idx, satrec in enumerate(satrecs):
                err, r, v = satrec.sgp4(jd, fr)
                if err == 0:
                    positions[s_idx, t_idx] = r
                    velocities[s_idx, t_idx] = v
                else:
                    # Decay / error: fill NaN
                    positions[s_idx, t_idx] = np.nan
                    velocities[s_idx, t_idx] = np.nan

        return positions, velocities


sgp4_engine = SGP4Engine()
