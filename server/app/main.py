from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.broker import get_broker
from app.config import get_settings
from app.db import database, lifespan_db
from app.npc_scheduler import NpcScheduler
from app.routers import auth, characters, health, me, websocket
from app.world import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with lifespan_db():
        assert database.db is not None
        await seed_if_empty(database.db)
        scheduler = NpcScheduler(database.db, get_broker())
        await scheduler.start()
        # Stash on app.state so tests can grab it via the test client app.
        app.state.npc_scheduler = scheduler
        try:
            yield
        finally:
            await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="StormFront",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(characters.router)
    app.include_router(websocket.router)
    return app


app = create_app()
