"""User schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    base_currency: str = Field(max_length=3, pattern=CURRENCY_PATTERN)
    is_active: bool


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=50, pattern=USERNAME_PATTERN
    )
    base_currency: str | None = Field(default=None, max_length=3, pattern=CURRENCY_PATTERN)
