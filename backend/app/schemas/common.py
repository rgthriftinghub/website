"""Shared schema building blocks."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100


class Page(BaseModel, Generic[ItemT]):
    """Consistent pagination envelope used by every listing endpoint."""

    items: list[ItemT]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, items: list[ItemT], page: int, page_size: int, total: int) -> "Page[ItemT]":
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class MessageResponse(BaseModel):
    detail: str
