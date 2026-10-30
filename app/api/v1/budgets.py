"""Budget endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.budget import BudgetRead, BudgetSet
from app.services import budgets

router = APIRouter()


@router.get("", response_model=list[BudgetRead])
async def list_budgets(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetRead]:
    return await budgets.list_with_spent(db, user)


@router.put("/{category_id}", response_model=BudgetRead)
async def set_budget(
    category_id: int,
    payload: BudgetSet,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetRead:
    return await budgets.set_budget(db, user, category_id, payload.monthly_limit)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    category_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await budgets.delete_budget(db, user, category_id)
