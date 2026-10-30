"""Тестовые фикстуры: SQLite in-memory + fakeredis + ASGI-клиент.

Переменные окружения выставляются ДО импорта приложения.
"""

import os

# Выставляем ДО импорта приложения. На случай, если в системе уже есть
# «чужая» DATABASE_URL (например, CI-раннер), принудительно используем SQLite.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ.setdefault("LOGIN_RATE_LIMIT", "50")
os.environ.setdefault("BCRYPT_ROUNDS", "4")

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import cache
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(engine):
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache.set_redis(fake_redis)

    app = create_app()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
    await fake_redis.aclose()
