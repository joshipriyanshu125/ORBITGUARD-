from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import logger
from typing import Optional
import asyncio
import certifi

client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
is_mock_db: bool = False


class AsyncMockCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    async def to_list(self, length: Optional[int] = None):
        docs = list(self._cursor)
        if length is not None:
            return docs[:length]
        return docs

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class AsyncMockCollection:
    def __init__(self, collection):
        self._col = collection

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self._col.insert_many(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    async def create_index(self, *args, **kwargs):
        try:
            return self._col.create_index(*args, **kwargs)
        except Exception:
            return None

    async def create_indexes(self, *args, **kwargs):
        return None

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncMockCursor(self._col.find(*args, **kwargs))


class AsyncMockDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> AsyncMockCollection:
        return AsyncMockCollection(self._db[name])

    def __getattr__(self, name: str) -> AsyncMockCollection:
        return AsyncMockCollection(self._db[name])

    async def command(self, *args, **kwargs):
        return {"ok": 1.0}


class AsyncMockAdmin:
    async def command(self, *args, **kwargs):
        return {"ok": 1.0}


class AsyncMockClient:
    def __init__(self):
        import mongomock
        self._sync_client = mongomock.MongoClient()
        self.admin = AsyncMockAdmin()

    def __getitem__(self, name: str) -> AsyncMockDatabase:
        return AsyncMockDatabase(self._sync_client[name])

    def __getattr__(self, name: str) -> AsyncMockDatabase:
        return AsyncMockDatabase(self._sync_client[name])

    def close(self):
        pass


async def connect_to_mongo() -> AsyncIOMotorDatabase:
    """Connect to MongoDB Atlas or fallback to in-memory mongomock if offline/testing."""
    global client, db, is_mock_db
    
    import sys
    import os
    # Check if testing or explicit mock requested
    is_test_env = (
        'pytest' in sys.modules
        or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or os.environ.get("ENVIRONMENT") == "test"
        or settings.ENVIRONMENT == "test"
        or "mock" in settings.MONGODB_URI
    )
    if is_test_env:
        if client is not None and is_mock_db and db is not None:
            return db
        try:
            logger.info("Using in-memory MongoMock for test environment")
            client = AsyncMockClient()
            db = client[settings.MONGODB_DB_NAME]
            is_mock_db = True
            return db
        except Exception as e:
            logger.warning(f"MongoMock init failed: {e}. Trying standard client...")

    uri = settings.MONGODB_URI
    # Ensure standard Atlas connection params if using mongodb+srv
    if uri.startswith("mongodb+srv://") and "retryWrites" not in uri:
        delimiter = "&" if "?" in uri else "?"
        uri = f"{uri}{delimiter}retryWrites=true&w=majority"

    try:
        masked_host = uri.split("@")[-1] if "@" in uri else uri
        logger.info(f"Connecting to MongoDB Atlas at {masked_host}...")
        
        client_kwargs = {
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
        }
        
        # Use certifi for TLS validation on Windows
        if "mongodb+srv" in uri or "ssl=true" in uri.lower():
            client_kwargs["tlsCAFile"] = certifi.where()

        client = AsyncIOMotorClient(uri, **client_kwargs)
        
        # Test ping with a 10-second timeout for remote Atlas clusters
        await asyncio.wait_for(client.admin.command('ping'), timeout=10.0)
        db = client[settings.MONGODB_DB_NAME]
        is_mock_db = False
        logger.info(f"Successfully connected to live MongoDB database '{settings.MONGODB_DB_NAME}'")
        await create_indexes(db)
        return db
        
    except Exception as exc:
        logger.warning(f"Could not connect to external MongoDB ({repr(exc)}). Falling back to in-memory mock client.")
        try:
            client = AsyncMockClient()
            db = client[settings.MONGODB_DB_NAME]
            is_mock_db = True
            logger.info("Fallback in-memory MongoMock initialized successfully.")
            return db
        except Exception as inner_exc:
            logger.error(f"Failed to initialize fallback mock client: {inner_exc}")
            raise exc


async def close_mongo_connection():
    global client
    if client and not is_mock_db:
        client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    global db
    if db is None:
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo() has been called.")
    return db


async def create_indexes(database: AsyncIOMotorDatabase):
    """Ensure all required performance and unique indexes exist in collections."""
    try:
        # 1. satellites
        await database.satellites.create_index("norad_id", unique=True)
        await database.satellites.create_index("object_type")
        await database.satellites.create_index([("perigee_km", 1), ("apogee_km", 1)])
        await database.satellites.create_index("epoch")
        
        # 2. tle_history
        await database.tle_history.create_index([("norad_id", 1), ("epoch", -1)])
        
        # 3. conjunctions
        await database.conjunctions.create_index("event_id", unique=True)
        await database.conjunctions.create_index([("primary_norad_id", 1), ("tca", 1)])
        await database.conjunctions.create_index([("risk_level", 1), ("status", 1)])
        
        # 4. maneuver_proposals
        await database.maneuver_proposals.create_index("conjunction_id")
        await database.maneuver_proposals.create_index("approval_status")
        
        # 5. agent_memory
        await database.agent_memory.create_index("session_id")
        await database.agent_memory.create_index("target_norad_id")
        
        logger.info("MongoDB indexes verified and ensured.")
    except Exception as e:
        logger.warning(f"Non-fatal error creating indexes: {e}")
