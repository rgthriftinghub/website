"""Authorization and error-surface tests for payments and shipping.

Covers the two rules that matter most here: a customer can never reach an admin
payment action, and no internal detail (stack traces, SQL, credentials, gateway
payloads) escapes to a client.
"""

import uuid

import pytest

from app.core.config import get_settings
from app.notifications import templates
from app.services import notifications
from tests.factories import make_order

# Every admin payment/shipping route, as (method, path template).
ADMIN_ROUTES = [
    ("get", "/api/v1/admin/payments"),
    ("get", "/api/v1/admin/payments/stats"),
    ("get", "/api/v1/admin/shipping/methods"),
    ("get", "/api/v1/admin/shipping/couriers"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_anonymous_cannot_reach_admin_payment_routes(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_customer_cannot_reach_admin_payment_routes(customer_client, method, path):
    response = getattr(customer_client, method)(path)
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("client_name", ["admin_client", "staff_client"])
def test_admin_and_staff_can_reach_payment_routes(request, client_name):
    signed_in = request.getfixturevalue(client_name)
    for method, path in ADMIN_ROUTES:
        response = getattr(signed_in, method)(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"


def test_customer_cannot_verify_their_own_payment(db, customer_client, customer_user):
    """The obvious privilege escalation: self-approving a bank transfer."""
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    payment_id = order.active_payment.id

    response = customer_client.post(
        f"/api/v1/admin/payments/{payment_id}/verify-bank-transfer", json={}
    )
    assert response.status_code == 403

    db.refresh(order)
    assert str(order.payment_status) == "PENDING"


def test_customer_cannot_read_another_customers_payment(
    db, customer_client, customer_user
):
    from app.models.enums import UserRole
    from tests.conftest import create_user

    other, _ = create_user(db, UserRole.CUSTOMER)
    other_order = make_order(db, other, payment_method="COD")

    response = customer_client.get(
        f"/api/v1/customer/orders/{other_order.order_number}/payment"
    )
    assert response.status_code == 404


def test_customer_payment_response_hides_gateway_and_staff_fields(
    db, customer_client, customer_user
):
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    response = customer_client.get(
        f"/api/v1/customer/orders/{order.order_number}/payment"
    )
    assert response.status_code == 200
    body = response.json()

    for forbidden in ("raw_response", "internal_note", "verified_by_user_id", "proof_url"):
        assert forbidden not in body, f"{forbidden} leaked to the customer"


def test_webhook_for_unknown_provider_slug_is_not_an_error_leak(client):
    """An unknown slug must not confirm which providers exist."""
    response = client.post("/api/v1/payments/not-a-provider/webhook", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is False
    assert "Unknown provider" in body["detail"]


def test_webhook_response_never_echoes_the_payload(client):
    """A reflected payload would be an injection and disclosure vector."""
    secret_marker = "SUPER-SECRET-MARKER-1234"
    response = client.post(
        "/api/v1/payments/payfast/webhook",
        json={"password": secret_marker, "amount": "1.00"},
        headers={"x-signature": "invalid"},
    )
    assert response.status_code == 200
    assert secret_marker not in response.text


def test_unconfigured_gateway_webhook_is_rejected_cleanly(client):
    """No stack trace, no provider internals — just a clean refusal."""
    response = client.post(
        "/api/v1/payments/jazzcash/webhook", json={"status": "PAID"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is False
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()


def test_provider_listing_never_claims_an_unbuilt_gateway_is_live(client):
    response = client.get("/api/v1/payments/providers")
    assert response.status_code == 200
    providers = {row["code"]: row for row in response.json()}

    for gateway in ("PAYFAST", "SAFEPAY", "JAZZCASH", "EASYPAISA"):
        assert providers[gateway]["is_live"] is False, f"{gateway} claims to be live"
        assert providers[gateway]["integration_checklist"]

    assert providers["COD"]["is_live"] is True
    assert providers["BANK_TRANSFER"]["is_live"] is True


def test_provider_listing_does_not_expose_credential_values(client):
    """Only names of missing settings, never their values."""
    settings = get_settings()
    response = client.get("/api/v1/payments/providers")
    body = response.text

    for secret in (
        settings.secret_key,
        settings.jwt_secret_key,
        settings.database_url,
    ):
        assert secret not in body


def test_checkout_rejects_an_unconfigured_payment_method(db, customer_client, customer_user):
    """The API surface must refuse a gateway that cannot process anything."""
    from tests.factories import make_address, make_shop_setup, seed_cart

    _, variant = make_shop_setup(db)
    address = make_address(db, customer_user.id)
    seed_cart(db, customer_user.id, variant.id, 1)

    response = customer_client.post(
        "/api/v1/checkout",
        json={"address_id": str(address.id), "payment_method": "PAYFAST"},
    )
    assert response.status_code == 422
    assert "not available yet" in response.text


def test_invalid_payment_id_returns_404_not_500(admin_client):
    response = admin_client.get(f"/api/v1/admin/payments/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "Traceback" not in response.text


# ------------------------------------------------------------- notifications
def test_notification_fires_once_per_real_change(db, customer_user):
    recorder = notifications.LoggingNotificationService()
    notifications.set_notification_service(recorder)
    try:
        make_order(db, customer_user, payment_method="COD")
    finally:
        notifications.set_notification_service(None)

    created = [
        event for event, _, _ in recorder.sent
        if event is notifications.NotificationEvent.ORDER_CREATED
    ]
    assert len(created) == 1


def test_notification_failure_never_breaks_the_operation(db, customer_user):
    """A broken mail transport must not roll back a successful order."""

    class ExplodingService:
        def notify(self, event, *, recipient, context):
            raise RuntimeError("mail server down")

    notifications.set_notification_service(ExplodingService())
    try:
        order = make_order(db, customer_user, payment_method="COD")
    finally:
        notifications.set_notification_service(None)

    assert order.order_number  # the order still committed


def test_every_notification_event_renders_a_template():
    """A missing template would silently send a generic email."""
    context = {
        "order_number": "RG-20260812-0001",
        "total_amount": "PKR 5,250",
        "payment_method_label": "Cash on Delivery",
        "items": [
            {"name": "Test Jeans", "variant": "Waist 32", "quantity": 1,
             "line_total": "PKR 5,000"}
        ],
    }
    for event in notifications.NotificationEvent:
        rendered = templates.render(event.value, context)
        assert rendered.subject
        assert "RG-20260812-0001" in rendered.subject or "order" in rendered.subject.lower()
        assert rendered.html.startswith("<!doctype html>")
        assert "RG-20260812-0001" in rendered.text
        # Branding must be present in every message.
        assert "RG Thrifting Hub" in rendered.html


def test_template_includes_the_logo_and_brand_palette():
    rendered = templates.render("order_created", {"order_number": "RG-1"})
    assert "/brand/logo.png" in rendered.html
    assert "#C39A51" in rendered.html  # brand gold


def test_logging_transports_report_themselves_as_not_live():
    """Development transports must never claim delivery."""
    from app.notifications.transports import (
        LoggingEmailTransport,
        LoggingWhatsAppTransport,
    )

    assert LoggingEmailTransport().is_live is False
    assert LoggingWhatsAppTransport().is_live is False
