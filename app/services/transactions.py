"""Transaction management."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.category import CategoryKind
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services.categories import get_owned_category


@dataclass
class TransactionFilters:
    category_id: int | None = None
    kind: CategoryKind | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None


def _apply_filters(stmt: Select, user_id: int, f: TransactionFilters) -> Select:
    stmt = stmt.where(Transaction.user_id == user_id)
    if f.category_id is not None:
        stmt = stmt.where(Transaction.category_id == f.category_id)
    if f.kind is not None:
        stmt = stmt.where(Transaction.kind == f.kind)
    if f.date_from is not None:
        stmt = stmt.where(Transaction.happened_at >= f.date_from)
    if f.date_to is not None:
        stmt = stmt.where(Transaction.happened_at <= f.date_to)
    return stmt


async def _get_with_category(db: AsyncSession, tx_id: int) -> Transaction:
    return await db.scalar(select(Transaction).where(Transaction.id == tx_id))


async def create_transaction(
    db: AsyncSession, user: User, payload: TransactionCreate
) -> Transaction:
    category = await get_owned_category(db, user.id, payload.category_id)
    if category is None:
        raise NotFoundError("Category not found")

    tx = Transaction(
        user_id=user.id,
        category_id=category.id,
        amount=payload.amount,
        currency=payload.currency,
        kind=category.kind,  # the kind is inherited from the category
        happened_at=payload.happened_at,
        note=payload.note,
    )
    db.add(tx)
    await db.commit()
    return await _get_with_category(db, tx.id)


async def get_owned_transaction(db: AsyncSession, user_id: int, tx_id: int) -> Transaction | None:
    return await db.scalar(
        select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )


async def update_transaction(
    db: AsyncSession, user: User, tx_id: int, payload: TransactionUpdate
) -> Transaction:
    tx = await get_owned_transaction(db, user.id, tx_id)
    if tx is None:
        raise NotFoundError("Transaction not found")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and data["category_id"] is not None:
        category = await get_owned_category(db, user.id, data["category_id"])
        if category is None:
            raise NotFoundError("Category not found")
        tx.category_id = category.id
        tx.kind = category.kind
    for field in ("amount", "currency", "happened_at", "note"):
        if field in data:
            setattr(tx, field, data[field])

    await db.commit()
    return await _get_with_category(db, tx.id)


async def delete_transaction(db: AsyncSession, user: User, tx_id: int) -> None:
    tx = await get_owned_transaction(db, user.id, tx_id)
    if tx is None:
        raise NotFoundError("Transaction not found")
    await db.delete(tx)
    await db.commit()


async def list_transactions(
    db: AsyncSession,
    user_id: int,
    filters: TransactionFilters,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Transaction], int]:
    base = _apply_filters(select(Transaction), user_id, filters)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0

    stmt = (
        _apply_filters(select(Transaction), user_id, filters)
        .order_by(Transaction.happened_at.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.scalars(stmt)).all())
    return items, total


async def recent_transactions(db: AsyncSession, user_id: int, limit: int = 6) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.happened_at.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())
