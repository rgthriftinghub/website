"""Cart schemas.

The client never sends a price. Requests carry only a variant id and a quantity;
every monetary value in the response is computed by the backend from the
catalogue.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class CartLineInput(BaseModel):
    product_variant_id: uuid.UUID
    quantity: int = Field(ge=1, le=10)


class GuestCartPreviewRequest(BaseModel):
    items: list[CartLineInput] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_variants(self) -> "GuestCartPreviewRequest":
        ids = [item.product_variant_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each size can appear only once in the bag")
        return self


class CartItemAdd(BaseModel):
    product_variant_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemRead(BaseModel):
    id: uuid.UUID
    # Product
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    brand_name: str | None
    image_url: str | None
    # Variant
    product_variant_id: uuid.UUID
    variant_label: str
    sku: str
    size: str | None
    waist: int | None
    color: str | None
    # Money and stock
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    available_stock: int
    # False when the variant went out of stock or inactive after being added.
    is_available: bool
    unavailable_reason: str | None = None


class CartRead(BaseModel):
    id: uuid.UUID | None
    items: list[CartItemRead]
    item_count: int
    subtotal: Decimal
    # Delivery and total are previews using the same configured rules checkout
    # applies, so the cart and checkout totals cannot disagree.
    delivery_amount: Decimal
    total: Decimal
    currency: str
    has_unavailable_items: bool
