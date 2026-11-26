"""Product variant model.

A variant is the actual purchasable unit. For this business a single garment
style can exist in several waists or sizes with independent stock, so stock is
never stored on :class:`~app.models.product.Product`:

    Product: Levi's Jeans
      variant waist 30 -> inventory quantity 5
      variant waist 32 -> inventory quantity 8
      variant waist 34 -> inventory quantity 0   (this variant alone is unavailable)
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.inventory import InventoryItem
    from app.models.product import Product

MONEY = Numeric(10, 2)


class ProductVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        # One variant per size/waist/colour combination within a product.
        # NULLS NOT DISTINCT (PostgreSQL 15+) is essential here: most variants
        # set only one of size/waist, so without it two rows that are both
        # (waist 30, size NULL) would count as distinct and slip past the
        # constraint.
        UniqueConstraint(
            "product_id",
            "size",
            "waist",
            "color",
            name="uq_variant_product_size_waist_color",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_variant_price_override_non_negative",
        ),
        CheckConstraint(
            "sale_price_override IS NULL OR sale_price_override >= 0",
            name="ck_variant_sale_override_non_negative",
        ),
        CheckConstraint("waist IS NULL OR waist > 0", name="ck_variant_waist_positive"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    size: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    waist: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    variant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Null means "inherit the product price".
    price_override: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    sale_price_override: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    product: Mapped["Product"] = relationship(back_populates="variants")
    inventory: Mapped["InventoryItem | None"] = relationship(
        back_populates="variant", cascade="all, delete-orphan", uselist=False, lazy="joined"
    )

    @property
    def quantity(self) -> int:
        """Current stock, read from the related inventory row (never derived elsewhere)."""
        return self.inventory.quantity if self.inventory is not None else 0

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.quantity > 0

    @property
    def is_low_stock(self) -> bool:
        if self.inventory is None or self.quantity <= 0:
            return False
        return self.quantity <= self.inventory.low_stock_threshold

    @property
    def label(self) -> str:
        """Human-readable variant label, e.g. "Waist 32" or "Size M"."""
        if self.variant_name:
            return self.variant_name
        if self.waist is not None:
            return f"Waist {self.waist}"
        if self.size:
            return self.size
        return self.sku

    def effective_price(self, product_price: Decimal) -> Decimal:
        return self.price_override if self.price_override is not None else product_price

    def __repr__(self) -> str:
        return f"<ProductVariant {self.sku} qty={self.quantity}>"
