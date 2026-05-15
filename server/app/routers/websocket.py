"""WebSocket entry point for the game session.

Scope:
  - Accept connection, authenticate via ?token=<jwt> query string
  - Send server.welcome with the player's profile + current RoomView
  - Handle ping / inventory / who / look / look <target> / move / take / drop /
    say / shout / quit
  - Fan out server.player.arrived / departed on move, server.item.taken /
    dropped on take/drop, plus chat events via the in-process broker
    (see app.broker)
  - Clean disconnect on close (including client-initiated quit), with
    broker cleanup in a finally block

Single-process only: ``app.broker`` is in-memory. Multi-worker deployments
need a redis-backed broker so events fan out across processes. The redis
service in docker-compose.yml is reserved for that change.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError

from app.broker import get_broker
from app.db import get_db
from app.models import (
    ClientDrop,
    ClientInventory,
    ClientLook,
    ClientMove,
    ClientPing,
    ClientQuit,
    ClientSay,
    ClientShout,
    ClientTake,
    ClientWho,
    Item,
    Player,
    RoomView,
    ServerChatSay,
    ServerChatShout,
    ServerError,
    ServerExamineResult,
    ServerInventoryUpdated,
    ServerItemDropped,
    ServerItemTaken,
    ServerPlayerArrived,
    ServerPlayerDeparted,
    ServerPong,
    ServerRoomEntered,
    ServerWelcome,
    ServerWhoList,
)
from app.security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()


# Observer's-viewpoint inverse: if a mover walks `north`, observers in the
# destination room see them arrive from the `south`.
_OPPOSITE_DIRECTION = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
    "up": "down", "down": "up",
}


# ---- protocol helpers ----

async def _send(ws: WebSocket, msg: Any) -> None:
    """Send a pydantic message model as JSON using its aliased field names."""
    await ws.send_text(msg.model_dump_json(by_alias=True))


async def _send_error(ws: WebSocket, code: str, message: str) -> None:
    await _send(ws, ServerError(data=ServerError.Data(code=code, message=message)))


# ---- domain helpers ----

async def _load_player(db: AsyncIOMotorDatabase, account_id: str) -> Player | None:
    doc = await db["players"].find_one({"accountId": account_id})
    if doc is None:
        return None
    return Player(
        id=doc["_id"],
        accountId=doc["accountId"],
        name=doc["name"],
        description=doc.get("description"),
        currentRoomId=doc["currentRoomId"],
        inventoryItemIds=doc.get("inventoryItemIds", []),
        createdAt=doc["createdAt"],
        lastSeenAt=doc.get("lastSeenAt"),
    )


async def _room_view(db: AsyncIOMotorDatabase, player: Player) -> RoomView | None:
    room = await db["rooms"].find_one({"_id": player.current_room_id})
    if room is None:
        return None

    item_ids = room.get("itemIds", []) or []
    npc_ids = room.get("npcIds", []) or []

    items_cursor = db["items"].find({"_id": {"$in": item_ids}}) if item_ids else None
    npcs_cursor = db["npcs"].find({"_id": {"$in": npc_ids}}) if npc_ids else None

    items = [Item(**d) async for d in items_cursor] if items_cursor is not None else []
    npcs = [n async for n in npcs_cursor] if npcs_cursor is not None else []

    # Other players in the room (excluding self).
    others_cursor = db["players"].find(
        {"currentRoomId": player.current_room_id, "_id": {"$ne": player.id}},
        projection={"name": 1},
    )
    others = [d["name"] async for d in others_cursor]

    return RoomView(
        id=room["_id"],
        name=room["name"],
        description=room["description"],
        exits=room.get("exits", []),
        items=items,
        players=others,
        npcs=[
            {  # type: ignore[list-item]
                "id": n["_id"],
                "name": n["name"],
                "shortDescription": n["shortDescription"],
                "longDescription": n.get("longDescription"),
                "homeRoomId": n["homeRoomId"],
                "dialogue": n.get("dialogue", []),
            }
            for n in npcs
        ],
    )


async def _handle_examine(
    ws: WebSocket, db: AsyncIOMotorDatabase, player: Player, target: str
) -> None:
    """Resolve a `look <target>` against the current room.

    Match order: self -> items in room -> NPCs in room -> other players in room.
    Matching is case-insensitive on full name; partial / prefix matching is a
    deliberate non-goal for the scaffold.
    """
    target_lower = target.lower()

    if target_lower == player.name.lower():
        await _send(
            ws,
            ServerExamineResult(
                data=ServerExamineResult.Data(
                    name=player.name,
                    kind="player",
                    description=player.description or "An unremarkable adventurer.",
                )
            ),
        )
        return

    room = await db["rooms"].find_one({"_id": player.current_room_id})
    if room is None:
        await _send_error(ws, "ROOM_MISSING", "Your current room no longer exists")
        return

    item_ids = room.get("itemIds", []) or []
    if item_ids:
        async for doc in db["items"].find({"_id": {"$in": item_ids}}):
            if doc["name"].lower() == target_lower:
                description = doc.get("longDescription") or doc["shortDescription"]
                await _send(
                    ws,
                    ServerExamineResult(
                        data=ServerExamineResult.Data(
                            name=doc["name"], kind="item", description=description,
                        )
                    ),
                )
                return

    npc_ids = room.get("npcIds", []) or []
    if npc_ids:
        async for doc in db["npcs"].find({"_id": {"$in": npc_ids}}):
            if doc["name"].lower() == target_lower:
                description = doc.get("longDescription") or doc["shortDescription"]
                await _send(
                    ws,
                    ServerExamineResult(
                        data=ServerExamineResult.Data(
                            name=doc["name"], kind="npc", description=description,
                        )
                    ),
                )
                return

    others_cursor = db["players"].find(
        {"currentRoomId": player.current_room_id, "_id": {"$ne": player.id}}
    )
    async for doc in others_cursor:
        if doc["name"].lower() == target_lower:
            description = doc.get("description") or "An unremarkable adventurer."
            await _send(
                ws,
                ServerExamineResult(
                    data=ServerExamineResult.Data(
                        name=doc["name"], kind="player", description=description,
                    )
                ),
            )
            return

    await _send_error(ws, "LOOK_NOT_FOUND", f"You see no '{target}' here.")


async def _handle_move(
    ws: WebSocket, db: AsyncIOMotorDatabase, player: Player, direction: str
) -> Player:
    """Move the player through an exit in the current room.

    Returns the updated Player on success, or the original Player on failure
    (an appropriate server.error is sent first).
    """
    room = await db["rooms"].find_one({"_id": player.current_room_id})
    if room is None:
        await _send_error(ws, "ROOM_MISSING", "Your current room no longer exists")
        return player

    exits = room.get("exits", []) or []
    matching = next((e for e in exits if e.get("direction") == direction), None)
    if matching is None:
        await _send_error(ws, "NO_EXIT", f"There is no exit {direction} from here.")
        return player

    if matching.get("locked", False):
        key_id = matching.get("keyItemId")
        if not key_id or key_id not in player.inventory_item_ids:
            await _send_error(ws, "LOCKED", f"The way {direction} is locked.")
            return player

    dest_room_id = matching["toRoomId"]
    dest_doc = await db["rooms"].find_one({"_id": dest_room_id})
    if dest_doc is None:
        await _send_error(
            ws, "ROOM_MISSING", f"Destination room '{dest_room_id}' does not exist",
        )
        return player

    now = datetime.now(UTC)
    await db["players"].update_one(
        {"_id": player.id},
        {"$set": {"currentRoomId": dest_room_id, "lastSeenAt": now}},
    )

    updated = player.model_copy(
        update={"current_room_id": dest_room_id, "last_seen_at": now}
    )

    view = await _room_view(db, updated)
    if view is None:
        await _send_error(ws, "ROOM_MISSING", "Destination room view could not be built")
        return updated

    await _send(ws, ServerRoomEntered(data=view))

    broker = get_broker()
    old_room_id = player.current_room_id
    await broker.move(player.id, dest_room_id)
    await broker.publish_to_room(
        old_room_id,
        ServerPlayerDeparted(
            data=ServerPlayerDeparted.Data(
                playerName=player.name, toDirection=direction,
            )
        ),
    )
    await broker.publish_to_room(
        dest_room_id,
        ServerPlayerArrived(
            data=ServerPlayerArrived.Data(
                playerName=player.name,
                fromDirection=_OPPOSITE_DIRECTION.get(direction, direction),
            )
        ),
        exclude_player_id=player.id,
    )
    return updated


async def _send_inventory(
    ws: WebSocket, db: AsyncIOMotorDatabase, inventory_ids: list[str]
) -> None:
    items = (
        [Item(**d) async for d in db["items"].find({"_id": {"$in": inventory_ids}})]
        if inventory_ids else []
    )
    await _send(ws, ServerInventoryUpdated(data=ServerInventoryUpdated.Data(items=items)))


async def _handle_take(
    ws: WebSocket, db: AsyncIOMotorDatabase, player: Player, target: str
) -> Player:
    """Pick up a named item from the current room into the player's inventory.

    Match: case-insensitive on full item name; first hit wins. Items with
    `takeable=false` (fixtures, scenery) are rejected. Concurrent takes are
    guarded by a conditional `$pull` against the room document.
    """
    target_lower = target.strip().lower()
    if not target_lower:
        await _send_error(ws, "BAD_PAYLOAD", "take target cannot be empty")
        return player

    room = await db["rooms"].find_one({"_id": player.current_room_id})
    if room is None:
        await _send_error(ws, "ROOM_MISSING", "Your current room no longer exists")
        return player

    item_ids = room.get("itemIds", []) or []
    matched: dict | None = None
    if item_ids:
        async for doc in db["items"].find({"_id": {"$in": item_ids}}):
            if doc["name"].lower() == target_lower:
                matched = doc
                break

    if matched is None:
        await _send_error(ws, "TAKE_NOT_FOUND", f"You see no '{target}' here.")
        return player

    if not matched.get("takeable", True):
        await _send_error(ws, "NOT_TAKEABLE", f"You cannot take the {matched['name']}.")
        return player

    item_id = matched["_id"]
    # Conditional pull: only succeeds if the item is still in this room.
    pull_result = await db["rooms"].update_one(
        {"_id": player.current_room_id, "itemIds": item_id},
        {"$pull": {"itemIds": item_id}},
    )
    if pull_result.modified_count == 0:
        await _send_error(
            ws, "TAKE_NOT_FOUND", f"The {matched['name']} is no longer here.",
        )
        return player

    now = datetime.now(UTC)
    await db["players"].update_one(
        {"_id": player.id},
        {"$push": {"inventoryItemIds": item_id}, "$set": {"lastSeenAt": now}},
    )

    new_inventory = [*player.inventory_item_ids, item_id]
    updated = player.model_copy(
        update={"inventory_item_ids": new_inventory, "last_seen_at": now}
    )

    await _send_inventory(ws, db, new_inventory)

    broker = get_broker()
    await broker.publish_to_room(
        player.current_room_id,
        ServerItemTaken(
            data=ServerItemTaken.Data(playerName=player.name, itemName=matched["name"])
        ),
        exclude_player_id=player.id,
    )
    return updated


async def _handle_drop(
    ws: WebSocket, db: AsyncIOMotorDatabase, player: Player, target: str
) -> Player:
    """Drop a named item from inventory into the current room.

    Match: case-insensitive on full item name. Concurrent drops are guarded
    by a conditional `$pull` against the player document so the item cannot
    be duplicated if two drop calls race.
    """
    target_lower = target.strip().lower()
    if not target_lower:
        await _send_error(ws, "BAD_PAYLOAD", "drop target cannot be empty")
        return player

    if not player.inventory_item_ids:
        await _send_error(ws, "DROP_NOT_FOUND", f"You are not carrying '{target}'.")
        return player

    matched: dict | None = None
    async for doc in db["items"].find({"_id": {"$in": player.inventory_item_ids}}):
        if doc["name"].lower() == target_lower:
            matched = doc
            break

    if matched is None:
        await _send_error(ws, "DROP_NOT_FOUND", f"You are not carrying '{target}'.")
        return player

    item_id = matched["_id"]
    now = datetime.now(UTC)
    pull_result = await db["players"].update_one(
        {"_id": player.id, "inventoryItemIds": item_id},
        {"$pull": {"inventoryItemIds": item_id}, "$set": {"lastSeenAt": now}},
    )
    if pull_result.modified_count == 0:
        await _send_error(
            ws, "DROP_NOT_FOUND", f"You no longer have the {matched['name']}.",
        )
        return player

    await db["rooms"].update_one(
        {"_id": player.current_room_id},
        {"$push": {"itemIds": item_id}},
    )

    new_inventory = [iid for iid in player.inventory_item_ids if iid != item_id]
    updated = player.model_copy(
        update={"inventory_item_ids": new_inventory, "last_seen_at": now}
    )

    await _send_inventory(ws, db, new_inventory)

    broker = get_broker()
    await broker.publish_to_room(
        player.current_room_id,
        ServerItemDropped(
            data=ServerItemDropped.Data(playerName=player.name, itemName=matched["name"])
        ),
        exclude_player_id=player.id,
    )
    return updated


async def _handle_say(ws: WebSocket, player: Player, message: str) -> Player:
    """Broadcast a room-scoped chat message. The sender is included in the fan-out
    so they see their own line — the simplest way to confirm send."""
    broker = get_broker()
    await broker.publish_to_room(
        player.current_room_id,
        ServerChatSay(data=ServerChatSay.Data(from_=player.name, message=message)),
    )
    return player


async def _handle_shout(ws: WebSocket, player: Player, message: str) -> Player:
    """Broadcast a globally visible chat message to every connected player."""
    broker = get_broker()
    await broker.publish_to_all(
        ServerChatShout(data=ServerChatShout.Data(from_=player.name, message=message)),
    )
    return player


# ---- auth ----

def _authenticate(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("kind") != "access":
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


# ---- command dispatch ----

def _format_validation_error(exc: ValidationError) -> str:
    """Return a short, human-readable summary of the first validation error."""
    errors = exc.errors()
    if not errors:
        return "validation failed"
    err = errors[0]
    loc = ".".join(str(p) for p in err.get("loc", ()))
    msg = err.get("msg", "invalid value")
    return f"{loc}: {msg}" if loc else msg


async def _handle(
    ws: WebSocket, db: AsyncIOMotorDatabase, player: Player, raw: str
) -> Player | None:
    """Dispatch a single client message.

    Returns the (possibly updated) player so the outer loop can carry forward
    any state changes (e.g. current room after a move). Returns None to
    signal the outer loop should close the connection (e.g. client quit)."""
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        await _send_error(ws, "BAD_JSON", "Could not parse message as JSON")
        return player

    mtype = envelope.get("type")
    if not isinstance(mtype, str):
        await _send_error(ws, "BAD_ENVELOPE", "Missing 'type' field")
        return player

    try:
        if mtype == "client.ping":
            ClientPing(**envelope)
            await _send(ws, ServerPong())
            return player

        if mtype == "client.command.inventory":
            ClientInventory(**envelope)
            await _send_inventory(ws, db, player.inventory_item_ids)
            return player

        if mtype == "client.command.who":
            ClientWho(**envelope)
            online_ids = get_broker().connected_player_ids()
            if online_ids:
                names = sorted(
                    [
                        d["name"]
                        async for d in db["players"].find(
                            {"_id": {"$in": online_ids}},
                            projection={"name": 1},
                        )
                    ],
                    key=str.lower,
                )
            else:
                names = []
            await _send(ws, ServerWhoList(data=ServerWhoList.Data(players=names)))
            return player

        if mtype == "client.command.look":
            msg = ClientLook(**envelope)
            target = (msg.data.target or "").strip()

            if not target:
                view = await _room_view(db, player)
                if view is None:
                    await _send_error(ws, "ROOM_MISSING", "Your current room no longer exists")
                    return player
                await _send(ws, ServerRoomEntered(data=view))
                return player

            await _handle_examine(ws, db, player, target)
            return player

        if mtype == "client.command.move":
            msg = ClientMove(**envelope)
            return await _handle_move(ws, db, player, msg.data.direction)

        if mtype == "client.command.take":
            tmsg = ClientTake(**envelope)
            return await _handle_take(ws, db, player, tmsg.data.target)

        if mtype == "client.command.drop":
            dmsg = ClientDrop(**envelope)
            return await _handle_drop(ws, db, player, dmsg.data.target)

        if mtype == "client.command.say":
            say_msg = ClientSay(**envelope)
            return await _handle_say(ws, player, say_msg.data.message)

        if mtype == "client.command.shout":
            shout_msg = ClientShout(**envelope)
            return await _handle_shout(ws, player, shout_msg.data.message)

        if mtype == "client.command.quit":
            ClientQuit(**envelope)
            # Signal the outer loop to close. We can't close inside the
            # handler because the loop would call ws.receive_text() again
            # on the closed socket, which raises a RuntimeError that the
            # outer `except WebSocketDisconnect` doesn't catch.
            return None

        await _send_error(ws, "UNKNOWN_TYPE", f"Unknown message type: {mtype}")
        return player
    except ValidationError as exc:
        await _send_error(
            ws, "BAD_PAYLOAD",
            f"Invalid payload for {mtype}: {_format_validation_error(exc)}",
        )
        return player


# ---- entrypoint ----

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")) -> None:
    account_id = _authenticate(token)
    if account_id is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    await ws.accept()
    db = get_db()

    player = await _load_player(db, account_id)
    if player is None:
        await _send_error(ws, "NO_CHARACTER", "Create a character first via POST /characters")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    view = await _room_view(db, player)
    if view is None:
        await _send_error(ws, "ROOM_MISSING", "Starting room not found; world may not be seeded")
        await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await _send(ws, ServerWelcome(data=ServerWelcome.Data(player=player, room=view)))

    broker = get_broker()
    await broker.connect(player.id, ws, player.current_room_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                result = await _handle(ws, db, player, raw)
            except Exception:
                logger.exception(
                    "Unhandled error processing message; player=%s", player.name,
                )
                try:
                    await _send_error(ws, "INTERNAL_ERROR", "Internal server error")
                except Exception:
                    # Socket likely already broken; let the outer disconnect path handle it.
                    pass
                continue
            if result is None:
                # Client requested quit. Close cleanly, then break so we never
                # call receive_text() on a closed socket.
                await ws.close(code=1000, reason="quit")
                break
            player = result
    except WebSocketDisconnect:
        logger.info("WS disconnect: player=%s", player.name)
    finally:
        await broker.disconnect(player.id, ws)
