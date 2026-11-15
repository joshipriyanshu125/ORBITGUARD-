import pytest
import os
import asyncio

# Force test environment before loading settings
os.environ["ENVIRONMENT"] = "test"
os.environ["MONGODB_URI"] = "mongodb://mock:27017"
os.environ["MONGODB_DB_NAME"] = "test_orbitguard_db"

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_db():
    await connect_to_mongo()
    yield
    await close_mongo_connection()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
