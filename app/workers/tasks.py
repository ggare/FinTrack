"""Celery tasks: exchange rates refresh, budget checks, notifications cleanup.

Each task creates its own event loop and fresh DB/Redis connections —
the safe pattern for asyncio code inside a Celery worker process.
"""

import asyncio

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services import budgets as budget_service
from app.services import exchange
from app.services import notifications as notification_service
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.tasks.update_exchange_rates")
def update_exchange_rates() -> str:
    async def _run() -> str:
        redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        try:
            rates = await exchange.fetch_and_cache_rates(redis)
            return f"rates updated: {len(rates)} currencies"
        finally:
            await redis.aclose()

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.check_budgets")
def check_budgets() -> str:
    async def _run() -> str:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            async with factory() as db:
                created = await budget_service.check_all_budgets(db, redis)
            return f"budget check finished, {created} notification(s) created"
        finally:
            await redis.aclose()
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.cleanup_old_notifications")
def cleanup_old_notifications(days: int = 30) -> str:
    async def _run() -> str:
        engine = create_async_engine(get_settings().database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                removed = await notification_service.delete_old_notifications(db, days)
            return f"removed {removed} old notification(s)"
        finally:
            await engine.dispose()

    return asyncio.run(_run())
