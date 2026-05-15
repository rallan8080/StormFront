from fastapi import APIRouter

from app.deps import CurrentAccount
from app.models import Account

router = APIRouter(tags=["account"])


@router.get("/me", response_model=Account)
async def me(account: CurrentAccount) -> Account:
    return account
