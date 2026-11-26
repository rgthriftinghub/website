"""Inventory model.

Stock is held in its own table keyed one-to-one to a product variant. Keeping it
separate from the variant row means a future phase can add stock movement
history (a `stock_movements` table referencing `product_variant_id`, with the
current quantity remaining here as the fast-read projection) without reshaping
the catalogue tables.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.variant import ProductVariant


class InventoryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_non_negative"),
        CheckConstraint(
            "low_stock_threshold >= 0", name="ck_inventory_low_stock_threshold_non_negative"
        ),
    )

    # Unique: exactly one inventory row per variant.
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    variant: Mapped["ProductVariant"] = relationship(back_populates="inventory")

    def __repr__(self) -> str:
        return f"<InventoryItem variant={self.product_variant_id} qty={self.quantity}>"
