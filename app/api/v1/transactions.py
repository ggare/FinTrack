"""Transaction CRUD endpoints."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.category import CategoryKind
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.common import Page
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services import transactions as tx_service

router = APIRouter()


@router.get("", response_model=Page[TransactionRead])
async def list_transactions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: int | None = None,
    kind: CategoryKind | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[TransactionRead]:
    filters = tx_service.TransactionFilters(
        category_id=category_id, kind=kind, date_from=date_from, date_to=date_to
    )
    items, total = await tx_service.list_transactions(db, user.id, filters, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Transaction:
    return await tx_service.create_transaction(db, user, payload)


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Transaction:
    return await tx_service.update_transaction(db, user, transaction_id, payload)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await tx_service.delete_transaction(db, user, transaction_id)
