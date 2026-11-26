"""Persistent shopping cart.

Cart items reference a **product variant**, not a product, because the variant is
the purchasable unit: "Straight Leg Jeans / waist 32" is what has stock and what
gets shipped.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.variant import ProductVariant

MONEY = Numeric(10, 2)


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "carts"
    __table_args__ = (
        # One open cart per customer.
        UniqueConstraint("user_id", name="uq_cart_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        order_by="CartItem.created_at",
    )

    def __repr__(self) -> str:
        return f"<Cart user={self.user_id} items={len(self.items)}>"


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        # A variant appears at most once per cart; adding it again raises the
        # quantity rather than creating a second line.
        UniqueConstraint("cart_id", "product_variant_id", name="uq_cart_item_variant"),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_cart_item_unit_price_non_negative"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Cached for display only. It is recomputed from the catalogue on every read
    # and again at checkout, so a stale value can never reach an order.
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")
    variant: Mapped["ProductVariant"] = relationship(lazy="joined")

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    def __repr__(self) -> str:
        return f"<CartItem variant={self.product_variant_id} qty={self.quantity}>"
