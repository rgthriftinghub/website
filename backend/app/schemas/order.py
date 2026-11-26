"""Order, checkout, and return-request schemas."""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import (
    DeliveryMethod,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ReturnRequestStatus,
    ReturnRequestType,
    SELECTABLE_PAYMENT_METHODS,
)
from app.schemas.address import AddressSnapshot
from app.schemas.cart import CartLineInput
from app.schemas.payment import PaymentRead, ShipmentRead


# ------------------------------------------------------------------- checkout
class CheckoutConfig(BaseModel):
    """Delivery pricing and payment options, served from backend configuration.

    The storefront reads this instead of hardcoding charges or method lists.
    """

    currency: str
    standard_delivery_charge: Decimal
    free_delivery_threshold: Decimal | None
    payment_methods: list[PaymentMethod]
    delivery_methods: list[DeliveryMethod]
    max_quantity_per_item: int
    jazzcash_number: str | None = None
    easypaisa_number: str | None = None
    payment_whatsapp_number: str | None = None


class CheckoutRequest(BaseModel):
    """Everything the customer chooses. Notably absent: any monetary amount."""

    address_id: uuid.UUID
    payment_method: PaymentMethod
    delivery_method: DeliveryMethod = DeliveryMethod.STANDARD
    # Optional overrides; they default to the account email and address phone.
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32)
    customer_note: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(default=None, max_length=40)

    @field_validator("payment_method")
    @classmethod
    def only_available_methods(cls, value: PaymentMethod) -> PaymentMethod:
        """Reject any method whose provider cannot actually process a payment.

        The allowed set is read from the live provider registry rather than a
        constant, so an unconfigured gateway is unselectable automatically.
        Imported lazily to keep the schema module free of service dependencies.
        """
        from app.payments.service import selectable_methods

        allowed = selectable_methods() or SELECTABLE_PAYMENT_METHODS
        if value not in allowed:
            available = ", ".join(sorted(m.value for m in allowed))
            raise ValueError(f"{value} is not available yet. Choose one of: {available}")
        return value


class GuestDeliveryDetails(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=32)
    address_line_1: str = Field(min_length=5, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    province: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="Pakistan", min_length=2, max_length=80)

    @field_validator(
        "full_name", "address_line_1", "address_line_2", "city", "province", "country",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"\+?[0-9 ().-]+", value):
            raise ValueError("Enter a valid phone number with 7 to 15 digits")
        return value


class GuestCheckoutRequest(BaseModel):
    items: list[CartLineInput] = Field(min_length=1, max_length=50)
    delivery: GuestDeliveryDetails
    payment_method: PaymentMethod = PaymentMethod.COD
    delivery_method: DeliveryMethod = DeliveryMethod.STANDARD
    contact_email: EmailStr | None = None
    customer_note: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def cod_only_and_unique_variants(self) -> "GuestCheckoutRequest":
        if self.payment_method is not PaymentMethod.COD:
            raise ValueError("Guest checkout currently supports Cash on Delivery")
        ids = [item.product_variant_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each size can appear only once in the bag")
        return self


# --------------------------------------------------------------------- orders
class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID | None
    product_variant_id: uuid.UUID | None
    product_name_snapshot: str
    product_slug_snapshot: str
    brand_name_snapshot: str | None
    sku_snapshot: str
    variant_snapshot: dict[str, Any]
    variant_label: str
    image_url_snapshot: str | None
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: OrderStatus
    note: str | None
    created_at: datetime


class ReturnRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ReturnRequestType
    reason: str
    description: str | None
    status: ReturnRequestStatus
    created_at: datetime
    updated_at: datetime


class OrderSummary(BaseModel):
    """Row shape for the customer's order list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    order_status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    coupon_code: str | None = None
    total_amount: Decimal
    item_count: int
    created_at: datetime


class OrderRead(OrderSummary):
    """Customer-facing detail. `internal_note` is deliberately not declared."""

    contact_email: str | None
    contact_phone: str
    shipping_address_snapshot: AddressSnapshot
    billing_address_snapshot: AddressSnapshot | None
    delivery_method: DeliveryMethod
    subtotal: Decimal
    discount_amount: Decimal
    shipping_amount: Decimal
    customer_note: str | None
    cancelled_at: datetime | None
    updated_at: datetime
    is_cancellable_by_customer: bool
    items: list[OrderItemRead]
    status_events: list[OrderStatusEventRead]
    return_requests: list[ReturnRequestRead]
    # Shipping progresses independently of order status, so the customer sees both.
    shipment: "ShipmentRead | None" = None
    # The active payment only. Gateway payloads and staff notes are not on
    # `PaymentRead`, so nothing internal reaches a customer through this.
    payment: "PaymentRead | None" = None


class OrderCustomerSummary(BaseModel):
    """Who placed the order, for admin listings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None
    email: str | None
    first_name: str
    last_name: str
    is_guest: bool = False


class OrderAdminSummary(OrderSummary):
    customer: OrderCustomerSummary


class OrderAdminRead(OrderRead):
    """Admin detail. Adds the customer record and staff-only notes."""

    customer: OrderCustomerSummary
    internal_note: str | None


# ----------------------------------------------------------- status + returns
class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=500)


class PaymentStatusUpdate(BaseModel):
    payment_status: PaymentStatus
    note: str | None = Field(default=None, max_length=500)


class InternalNoteUpdate(BaseModel):
    internal_note: str | None = Field(default=None, max_length=2000)


class OrderCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReturnRequestCreate(BaseModel):
    type: ReturnRequestType
    reason: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class ReturnRequestDecision(BaseModel):
    status: ReturnRequestStatus
    resolution_note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def not_back_to_requested(cls, value: ReturnRequestStatus) -> ReturnRequestStatus:
        if value is ReturnRequestStatus.REQUESTED:
            raise ValueError("A decision cannot set the status back to REQUESTED")
        return value


class ReturnRequestAdminRead(ReturnRequestRead):
    order_id: uuid.UUID
    order_number: str
    resolution_note: str | None


# ------------------------------------------------------------------ inventory
class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_variant_id: uuid.UUID
    type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reference_type: str | None
    reference_id: str | None
    note: str | None
    created_at: datetime
