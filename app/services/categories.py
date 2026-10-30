"""Category management."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationDomainError
from app.models.budget import Budget
from app.models.category import Category, CategoryKind
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryUpdate

DEFAULT_CATEGORIES: list[tuple[str, CategoryKind, str]] = [
    ("Groceries", CategoryKind.expense, "#22c55e"),
    ("Transport", CategoryKind.expense, "#3b82f6"),
    ("Housing", CategoryKind.expense, "#8b5cf6"),
    ("Health", CategoryKind.expense, "#ef4444"),
    ("Entertainment", CategoryKind.expense, "#f59e0b"),
    ("Dining out", CategoryKind.expense, "#ec4899"),
    ("Salary", CategoryKind.income, "#10b981"),
    ("Other income", CategoryKind.income, "#14b8a6"),
]


async def create_default_categories(db: AsyncSession, user: User) -> None:
    db.add_all(
        Category(user_id=user.id, name=name, kind=kind, color=color)
        for name, kind, color in DEFAULT_CATEGORIES
    )
    await db.commit()


async def list_categories(db: AsyncSession, user_id: int) -> list[Category]:
    stmt = (
        select(Category).where(Category.user_id == user_id).order_by(Category.kind, Category.name)
    )
    return list((await db.scalars(stmt)).all())


async def get_owned_category(db: AsyncSession, user_id: int, category_id: int) -> Category | None:
    return await db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )


async def create_category(db: AsyncSession, user_id: int, payload: CategoryCreate) -> Category:
    name = payload.name.strip()
    if await db.scalar(select(Category).where(Category.user_id == user_id, Category.name == name)):
        raise ConflictError("A category with this name already exists")
    category = Category(user_id=user_id, name=name, kind=payload.kind, color=payload.color)
    db.add(category)
    await db.commit()
    return category


async def update_category(
    db: AsyncSession, user_id: int, category_id: int, payload: CategoryUpdate
) -> Category:
    category = await get_owned_category(db, user_id, category_id)
    if category is None:
        raise NotFoundError("Category not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = data["name"].strip()
        duplicate = await db.scalar(
            select(Category).where(
                Category.user_id == user_id,
                Category.name == name,
                Category.id != category_id,
            )
        )
        if duplicate:
            raise ConflictError("A category with this name already exists")
        category.name = name
    if data.get("color"):
        category.color = data["color"]

    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(
    db: AsyncSession, user_id: int, category_id: int, force: bool = False
) -> None:
    category = await get_owned_category(db, user_id, category_id)
    if category is None:
        raise NotFoundError("Category not found")

    tx_count = (
        await db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.category_id == category_id)
        )
        or 0
    )
    if tx_count and not force:
        raise ValidationDomainError(
            f"The category has {tx_count} transaction(s). Pass force=true "
            "to delete them along with the category."
        )

    await db.execute(delete(Budget).where(Budget.category_id == category_id))
    if tx_count:
        await db.execute(delete(Transaction).where(Transaction.category_id == category_id))
    await db.delete(category)
    await db.commit()
