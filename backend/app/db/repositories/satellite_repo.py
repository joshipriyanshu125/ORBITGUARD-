from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.db.mongodb import get_database
from app.models.satellite import SatelliteCreate, SatelliteInDB, TLEHistoryRecord
from app.core.logging import logger


class SatelliteRepository:
    """Async repository for satellite catalog and TLE history storage."""

    @property
    def collection(self):
        return get_database().satellites

    @property
    def history_collection(self):
        return get_database().tle_history

    async def upsert_satellite(self, satellite: SatelliteCreate) -> Dict[str, Any]:
        """Insert or update satellite in catalog, and append to TLE history."""
        doc = satellite.model_dump()
        doc["updated_at"] = datetime.now(timezone.utc)
        
        # 1. Update active catalog
        await self.collection.update_one(
            {"norad_id": satellite.norad_id},
            {"$set": doc},
            upsert=True
        )
        
        # 2. Archive to TLE history if not already present for this exact epoch
        history_record = TLEHistoryRecord(
            norad_id=satellite.norad_id,
            epoch=satellite.epoch,
            tle_line1=satellite.tle_line1,
            tle_line2=satellite.tle_line2,
            mean_motion=satellite.mean_motion_rev_day or 0.0,
            eccentricity=satellite.eccentricity,
            inclination=satellite.inclination_deg,
            bstar=satellite.bstar or 0.0,
            apogee_km=satellite.apogee_km,
            perigee_km=satellite.perigee_km,
        )
        
        await self.history_collection.update_one(
            {"norad_id": satellite.norad_id, "epoch": satellite.epoch},
            {"$setOnInsert": history_record.model_dump()},
            upsert=True
        )
        
        return doc

    async def get_by_norad_id(self, norad_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve single satellite by NORAD ID."""
        doc = await self.collection.find_one({"norad_id": norad_id})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def list_satellites(
        self,
        object_type: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List satellites with filtering and pagination."""
        query: Dict[str, Any] = {}
        if object_type:
            query["object_type"] = object_type.upper()
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"norad_id": int(search) if search.isdigit() else -1}
            ]
        
        cursor = self.collection.find(query).sort("norad_id", 1).skip(skip).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def count_satellites(self, object_type: Optional[str] = None) -> int:
        """Count total satellites in catalog."""
        query = {"object_type": object_type.upper()} if object_type else {}
        return await self.collection.count_documents(query)

    async def get_history(self, norad_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chronological TLE history for a satellite."""
        cursor = self.history_collection.find({"norad_id": norad_id}).sort("epoch", -1).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def find_orbital_shell_candidates(
        self,
        min_perigee: float,
        max_apogee: float,
        exclude_norad_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Find satellites whose altitude range overlaps with [min_perigee, max_apogee]."""
        query: Dict[str, Any] = {
            "perigee_km": {"$lte": max_apogee},
            "apogee_km": {"$gte": min_perigee}
        }
        if exclude_norad_id:
            query["norad_id"] = {"$ne": exclude_norad_id}
            
        cursor = self.collection.find(query)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results


satellite_repo = SatelliteRepository()
