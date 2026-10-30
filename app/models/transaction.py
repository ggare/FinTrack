"""Transaction model."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.category import CategoryKind, category_kind_enum


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB", server_default="RUB")
    kind: Mapped[CategoryKind] = mapped_column(category_kind_enum, default=CategoryKind.expense)
    happened_at: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, index=True)
    note: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="transactions")
    # selectin: категория подгружается вторым запросом (IN (...)) — безопасно в async.
    category = relationship("Category", back_populates="transactions", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Transaction id={self.id} amount={self.amount} {self.currency}>"
