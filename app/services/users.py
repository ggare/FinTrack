"""User registration and authentication."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.categories import create_default_categories


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    email = payload.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise ConflictError("A user with this email is already registered")
    if await db.scalar(select(User).where(User.username == payload.username)):
        raise ConflictError("This username is already taken")

    user = User(
        email=email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await create_default_categories(db, user)
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return user
