from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt

from app.config import get_settings

TokenKind = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def issue_token(account_id: str, kind: TokenKind) -> tuple[str, int]:
    """Return (encoded_jwt, seconds_until_expiry)."""
    settings = get_settings()
    now = datetime.now(UTC)
    if kind == "access":
        ttl = timedelta(minutes=settings.jwt_access_ttl_min)
    else:
        ttl = timedelta(days=settings.jwt_refresh_ttl_days)

    exp = now + ttl
    payload: dict[str, Any] = {
        "sub": account_id,
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
