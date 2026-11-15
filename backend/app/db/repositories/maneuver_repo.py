from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from app.db.mongodb import get_database
from app.models.maneuver import ManeuverProposalInDB, ApprovalStatus
from app.core.logging import logger


class ManeuverRepository:
    """Async repository for collision avoidance maneuver proposals and human approvals."""

    @property
    def collection(self):
        return get_database().maneuver_proposals

    async def create_proposal(self, proposal: ManeuverProposalInDB) -> Dict[str, Any]:
        """Create new pending maneuver proposal."""
        doc = proposal.model_dump(exclude={"id"})
        doc["created_at"] = datetime.now(timezone.utc)
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    async def get_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve proposal by ID."""
        try:
            oid = ObjectId(proposal_id)
            query = {"_id": oid}
        except Exception:
            query = {"conjunction_id": proposal_id}

        doc = await self.collection.find_one(query)
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def list_proposals(
        self,
        approval_status: Optional[str] = None,
        target_norad_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List maneuver proposals with filtering."""
        query: Dict[str, Any] = {}
        if approval_status:
            query["approval_status"] = approval_status.upper()
        if target_norad_id:
            query["target_norad_id"] = target_norad_id

        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def record_decision(
        self,
        proposal_id: str,
        operator_name: str,
        decision: ApprovalStatus,
        notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Record Human-In-The-Loop approval or rejection decision.
        Enforces operator identity check.
        """
        try:
            query = {"_id": ObjectId(proposal_id)}
        except Exception:
            query = {"conjunction_id": proposal_id}

        now = datetime.now(timezone.utc)
        update_data = {
            "approval_status": decision.value,
            "reviewed_by": operator_name,
            "reviewed_at": now,
            "review_notes": notes
        }

        result = await self.collection.update_one(query, {"$set": update_data})
        if result.matched_count == 0:
            return None

        updated = await self.collection.find_one(query)
        if updated and "_id" in updated:
            updated["_id"] = str(updated["_id"])
        logger.info(f"Maneuver proposal {proposal_id} transitioned to {decision.value} by {operator_name}")
        return updated


maneuver_repo = ManeuverRepository()
