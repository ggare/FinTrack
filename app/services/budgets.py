"""Budgets: per-category monthly limits, progress and Celery-driven alerts."""

import datetime as dt
from decimal import Decimal

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationDomainError
from app.models.budget import Budget
from app.models.category import Category, CategoryKind
from app.models.notification import Notification
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.budget import BudgetRead
from app.schemas.category import CategoryRead
from app.services import analytics, exchange
from app.services.categories import get_owned_category

logger = structlog.get_logger(__name__)


async def list_with_spent(
    db: AsyncSession, user: User, month: dt.date | None = None
) -> list[BudgetRead]:
    stmt = (
        select(Budget, Category)
        .join(Category, Budget.category_id == Category.id)
        .where(Budget.user_id == user.id)
        .order_by(Category.name)
    )
    rows = (await db.execute(stmt)).all()

    rates = await exchange.get_rates()
    start, end = analytics.month_bounds(month or dt.date.today())
    spent_stmt = (
        select(
            Transaction.category_id,
            Transaction.currency,
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.kind == CategoryKind.expense,
            Transaction.happened_at >= start,
            Transaction.happened_at < end,
        )
        .group_by(Transaction.category_id, Transaction.currency)
    )
    spent_rows = (await db.execute(spent_stmt)).all()

    spent_by_cat: dict[int, Decimal] = {}
    for row in spent_rows:
        converted = exchange.convert(Decimal(row.total), row.currency, user.base_currency, rates)
        spent_by_cat[row.category_id] = spent_by_cat.get(row.category_id, Decimal("0")) + converted

    result: list[BudgetRead] = []
    for budget, category in rows:
        limit = Decimal(budget.monthly_limit)
        spent = spent_by_cat.get(category.id, Decimal("0"))
        result.append(
            BudgetRead(
                category=CategoryRead.model_validate(category),
                monthly_limit=limit,
                spent=spent,
                remaining=limit - spent,
                percent=round(float(spent / limit * 100), 1) if limit else 0.0,
            )
        )
    return result


async def set_budget(
    db: AsyncSession, user: User, category_id: int, monthly_limit: Decimal
) -> BudgetRead:
    category = await get_owned_category(db, user.id, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    if category.kind != CategoryKind.expense:
        raise ValidationDomainError("Budgets can only be set for expense categories")

    budget = await db.scalar(
        select(Budget).where(Budget.user_id == user.id, Budget.category_id == category_id)
    )
    if budget is None:
        budget = Budget(user_id=user.id, category_id=category_id, monthly_limit=monthly_limit)
        db.add(budget)
    else:
        budget.monthly_limit = monthly_limit
    await db.commit()

    items = await list_with_spent(db, user)
    for item in items:
        if item.category.id == category_id:
            return item
    raise NotFoundError  # pragma: no cover


async def delete_budget(db: AsyncSession, user: User, category_id: int) -> None:
    budget = await db.scalar(
        select(Budget).where(Budget.user_id == user.id, Budget.category_id == category_id)
    )
    if budget is None:
        raise NotFoundError("Budget not found")
    await db.delete(budget)
    await db.commit()


async def check_all_budgets(db: AsyncSession, redis: aioredis.Redis | None = None) -> int:
    """Create notifications for budgets that are >= 80% used (runs in Celery beat)."""
    stmt = (
        select(Budget, Category, User)
        .join(Category, Budget.category_id == Category.id)
        .join(User, Budget.user_id == User.id)
    )
    rows = (await db.execute(stmt)).all()
    rates = await exchange.get_rates(redis)
    start, end = analytics.month_bounds(dt.date.today())
    month_start = dt.datetime.combine(start, dt.time.min)

    created = 0
    for budget, category, user in rows:
        spent_rows = (
            await db.execute(
                select(Transaction.currency, func.sum(Transaction.amount).label("total"))
                .where(
                    Transaction.user_id == user.id,
                    Transaction.category_id == category.id,
                    Transaction.kind == CategoryKind.expense,
                    Transaction.happened_at >= start,
                    Transaction.happened_at < end,
                )
                .group_by(Transaction.currency)
            )
        ).all()
        spent = Decimal("0")
        for row in spent_rows:
            spent += exchange.convert(Decimal(row.total), row.currency, user.base_currency, rates)

        limit = Decimal(budget.monthly_limit)
        if spent < limit * Decimal("0.8"):
            continue

        percent = int((spent / limit * 100).to_integral_value()) if limit else 0
        title = f'Budget "{category.name}": {percent}%'
        exists = await db.scalar(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.title == title,
                Notification.created_at >= month_start,
            )
        )
        if exists:
            continue

        if spent >= limit:
            message = (
                f"Limit of {limit} {user.base_currency} exceeded: {spent} spent. Time to slow down."
            )
        else:
            message = (
                f"{spent} out of {limit} {user.base_currency} spent ({percent}%). "
                "Less than 20% of the budget remains."
            )
        db.add(Notification(user_id=user.id, title=title, message=message))
        created += 1

    await db.commit()
    logger.info("budget_check_finished", budgets=len(rows), notifications_created=created)
    return created
