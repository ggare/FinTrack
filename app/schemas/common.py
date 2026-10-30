"""Shared generic schemas."""

from pydantic import BaseModel


class Page[T](BaseModel):
    """A single page of items plus pagination metadata."""

    items: list[T]
    total: int
    limit: int
    offset: int
