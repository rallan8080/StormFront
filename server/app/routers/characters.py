from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.deps import CurrentAccount, Db
from app.models import CreateCharacterRequest, Player
from app.world import STARTING_ROOM_ID

router = APIRouter(prefix="/characters", tags=["characters"])


def _doc_to_player(doc: dict) -> Player:
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


@router.get("", response_model=list[Player])
async def list_characters(account: CurrentAccount, db: Db) -> list[Player]:
    cursor = db["players"].find({"accountId": account.id})
    return [_doc_to_player(d) async for d in cursor]


@router.post("", response_model=Player, status_code=status.HTTP_201_CREATED)
async def create_character(
    req: CreateCharacterRequest, account: CurrentAccount, db: Db
) -> Player:
    player_id = uuid4().hex
    now = datetime.now(UTC)
    doc = {
        "_id": player_id,
        "accountId": account.id,
        "name": req.name,
        "description": req.description,
        "currentRoomId": STARTING_ROOM_ID,
        "inventoryItemIds": [],
        "createdAt": now,
    }
    try:
        await db["players"].insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Name already taken") from exc
    return _doc_to_player(doc)
