"""Shipping configuration and shipment lifecycle.

Shipping status is kept strictly separate from order status. They describe
different things and move on different clocks: an order can be DISPATCHED while
its shipment is still IN_TRANSIT, and DELIVERED while payment is PENDING.

Where they *do* relate, the relationship is one-way and explicit: marking a
shipment delivered offers to advance the order, it never silently rewrites it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.enums import (
    SHIPPING_STATUS_TRANSITIONS,
    CourierProvider,
    DeliveryMethod,
    ShippingStatus,
)
from app.models.order import Order
from app.models.shipping import BankAccount, Shipment, ShipmentEvent, ShippingMethod
from app.models.user import User
from app.services import notifications
from app.services.exceptions import InvalidRequestError, NotFoundError
from app.shipping_ops.base import (
    BaseCourierProvider,
    LeopardsProvider,
    ManualCourierProvider,
    MPProvider,
    PostExProvider,
    TCSProvider,
    TraxProvider,
)

# Statuses that mean the parcel has physically left us.
DISPATCHED_STATUSES = frozenset(
    {
        ShippingStatus.DISPATCHED,
        ShippingStatus.IN_TRANSIT,
        ShippingStatus.OUT_FOR_DELIVERY,
    }
)


def _build_registry() -> dict[CourierProvider, BaseCourierProvider]:
    providers: list[BaseCourierProvider] = [
        ManualCourierProvider(),
        TCSProvider(),
        LeopardsProvider(),
        MPProvider(),
        TraxProvider(),
        PostExProvider(),
    ]
    return {provider.code: provider for provider in providers}


_registry: dict[CourierProvider, BaseCourierProvider] | None = None


def courier_registry() -> dict[CourierProvider, BaseCourierProvider]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def get_courier(code: CourierProvider) -> BaseCourierProvider:
    provider = courier_registry().get(code)
    if provider is None:
        raise NotFoundError(f"Unknown courier: {code}")
    return provider


# ------------------------------------------------------------ shipping methods
def active_methods(db: Session) -> list[ShippingMethod]:
    return list(
        db.execute(
            select(ShippingMethod)
            .where(ShippingMethod.is_active.is_(True))
            .order_by(ShippingMethod.sort_order, ShippingMethod.name)
        )
        .scalars()
        .all()
    )


def method_for(db: Session, code: DeliveryMethod) -> ShippingMethod | None:
    return db.execute(
        select(ShippingMethod).where(
            ShippingMethod.code == code, ShippingMethod.is_active.is_(True)
        )
    ).scalar_one_or_none()


def delivery_charge(
    db: Session, subtotal: Decimal, code: DeliveryMethod = DeliveryMethod.STANDARD
) -> Decimal:
    """Charge for a subtotal, preferring the admin-configured method row.

    Falls back to the environment settings when no active method exists, so a
    fresh database without seeded shipping methods still prices correctly.
    """
    method = method_for(db, code)
    if method is not None:
        return method.charge_for(subtotal)

    settings = get_settings()
    if subtotal <= 0:
        return Decimal("0.00")
    threshold = settings.free_delivery_threshold
    if threshold > 0 and subtotal >= threshold:
        return Decimal("0.00")
    return Decimal(settings.standard_delivery_charge)


def update_method(
    db: Session,
    method_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    price: Decimal | None = None,
    free_threshold: Decimal | None = None,
    is_active: bool | None = None,
) -> ShippingMethod:
    method = db.get(ShippingMethod, method_id)
    if method is None:
        raise NotFoundError("Shipping method not found")
    if price is not None and price < 0:
        raise InvalidRequestError("Price cannot be negative")

    if name is not None:
        method.name = name
    if description is not None:
        method.description = description
    if price is not None:
        method.price = price
    if free_threshold is not None:
        method.free_threshold = free_threshold
    if is_active is not None:
        method.is_active = is_active
    db.commit()
    db.refresh(method)
    return method


# --------------------------------------------------------------- bank accounts
def active_bank_accounts(db: Session) -> list[BankAccount]:
    return list(
        db.execute(
            select(BankAccount)
            .where(BankAccount.is_active.is_(True))
            .order_by(BankAccount.sort_order, BankAccount.bank_name)
        )
        .scalars()
        .all()
    )


# -------------------------------------------------------------------- shipments
def get_shipment_for_order(db: Session, order_id: uuid.UUID) -> Shipment | None:
    return (
        db.execute(
            select(Shipment)
            .where(Shipment.order_id == order_id)
            .options(selectinload(Shipment.events))
        )
        .unique()
        .scalar_one_or_none()
    )


def ensure_shipment(db: Session, order: Order) -> Shipment:
    """Get or create the shipment record for an order."""
    existing = get_shipment_for_order(db, order.id)
    if existing is not None:
        return existing
    shipment = Shipment(
        order_id=order.id,
        provider=CourierProvider.MANUAL,
        shipping_status=ShippingStatus.PENDING,
    )
    db.add(shipment)
    db.flush()
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            status=ShippingStatus.PENDING,
            note="Shipment record created",
        )
    )
    return shipment


def assign_courier(
    db: Session,
    order_id: uuid.UUID,
    *,
    provider: CourierProvider,
    tracking_number: str | None = None,
    shipment_reference: str | None = None,
    tracking_url: str | None = None,
    label_url: str | None = None,
    notes: str | None = None,
    actor: User,
) -> Shipment:
    """Record courier details for an order.

    With no courier API connected this is how a tracking number gets here: a
    person books the consignment and types the number in. The provider's
    `create_shipment` is still invoked so a future automated courier slots in
    without changing this call site.
    """
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")

    shipment = ensure_shipment(db, order)
    courier = get_courier(provider)
    shipment.provider = provider

    booking = courier.create_shipment(order, shipment)
    # A real courier returns identifiers; the manual provider returns nothing and
    # the staff-supplied values below stand alone.
    if booking.tracking_number:
        shipment.tracking_number = booking.tracking_number
    if booking.shipment_id:
        shipment.shipment_id = booking.shipment_id
    if booking.label_url:
        shipment.label_url = booking.label_url
    if booking.tracking_url:
        shipment.tracking_url = booking.tracking_url
    if booking.raw:
        shipment.provider_response = booking.raw

    if tracking_number is not None:
        shipment.tracking_number = tracking_number.strip() or None
    if shipment_reference is not None:
        shipment.shipment_id = shipment_reference.strip() or None
    if tracking_url is not None:
        shipment.tracking_url = tracking_url.strip() or None
    if label_url is not None:
        shipment.label_url = label_url.strip() or None
    if notes is not None:
        shipment.notes = notes

    # Having a tracking number means the parcel is at least ready to go.
    if shipment.tracking_number and shipment.shipping_status is ShippingStatus.PENDING:
        shipment.shipping_status = ShippingStatus.READY
        db.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                status=ShippingStatus.READY,
                note=f"{courier.display_name} · {shipment.tracking_number}",
                changed_by_user_id=actor.id,
            )
        )

    db.commit()
    db.refresh(shipment)
    return shipment


def update_shipping_status(
    db: Session,
    order_id: uuid.UUID,
    new_status: ShippingStatus,
    *,
    actor: User,
    note: str | None = None,
    location: str | None = None,
) -> Shipment:
    """Advance shipping status, validated against the transition table."""
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")

    shipment = ensure_shipment(db, order)
    current = shipment.shipping_status
    if new_status == current:
        raise InvalidRequestError(f"Shipping is already {current}")

    allowed = SHIPPING_STATUS_TRANSITIONS.get(current, frozenset())
    if new_status not in allowed:
        permitted = ", ".join(sorted(str(s) for s in allowed)) or "no further changes"
        raise InvalidRequestError(
            f"Cannot move shipping from {current} to {new_status}. Allowed: {permitted}"
        )

    if new_status in DISPATCHED_STATUSES and not shipment.tracking_number:
        raise InvalidRequestError(
            "Add a tracking number before marking the shipment dispatched"
        )

    shipment.shipping_status = new_status
    if new_status is ShippingStatus.DISPATCHED and shipment.shipped_at is None:
        shipment.shipped_at = datetime.now(UTC)
    if new_status is ShippingStatus.DELIVERED:
        shipment.delivered_at = datetime.now(UTC)

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            status=new_status,
            note=note,
            location=location,
            changed_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(shipment)

    # Order status is never rewritten silently here; the customer is simply told
    # the shipping picture changed.
    order.shipment = shipment
    notifications.notify_order_event(
        notifications.NotificationEvent.SHIPPING_UPDATED,
        order,
        shipping_status=str(new_status),
        tracking_number=shipment.tracking_number,
    )
    return shipment


# ------------------------------------------------------------ customer tracking
def track_by_order_number(
    db: Session, order_number: str, *, contact: str
) -> Order:
    """Public order lookup, gated on a matching contact detail.

    An order number alone is never enough: the caller must also supply the email
    or phone on the order. Both are compared case-insensitively, and phone
    comparison ignores spaces and punctuation so a customer typing their number
    differently still matches.
    """
    order = (
        db.execute(
            select(Order)
            .where(Order.order_number == order_number.strip().upper())
            .options(
                selectinload(Order.items),
                selectinload(Order.status_events),
                selectinload(Order.shipment).selectinload(Shipment.events),
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    # Identical failure for "no such order" and "wrong contact", so this endpoint
    # cannot be used to discover which order numbers exist.
    failure = NotFoundError(
        "We could not find an order with that number and contact detail."
    )
    if order is None:
        raise failure

    supplied = contact.strip().lower()
    if not supplied:
        raise failure

    def digits(value: str | None) -> str:
        return "".join(char for char in (value or "") if char.isdigit())

    email_match = (order.contact_email or "").strip().lower() == supplied
    supplied_digits = digits(supplied)
    phone_match = bool(supplied_digits) and digits(order.contact_phone).endswith(
        supplied_digits[-9:]
    )

    if not (email_match or phone_match):
        raise failure
    return order
