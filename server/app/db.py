from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings


class Database:
    """Lightweight handle to the Motor client + active database.

    Held on app.state so request-scoped dependencies can pull from it.
    """

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


database = Database()


@asynccontextmanager
async def lifespan_db() -> AsyncIterator[None]:
    settings = get_settings()
    database.client = AsyncIOMotorClient(settings.mongo_url)
    database.db = database.client[settings.mongo_db]
    await _ensure_indexes(database.db)
    try:
        yield
    finally:
        if database.client is not None:
            database.client.close()


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["accounts"].create_index("email", unique=True)
    await db["players"].create_index(
        "name",
        unique=True,
        collation={"locale": "en", "strength": 2},  # case-insensitive uniqueness
    )
    await db["players"].create_index("accountId")
    await db["rooms"].create_index("id", unique=True)
    await db["items"].create_index("id", unique=True)
    await db["npcs"].create_index("id", unique=True)


def get_db() -> AsyncIOMotorDatabase:
    if database.db is None:
        raise RuntimeError("Database not initialized; call lifespan_db first.")
    return database.db
