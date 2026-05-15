from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db as _get_db
from app.models import Account
from app.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def db() -> AsyncIOMotorDatabase:
    return _get_db()


async def current_account(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    database: Annotated[AsyncIOMotorDatabase, Depends(db)],
) -> Account:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc

    if payload.get("kind") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token kind")

    account_id = payload.get("sub")
    if not account_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")

    doc = await database["accounts"].find_one({"_id": account_id})
    if doc is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")

    return Account(id=doc["_id"], email=doc["email"], createdAt=doc["createdAt"])


CurrentAccount = Annotated[Account, Depends(current_account)]
Db = Annotated[AsyncIOMotorDatabase, Depends(db)]
