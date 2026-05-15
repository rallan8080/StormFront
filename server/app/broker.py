"""In-process pub/sub broker for cross-WebSocket fan-out.

Tracks which player is connected on which socket and which room each player
currently occupies, so server-side events (chat, presence, NPC dialogue) can
be routed to the right subset of sockets.

Single-process only. Multi-worker deployments need a different implementation
that fans out via Redis pub/sub (or NATS, etc.); the redis service already in
docker-compose.yml is reserved for that future change.

Reconnect policy: newer wins. A second connect for an already-connected
player closes the prior socket. The displaced socket's own ``disconnect``
call then no-ops because the registry entry no longer points at it.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Broker:
    def __init__(self) -> None:
        self._players: dict[str, WebSocket] = {}
        self._player_rooms: dict[str, str] = {}
        self._room_members: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, player_id: str, ws: WebSocket, room_id: str) -> None:
        displaced: WebSocket | None = None
        async with self._lock:
            existing = self._players.get(player_id)
            if existing is not None and existing is not ws:
                displaced = existing
            self._players[player_id] = ws

            prev_room = self._player_rooms.get(player_id)
            if prev_room is not None and prev_room != room_id:
                self._room_members[prev_room].discard(player_id)
                if not self._room_members[prev_room]:
                    del self._room_members[prev_room]
            self._player_rooms[player_id] = room_id
            self._room_members[room_id].add(player_id)

        if displaced is not None:
            try:
                await displaced.close(code=1000, reason="Replaced by new connection")
            except Exception:
                logger.debug("Failed to close displaced socket", exc_info=True)

    async def disconnect(self, player_id: str, ws: WebSocket) -> None:
        """Remove the player's socket only if it's still the registered one.

        If a newer ``connect`` already displaced this socket, this is a no-op
        so the newer connection's room membership stays intact.
        """
        async with self._lock:
            if self._players.get(player_id) is not ws:
                return
            self._players.pop(player_id, None)
            room = self._player_rooms.pop(player_id, None)
            if room is not None:
                self._room_members[room].discard(player_id)
                if not self._room_members[room]:
                    del self._room_members[room]

    def connected_player_ids(self) -> list[str]:
        """Snapshot of currently connected player IDs.

        Sync because dict.keys() is atomic enough under the GIL for a
        read-only snapshot; callers shouldn't hold this list across
        awaits if they care about exact-moment accuracy.
        """
        return list(self._players.keys())

    async def move(self, player_id: str, new_room_id: str) -> None:
        async with self._lock:
            old_room = self._player_rooms.get(player_id)
            if old_room == new_room_id:
                return
            if old_room is not None:
                self._room_members[old_room].discard(player_id)
                if not self._room_members[old_room]:
                    del self._room_members[old_room]
            self._player_rooms[player_id] = new_room_id
            self._room_members[new_room_id].add(player_id)

    async def publish_to_room(
        self,
        room_id: str,
        payload: Any,
        *,
        exclude_player_id: str | None = None,
    ) -> None:
        """Send ``payload`` to every connected player in ``room_id``.

        ``exclude_player_id`` is typically the actor whose action triggered the
        event (they get their own confirmation elsewhere — e.g. the mover
        receives ``server.room.entered`` while observers receive
        ``server.player.arrived``).
        """
        async with self._lock:
            members = set(self._room_members.get(room_id, set()))
            if exclude_player_id is not None:
                members.discard(exclude_player_id)
            sockets = [self._players[mid] for mid in members if mid in self._players]

        await self._fan_out(sockets, payload)

    async def publish_to_all(self, payload: Any) -> None:
        async with self._lock:
            sockets = list(self._players.values())
        await self._fan_out(sockets, payload)

    @staticmethod
    async def _fan_out(sockets: list[WebSocket], payload: Any) -> None:
        if not sockets:
            return
        text = payload.model_dump_json(by_alias=True)
        await asyncio.gather(
            *(Broker._safe_send(ws, text) for ws in sockets),
            return_exceptions=True,
        )

    @staticmethod
    async def _safe_send(ws: WebSocket, text: str) -> None:
        try:
            await ws.send_text(text)
        except Exception:
            logger.debug("Broker fan-out send failed; socket likely closed.", exc_info=True)


_broker: Broker | None = None


def get_broker() -> Broker:
    """Return the process-wide broker singleton."""
    global _broker
    if _broker is None:
        _broker = Broker()
    return _broker
