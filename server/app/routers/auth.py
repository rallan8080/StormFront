from datetime import UTC, datetime
from uuid import uuid4

import jwt
from fastapi import APIRouter, HTTPException, status

from app.deps import Db
from app.models import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.security import decode_token, hash_password, issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_token_pair(account_id: str) -> TokenPair:
    access, ttl = issue_token(account_id, "access")
    refresh, _ = issue_token(account_id, "refresh")
    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        tokenType="Bearer",
        expiresIn=ttl,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: Db) -> TokenPair:
    existing = await db["accounts"].find_one({"email": req.email.lower()})
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")

    account_id = uuid4().hex
    await db["accounts"].insert_one(
        {
            "_id": account_id,
            "email": req.email.lower(),
            "passwordHash": hash_password(req.password),
            "createdAt": datetime.now(UTC),
        }
    )
    return _build_token_pair(account_id)


@router.post("/login", response_model=TokenPair)
async def login(req: LoginRequest, db: Db) -> TokenPair:
    doc = await db["accounts"].find_one({"email": req.email.lower()})
    if doc is None or not verify_password(req.password, doc["passwordHash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    return _build_token_pair(doc["_id"])


@router.post("/refresh", response_model=TokenPair)
async def refresh(req: RefreshRequest, db: Db) -> TokenPair:
    try:
        payload = decode_token(req.refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    if payload.get("kind") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token kind")
    account_id = payload.get("sub")
    if not account_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    if await db["accounts"].find_one({"_id": account_id}) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")
    return _build_token_pair(account_id)
