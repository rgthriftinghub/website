"""Payment, audit trail, and refund records.

Gateway-specific fields live here, never on `Order`. An order therefore does not
change shape when a new provider is added: it keeps a denormalised
`payment_status` for listing and filtering, while the authoritative detail —
provider transaction ids, raw responses, failure reasons — belongs to `Payment`.

An order may have several payments over its life (a declined gateway attempt
followed by a successful retry, for example), so the relationship is one-to-many
with one "active" payment resolved by recency.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionEvent,
    RefundStatus,
)
from app.models._types import (
    PAYMENT_METHOD_ENUM,
    PAYMENT_PROVIDER_ENUM,
    PAYMENT_STATUS_ENUM,
    PAYMENT_TRANSACTION_EVENT_ENUM,
    REFUND_STATUS_ENUM,
)
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.order import SNAPSHOT_JSON, Order

MONEY = Numeric(10, 2)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_amount_non_negative"),
        # A provider's transaction id is unique within that provider. Nullable
        # because COD and an unstarted gateway payment have none, and PostgreSQL
        # allows repeated NULLs under a unique constraint.
        UniqueConstraint(
            "provider", "provider_transaction_id", name="uq_payment_provider_transaction"
        ),
        Index("ix_payment_status_created", "status", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        PAYMENT_PROVIDER_ENUM, nullable=False, index=True
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        PAYMENT_METHOD_ENUM, nullable=False, index=True
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    status: Mapped[PaymentStatus] = mapped_column(
        PAYMENT_STATUS_ENUM, nullable=False, default=PaymentStatus.PENDING, index=True
    )
    # Whatever the provider last sent us, with secrets redacted before storage.
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(SNAPSHOT_JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- bank transfer: what the customer told us they sent ----------------
    customer_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A URL/path to an uploaded slip. No file bytes are stored in the database.
    proof_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    proof_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- staff verification ------------------------------------------------
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentTransaction.created_at",
    )
    refunds: Mapped[list["Refund"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )

    @property
    def is_settled(self) -> bool:
        from app.models.enums import TERMINAL_PAYMENT_STATUSES

        return self.status in TERMINAL_PAYMENT_STATUSES

    @property
    def awaiting_verification(self) -> bool:
        """Bank transfer where the customer has submitted a reference."""
        return (
            self.provider is PaymentProvider.BANK_TRANSFER
            and self.status is PaymentStatus.PENDING
            and self.proof_submitted_at is not None
        )

    def __repr__(self) -> str:
        return f"<Payment {self.provider} {self.status} {self.amount}>"


class PaymentTransaction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail of everything that happened to a payment."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_tx_payment_created", "payment_id", "created_at"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[PaymentTransactionEvent] = mapped_column(
        PAYMENT_TRANSACTION_EVENT_ENUM, nullable=False, index=True
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    # The payment's status *after* this event, so the trail replays the lifecycle.
    status: Mapped[PaymentStatus | None] = mapped_column(PAYMENT_STATUS_ENUM, nullable=True)
    response_data: Mapped[dict[str, Any] | None] = mapped_column(SNAPSHOT_JSON, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    payment: Mapped[Payment] = relationship(back_populates="transactions")

    def __repr__(self) -> str:
        return f"<PaymentTransaction {self.event_type}>"


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Refund foundation.

    Recording a refund here does not move money. Automatic gateway refunds
    require a configured provider API; until then a refund is a bookkeeping
    record that staff settle out of band.
    """

    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_refund_amount_positive"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        REFUND_STATUS_ENUM, nullable=False, default=RefundStatus.REQUESTED, index=True
    )
    provider_refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    payment: Mapped[Payment] = relationship(back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund {self.amount} {self.status}>"


class WebhookEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Record of every inbound gateway callback, used to make them idempotent.

    The unique constraint on (provider, external_id) is the actual idempotency
    guarantee: a duplicate delivery hits the constraint, is recognised as already
    seen, and short-circuits before any payment, stock, or notification work.

    `payload_fingerprint` covers providers that do not supply a usable event id —
    a hash of the body serves as the dedupe key instead.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_webhook_provider_external_id"),
        Index("ix_webhook_provider_created", "provider", "created_at"),
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        PAYMENT_PROVIDER_ENUM, nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Redacted payload, kept for support and dispute investigation.
    payload: Mapped[dict[str, Any] | None] = mapped_column(SNAPSHOT_JSON, nullable=True)
    signature_valid: Mapped[bool] = mapped_column(nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<WebhookEvent {self.provider} {self.external_id}>"
