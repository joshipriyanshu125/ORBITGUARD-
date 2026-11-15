import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np

from app.services.orbital_math import (
    EARTH_RADIUS_EQUATORIAL_KM,
    EARTH_MU,
    compute_keplerian_altitudes
)

# Earth J2 zonal harmonic constant
J2_CONSTANT = 1.08262668e-3


class OrbitalFeatureExtractor:
    """
    Extracts physically motivated orbital dynamic features and temporal derivatives
    from TLE and ephemeris history for ML anomaly and risk models.
    """

    @staticmethod
    def compute_specific_orbital_energy(semi_major_axis_km: float) -> float:
        """Specific orbital energy E = -mu / (2*a) in km^2 / s^2."""
        if semi_major_axis_km <= 0:
            return 0.0
        return -EARTH_MU / (2.0 * semi_major_axis_km)

    @staticmethod
    def compute_nodal_precession_rates(
        semi_major_axis_km: float,
        eccentricity: float,
        inclination_deg: float,
        mean_motion_rev_day: float
    ) -> Dict[str, float]:
        """
        Computes analytical J2 secular perturbation drift rates:
        - RAAN drift rate dOmega/dt (deg/day)
        - Argument of perigee drift rate domega/dt (deg/day)
        """
        if semi_major_axis_km <= EARTH_RADIUS_EQUATORIAL_KM or eccentricity >= 1.0:
            return {"raan_drift_deg_day": 0.0, "arg_perigee_drift_deg_day": 0.0}

        # Semi-latus rectum p = a * (1 - e^2)
        p = semi_major_axis_km * (1.0 - eccentricity**2)
        re_p_ratio = (EARTH_RADIUS_EQUATORIAL_KM / p) ** 2
        
        inc_rad = math.radians(inclination_deg)
        cos_inc = math.cos(inc_rad)
        sin_inc = math.sin(inc_rad)

        # Mean motion in deg/day
        n_deg_day = mean_motion_rev_day * 360.0

        # RAAN secular precession: dOmega/dt = -3/2 * J2 * (Re/p)^2 * n * cos(i)
        raan_drift = -1.5 * J2_CONSTANT * re_p_ratio * n_deg_day * cos_inc

        # Argument of perigee precession: domega/dt = 3/4 * J2 * (Re/p)^2 * n * (5*cos^2(i) - 1)
        arg_p_drift = 0.75 * J2_CONSTANT * re_p_ratio * n_deg_day * (5.0 * (cos_inc**2) - 1.0)

        return {
            "raan_drift_deg_day": round(raan_drift, 6),
            "arg_perigee_drift_deg_day": round(arg_p_drift, 6)
        }

    def extract_satellite_features(self, sat_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract baseline feature vector from a single satellite catalog entry."""
        a = float(sat_data.get("semi_major_axis_km", 6800.0))
        e = float(sat_data.get("eccentricity", 0.001))
        inc = float(sat_data.get("inclination_deg", 51.6))
        bstar = float(sat_data.get("bstar", 0.0))
        mm = float(sat_data.get("mean_motion_rev_day", 15.5))
        apogee = float(sat_data.get("apogee_km", 420.0))
        perigee = float(sat_data.get("perigee_km", 415.0))

        energy = self.compute_specific_orbital_energy(a)
        drifts = self.compute_nodal_precession_rates(a, e, inc, mm)

        # Altitude eccentricity ratio
        alt_span = max(0.01, apogee - perigee)
        mean_alt = (apogee + perigee) / 2.0

        return {
            "semi_major_axis_km": a,
            "eccentricity": e,
            "inclination_deg": inc,
            "bstar": bstar,
            "mean_motion_rev_day": mm,
            "apogee_km": apogee,
            "perigee_km": perigee,
            "mean_altitude_km": mean_alt,
            "altitude_span_km": alt_span,
            "specific_orbital_energy": energy,
            "raan_drift_deg_day": drifts["raan_drift_deg_day"],
            "arg_perigee_drift_deg_day": drifts["arg_perigee_drift_deg_day"]
        }

    def extract_time_series_deltas(
        self,
        current_epoch: Dict[str, Any],
        previous_epoch: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract rate of change / temporal derivatives between successive TLE epochs.
        Crucial for detecting maneuvers vs natural atmospheric decay.
        """
        t_curr = current_epoch["epoch"] if isinstance(current_epoch["epoch"], datetime) else datetime.fromisoformat(str(current_epoch["epoch"]).replace("Z", "+00:00"))
        t_prev = previous_epoch["epoch"] if isinstance(previous_epoch["epoch"], datetime) else datetime.fromisoformat(str(previous_epoch["epoch"]).replace("Z", "+00:00"))

        dt_days = max(1e-4, abs((t_curr - t_prev).total_seconds()) / 86400.0)

        # Deltas
        da_dt = (float(current_epoch.get("apogee_km", 0.0) + current_epoch.get("perigee_km", 0.0)) - 
                 float(previous_epoch.get("apogee_km", 0.0) + previous_epoch.get("perigee_km", 0.0))) / (2.0 * dt_days)
        de_dt = (float(current_epoch.get("eccentricity", 0.0)) - float(previous_epoch.get("eccentricity", 0.0))) / dt_days
        di_dt = (float(current_epoch.get("inclination", 0.0)) - float(previous_epoch.get("inclination", 0.0))) / dt_days
        dbstar_dt = (float(current_epoch.get("bstar", 0.0)) - float(previous_epoch.get("bstar", 0.0))) / dt_days

        # Specific energy delta
        a_curr = (float(current_epoch.get("apogee_km", 400.0)) + float(current_epoch.get("perigee_km", 400.0))) / 2.0 + EARTH_RADIUS_EQUATORIAL_KM
        a_prev = (float(previous_epoch.get("apogee_km", 400.0)) + float(previous_epoch.get("perigee_km", 400.0))) / 2.0 + EARTH_RADIUS_EQUATORIAL_KM
        denergy_dt = (self.compute_specific_orbital_energy(a_curr) - self.compute_specific_orbital_energy(a_prev)) / dt_days

        return {
            "dt_days": round(dt_days, 4),
            "delta_semi_major_axis_km_day": round(da_dt, 6),
            "delta_eccentricity_day": round(de_dt, 8),
            "delta_inclination_deg_day": round(di_dt, 6),
            "delta_bstar_day": round(dbstar_dt, 8),
            "delta_energy_day": round(denergy_dt, 6)
        }

    def extract_conjunction_features(
        self,
        conjunction: Dict[str, Any],
        primary: Optional[Dict[str, Any]] = None,
        secondary: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Formulate feature vector for the XGBoost / Gradient Boosting conjunction risk model:
        [miss_distance_km, relative_velocity_kms, lead_time_hours, secondary_is_debris, 
         primary_altitude_km, anomaly_score, relative_kinetic_energy]
        """
        miss_dist = float(conjunction.get("miss_distance_km", 10.0))
        rel_vel = float(conjunction.get("relative_velocity_kms", 10.0))
        
        # Calculate lead time to TCA
        tca = conjunction.get("tca")
        if isinstance(tca, str):
            tca_dt = datetime.fromisoformat(tca.replace("Z", "+00:00"))
        elif isinstance(tca, datetime):
            tca_dt = tca
        else:
            tca_dt = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        lead_time_hours = max(0.1, (tca_dt - now).total_seconds() / 3600.0)

        sec_type = str(conjunction.get("secondary_type", "DEBRIS")).upper()
        sec_is_debris = 1.0 if "DEB" in sec_type or "R/B" in sec_type else 0.0

        p_alt = float(primary.get("perigee_km", 415.0)) if primary else 415.0
        anomaly_score = float(conjunction.get("ml_anomaly_score", 0.0))

        # Relative kinetic energy surrogate ~ 0.5 * v_rel^2
        rel_ke = 0.5 * (rel_vel ** 2)

        return np.array([
            miss_dist,
            rel_vel,
            lead_time_hours,
            sec_is_debris,
            p_alt,
            anomaly_score,
            rel_ke
        ], dtype=np.float64)


feature_extractor = OrbitalFeatureExtractor()
