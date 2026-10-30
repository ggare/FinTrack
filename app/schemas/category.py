"""Category schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.category import CategoryKind

COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: CategoryKind = CategoryKind.expense
    color: str = Field(default="#6366f1", pattern=COLOR_PATTERN)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: CategoryKind
    color: str
