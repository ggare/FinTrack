"""Demo data seeder: creates a demo user with ~3 months of history.

Usage:  python -m app.db.seeds
Idempotent: skips seeding if the demo user already exists.
"""

import asyncio
import datetime as dt
import random
from decimal import Decimal

import structlog
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import Budget, Category, CategoryKind, Transaction, User

logger = structlog.get_logger(__name__)

DEMO_EMAIL = "demo@fintrack.dev"
DEMO_PASSWORD = "demo1234"

# name -> (kind, color, count_per_month, (min, max), probability_per_day)
EXPENSE_PLAN: dict[str, tuple[CategoryKind, str, int, tuple[float, float], float]] = {
    "Groceries": (CategoryKind.expense, "#22c55e", 0, (350.0, 2600.0), 0.55),
    "Transport": (CategoryKind.expense, "#3b82f6", 0, (50.0, 320.0), 0.35),
    "Housing": (CategoryKind.expense, "#8b5cf6", 0, (32000.0, 36000.0), 0.0),  # fixed on the 10th
    "Health": (CategoryKind.expense, "#ef4444", 0, (900.0, 6500.0), 0.04),
    "Entertainment": (CategoryKind.expense, "#f59e0b", 0, (500.0, 3200.0), 0.12),
    "Dining out": (CategoryKind.expense, "#ec4899", 0, (250.0, 1800.0), 0.30),
}
RENT_DAY = 10
SALARY_DAY = 5
SALARY_AMOUNT = Decimal("120000")
FREELANCE_PROBABILITY = 0.15

DEFAULT_BUDGETS: dict[str, float] = {
    "Groceries": 30000.0,
    "Transport": 5000.0,
    "Entertainment": 8000.0,
    "Dining out": 10000.0,
}


def _money(rng: random.Random, lo: float, hi: float) -> Decimal:
    return Decimal(str(round(rng.uniform(lo, hi), 2)))


def _build_transactions(rng: random.Random, user_id: int, cats: dict[str, Category]) -> list:
    today = dt.date.today()
    txs: list[Transaction] = []
    for offset in range(90):  # the last ~3 months
        day = today - dt.timedelta(days=offset)

        if day.day == SALARY_DAY:
            txs.append(
                Transaction(
                    user_id=user_id,
                    category_id=cats["Salary"].id,
                    amount=SALARY_AMOUNT,
                    currency="RUB",
                    kind=CategoryKind.income,
                    happened_at=day,
                    note="Salary",
                )
            )
        elif rng.random() < FREELANCE_PROBABILITY:
            txs.append(
                Transaction(
                    user_id=user_id,
                    category_id=cats["Other income"].id,
                    amount=_money(rng, 4000, 18000),
                    currency="RUB",
                    kind=CategoryKind.income,
                    happened_at=day,
                    note="A small freelance gig",
                )
            )

        if day.day == RENT_DAY:
            txs.append(
                Transaction(
                    user_id=user_id,
                    category_id=cats["Housing"].id,
                    amount=_money(rng, *EXPENSE_PLAN["Housing"][3]),
                    currency="RUB",
                    kind=CategoryKind.expense,
                    happened_at=day,
                    note="Apartment rent and utilities",
                )
            )

        for name, (_, _, _, (lo, hi), prob) in EXPENSE_PLAN.items():
            if name == "Housing":
                continue
            if rng.random() < prob:
                # ~7% of everyday expenses in USD (cards/subscriptions), to demo conversion
                in_usd = name in ("Entertainment", "Dining out") and rng.random() < 0.07
                txs.append(
                    Transaction(
                        user_id=user_id,
                        category_id=cats[name].id,
                        amount=_money(rng, lo, hi) if not in_usd else _money(rng, 3, 25),
                        currency="USD" if in_usd else "RUB",
                        kind=CategoryKind.expense,
                        happened_at=day,
                        note=None,
                    )
                )
    return txs


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing:
            logger.info("demo_data_already_present")
            return

        user = User(
            email=DEMO_EMAIL,
            username="demo",
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        await db.flush()

        cats: dict[str, Category] = {}
        for name, (kind, color, *_) in EXPENSE_PLAN.items():
            cats[name] = Category(user_id=user.id, name=name, kind=kind, color=color)
        cats["Salary"] = Category(
            user_id=user.id, name="Salary", kind=CategoryKind.income, color="#10b981"
        )
        cats["Other income"] = Category(
            user_id=user.id, name="Other income", kind=CategoryKind.income, color="#14b8a6"
        )
        db.add_all(cats.values())
        await db.flush()

        rng = random.Random(42)  # fixed seed keeps the data reproducible
        txs = _build_transactions(rng, user.id, cats)
        db.add_all(txs)

        for name, limit in DEFAULT_BUDGETS.items():
            db.add(
                Budget(
                    user_id=user.id,
                    category_id=cats[name].id,
                    monthly_limit=Decimal(str(limit)),
                )
            )

        await db.commit()

    logger.info(
        "demo_data_seeded",
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        transactions=len(txs),
        budgets=len(DEFAULT_BUDGETS),
    )


if __name__ == "__main__":
    asyncio.run(seed())
