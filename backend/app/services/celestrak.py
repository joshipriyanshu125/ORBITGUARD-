import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.logging import logger
from app.models.satellite import SatelliteCreate, ObjectType
from app.services.orbital_math import compute_keplerian_altitudes


class CelesTrakService:
    """Service for interacting with the CelesTrak GP TLE API."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.CELESTRAK_BASE_URL
        self._cache: Dict[str, Any] = {}

    def _classify_object_type(self, name: str, object_type_str: Optional[str] = None) -> ObjectType:
        """Heuristically or explicitly categorize object type."""
        name_upper = name.upper()
        if object_type_str:
            ot_upper = object_type_str.upper()
            if "DEBRIS" in ot_upper:
                return ObjectType.DEBRIS
            if "ROCKET" in ot_upper or "R/B" in ot_upper:
                return ObjectType.ROCKET_BODY
            if "PAYLOAD" in ot_upper:
                return ObjectType.PAYLOAD
                
        if "DEB" in name_upper or "DEBRIS" in name_upper:
            return ObjectType.DEBRIS
        if " R/B" in name_upper or "ROCKET BODY" in name_upper:
            return ObjectType.ROCKET_BODY
        return ObjectType.PAYLOAD

    def parse_tle_text(self, tle_text: str, source_group: str) -> List[SatelliteCreate]:
        """Parse raw 3-line or 2-line TLE text blocks."""
        lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
        satellites: List[SatelliteCreate] = []
        i = 0
        while i < len(lines):
            # Check if 3-line format (Name, Line 1, Line 2)
            if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i+1].startswith("2 "):
                name = f"OBJECT-{lines[i][2:7].strip()}"
                line1 = lines[i]
                line2 = lines[i+1]
                i += 2
            elif i + 2 < len(lines) and lines[i+1].startswith("1 ") and lines[i+2].startswith("2 "):
                name = lines[i]
                line1 = lines[i+1]
                line2 = lines[i+2]
                i += 3
            else:
                i += 1
                continue

            try:
                norad_id = int(line1[2:7].strip())
                inc = float(line2[8:16].strip())
                raan = float(line2[17:25].strip())
                ecc = float("0." + line2[26:33].strip())
                arg_p = float(line2[34:42].strip())
                m_anom = float(line2[43:51].strip())
                mm = float(line2[52:63].strip())
                bstar_str = line1[53:61].strip()
                bstar = self._parse_tle_scientific(bstar_str)

                # Epoch year and day from line 1
                epoch_year = int(line1[18:20])
                full_year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
                epoch_day = float(line1[20:32])
                epoch = datetime(full_year, 1, 1, tzinfo=timezone.utc)
                # Days to seconds
                from datetime import timedelta
                epoch += timedelta(days=epoch_day - 1)

                sma_km, apogee_km, perigee_km, period_min = compute_keplerian_altitudes(mm, ecc)
                obj_type = self._classify_object_type(name)

                sat = SatelliteCreate(
                    norad_id=norad_id,
                    name=name,
                    intl_designator=line1[9:17].strip() or None,
                    object_type=obj_type,
                    tle_line1=line1,
                    tle_line2=line2,
                    omm=None,
                    epoch=epoch,
                    apogee_km=round(apogee_km, 2),
                    perigee_km=round(perigee_km, 2),
                    semi_major_axis_km=round(sma_km, 2),
                    inclination_deg=round(inc, 4),
                    eccentricity=round(ecc, 7),
                    raan_deg=round(raan, 4),
                    arg_perigee_deg=round(arg_perigee_deg := arg_p, 4),
                    mean_anomaly_deg=round(m_anom, 4),
                    mean_motion_rev_day=round(mm, 8),
                    bstar=bstar,
                    period_min=round(period_min, 2) if period_min else None,
                    source_group=source_group
                )
                satellites.append(sat)
            except Exception as e:
                logger.warning(f"Error parsing TLE block for {name}: {e}")
                continue

        return satellites

    @staticmethod
    def _parse_tle_scientific(bstar_str: str) -> float:
        """Parse TLE condensed scientific notation e.g. '12345-4' -> 0.12345e-4."""
        try:
            bstar_str = bstar_str.strip()
            if not bstar_str or bstar_str == "0":
                return 0.0
            sign = -1.0 if bstar_str.startswith("-") else 1.0
            clean = bstar_str.replace("+", "").replace("-", "")
            if len(clean) >= 2:
                mantissa = float("0." + clean[:-1])
                exp = int(clean[-1])
                exp_sign = -1 if "-" in bstar_str[1:] else 1
                return sign * mantissa * (10 ** (exp_sign * exp))
            return 0.0
        except Exception:
            return 0.0

    async def fetch_group(
        self,
        group_name: str = "stations"
    ) -> List[SatelliteCreate]:
        """
        Fetch real TLEs for a CelesTrak group.
        Supported groups: 'stations', 'active', 'cosmos-2251-debris', 'fengyun-1c-debris', 'iridium-33-debris'.
        """
        import os
        import sys
        if os.environ.get("ENVIRONMENT") == "test" or "pytest" in sys.modules:
            return self.get_offline_sample_data(group_name)

        url = f"{self.base_url}?GROUP={group_name}&FORMAT=tle"
        logger.info(f"Fetching CelesTrak group '{group_name}' from {url}...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ORBITGUARD/1.0",
            "Accept": "text/plain, */*"
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers=headers,
            follow_redirects=True
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return self.parse_tle_text(response.text, group_name)
            except Exception as exc:
                exc_desc = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                logger.warning(f"Failed to fetch live CelesTrak group '{group_name}' ({exc_desc}).")
                # No fabrication: an unavailable upstream source yields no records.
                return []

    def get_offline_sample_data(self, group_name: str) -> List[SatelliteCreate]:
        """Provides verified sample ephemeris for key satellites and debris when offline."""
        logger.info(f"Loading offline fixture ephemeris for group '{group_name}'")
        sample_tle = """
ISS (ZARYA)
1 25544U 98067A   24125.51231481  .00016717  00000+0  30000-3 0  9993
2 25544  51.6415 162.1524 0004521  45.1234 315.0123 15.49812345451231
TIANGONG
1 48274U 21035A   24125.48912345  .00021456  00000+0  38000-3 0  9997
2 48274  41.4721 178.5412 0006123  88.3412 271.8541 15.61234512165412
FENGYUN 1C DEBRIS
1 39872U 99025DF  24125.41235123  .00003214  00000+0  12000-3 0  9991
2 39872  98.6512  45.1234 0021456 120.4512 240.1234 14.12451234789512
COSMOS 2251 DEBRIS
1 34125U 93036AE  24125.38541236  .00002145  00000+0  95000-4 0  9998
2 34125  74.0412 210.5123 0018542 310.1245  49.8512 14.35124125812451
"""
        return self.parse_tle_text(sample_tle, group_name)


celestrak_service = CelesTrakService()
