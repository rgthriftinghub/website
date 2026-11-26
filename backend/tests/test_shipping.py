"""Shipping, courier, and public tracking tests."""

from decimal import Decimal

import pytest

from app.models.enums import CourierProvider, OrderStatus, ShippingStatus
from app.services.exceptions import InvalidRequestError, NotFoundError
from app.shipping_ops import service as shipping_service
from app.shipping_ops.base import ManualCourierProvider, UnconfiguredCourierProvider
from tests.factories import make_bank_account, make_order, make_shipping_method


# ------------------------------------------------------------ shipping methods
def test_configured_method_overrides_the_environment_default(db):
    """The admin-configured price is what checkout charges."""
    make_shipping_method(db, price=Decimal("399.00"), free_threshold=None)
    assert shipping_service.delivery_charge(db, Decimal("1000.00")) == Decimal("399.00")


def test_free_threshold_is_respected(db):
    make_shipping_method(db, price=Decimal("250.00"), free_threshold=Decimal("5000.00"))
    assert shipping_service.delivery_charge(db, Decimal("4999.00")) == Decimal("250.00")
    assert shipping_service.delivery_charge(db, Decimal("5000.00")) == Decimal("0.00")


def test_null_threshold_never_ships_free(db):
    make_shipping_method(db, price=Decimal("250.00"), free_threshold=None)
    assert shipping_service.delivery_charge(db, Decimal("999999.00")) == Decimal("250.00")


def test_empty_basket_is_never_charged_delivery(db):
    make_shipping_method(db, price=Decimal("250.00"))
    assert shipping_service.delivery_charge(db, Decimal("0.00")) == Decimal("0.00")


def test_inactive_method_falls_back_to_settings(db):
    """A deactivated method must not silently make delivery free."""
    make_shipping_method(db, price=Decimal("399.00"), is_active=False)
    charge = shipping_service.delivery_charge(db, Decimal("1000.00"))
    assert charge == Decimal("250.00")  # the environment default


def test_update_method_rejects_a_negative_price(db):
    method = make_shipping_method(db)
    with pytest.raises(InvalidRequestError, match="negative"):
        shipping_service.update_method(db, method.id, price=Decimal("-1.00"))


# -------------------------------------------------------------------- couriers
def test_manual_courier_is_the_only_configured_one():
    """Nothing may claim a courier API integration that does not exist."""
    registry = shipping_service.courier_registry()
    configured = [code for code, provider in registry.items() if provider.is_configured]
    assert configured == [CourierProvider.MANUAL]


def test_manual_courier_invents_no_tracking_number(db, customer_user):
    """A tracking number must come from a person, never be fabricated."""
    order = make_order(db, customer_user)
    shipment = shipping_service.ensure_shipment(db, order)
    booking = ManualCourierProvider().create_shipment(order, shipment)
    assert booking.tracking_number is None
    assert booking.shipment_id is None


def test_named_couriers_declare_what_they_need():
    for code, provider in shipping_service.courier_registry().items():
        if isinstance(provider, UnconfiguredCourierProvider):
            assert provider.is_configured is False
            assert provider.required_settings
            assert provider.integration_checklist
            assert "not implemented" in provider.configuration_hint


# ------------------------------------------------------------------- shipments
def test_order_placement_creates_a_pending_shipment(db, customer_user):
    order = make_order(db, customer_user)
    assert order.shipment is not None
    assert order.shipment.shipping_status is ShippingStatus.PENDING
    assert order.shipment.tracking_number is None


def test_ensure_shipment_is_idempotent(db, customer_user):
    order = make_order(db, customer_user)
    first = shipping_service.ensure_shipment(db, order)
    second = shipping_service.ensure_shipment(db, order)
    assert first.id == second.id


def test_assigning_tracking_number_moves_shipment_to_ready(db, customer_user, admin_user):
    order = make_order(db, customer_user)
    shipment = shipping_service.assign_courier(
        db,
        order.id,
        provider=CourierProvider.LEOPARDS,
        tracking_number="LE-123456789",
        actor=admin_user,
    )
    assert shipment.provider is CourierProvider.LEOPARDS
    assert shipment.tracking_number == "LE-123456789"
    assert shipment.shipping_status is ShippingStatus.READY
    assert shipment.is_trackable is True


def test_dispatch_requires_a_tracking_number(db, customer_user, admin_user):
    """Marking a parcel dispatched with no tracking number would be a lie."""
    order = make_order(db, customer_user)
    with pytest.raises(InvalidRequestError, match="tracking number"):
        shipping_service.update_shipping_status(
            db, order.id, ShippingStatus.READY, actor=admin_user
        )
        shipping_service.update_shipping_status(
            db, order.id, ShippingStatus.DISPATCHED, actor=admin_user
        )


def test_full_shipping_progression_records_history(db, customer_user, admin_user):
    order = make_order(db, customer_user)
    shipping_service.assign_courier(
        db, order.id, provider=CourierProvider.TCS, tracking_number="TCS-1", actor=admin_user
    )

    for target in (
        ShippingStatus.DISPATCHED,
        ShippingStatus.IN_TRANSIT,
        ShippingStatus.OUT_FOR_DELIVERY,
        ShippingStatus.DELIVERED,
    ):
        shipping_service.update_shipping_status(db, order.id, target, actor=admin_user)

    shipment = shipping_service.get_shipment_for_order(db, order.id)
    assert shipment.shipping_status is ShippingStatus.DELIVERED
    assert shipment.shipped_at is not None
    assert shipment.delivered_at is not None
    recorded = [event.status for event in shipment.events]
    assert ShippingStatus.DISPATCHED in recorded
    assert ShippingStatus.DELIVERED in recorded


def test_illegal_shipping_transition_is_refused(db, customer_user, admin_user):
    order = make_order(db, customer_user)
    # PENDING may only go to READY or CANCELLED.
    with pytest.raises(InvalidRequestError, match="Cannot move shipping"):
        shipping_service.update_shipping_status(
            db, order.id, ShippingStatus.DELIVERED, actor=admin_user
        )


def test_shipping_status_does_not_rewrite_order_status(db, customer_user, admin_user):
    """The two are deliberately independent."""
    order = make_order(db, customer_user)
    shipping_service.assign_courier(
        db, order.id, provider=CourierProvider.MANUAL, tracking_number="MAN-1", actor=admin_user
    )
    shipping_service.update_shipping_status(
        db, order.id, ShippingStatus.DISPATCHED, actor=admin_user
    )
    db.refresh(order)
    # Order is still PENDING; only the shipment moved.
    assert order.order_status is OrderStatus.PENDING


def test_repeating_the_same_shipping_status_is_refused(db, customer_user, admin_user):
    order = make_order(db, customer_user)
    with pytest.raises(InvalidRequestError, match="already"):
        shipping_service.update_shipping_status(
            db, order.id, ShippingStatus.PENDING, actor=admin_user
        )


# -------------------------------------------------------------- bank accounts
def test_only_active_bank_accounts_are_published(db):
    active = make_bank_account(db, is_active=True)
    make_bank_account(db, is_active=False)
    published = shipping_service.active_bank_accounts(db)
    assert [account.id for account in published] == [active.id]


# ------------------------------------------------------------ public tracking
def test_tracking_succeeds_with_the_order_email(db, customer_user):
    order = make_order(db, customer_user)
    found = shipping_service.track_by_order_number(
        db, order.order_number, contact=order.contact_email
    )
    assert found.id == order.id


def test_tracking_succeeds_with_the_order_phone(db, customer_user):
    order = make_order(db, customer_user)
    found = shipping_service.track_by_order_number(
        db, order.order_number, contact=order.contact_phone
    )
    assert found.id == order.id


def test_tracking_matches_a_differently_formatted_phone(db, customer_user):
    """A customer typing their number with different spacing still matches."""
    order = make_order(db, customer_user)
    digits = "".join(char for char in order.contact_phone if char.isdigit())
    found = shipping_service.track_by_order_number(db, order.order_number, contact=digits)
    assert found.id == order.id


def test_tracking_rejects_a_wrong_contact(db, customer_user):
    order = make_order(db, customer_user)
    with pytest.raises(NotFoundError):
        shipping_service.track_by_order_number(
            db, order.order_number, contact="someone-else@example.com"
        )


def test_tracking_rejects_an_unknown_order_with_the_same_error(db, customer_user):
    """Identical failures, so this cannot be used to enumerate order numbers."""
    order = make_order(db, customer_user)

    wrong_contact = None
    unknown_order = None
    try:
        shipping_service.track_by_order_number(
            db, order.order_number, contact="nope@example.com"
        )
    except NotFoundError as exc:
        wrong_contact = str(exc)
    try:
        shipping_service.track_by_order_number(
            db, "RG-19990101-9999", contact=order.contact_email
        )
    except NotFoundError as exc:
        unknown_order = str(exc)

    assert wrong_contact == unknown_order


def test_tracking_rejects_a_blank_contact(db, customer_user):
    order = make_order(db, customer_user)
    with pytest.raises(NotFoundError):
        shipping_service.track_by_order_number(db, order.order_number, contact="   ")


def test_tracking_endpoint_exposes_no_private_detail(db, client, customer_user):
    """The public response must not leak the address, prices, or identity."""
    order = make_order(db, customer_user)
    response = client.post(
        "/api/v1/track-order",
        json={"order_number": order.order_number, "contact": order.contact_email},
    )
    assert response.status_code == 200, response.text
    body = response.text.lower()

    assert "gulberg" not in body          # address line
    assert "house 14" not in body
    assert "total_amount" not in body     # money
    assert "shipping_address" not in body
    payload = response.json()
    assert payload["order_number"] == order.order_number
    assert payload["shipping_status"] == "PENDING"


def test_tracking_endpoint_returns_404_for_a_bad_contact(db, client, customer_user):
    order = make_order(db, customer_user)
    response = client.post(
        "/api/v1/track-order",
        json={"order_number": order.order_number, "contact": "wrong@example.com"},
    )
    assert response.status_code == 404


def test_tracking_endpoint_rate_limits_repeated_attempts(client):
    from app.core.rate_limit import _events

    _events.pop("testclient", None)
    payload = {"order_number": "RG-UNKNOWN-1234", "contact": "nobody@example.com"}
    for _ in range(10):
        assert client.post("/api/v1/track-order", json=payload).status_code == 404

    limited = client.post("/api/v1/track-order", json=payload)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "900"
