"""User profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter()


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    data = payload.model_dump(exclude_unset=True)
    if data.get("username"):
        duplicate = await db.scalar(
            select(User).where(User.username == data["username"], User.id != user.id)
        )
        if duplicate:
            raise ConflictError("Это имя пользователя уже занято")
        user.username = data["username"]
    if data.get("base_currency"):
        user.base_currency = data["base_currency"].upper()
    await db.commit()
    await db.refresh(user)
    return user
