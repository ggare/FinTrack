"""Category model and the expense/income enum."""

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CategoryKind(enum.StrEnum):
    expense = "expense"
    income = "income"


# Non-native enum: portable VARCHAR + CHECK on both PostgreSQL and SQLite.
category_kind_enum = SAEnum(
    CategoryKind,
    values_callable=lambda x: [e.value for e in x],
    native_enum=False,
    length=10,
)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[CategoryKind] = mapped_column(category_kind_enum, default=CategoryKind.expense)
    color: Mapped[str] = mapped_column(String(7), default="#6366f1", server_default="#6366f1")

    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} name={self.name!r}>"
