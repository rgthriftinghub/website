"""Shared SQLAlchemy enum type instances.

Any native enum used by more than one table must be a *single* `Enum(...)`
instance. Two separate instances with the same `name` each try to emit
`CREATE TYPE`, and the second fails with "type already exists" during migration.
"""

from sqlalchemy import Enum

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

ORDER_STATUS_ENUM = Enum(OrderStatus, name="order_status")
PAYMENT_METHOD_ENUM = Enum(PaymentMethod, name="payment_method")
PAYMENT_STATUS_ENUM = Enum(PaymentStatus, name="payment_status")
PAYMENT_PROVIDER_ENUM = Enum(PaymentProvider, name="payment_provider")
PAYMENT_TRANSACTION_EVENT_ENUM = Enum(PaymentTransactionEvent, name="payment_transaction_event")
REFUND_STATUS_ENUM = Enum(RefundStatus, name="refund_status")
DELIVERY_METHOD_ENUM = Enum(DeliveryMethod, name="delivery_method")
COURIER_PROVIDER_ENUM = Enum(CourierProvider, name="courier_provider")
SHIPPING_STATUS_ENUM = Enum(ShippingStatus, name="shipping_status")
