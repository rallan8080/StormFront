"""Shared pytest fixtures.

These tests assume a MongoDB instance is reachable at MONGO_URL. For CI /
local dev that means either a real Mongo or ``mongomock-motor`` (out of
scope for the scaffold).

For now: start Mongo via docker compose, then run pytest.
"""

import asyncio
import contextlib
import os
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Use a per-test-run database name so tests do not collide with dev data.
os.environ.setdefault("MONGO_DB", f"stormfront_test_{uuid.uuid4().hex[:8]}")
os.environ.setdefault("JWT_SECRET", "test-only-secret-please-change")


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.config import get_settings
    from app.db import database
    from app.main import app

    get_settings.cache_clear()

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac,
        app.router.lifespan_context(app),
    ):
        try:
            yield ac
        finally:
            # Drop the test DB *before* leaving the lifespan context —
            # lifespan_db's finally block calls database.client.close(),
            # after which the motor client raises InvalidOperation.
            if database.client is not None and database.db is not None:
                await database.client.drop_database(database.db.name)


@pytest.fixture
def sync_client() -> Iterator:
    """Synchronous TestClient for tests that need WebSocket support.

    Starlette's TestClient handles lifespan internally (so the world gets
    seeded), runs the app in a background thread, and provides a sync
    ``websocket_connect`` context manager — httpx.AsyncClient has no WS
    support, hence the separate fixture.

    Teardown drops the test DB with a fresh motor client in a fresh event
    loop. The lifespan-owned motor client is bound to TestClient's loop,
    which is already closed by this point, so we cannot reuse it.
    """
    from fastapi.testclient import TestClient
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()

    with TestClient(app) as tc:
        yield tc

    settings = get_settings()

    async def _drop() -> None:
        tmp = AsyncIOMotorClient(settings.mongo_url)
        await tmp.drop_database(settings.mongo_db)

    # Best-effort cleanup; an unreachable Mongo shouldn't fail an otherwise-passing test.
    with contextlib.suppress(Exception):
        asyncio.run(_drop())
