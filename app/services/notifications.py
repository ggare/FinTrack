"""Notifications: listing and marking as read."""

import datetime as dt

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def list_notifications(
    db: AsyncSession, user_id: int, unread_only: bool = False
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(50)
    return list((await db.scalars(stmt)).all())


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount or 0


async def mark_read(db: AsyncSession, user_id: int, notification_id: int) -> None:
    notification = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if notification is not None:
        notification.is_read = True
        await db.commit()


async def delete_old_notifications(db: AsyncSession, days: int = 30) -> int:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    result = await db.execute(delete(Notification).where(Notification.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0
