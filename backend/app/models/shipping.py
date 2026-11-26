"""Shipping methods and shipment records.

`ShippingMethod` makes the delivery charge admin-configurable in the database
rather than a redeploy-only environment variable; the configured value is what
pricing reads, with the environment setting as the fallback when no active row
exists.

`Shipment` is the courier-side record. It is deliberately separate from the
order's own status: an order can be DISPATCHED while its shipment is IN_TRANSIT,
and the two progress on different clocks.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import (
    COURIER_PROVIDER_ENUM,
    DELIVERY_METHOD_ENUM,
    SHIPPING_STATUS_ENUM,
)
from app.models.enums import CourierProvider, DeliveryMethod, ShippingStatus
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.order import SNAPSHOT_JSON, Order

MONEY = Numeric(10, 2)


class ShippingMethod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An offerable delivery option and its price."""

    __tablename__ = "shipping_methods"
    __table_args__ = (
        UniqueConstraint("code", name="uq_shipping_method_code"),
        CheckConstraint("price >= 0", name="ck_shipping_method_price_non_negative"),
        CheckConstraint(
            "free_threshold IS NULL OR free_threshold >= 0",
            name="ck_shipping_method_threshold_non_negative",
        ),
    )

    code: Mapped[DeliveryMethod] = mapped_column(
        DELIVERY_METHOD_ENUM, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Null means "never free"; 0 means "always free".
    free_threshold: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    estimated_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def charge_for(self, subtotal: Decimal) -> Decimal:
        if subtotal <= 0:
            return Decimal("0.00")
        if self.free_threshold is not None and subtotal >= self.free_threshold:
            return Decimal("0.00")
        return self.price

    def __repr__(self) -> str:
        return f"<ShippingMethod {self.code} {self.price}>"


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The courier record for an order.

    One per order. A future return shipment would add a `direction` column
    rather than a second row of ambiguous meaning.
    """

    __tablename__ = "shipments"
    __table_args__ = (UniqueConstraint("order_id", name="uq_shipment_order"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[CourierProvider] = mapped_column(
        COURIER_PROVIDER_ENUM, nullable=False, default=CourierProvider.MANUAL, index=True
    )
    # Entered by staff when there is no courier API, or returned by one when there is.
    tracking_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # The courier's own identifier for the consignment, when it differs.
    shipment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shipping_status: Mapped[ShippingStatus] = mapped_column(
        SHIPPING_STATUS_ENUM, nullable=False, default=ShippingStatus.PENDING, index=True
    )
    label_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whatever a courier API last returned, redacted. Null while manual.
    provider_response: Mapped[dict[str, Any] | None] = mapped_column(SNAPSHOT_JSON, nullable=True)

    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="shipment")
    events: Mapped[list["ShipmentEvent"]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentEvent.created_at",
    )

    @property
    def is_trackable(self) -> bool:
        return bool(self.tracking_number)

    def __repr__(self) -> str:
        return f"<Shipment {self.provider} {self.shipping_status}>"


class ShipmentEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only shipping history, mirroring how order status events work."""

    __tablename__ = "shipment_events"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ShippingStatus] = mapped_column(
        SHIPPING_STATUS_ENUM, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    shipment: Mapped[Shipment] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<ShipmentEvent {self.status}>"


class BankAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Store bank details shown to customers who choose bank transfer.

    Held in the database rather than environment variables so staff can change
    an account without a redeploy. These are the store's *own* published
    receiving details — no customer banking data is stored anywhere.
    """

    __tablename__ = "bank_accounts"

    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_title: Mapped[str] = mapped_column(String(160), nullable=False)
    account_number: Mapped[str] = mapped_column(String(64), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<BankAccount {self.bank_name}>"
