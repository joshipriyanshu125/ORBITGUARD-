from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.db.mongodb import get_database
from app.models.conjunction import ConjunctionBase, ConjunctionInDB, RiskLevel, ConjunctionStatus
from app.core.logging import logger


class ConjunctionRepository:
    """Async repository for screened close encounters and collision assessments."""

    @property
    def collection(self):
        return get_database().conjunctions

    async def upsert_conjunction(self, conjunction: ConjunctionBase) -> Dict[str, Any]:
        """Insert or update a conjunction event by its deterministic event_id."""
        doc = conjunction.model_dump()
        doc["updated_at"] = datetime.now(timezone.utc)
        
        await self.collection.update_one(
            {"event_id": conjunction.event_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        return doc

    async def get_by_event_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conjunction event by event_id."""
        doc = await self.collection.find_one({"event_id": event_id})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def list_conjunctions(
        self,
        primary_norad_id: Optional[int] = None,
        secondary_norad_id: Optional[int] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        max_miss_distance_km: Optional[float] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List conjunction events with multi-criteria filtering and pagination."""
        query: Dict[str, Any] = {}
        if primary_norad_id:
            query["primary_norad_id"] = primary_norad_id
        if secondary_norad_id:
            query["secondary_norad_id"] = secondary_norad_id
        if risk_level:
            query["risk_level"] = risk_level.upper()
        if status:
            query["status"] = status.upper()
        if max_miss_distance_km is not None:
            query["miss_distance_km"] = {"$lte": max_miss_distance_km}

        cursor = self.collection.find(query).sort("tca", 1).skip(skip).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def count_conjunctions(
        self,
        primary_norad_id: Optional[int] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count total conjunction events matching query."""
        query: Dict[str, Any] = {}
        if primary_norad_id:
            query["primary_norad_id"] = primary_norad_id
        if risk_level:
            query["risk_level"] = risk_level.upper()
        if status:
            query["status"] = status.upper()
        return await self.collection.count_documents(query)

    async def update_status(
        self,
        event_id: str,
        status: ConjunctionStatus,
        notes: Optional[str] = None
    ) -> bool:
        """Update the operational status of a conjunction (e.g. AWAITING_APPROVAL -> APPROVED)."""
        update_data: Dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc)
        }
        if notes:
            update_data["analysis_summary"] = notes

        result = await self.collection.update_one(
            {"event_id": event_id},
            {"$set": update_data}
        )
        return result.modified_count > 0


conjunction_repo = ConjunctionRepository()
