"""Global async Redis client: cache, rate limiting, exchange rates.

The connection is created lazily on first use. Tests inject a fake
instance via ``set_redis`` (see tests/conftest.py).
"""

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis


def set_redis(client: aioredis.Redis | None) -> None:
    """Replace the global client (used in tests)."""
    global _redis
    _redis = client
