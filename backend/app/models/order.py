"""Orders, order items, and status history.

Orders are **immutable records of a past transaction**. They therefore store
snapshots of the address, product, and variant as they were at purchase time,
rather than relying on the live rows: a customer who later edits their address,
or an admin who renames a product or changes its price, must not retroactively
alter what a historical order says was bought and where it was sent.

The foreign keys to product and variant are kept alongside the snapshots for
reporting and restock purposes, but nothing customer-facing reads through them.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base
# Native enum type instances are shared so each is created exactly once by the
# migration; two instances of the same named type would both emit CREATE TYPE.
from app.models._types import (
    DELIVERY_METHOD_ENUM,
    ORDER_STATUS_ENUM,
    PAYMENT_METHOD_ENUM,
    PAYMENT_STATUS_ENUM,
)
from app.models.enums import DeliveryMethod, OrderStatus, PaymentMethod, PaymentStatus
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.returns import ReturnRequest
    from app.models.shipping import Shipment

MONEY = Numeric(10, 2)

# JSONB on PostgreSQL, plain JSON elsewhere, so the snapshot columns stay
# queryable in production without breaking a SQLite-backed test run.
SNAPSHOT_JSON = JSON().with_variant(JSONB(), "postgresql")


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_order_subtotal_non_negative"),
        CheckConstraint("shipping_amount >= 0", name="ck_order_shipping_non_negative"),
        CheckConstraint("discount_amount >= 0", name="ck_order_discount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_order_total_non_negative"),
        # The listing queries admins and customers run most often.
        Index("ix_order_user_created", "user_id", "created_at"),
        Index("ix_order_status_created", "order_status", "created_at"),
    )

    # Human-facing identifier, e.g. RG-20260812-0001. The UUID primary key is
    # never shown to customers.
    order_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    # Orders outlive accounts: RESTRICT stops a user row being removed while
    # their order history exists.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Contact details captured at checkout, independent of the account record.
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)

    shipping_address_snapshot: Mapped[dict[str, Any]] = mapped_column(
        SNAPSHOT_JSON, nullable=False
    )
    # Null means "same as shipping", which is the common case here.
    billing_address_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        SNAPSHOT_JSON, nullable=True
    )

    payment_method: Mapped[PaymentMethod] = mapped_column(
        PAYMENT_METHOD_ENUM, nullable=False, index=True
    )
    # Denormalised from the active Payment so order listings can filter on it
    # without a join. Payment remains the source of truth.
    payment_status: Mapped[PaymentStatus] = mapped_column(
        PAYMENT_STATUS_ENUM, nullable=False, default=PaymentStatus.PENDING, index=True
    )
    order_status: Mapped[OrderStatus] = mapped_column(
        ORDER_STATUS_ENUM, nullable=False, default=OrderStatus.PENDING, index=True
    )
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        DELIVERY_METHOD_ENUM, nullable=False, default=DeliveryMethod.STANDARD
    )

    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    # Snapshot for code-based promotions; the order remains readable if a coupon is edited later.
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    shipping_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Staff-only; never serialised to a customer response model.
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    cancelled_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(lazy="joined")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.created_at"
    )
    status_events: Mapped[list["OrderStatusEvent"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusEvent.created_at",
    )
    return_requests: Mapped[list["ReturnRequest"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    # Gateway detail lives on Payment, never here, so adding a provider does not
    # reshape this table. Several payments can exist if an attempt failed and the
    # customer retried.
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Payment.created_at",
    )
    shipment: Mapped["Shipment | None"] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False
    )

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def customer(self) -> User | dict[str, object | None]:
        """Return the account or a guest identity derived from the delivery snapshot."""
        if self.user is not None:
            return self.user
        full_name = str((self.shipping_address_snapshot or {}).get("full_name", "Guest"))
        first_name, _, last_name = full_name.partition(" ")
        return {
            "id": None,
            "email": self.contact_email,
            "first_name": first_name,
            "last_name": last_name,
            "is_guest": True,
        }

    @property
    def active_payment(self) -> "Payment | None":
        """The payment that currently represents this order.

        A settled payment always wins over an unsettled one, so a successful
        retry is authoritative even if a failed attempt was created later.
        """
        if not self.payments:
            return None
        settled = [payment for payment in self.payments if payment.is_settled]
        pool = settled or list(self.payments)
        return max(pool, key=lambda payment: payment.created_at)

    @property
    def payment(self) -> "Payment | None":
        """Alias for `active_payment`, so response models can validate off the ORM."""
        return self.active_payment

    @property
    def is_cancellable_by_customer(self) -> bool:
        from app.models.enums import CUSTOMER_CANCELLABLE_STATUSES

        return self.order_status in CUSTOMER_CANCELLABLE_STATUSES

    def __repr__(self) -> str:
        return f"<Order {self.order_number} {self.order_status}>"


class OrderItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_item_unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_order_item_line_total_non_negative"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL rather than RESTRICT: the snapshot below carries everything the
    # order needs, so a purged catalogue row must not block or corrupt history.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    product_slug_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    brand_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    # {"size": "M", "waist": 32, "color": "Indigo", "label": "Waist 32"}
    variant_snapshot: Mapped[dict[str, Any]] = mapped_column(SNAPSHOT_JSON, nullable=False)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)

    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def variant_label(self) -> str:
        snapshot = self.variant_snapshot or {}
        return str(snapshot.get("label") or snapshot.get("size") or "—")

    def __repr__(self) -> str:
        return f"<OrderItem {self.sku_snapshot} x{self.quantity}>"


class OrderStatusEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only status history, used to render the customer order timeline."""

    __tablename__ = "order_status_events"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(ORDER_STATUS_ENUM, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null when the system recorded it (for example the initial PENDING event).
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    order: Mapped[Order] = relationship(back_populates="status_events")

    def __repr__(self) -> str:
        return f"<OrderStatusEvent {self.status}>"
