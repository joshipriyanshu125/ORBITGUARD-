import math
from datetime import datetime, timezone
from typing import Tuple, List
import numpy as np

# WGS-84 Earth Constants
EARTH_RADIUS_EQUATORIAL_KM = 6378.137
EARTH_RADIUS_POLAR_KM = 6356.7523142
EARTH_FLATTENING = 1.0 / 298.257223563
EARTH_MU = 398600.4418  # Standard gravitational parameter km^3 / s^2
EARTH_ROTATION_RATE_RAD_S = 7.292115e-5  # rad/s


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


def teme_to_ecef_full(
    r_teme: Tuple[float, float, float],
    v_teme: Tuple[float, float, float],
    dt: datetime
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Transform position and velocity from TEME (ECI) to ECEF frame.
    Accounts for Earth rotation rate omega_E cross-product:
    v_ecef = R_z(theta) * v_teme - omega_E x r_ecef
    """
    theta = gmst_angle(dt)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    x, y, z = r_teme
    vx, vy, vz = v_teme

    # Position in ECEF
    x_ecef = cos_t * x + sin_t * y
    y_ecef = -sin_t * x + cos_t * y
    z_ecef = z

    # Velocity in ECEF with Coriolis/transport correction
    # d(R_z)/dt * r_teme = [-sin(t)*x + cos(t)*y, -cos(t)*x - sin(t)*y, 0] * omega_E
    omega = EARTH_ROTATION_RATE_RAD_S
    vx_ecef = (cos_t * vx + sin_t * vy) + omega * y_ecef
    vy_ecef = (-sin_t * vx + cos_t * vy) - omega * x_ecef
    vz_ecef = vz

    return (x_ecef, y_ecef, z_ecef), (vx_ecef, vy_ecef, vz_ecef)


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


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_km: float) -> Tuple[float, float, float]:
    """Convert Geodetic coordinates (lat, lon deg, alt km) to ECEF Cartesian coordinates (km)."""
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    a = EARTH_RADIUS_EQUATORIAL_KM
    e2 = 1.0 - (EARTH_RADIUS_POLAR_KM ** 2 / a ** 2)
    
    n = a / math.sqrt(1.0 - e2 * (math.sin(lat_rad) ** 2))
    
    x = (n + alt_km) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (n + alt_km) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (n * (1.0 - e2) + alt_km) * math.sin(lat_rad)
    return x, y, z


def teme_to_eci_j2000(r_teme: Tuple[float, float, float], dt: datetime) -> Tuple[float, float, float]:
    """
    Convert TEME position coordinates to ECI J2000 (GCRF) frame
    accounting for equinox precession and equation of the equinoxes.
    """
    jd = datetime_to_jd(dt)
    t = (jd - 2451545.0) / 36525.0
    
    # Precession angles (zeta, z, theta in arcseconds)
    zeta = (2306.2181 * t + 0.30188 * t**2 + 0.017998 * t**3) * (math.pi / (180.0 * 3600.0))
    z_ang = (2306.2181 * t + 1.09468 * t**2 + 0.018203 * t**3) * (math.pi / (180.0 * 3600.0))
    theta = (2004.3109 * t - 0.42665 * t**2 - 0.041833 * t**3) * (math.pi / (180.0 * 3600.0))
    
    # Precession rotation matrix P
    p11 = math.cos(zeta) * math.cos(theta) * math.cos(z_ang) - math.sin(zeta) * math.sin(z_ang)
    p12 = -math.sin(zeta) * math.cos(theta) * math.cos(z_ang) - math.cos(zeta) * math.sin(z_ang)
    p13 = -math.sin(theta) * math.cos(z_ang)
    
    p21 = math.cos(zeta) * math.cos(theta) * math.sin(z_ang) + math.sin(zeta) * math.cos(z_ang)
    p22 = -math.sin(zeta) * math.cos(theta) * math.sin(z_ang) + math.cos(zeta) * math.cos(z_ang)
    p23 = -math.sin(theta) * math.sin(z_ang)
    
    p31 = math.cos(zeta) * math.sin(theta)
    p32 = -math.sin(zeta) * math.sin(theta)
    p33 = math.cos(theta)

    rx, ry, rz = r_teme
    # J2000 = P^T * TEME (approximate equinox alignment)
    x_j2000 = p11 * rx + p21 * ry + p31 * rz
    y_j2000 = p12 * rx + p22 * ry + p32 * rz
    z_j2000 = p13 * rx + p23 * ry + p33 * rz
    return x_j2000, y_j2000, z_j2000


def eci_to_lvlh(
    r_primary: Tuple[float, float, float],
    v_primary: Tuple[float, float, float],
    r_secondary: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """
    Transform relative displacement of secondary object into the Primary spacecraft's
    Local-Vertical Local-Horizontal (LVLH / Hill / RIC) frame:
    - Radial (R): Unit vector pointing from Earth center outward along primary position.
    - Cross-Track (C): Unit vector normal to orbital plane (along angular momentum h = r x v).
    - In-Track (I): Completes right-handed orthogonal system (along velocity in circular orbits).
    Returns (radial_km, in_track_km, cross_track_km).
    """
    r1 = np.array(r_primary, dtype=np.float64)
    v1 = np.array(v_primary, dtype=np.float64)
    r2 = np.array(r_secondary, dtype=np.float64)

    dr = r2 - r1  # Relative vector in ECI

    # Unit vectors
    r1_norm = np.linalg.norm(r1)
    if r1_norm < 1e-6:
        return float(dr[0]), float(dr[1]), float(dr[2])

    u_radial = r1 / r1_norm

    h = np.cross(r1, v1)
    h_norm = np.linalg.norm(h)
    if h_norm < 1e-6:
        u_cross = np.array([0.0, 0.0, 1.0])
    else:
        u_cross = h / h_norm

    u_in_track = np.cross(u_cross, u_radial)

    # Projections
    radial_km = float(np.dot(dr, u_radial))
    in_track_km = float(np.dot(dr, u_in_track))
    cross_track_km = float(np.dot(dr, u_cross))

    return radial_km, in_track_km, cross_track_km


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
