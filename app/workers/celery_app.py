"""Celery application and beat schedule."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fintrack",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "update-exchange-rates": {
        "task": "app.workers.tasks.update_exchange_rates",
        "schedule": crontab(minute="*/30"),
    },
    "check-budgets": {
        "task": "app.workers.tasks.check_budgets",
        "schedule": crontab(hour=9, minute=0),
    },
    "cleanup-old-notifications": {
        "task": "app.workers.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=3, minute=30),
    },
}
