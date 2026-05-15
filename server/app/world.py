"""Seed data for the initial world.

Run at startup (idempotent): if the rooms collection is empty, populate with
a tiny three-room demo so the scaffold has something walkable. Replace with
a full world spec post-MVP.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

_ROOMS = [
    {
        "_id": "town-square",
        "id": "town-square",
        "name": "Town Square",
        "description": (
            "A worn cobblestone square at the heart of a forgotten town. "
            "A weathered fountain trickles softly at its center."
        ),
        "exits": [
            {"direction": "north", "toRoomId": "north-road"},
            {"direction": "east", "toRoomId": "east-market"},
        ],
        "itemIds": ["rusty-key"],
        "npcIds": ["town-crier"],
        "tags": ["safe-zone", "outdoors"],
    },
    {
        "_id": "north-road",
        "id": "north-road",
        "name": "North Road",
        "description": "A muddy road heading out of town. The square lies to the south.",
        "exits": [{"direction": "south", "toRoomId": "town-square"}],
        "itemIds": [],
        "npcIds": [],
        "tags": ["outdoors"],
    },
    {
        "_id": "east-market",
        "id": "east-market",
        "name": "East Market",
        "description": (
            "Empty stalls line a narrow lane. The town square is just to the west."
        ),
        "exits": [{"direction": "west", "toRoomId": "town-square"}],
        "itemIds": [],
        "npcIds": [],
        "tags": ["outdoors"],
    },
]

_ITEMS = [
    {
        "_id": "rusty-key",
        "id": "rusty-key",
        "name": "rusty key",
        "shortDescription": "a rusty iron key",
        "longDescription": "An old iron key, pitted with rust. Whatever it opens has likely long been lost.",
        "takeable": True,
        "weight": 0.1,
        "tags": ["key"],
    },
]

_NPCS = [
    {
        "_id": "town-crier",
        "id": "town-crier",
        "name": "town crier",
        "shortDescription": "a weary town crier",
        "longDescription": "A graying man in a faded cloak. He looks like he has been here a very long time.",
        "homeRoomId": "town-square",
        "dialogue": [
            "Hear ye, hear ye! Naught of consequence today.",
            "Mind the cobbles, traveler.",
            "Aye, the fountain still runs. Has for as long as I remember.",
        ],
    },
]


async def seed_if_empty(db: AsyncIOMotorDatabase) -> None:
    if await db["rooms"].count_documents({}) == 0:
        await db["rooms"].insert_many(_ROOMS)
    if await db["items"].count_documents({}) == 0:
        await db["items"].insert_many(_ITEMS)
    if await db["npcs"].count_documents({}) == 0:
        await db["npcs"].insert_many(_NPCS)


STARTING_ROOM_ID = "town-square"
