"""Budget schemas."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.category import CategoryRead


class BudgetSet(BaseModel):
    monthly_limit: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class BudgetRead(BaseModel):
    category: CategoryRead
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    percent: float
