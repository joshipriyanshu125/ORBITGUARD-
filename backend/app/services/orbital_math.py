import math
from datetime import datetime, timezone
from typing import Tuple

# WGS-84 Earth Constants
EARTH_RADIUS_EQUATORIAL_KM = 6378.137
EARTH_RADIUS_POLAR_KM = 6356.7523142
EARTH_FLATTENING = 1.0 / 298.257223563
EARTH_MU = 398600.4418  # Standard gravitational parameter km^3 / s^2


def datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
        
    year = dt.year
    month = dt.month
    day = dt.day + (dt.hour + (dt.minute + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0) / 24.0

    if month <= 2:
        year -= 1
        month += 12

    A = int(year / 100)
    B = 2 - A + int(A / 4)
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    return jd


def gmst_angle(dt: datetime) -> float:
    """Calculate Greenwich Mean Sidereal Time (GMST) in radians."""
    jd = datetime_to_jd(dt)
    t = (jd - 2451545.0) / 36525.0
    # GMST in seconds
    gmst_sec = (
        24110.54841
        + 8640184.812866 * t
        + 0.093104 * (t ** 2)
        - 6.2e-6 * (t ** 3)
    )
    # Add fractional day
    day_fraction = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6) % 86400
    gmst_sec += day_fraction * 1.002737909350795
    # Normalize to [0, 2pi) radians
    gmst_rad = (gmst_sec % 86400) * (2.0 * math.pi / 86400.0)
    return gmst_rad


def teme_to_ecef(x: float, y: float, z: float, dt: datetime) -> Tuple[float, float, float]:
    """Rotate TEME (ECI) position coordinates into ECEF frame."""
    theta = gmst_angle(dt)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    x_ecef = cos_t * x + sin_t * y
    y_ecef = -sin_t * x + cos_t * y
    z_ecef = z
    return x_ecef, y_ecef, z_ecef


def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """
    Convert ECEF Cartesian coordinates (km) to Geodetic (Lat deg, Lon deg, Alt km)
    using Bowring's closed-form algorithm for WGS-84.
    """
    a = EARTH_RADIUS_EQUATORIAL_KM
    b = EARTH_RADIUS_POLAR_KM
    e2 = (a ** 2 - b ** 2) / (a ** 2)
    e_prime2 = (a ** 2 - b ** 2) / (b ** 2)
    
    p = math.sqrt(x ** 2 + y ** 2)
    if p < 1e-6:
        # Near pole
        lat = 90.0 if z > 0 else -90.0
        lon = 0.0
        alt = abs(z) - b
        return lat, lon, alt
        
    theta = math.atan2(z * a, p * b)
    lat_rad = math.atan2(
        z + e_prime2 * b * (math.sin(theta) ** 3),
        p - e2 * a * (math.cos(theta) ** 3)
    )
    lon_rad = math.atan2(y, x)
    
    # Radius of curvature in prime vertical
    n = a / math.sqrt(1.0 - e2 * (math.sin(lat_rad) ** 2))
    alt = (p / math.cos(lat_rad)) - n
    
    lat_deg = math.degrees(lat_rad)
    lon_deg = math.degrees(lon_rad)
    
    # Normalize lon to [-180, 180]
    lon_deg = (lon_deg + 180.0) % 360.0 - 180.0
    
    return lat_deg, lon_deg, alt


def compute_keplerian_altitudes(
    mean_motion_rev_day: float,
    eccentricity: float
) -> Tuple[float, float, float, float]:
    """
    Given mean motion (rev/day) and eccentricity, return:
    (semi_major_axis_km, apogee_km, perigee_km, period_minutes)
    """
    if mean_motion_rev_day <= 0:
        return 0.0, 0.0, 0.0, 0.0
        
    # Convert rev/day to rad/s
    n_rad_s = mean_motion_rev_day * (2.0 * math.pi / 86400.0)
    # semi-major axis a = (mu / n^2)^(1/3)
    a = (EARTH_MU / (n_rad_s ** 2)) ** (1.0 / 3.0)
    
    perigee = a * (1.0 - eccentricity) - EARTH_RADIUS_EQUATORIAL_KM
    apogee = a * (1.0 + eccentricity) - EARTH_RADIUS_EQUATORIAL_KM
    period_min = 1440.0 / mean_motion_rev_day
    
    return a, apogee, perigee, period_min
