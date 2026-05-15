"""Pydantic models for both HTTP and WebSocket surfaces.

Kept in one module for now to mirror the spec/ layout closely; split as the
file grows.

These types are the Python-side mirror of the JSON Schemas under
``spec/schemas`` and the AsyncAPI message catalog at ``spec/asyncapi.yaml``.
When the spec changes, change the models here too — eventually swap manual
maintenance for codegen.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

# ---- shared ----

PlayerName = Annotated[
    str,
    StringConstraints(min_length=3, max_length=24, pattern=r"^[A-Za-z][A-Za-z0-9_\-]*$"),
]

Direction = Literal[
    "north", "south", "east", "west",
    "northeast", "northwest", "southeast", "southwest",
    "up", "down",
]


class Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


# ---- domain ----

class Exit(Base):
    direction: Direction
    to_room_id: str = Field(alias="toRoomId")
    description: str | None = None
    locked: bool = False
    key_item_id: str | None = Field(default=None, alias="keyItemId")


class Room(Base):
    id: str
    name: str = Field(min_length=1, max_length=80)
    description: str
    exits: list[Exit] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list, alias="itemIds")
    npc_ids: list[str] = Field(default_factory=list, alias="npcIds")
    tags: list[str] = Field(default_factory=list)


class Item(Base):
    id: str
    name: str = Field(min_length=1, max_length=60)
    short_description: str = Field(alias="shortDescription")
    long_description: str | None = Field(default=None, alias="longDescription")
    takeable: bool = True
    weight: float = 1
    tags: list[str] = Field(default_factory=list)


class Npc(Base):
    id: str
    name: str = Field(min_length=1, max_length=60)
    short_description: str = Field(alias="shortDescription")
    long_description: str | None = Field(default=None, alias="longDescription")
    home_room_id: str = Field(alias="homeRoomId")
    dialogue: list[str] = Field(default_factory=list)


class Player(Base):
    id: str
    account_id: str = Field(alias="accountId")
    name: PlayerName
    description: str | None = None
    current_room_id: str = Field(alias="currentRoomId")
    inventory_item_ids: list[str] = Field(default_factory=list, alias="inventoryItemIds")
    created_at: datetime = Field(alias="createdAt")
    last_seen_at: datetime | None = Field(default=None, alias="lastSeenAt")


class Account(Base):
    id: str
    email: EmailStr
    created_at: datetime = Field(alias="createdAt")


# ---- HTTP ----

class RegisterRequest(Base):
    email: EmailStr
    # 72 byte hard cap is bcrypt's input limit.
    password: str = Field(min_length=12, max_length=72)


class LoginRequest(Base):
    email: EmailStr
    password: str = Field(max_length=72)


class RefreshRequest(Base):
    refresh_token: str = Field(alias="refreshToken")


class TokenPair(Base):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn")


class CreateCharacterRequest(Base):
    name: PlayerName
    description: str | None = None


# ---- WebSocket envelopes ----
#
# Every message on /ws is { "type": "<event>", "data": { ... } }.
# Below: the union of client→server commands and server→client events,
# plus the RoomView projection used in server.welcome / server.room.entered.


class RoomView(Base):
    id: str
    name: str
    description: str
    exits: list[Exit]
    items: list[Item]
    players: list[str]  # names of other players in the room
    npcs: list[Npc]


# ---- client → server ----

class _ClientMessage(Base):
    """Base for client→server envelopes. Subclasses override ``type``."""


class ClientMove(_ClientMessage):
    type: Literal["client.command.move"] = "client.command.move"

    class Data(Base):
        direction: Direction

    data: Data


class ClientLook(_ClientMessage):
    type: Literal["client.command.look"] = "client.command.look"

    class Data(Base):
        target: str | None = None

    data: Data = Field(default_factory=lambda: ClientLook.Data())


class ClientSay(_ClientMessage):
    type: Literal["client.command.say"] = "client.command.say"

    class Data(Base):
        message: str = Field(min_length=1, max_length=500)

    data: Data


class ClientShout(_ClientMessage):
    type: Literal["client.command.shout"] = "client.command.shout"

    class Data(Base):
        message: str = Field(min_length=1, max_length=500)

    data: Data


class ClientTake(_ClientMessage):
    type: Literal["client.command.take"] = "client.command.take"

    class Data(Base):
        target: str

    data: Data


class ClientDrop(_ClientMessage):
    type: Literal["client.command.drop"] = "client.command.drop"

    class Data(Base):
        target: str

    data: Data


class ClientInventory(_ClientMessage):
    type: Literal["client.command.inventory"] = "client.command.inventory"


class ClientWho(_ClientMessage):
    type: Literal["client.command.who"] = "client.command.who"


class ClientQuit(_ClientMessage):
    type: Literal["client.command.quit"] = "client.command.quit"


class ClientPing(_ClientMessage):
    type: Literal["client.ping"] = "client.ping"


# ---- server → client ----

class _ServerMessage(Base):
    """Base for server→client envelopes."""


class ServerWelcome(_ServerMessage):
    type: Literal["server.welcome"] = "server.welcome"

    class Data(Base):
        player: Player
        room: RoomView

    data: Data


class ServerError(_ServerMessage):
    type: Literal["server.error"] = "server.error"

    class Data(Base):
        code: str
        message: str

    data: Data


class ServerRoomEntered(_ServerMessage):
    type: Literal["server.room.entered"] = "server.room.entered"
    data: RoomView


class ServerInventoryUpdated(_ServerMessage):
    type: Literal["server.inventory.updated"] = "server.inventory.updated"

    class Data(Base):
        items: list[Item]

    data: Data


class ServerExamineResult(_ServerMessage):
    type: Literal["server.examine.result"] = "server.examine.result"

    class Data(Base):
        name: str
        kind: Literal["item", "npc", "player"]
        description: str

    data: Data


class ServerPlayerArrived(_ServerMessage):
    type: Literal["server.player.arrived"] = "server.player.arrived"

    class Data(Base):
        player_name: str = Field(alias="playerName")
        # Direction the new arrival came from, expressed from the observer's
        # viewpoint (i.e. opposite of the mover's chosen direction).
        from_direction: str = Field(alias="fromDirection")

    data: Data


class ServerPlayerDeparted(_ServerMessage):
    type: Literal["server.player.departed"] = "server.player.departed"

    class Data(Base):
        player_name: str = Field(alias="playerName")
        to_direction: str = Field(alias="toDirection")

    data: Data


class ServerItemTaken(_ServerMessage):
    type: Literal["server.item.taken"] = "server.item.taken"

    class Data(Base):
        player_name: str = Field(alias="playerName")
        item_name: str = Field(alias="itemName")

    data: Data


class ServerItemDropped(_ServerMessage):
    type: Literal["server.item.dropped"] = "server.item.dropped"

    class Data(Base):
        player_name: str = Field(alias="playerName")
        item_name: str = Field(alias="itemName")

    data: Data


class ServerChatSay(_ServerMessage):
    type: Literal["server.chat.say"] = "server.chat.say"

    class Data(Base):
        # 'from' is a Python keyword, hence the trailing underscore + alias.
        from_: str = Field(alias="from")
        message: str

    data: Data


class ServerChatShout(_ServerMessage):
    type: Literal["server.chat.shout"] = "server.chat.shout"

    class Data(Base):
        from_: str = Field(alias="from")
        message: str

    data: Data


class ServerNpcSpoke(_ServerMessage):
    type: Literal["server.npc.spoke"] = "server.npc.spoke"

    class Data(Base):
        npc_name: str = Field(alias="npcName")
        message: str

    data: Data


class ServerWhoList(_ServerMessage):
    type: Literal["server.who.list"] = "server.who.list"

    class Data(Base):
        players: list[str]

    data: Data


class ServerPong(_ServerMessage):
    type: Literal["server.pong"] = "server.pong"
