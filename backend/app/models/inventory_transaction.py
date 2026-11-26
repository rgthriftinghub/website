"""Inventory movement history.

Every stock change goes through here, recording the before and after quantities
so a variant's current stock can always be reconciled against its history. This
is the foundation the Phase 2 inventory model was designed to grow into.

`reference_type` / `reference_id` are a deliberately loose link rather than a
foreign key: a movement can originate from an order, a return, or a manual
adjustment, and adding a nullable FK column per source would bloat the table.
"""

import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import InventoryTransactionType
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.variant import ProductVariant

REFERENCE_ORDER = "ORDER"
REFERENCE_RETURN = "RETURN_REQUEST"
REFERENCE_MANUAL = "MANUAL"


class InventoryTransaction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint("quantity_before >= 0", name="ck_inventory_tx_before_non_negative"),
        CheckConstraint("quantity_after >= 0", name="ck_inventory_tx_after_non_negative"),
        # Reading one variant's history in order is the common query.
        Index("ix_inventory_tx_variant_created", "product_variant_id", "created_at"),
        Index("ix_inventory_tx_reference", "reference_type", "reference_id"),
    )

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[InventoryTransactionType] = mapped_column(
        Enum(InventoryTransactionType, name="inventory_transaction_type"),
        nullable=False,
        index=True,
    )
    # Signed: negative for a sale, positive for a restock or cancellation.
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)

    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    variant: Mapped[ProductVariant] = relationship()

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction {self.type} {self.quantity_change:+d} "
            f"({self.quantity_before}->{self.quantity_after})>"
        )
