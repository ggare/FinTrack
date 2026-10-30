"""Auth endpoints: register, login (OAuth2 password flow), current user."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services import ratelimit, users

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await users.register_user(db, payload)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    settings = get_settings()
    await ratelimit.enforce_rate_limit(
        request,
        scope="login",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window,
    )
    user = await users.authenticate(db, form.username, form.password)
    if user is None:
        raise AuthError("Invalid email or password")
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
