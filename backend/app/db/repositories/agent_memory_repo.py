from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.db.mongodb import get_database
from app.models.agent import AgentInvestigationMemory, AgentStepTrace
from app.core.logging import logger


class AgentMemoryRepository:
    """Async repository for persistent agent investigation memory and execution traces."""

    @property
    def collection(self):
        return get_database().agent_memory

    async def save_memory(self, memory: AgentInvestigationMemory) -> Dict[str, Any]:
        """Save or update agent session memory."""
        doc = memory.model_dump(exclude={"created_at"})
        doc["updated_at"] = datetime.now(timezone.utc)

        await self.collection.update_one(
            {"session_id": memory.session_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        return doc

    async def get_memory(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve memory by session_id."""
        doc = await self.collection.find_one({"session_id": session_id})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def list_memories(
        self,
        target_norad_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List past investigation sessions chronologically."""
        query: Dict[str, Any] = {}
        if target_norad_id:
            query["target_norad_id"] = target_norad_id

        cursor = self.collection.find(query).sort("updated_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def append_trace(self, session_id: str, trace_step: AgentStepTrace):
        """Append a step trace to persistent agent memory."""
        await self.collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"agent_trace": trace_step.model_dump()},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )


agent_memory_repo = AgentMemoryRepository()
