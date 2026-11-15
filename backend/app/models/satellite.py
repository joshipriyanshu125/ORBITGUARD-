from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def now_utc():
    return datetime.now(timezone.utc)


class ObjectType(str, Enum):
    PAYLOAD = "PAYLOAD"
    DEBRIS = "DEBRIS"
    ROCKET_BODY = "ROCKET_BODY"
    UNKNOWN = "UNKNOWN"


class OrbitPoint(BaseModel):
    timestamp: datetime
    # ECI (TEME / J2000) coordinates in km
    x_km: float
    y_km: float
    z_km: float
    # Velocity components in km/s
    vx_kms: float
    vy_kms: float
    vz_kms: float
    # Geodetic coordinates for 3D Earth mapping
    latitude_deg: float
    longitude_deg: float
    altitude_km: float


class SatelliteBase(BaseModel):
    norad_id: int = Field(..., description="NORAD Catalog Number")
    name: str = Field(..., description="Common Satellite / Debris Name")
    object_type: ObjectType = Field(default=ObjectType.UNKNOWN)
    tle_line1: str
    tle_line2: str
    omm: Optional[Dict[str, Any]] = Field(default=None, description="Raw OMM JSON metadata")
    epoch: datetime = Field(..., description="Ephemeris epoch datetime")
    apogee_km: float = Field(..., description="Apogee altitude in kilometers")
    perigee_km: float = Field(..., description="Perigee altitude in kilometers")
    semi_major_axis_km: float = Field(..., description="Semi-major axis in kilometers")
    inclination_deg: float = Field(..., description="Inclination in degrees")
    eccentricity: float = Field(..., description="Eccentricity")
    raan_deg: Optional[float] = Field(default=0.0, description="Right Ascension of Ascending Node")
    arg_perigee_deg: Optional[float] = Field(default=0.0, description="Argument of Perigee")
    mean_anomaly_deg: Optional[float] = Field(default=0.0, description="Mean Anomaly")
    mean_motion_rev_day: Optional[float] = Field(default=0.0, description="Mean Motion in revs/day")
    bstar: Optional[float] = Field(default=0.0, description="BSTAR aerodynamic drag term")
    period_min: Optional[float] = Field(default=None, description="Orbital period in minutes")
    source_group: Optional[str] = Field(default="stations", description="CelesTrak group query origin")


class SatelliteCreate(SatelliteBase):
    pass


class SatelliteInDB(SatelliteBase):
    id: Optional[str] = Field(default=None, alias="_id")
    updated_at: datetime = Field(default_factory=now_utc)

    model_config = ConfigDict(populate_by_name=True)


class SatelliteResponse(SatelliteBase):
    updated_at: datetime
    disclaimer: str = (
        "Analytical/illustrative assessment based on public TLE/OMM data, "
        "not certified operational flight-dynamics commands."
    )


class TLEHistoryRecord(BaseModel):
    norad_id: int
    epoch: datetime
    tle_line1: str
    tle_line2: str
    mean_motion: float
    eccentricity: float
    inclination: float
    bstar: float
    apogee_km: float
    perigee_km: float
    created_at: datetime = Field(default_factory=now_utc)


class OrbitPropagationResponse(BaseModel):
    norad_id: int
    name: str
    epoch: datetime
    start_time: datetime
    end_time: datetime
    step_seconds: int
    point_count: int
    points: List[OrbitPoint]
    disclaimer: str = (
        "Analytical/illustrative assessment based on public TLE/OMM data, "
        "not certified operational flight-dynamics commands."
    )
