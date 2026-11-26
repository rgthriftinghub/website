"""Payment, shipping, and tracking schemas.

No request schema here accepts an amount, a status, an order id chosen by the
client, or a transaction id. Those are all derived server-side; a client may only
identify *which* order it is acting on and supply human information such as a
bank reference.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    CourierProvider,
    DeliveryMethod,
    OrderStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionEvent,
    RefundStatus,
    ShippingStatus,
)


# ------------------------------------------------------------------- payments
class PaymentTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: PaymentTransactionEvent
    provider_transaction_id: str | None
    amount: Decimal | None
    status: PaymentStatus | None
    message: str | None
    created_at: datetime


class RefundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    reason: str
    status: RefundStatus
    provider_refund_id: str | None
    created_at: datetime


class PaymentRead(BaseModel):
    """Customer-facing payment view.

    `raw_response` and `internal_note` are deliberately absent: a customer has no
    business seeing gateway payloads or staff notes.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: PaymentProvider
    payment_method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    currency: str
    customer_reference: str | None
    proof_submitted_at: datetime | None
    failure_reason: str | None
    paid_at: datetime | None
    created_at: datetime


class PaymentAdminRead(PaymentRead):
    """Admin view. Adds the audit trail, redacted gateway payload, and staff notes."""

    order_id: uuid.UUID
    order_number: str
    customer_email: str
    customer_name: str
    provider_transaction_id: str | None
    customer_note: str | None
    proof_url: str | None
    internal_note: str | None
    verified_at: datetime | None
    raw_response: dict[str, Any] | None
    transactions: list[PaymentTransactionRead] = Field(default_factory=list)
    refunds: list[RefundRead] = Field(default_factory=list)
    updated_at: datetime


class PaymentIntentRead(BaseModel):
    """How the customer should continue a payment.

    Carries no authoritative status — a frontend cannot conclude success from it.
    """

    payment_id: uuid.UUID
    provider: PaymentProvider
    status: PaymentStatus
    requires_redirect: bool
    redirect_url: str | None = None
    form_action: str | None = None
    form_fields: dict[str, str] = Field(default_factory=dict)
    instructions: str | None = None
    reference: str | None = None


class BankAccountRead(BaseModel):
    """The store's own published receiving details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bank_name: str
    account_title: str
    account_number: str
    iban: str | None
    branch: str | None
    instructions: str | None


class BankTransferSubmission(BaseModel):
    """What a customer tells us about a transfer they made.

    No banking credentials are accepted or stored — only the reference they quote.
    """

    reference: str = Field(min_length=3, max_length=120)
    note: str | None = Field(default=None, max_length=1000)
    # A URL to a slip the customer uploaded elsewhere. File upload is not
    # implemented in this phase.
    proof_url: str | None = Field(default=None, max_length=500)

    @field_validator("reference")
    @classmethod
    def strip_reference(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class PaymentVerifyRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class PaymentRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=3, max_length=300)


class ProviderStatusRead(BaseModel):
    """Whether a provider can actually be used, and what it still needs.

    `is_live` distinguishes a working integration from one that is merely
    declared, so the admin surface never implies a gateway is ready when it is not.
    """

    code: str
    display_name: str
    is_live: bool
    has_credentials: bool
    configuration_hint: str
    integration_checklist: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------- shipping
class ShippingMethodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: DeliveryMethod
    name: str
    description: str | None
    price: Decimal
    free_threshold: Decimal | None
    estimated_days_min: int | None
    estimated_days_max: int | None
    is_active: bool


class ShippingMethodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    free_threshold: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None


class ShipmentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ShippingStatus
    note: str | None
    location: str | None
    created_at: datetime


class ShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: CourierProvider
    tracking_number: str | None
    shipment_id: str | None
    shipping_status: ShippingStatus
    label_url: str | None
    tracking_url: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    events: list[ShipmentEventRead] = Field(default_factory=list)


class ShipmentAdminRead(ShipmentRead):
    notes: str | None


class CourierAssignRequest(BaseModel):
    provider: CourierProvider
    tracking_number: str | None = Field(default=None, max_length=120)
    shipment_reference: str | None = Field(default=None, max_length=128)
    tracking_url: str | None = Field(default=None, max_length=500)
    label_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class ShippingStatusUpdate(BaseModel):
    status: ShippingStatus
    note: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=160)


class CourierStatusRead(BaseModel):
    code: str
    display_name: str
    is_automated: bool
    is_configured: bool
    configuration_hint: str


# ------------------------------------------------------------------- tracking
class TrackingRequest(BaseModel):
    """Public tracking lookup.

    Requires both the order number and a matching contact detail, so an order
    number alone never exposes anyone's delivery address.
    """

    order_number: str = Field(min_length=4, max_length=32)
    contact: str = Field(min_length=3, max_length=320)


class TrackingItemRead(BaseModel):
    name: str
    variant_label: str
    quantity: int


class TrackingRead(BaseModel):
    """Deliberately minimal. No address, no prices, no customer identity."""

    order_number: str
    order_status: OrderStatus
    payment_status: PaymentStatus
    placed_at: datetime
    item_count: int
    items: list[TrackingItemRead]
    shipping_status: ShippingStatus | None
    courier: CourierProvider | None
    tracking_number: str | None
    tracking_url: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    status_history: list[ShipmentEventRead] = Field(default_factory=list)
