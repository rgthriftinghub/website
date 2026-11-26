"""Wishlist schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.catalog import ProductListItem


class WishlistItemRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    # The full listing shape, so the wishlist page can reuse ProductCard.
    product: ProductListItem


class WishlistRead(BaseModel):
    items: list[WishlistItemRead]
    total: int
