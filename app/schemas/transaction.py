"""Transaction schemas."""

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.category import CategoryKind
from app.schemas.category import CategoryRead
from app.schemas.user import CURRENCY_PATTERN


class TransactionCreate(BaseModel):
    category_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="RUB", max_length=3, pattern=CURRENCY_PATTERN)
    happened_at: dt.date = Field(default_factory=dt.date.today)
    note: str | None = Field(default=None, max_length=500)


class TransactionUpdate(BaseModel):
    category_id: int | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, max_length=3, pattern=CURRENCY_PATTERN)
    happened_at: dt.date | None = None
    note: str | None = Field(default=None, max_length=500)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: CategoryRead
    amount: Decimal
    currency: str
    kind: CategoryKind
    happened_at: dt.date
    note: str | None
    created_at: dt.datetime
