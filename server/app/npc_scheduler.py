"""Periodic NPC chatter broadcaster.

One asyncio task per room with NPCs. Each task sleeps for a random
interval, then picks a random NPC + random dialogue line from that
room's roster and publishes a ``server.npc.spoke`` event via the broker.

NPC rosters are loaded once at ``start()`` so the loop body doesn't hit
the DB on every tick. If you mutate the seed at runtime, restart the
process to pick up the new NPC set.

The broker's room-scoped publish is already a no-op when nobody is
listening, so empty rooms cost nothing beyond the timer itself.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.broker import Broker
from app.models import ServerNpcSpoke

logger = logging.getLogger(__name__)

# Defaults tuned for a portfolio demo — frequent enough that an NPC speaks
# within a minute of arrival, sparse enough that it doesn't drown chat.
DEFAULT_MIN_INTERVAL_SEC = 20.0
DEFAULT_MAX_INTERVAL_SEC = 45.0


class NpcScheduler:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        broker: Broker,
        *,
        min_interval: float = DEFAULT_MIN_INTERVAL_SEC,
        max_interval: float = DEFAULT_MAX_INTERVAL_SEC,
    ) -> None:
        if min_interval <= 0 or max_interval < min_interval:
            raise ValueError("require 0 < min_interval <= max_interval")
        self._db = db
        self._broker = broker
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        """Load NPC rosters from the DB and spawn one chatter loop per room."""
        rosters = await self._load_rosters()
        for room_id, npcs in rosters.items():
            task = asyncio.create_task(
                self._chatter_loop(room_id, npcs),
                name=f"npc-chatter:{room_id}",
            )
            self._tasks.append(task)
        logger.info("npc scheduler started: %d room(s)", len(self._tasks))

    async def stop(self) -> None:
        """Cancel all chatter tasks and wait for them to unwind."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("npc scheduler stopped")

    async def fire_once(self, room_id: str, npcs: list[dict[str, Any]]) -> None:
        """Pick one random NPC + line and publish to the room.

        Public so tests can drive a tick deterministically without waiting
        for the random sleep in ``_chatter_loop``.
        """
        speakable = [n for n in npcs if n.get("dialogue")]
        if not speakable:
            return
        npc = random.choice(speakable)
        line = random.choice(npc["dialogue"])
        await self._broker.publish_to_room(
            room_id,
            ServerNpcSpoke(
                data=ServerNpcSpoke.Data(npcName=npc["name"], message=line),
            ),
        )

    async def _load_rosters(self) -> dict[str, list[dict[str, Any]]]:
        """Return {room_id: [npc_doc, ...]} for every room with at least one
        NPC that has non-empty dialogue. Rooms without speakable NPCs are
        omitted so we don't spawn tasks that can never speak."""
        rosters: dict[str, list[dict[str, Any]]] = {}
        async for room in self._db["rooms"].find({"npcIds": {"$ne": []}}):
            npc_ids = room.get("npcIds") or []
            if not npc_ids:
                continue
            npcs = [
                doc
                async for doc in self._db["npcs"].find({"_id": {"$in": npc_ids}})
                if doc.get("dialogue")
            ]
            if npcs:
                rosters[room["_id"]] = npcs
        return rosters

    async def _chatter_loop(self, room_id: str, npcs: list[dict[str, Any]]) -> None:
        while True:
            try:
                interval = random.uniform(self._min_interval, self._max_interval)
                await asyncio.sleep(interval)
                await self.fire_once(room_id, npcs)
            except asyncio.CancelledError:
                return
            except Exception:
                # Don't let a single failed tick kill the loop. Log + continue.
                logger.exception("npc chatter tick failed for room=%s", room_id)
