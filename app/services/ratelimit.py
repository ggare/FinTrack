"""Redis fixed-window rate limiter. Fails open if Redis is unavailable."""

import structlog
from fastapi import HTTPException, Request, status

from app.core.cache import get_redis

logger = structlog.get_logger(__name__)


async def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    if limit <= 0:
        return
    client_ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:{scope}:{client_ip}"
    try:
        redis = get_redis()
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Слишком много попыток. Повторите через {window_seconds} секунд.",
            )
    except HTTPException:
        raise
    except Exception:
        # Redis недоступен — не блокируем пользователей.
        logger.warning("rate_limiter_unavailable", scope=scope)
