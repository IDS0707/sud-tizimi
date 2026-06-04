"""Generic, reusable response schemas."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    """Simple message envelope."""

    detail: str


class Page(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    total: int
    limit: int
    offset: int
