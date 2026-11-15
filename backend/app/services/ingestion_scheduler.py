import asyncio
import os
import sys
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.celestrak import celestrak_service
from app.db.repositories.satellite_repo import satellite_repo


class IngestionScheduler:
    """
    Automated Background Ingestion Service for live CelesTrak ephemeris.
    Runs an immediate initial sync in the background on startup,
    and then periodically refreshes the catalog every `interval_hours`.
    """

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    @property
    def groups(self) -> List[str]:
        return settings.AUTO_SYNC_GROUPS

    @property
    def interval_hours(self) -> float:
        return settings.AUTO_SYNC_INTERVAL_HOURS

    async def run_sync_cycle(self) -> int:
        """Fetch live orbital elements and synchronize with MongoDB Atlas."""
        logger.info(f"Starting automated live CelesTrak catalog synchronization for groups: {self.groups}...")
        total_synced = 0
        batch_size = 40
        for group in self.groups:
            try:
                records = await celestrak_service.fetch_group(group_name=group)
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    await asyncio.gather(*(satellite_repo.upsert_satellite(rec) for rec in batch))
                total_synced += len(records)
                logger.info(f"Auto-ingested {len(records)} orbital objects for group '{group}'.")
            except Exception as e:
                logger.error(f"Error during automated ingestion for group '{group}': {e}")

        catalog_count = await satellite_repo.count_satellites()
        logger.info(f"Automated ingestion cycle completed. Total synced: {total_synced}. Current catalog size: {catalog_count}.")
        return total_synced

    async def _loop(self):
        try:
            # 1. Immediate initial sync in background
            await self.run_sync_cycle()
        except Exception as e:
            logger.warning(f"Initial automated sync encountered an error: {e}")

        # 2. Periodic sync
        while self._is_running:
            try:
                await asyncio.sleep(self.interval_hours * 3600)
                if self._is_running:
                    await self.run_sync_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in automated ingestion loop: {e}")
                await asyncio.sleep(60)

    def start(self):
        if not settings.AUTO_SYNC_ENABLED:
            logger.info("Automated ingestion scheduler is disabled by configuration (AUTO_SYNC_ENABLED=False).")
            return

        is_test = (
            os.environ.get("ENVIRONMENT") == "test"
            or "pytest" in sys.modules
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        )
        if is_test:
            logger.info("Automated ingestion scheduler disabled in test environment.")
            return

        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._loop())
            logger.info(f"Automated CelesTrak ingestion scheduler started (Interval: {self.interval_hours}h).")

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._task and not self._task.done():
                self._task.cancel()
            logger.info("Automated CelesTrak ingestion scheduler stopped.")


ingestion_scheduler = IngestionScheduler()
