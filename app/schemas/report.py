"""Report schemas."""

from decimal import Decimal

from pydantic import BaseModel

from app.models.category import CategoryKind


class CategoryTotal(BaseModel):
    category_id: int
    name: str
    color: str
    kind: CategoryKind
    total: Decimal


class SummaryReport(BaseModel):
    month: str  # YYYY-MM
    base_currency: str
    income_total: Decimal
    expense_total: Decimal
    balance: Decimal
    by_category: list[CategoryTotal]


class MonthlyPoint(BaseModel):
    month: str  # YYYY-MM
    income: Decimal
    expense: Decimal
