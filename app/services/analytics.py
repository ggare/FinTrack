"""Analytics: monthly summary and 6-month income/expense series."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryKind
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.report import CategoryTotal, MonthlyPoint, SummaryReport
from app.services import exchange


def month_bounds(month: dt.date) -> tuple[dt.date, dt.date]:
    """First day of the month and first day of the next month."""
    start = month.replace(day=1)
    next_month = dt.date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, next_month


def shift_month(month: dt.date, delta: int) -> dt.date:
    """Shift ``month`` (a first-day date) by ``delta`` months."""
    total = month.year * 12 + (month.month - 1) + delta
    return dt.date(total // 12, total % 12 + 1, 1)


async def monthly_summary(
    db: AsyncSession, user: User, month: dt.date | None = None
) -> SummaryReport:
    month = month or dt.date.today()
    start, end = month_bounds(month)
    rates = await exchange.get_rates()

    stmt = (
        select(
            Category.id,
            Category.name,
            Category.color,
            Category.kind,
            Transaction.currency,
            func.sum(Transaction.amount).label("total"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user.id,
            Transaction.happened_at >= start,
            Transaction.happened_at < end,
        )
        .group_by(Category.id, Category.name, Category.color, Category.kind, Transaction.currency)
    )
    rows = (await db.execute(stmt)).all()

    by_category: dict[int, CategoryTotal] = {}
    income_total = Decimal("0")
    expense_total = Decimal("0")
    for row in rows:
        total = exchange.convert(Decimal(row.total), row.currency, user.base_currency, rates)
        if row.kind == CategoryKind.income:
            income_total += total
        else:
            expense_total += total
        if row.id in by_category:
            by_category[row.id].total += total
        else:
            by_category[row.id] = CategoryTotal(
                category_id=row.id,
                name=row.name,
                color=row.color,
                kind=row.kind,
                total=total,
            )

    return SummaryReport(
        month=f"{month.year}-{month.month:02d}",
        base_currency=user.base_currency,
        income_total=income_total,
        expense_total=expense_total,
        balance=income_total - expense_total,
        by_category=sorted(by_category.values(), key=lambda c: -c.total),
    )


async def monthly_series(db: AsyncSession, user: User, months: int = 6) -> list[MonthlyPoint]:
    today = dt.date.today()
    first = dt.date(today.year, today.month, 1)
    start = shift_month(first, -(months - 1))
    rates = await exchange.get_rates()

    year_expr = extract("year", Transaction.happened_at).label("year")
    month_expr = extract("month", Transaction.happened_at).label("month")
    stmt = (
        select(
            year_expr,
            month_expr,
            Transaction.kind,
            Transaction.currency,
            func.sum(Transaction.amount).label("total"),
        )
        .where(Transaction.user_id == user.id, Transaction.happened_at >= start)
        .group_by(year_expr, month_expr, Transaction.kind, Transaction.currency)
        .order_by(year_expr, month_expr)
    )
    rows = (await db.execute(stmt)).all()

    totals: dict[tuple[int, int], dict[str, Decimal]] = {}
    for row in rows:
        key = (int(row.year), int(row.month))
        bucket = totals.setdefault(key, {"income": Decimal("0"), "expense": Decimal("0")})
        field = "income" if row.kind == CategoryKind.income else "expense"
        bucket[field] += exchange.convert(
            Decimal(row.total), row.currency, user.base_currency, rates
        )

    series: list[MonthlyPoint] = []
    for i in range(months):
        month = shift_month(first, -(months - 1 - i))
        bucket = totals.get(
            (month.year, month.month), {"income": Decimal("0"), "expense": Decimal("0")}
        )
        series.append(
            MonthlyPoint(
                month=f"{month.year}-{month.month:02d}",
                income=bucket["income"],
                expense=bucket["expense"],
            )
        )
    return series
