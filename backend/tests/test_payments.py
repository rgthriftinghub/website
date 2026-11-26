"""Payment tests.

No real gateway credentials are used anywhere. Gateway behaviour is exercised
through a `FakeGatewayProvider` registered into the provider registry — the same
`BasePaymentProvider` contract a real integration would implement — which is what
lets webhook verification, idempotency, and notification behaviour be tested
honestly without inventing any provider's actual API.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from app.models.enums import (
    DeliveryMethod,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionEvent,
    RefundStatus,
)
from app.models.payment import Payment, WebhookEvent
from app.payments import service as payment_service
from app.payments.base import (
    BasePaymentProvider,
    ParsedWebhook,
    PaymentIntent,
    ProviderNotConfigured,
    WebhookVerificationError,
    fingerprint,
    redact,
)
from app.payments.providers.gateways import build_gateway_providers
from app.services import notifications
from app.services.exceptions import InvalidRequestError
from tests.conftest import create_user
from tests.factories import make_order, make_shop_setup




# --------------------------------------------------------------- fake provider
@dataclass
class FakeGatewayProvider(BasePaymentProvider):
    """Stand-in for a real gateway, used only in tests.

    Implements the same contract a live provider would. Its "signature" check is a
    single header equality, which is enough to prove the *framework* rejects
    unverified messages without pretending to model any real algorithm.
    """

    code: PaymentProvider = PaymentProvider.PAYFAST
    display_name: str = "Fake Gateway"
    secret: str = "test-signature"
    next_status: PaymentStatus = PaymentStatus.PAID
    event_id: str = "evt-1"
    payment_reference: str | None = None
    provider_txn: str = "gw-txn-1"
    amount: Decimal | None = None
    calls: list[str] = field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return True

    def create_payment(self, db, payment, order) -> PaymentIntent:
        self.calls.append("create_payment")
        return PaymentIntent(
            payment_id=str(payment.id),
            provider=self.code,
            status=PaymentStatus.PENDING,
            requires_redirect=True,
            redirect_url="https://gateway.example/checkout/abc",
        )

    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhook:
        if headers.get("x-signature") != self.secret:
            raise WebhookVerificationError("Signature mismatch")
        return ParsedWebhook(
            external_id=self.event_id,
            payment_reference=self.payment_reference,
            status=self.next_status,
            provider_transaction_id=self.provider_txn,
            amount=self.amount,
            failure_reason=None if self.next_status is PaymentStatus.PAID else "Declined",
            payload={"event": self.event_id, "status": str(self.next_status)},
        )

    def parse_callback(self, params: dict[str, Any]) -> ParsedWebhook:
        return self.parse_webhook(b"", {"x-signature": params.get("sig", "")})


@pytest.fixture
def fake_gateway():
    """Register a fake gateway, then restore the real registry."""
    provider = FakeGatewayProvider()
    original = payment_service.registry().copy()
    payment_service.registry()[PaymentProvider.PAYFAST] = provider
    payment_service.METHOD_TO_PROVIDER[PaymentMethod.PAYFAST] = PaymentProvider.PAYFAST
    yield provider
    payment_service._registry = original


@pytest.fixture
def recorder():
    """Capture notifications instead of rendering and sending them."""
    service = notifications.LoggingNotificationService()
    notifications.set_notification_service(service)
    yield service
    notifications.set_notification_service(None)


# ------------------------------------------------------------------ COD basics
def test_cod_order_creates_pending_payment(db, customer_user):
    """COD must never be born PAID — nothing has been collected yet."""
    order = make_order(db, customer_user, payment_method="COD")

    payment = db.execute(
        select(Payment).where(Payment.order_id == order.id)
    ).scalar_one()

    assert payment.provider is PaymentProvider.COD
    assert payment.status is PaymentStatus.PENDING
    assert payment.paid_at is None
    assert payment.amount == order.total_amount
    assert order.payment_status is PaymentStatus.PENDING
    # The audit trail starts immediately.
    assert [tx.event_type for tx in payment.transactions] == [
        PaymentTransactionEvent.INITIATED
    ]


def test_cod_marked_collected_by_staff(db, customer_user, admin_user, recorder):
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment

    updated = payment_service.mark_cod_collected(
        db, payment.id, actor=admin_user, note="Courier handed cash in"
    )

    assert updated.status is PaymentStatus.PAID
    assert updated.paid_at is not None
    assert updated.verified_by_user_id == admin_user.id
    db.refresh(order)
    assert order.payment_status is PaymentStatus.PAID
    assert any(event is notifications.NotificationEvent.PAYMENT_RECEIVED
               for event, _, _ in recorder.sent)


def test_cod_cannot_be_verified_as_bank_transfer(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    with pytest.raises(InvalidRequestError, match="bank transfers"):
        payment_service.verify_bank_transfer(
            db, order.active_payment.id, actor=admin_user
        )


# ---------------------------------------------------------- bank transfer flow
def test_bank_transfer_submission_does_not_mark_paid(db, customer_user):
    """A customer's own claim must never settle a payment."""
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")

    payment = payment_service.submit_bank_transfer_proof(
        db,
        order.user_id,
        order.order_number,
        reference="TRX-99881",
        note="Sent from Meezan",
    )

    assert payment.status is PaymentStatus.PENDING
    assert payment.customer_reference == "TRX-99881"
    assert payment.proof_submitted_at is not None
    assert payment.awaiting_verification is True
    assert PaymentTransactionEvent.PROOF_SUBMITTED in {
        tx.event_type for tx in payment.transactions
    }


def test_bank_transfer_verified_by_staff_marks_paid(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    payment_service.submit_bank_transfer_proof(
        db, customer_user.id, order.order_number, reference="TRX-1"
    )

    verified = payment_service.verify_bank_transfer(
        db, order.active_payment.id, actor=admin_user, note="Matched statement"
    )

    assert verified.status is PaymentStatus.PAID
    assert verified.paid_at is not None
    db.refresh(order)
    assert order.payment_status is PaymentStatus.PAID


def test_bank_transfer_rejected_records_reason(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    rejected = payment_service.reject_bank_transfer(
        db, order.active_payment.id, actor=admin_user, reason="No matching credit"
    )

    assert rejected.status is PaymentStatus.FAILED
    assert rejected.failure_reason == "No matching credit"
    db.refresh(order)
    assert order.payment_status is PaymentStatus.FAILED


def test_another_customer_cannot_submit_transfer_for_someone_elses_order(db, customer_user):
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    from app.models.enums import UserRole

    intruder, _ = create_user(db, UserRole.CUSTOMER)

    from app.services.exceptions import NotFoundError

    # Ownership is part of the query, so someone else's order number is not found
    # rather than being writable.
    with pytest.raises(NotFoundError):
        payment_service.submit_bank_transfer_proof(
            db, intruder.id, order.order_number, reference="STOLEN"
        )


def test_submission_rejected_once_payment_is_settled(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="BANK_TRANSFER")
    payment_service.verify_bank_transfer(
        db, order.active_payment.id, actor=admin_user
    )

    with pytest.raises(InvalidRequestError, match="already been verified"):
        payment_service.submit_bank_transfer_proof(
            db, customer_user.id, order.order_number, reference="LATE"
        )


# ------------------------------------------------------------ status machine
def test_illegal_payment_transition_is_refused(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment
    payment_service.mark_cod_collected(db, payment.id, actor=admin_user)

    # PAID may only go to REFUNDED.
    with pytest.raises(InvalidRequestError, match="Cannot move a payment"):
        payment_service.transition(
            db,
            payment,
            PaymentStatus.PENDING,
            event=PaymentTransactionEvent.FAILED,
        )


def test_transition_to_same_status_reports_no_change(db, customer_user):
    """This is the second idempotency layer, independent of webhook dedupe."""
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment

    changed = payment_service.transition(
        db,
        payment,
        PaymentStatus.PENDING,
        event=PaymentTransactionEvent.WEBHOOK_RECEIVED,
    )
    assert changed is False

    # `transition` adds the audit row without flushing; production commits right
    # after, so flush here to see it on the already-loaded relationship.
    db.flush()
    db.refresh(payment)
    assert PaymentTransactionEvent.WEBHOOK_DUPLICATE in {
        tx.event_type for tx in payment.transactions
    }


# ----------------------------------------------------------------- webhooks
def test_webhook_marks_payment_paid(db, customer_user, fake_gateway, recorder):
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)

    outcome = payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )

    assert outcome.accepted is True
    assert outcome.duplicate is False
    assert outcome.status is PaymentStatus.PAID
    db.refresh(payment)
    assert payment.status is PaymentStatus.PAID
    assert payment.provider_transaction_id == "gw-txn-1"
    db.refresh(order)
    assert order.payment_status is PaymentStatus.PAID
    paid_notifications = [
        e for e, _, _ in recorder.sent
        if e is notifications.NotificationEvent.PAYMENT_RECEIVED
    ]
    assert len(paid_notifications) == 1


def test_duplicate_webhook_is_processed_once(db, customer_user, fake_gateway, recorder):
    """The core idempotency requirement: three identical deliveries, one effect."""
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)
    headers = {"x-signature": fake_gateway.secret}

    first = payment_service.process_inbound(
        db, PaymentProvider.PAYFAST, raw_body=b"{}", headers=headers
    )
    second = payment_service.process_inbound(
        db, PaymentProvider.PAYFAST, raw_body=b"{}", headers=headers
    )
    third = payment_service.process_inbound(
        db, PaymentProvider.PAYFAST, raw_body=b"{}", headers=headers
    )

    assert first.duplicate is False
    assert second.duplicate is True
    assert third.duplicate is True

    # Exactly one webhook event row, one PAID transition, one notification.
    events = db.execute(
        select(WebhookEvent).where(WebhookEvent.provider == PaymentProvider.PAYFAST)
    ).scalars().all()
    assert len(events) == 1

    db.refresh(payment)
    verified = [
        tx for tx in payment.transactions
        if tx.event_type is PaymentTransactionEvent.VERIFIED
    ]
    assert len(verified) == 1
    paid_notifications = [
        e for e, _, _ in recorder.sent
        if e is notifications.NotificationEvent.PAYMENT_RECEIVED
    ]
    assert len(paid_notifications) == 1


def test_invalid_signature_is_rejected_and_never_touches_payment(db, customer_user, fake_gateway, recorder):
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)

    # Placing the order legitimately sent ORDER_CREATED. Clear it so what remains
    # is attributable to the forged webhook alone.
    recorder.sent.clear()

    outcome = payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b'{"status":"PAID"}',
        headers={"x-signature": "forged"},
    )

    assert outcome.accepted is False
    db.refresh(payment)
    assert payment.status is PaymentStatus.PENDING
    assert recorder.sent == []
    # The rejection is still recorded for investigation.
    rejected = db.execute(
        select(WebhookEvent).where(WebhookEvent.signature_valid.is_(False))
    ).scalars().all()
    assert len(rejected) == 1


def test_webhook_amount_mismatch_is_rejected(db, customer_user, fake_gateway):
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)
    fake_gateway.amount = payment.amount + Decimal("1.00")

    outcome = payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )

    assert outcome.accepted is False
    assert "amount" in outcome.message.lower()
    db.refresh(payment)
    assert payment.status is PaymentStatus.PENDING


def test_webhook_for_unknown_payment_is_not_applied(db, fake_gateway):
    fake_gateway.payment_reference = str(uuid.uuid4())
    fake_gateway.provider_txn = "no-such-txn"

    outcome = payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )
    assert outcome.accepted is False
    assert "No matching payment" in outcome.message


def test_late_webhook_cannot_reopen_a_settled_payment(
    db, customer_user, fake_gateway, admin_user
):
    """A gateway retry arriving after a refund must not flip it back to PAID."""
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)

    payment_service.transition(
        db, payment, PaymentStatus.PAID,
        event=PaymentTransactionEvent.VERIFIED,
    )
    payment_service.transition(
        db, payment, PaymentStatus.REFUNDED,
        event=PaymentTransactionEvent.REFUNDED, actor=admin_user,
    )
    db.commit()

    fake_gateway.event_id = "evt-late"
    outcome = payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )

    assert outcome.duplicate is True
    db.refresh(payment)
    assert payment.status is PaymentStatus.REFUNDED


def test_failed_webhook_records_reason(db, customer_user, fake_gateway, recorder):
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)
    fake_gateway.next_status = PaymentStatus.FAILED

    payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )

    db.refresh(payment)
    assert payment.status is PaymentStatus.FAILED
    assert payment.failure_reason == "Declined"
    assert any(
        e is notifications.NotificationEvent.PAYMENT_FAILED for e, _, _ in recorder.sent
    )


# ------------------------------------------------------- unconfigured gateways
@pytest.mark.parametrize(
    "method",
    [
        PaymentMethod.PAYFAST,
        PaymentMethod.SAFEPAY,
        PaymentMethod.JAZZCASH,
        PaymentMethod.EASYPAISA,
    ],
)
def test_unconfigured_gateway_refuses_to_create_a_payment(method):
    """No gateway may silently accept a payment it cannot actually process."""
    payment_service.reset_registry()
    provider = payment_service.provider_for_method(method)
    assert provider.is_configured is False
    with pytest.raises(ProviderNotConfigured):
        provider.create_payment(None, None, None)


def test_gateway_boundaries_declare_required_settings():
    """Each boundary must say what it needs, so the gap is documented in code."""
    for provider in build_gateway_providers():
        assert provider.required_settings, f"{provider.code} declares no settings"
        assert provider.integration_checklist, f"{provider.code} has no checklist"
        assert provider.is_configured is False
        assert "Missing configuration" in provider.configuration_hint


def test_checkout_with_unconfigured_gateway_rolls_back_the_whole_order(db, customer_user):
    """A provider that cannot start must not leave a paymentless order behind."""
    from app.models.order import Order

    payment_service.reset_registry()
    before = db.execute(select(Order)).scalars().all()

    # The schema validator rejects an unconfigured method before checkout even
    # starts; constructing the request directly proves the service layer also
    # refuses and rolls the transaction back.
    from app.schemas.order import CheckoutRequest
    from app.services import orders as order_service
    from tests.factories import make_address, seed_cart

    _, variant = make_shop_setup(db)
    address = make_address(db, customer_user.id)
    seed_cart(db, customer_user.id, variant.id, 1)

    payload = CheckoutRequest.model_construct(
        address_id=address.id,
        payment_method=PaymentMethod.SAFEPAY,
        delivery_method=DeliveryMethod.STANDARD,
        contact_email=None,
        contact_phone=None,
        customer_note=None,
    )

    with pytest.raises(ProviderNotConfigured):
        order_service.place_order(db, customer_user, payload)

    db.rollback()
    after = db.execute(select(Order)).scalars().all()
    assert len(after) == len(before)


# ---------------------------------------------------------------- redaction
@pytest.mark.parametrize(
    "key",
    [
        "password",
        "secured_key",
        "api_key",
        "X-Signature",
        "integrity_salt",
        "card_number",
        "cvv",
        "authorization",
    ],
)
def test_sensitive_keys_are_redacted(key):
    cleaned = redact({key: "super-secret", "amount": "100.00"})
    assert cleaned[key] == "[redacted]"
    assert cleaned["amount"] == "100.00"


def test_redaction_reaches_nested_structures():
    cleaned = redact(
        {"data": {"items": [{"token": "abc", "sku": "RG-1"}]}, "merchant_password": "x"}
    )
    assert cleaned["data"]["items"][0]["token"] == "[redacted]"
    assert cleaned["data"]["items"][0]["sku"] == "RG-1"
    assert cleaned["merchant_password"] == "[redacted]"


def test_stored_webhook_payload_contains_no_secrets(db, customer_user, fake_gateway):
    order = make_order(db, customer_user, payment_method="PAYFAST")
    payment = order.active_payment
    fake_gateway.payment_reference = str(payment.id)

    payment_service.process_inbound(
        db,
        PaymentProvider.PAYFAST,
        raw_body=b"{}",
        headers={"x-signature": fake_gateway.secret},
    )

    event = db.execute(select(WebhookEvent)).scalars().first()
    assert "test-signature" not in str(event.payload)


def test_fingerprint_is_stable_regardless_of_key_order():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})


# ------------------------------------------------------------------- refunds
def test_refund_requires_a_paid_payment(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    with pytest.raises(InvalidRequestError, match="Only a paid payment"):
        payment_service.request_refund(
            db,
            order.active_payment.id,
            amount=Decimal("100.00"),
            reason="Customer changed mind",
            actor=admin_user,
        )


def test_refund_cannot_exceed_the_payment(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment
    payment_service.mark_cod_collected(db, payment.id, actor=admin_user)

    from app.services.exceptions import ConflictError

    with pytest.raises(ConflictError):
        payment_service.request_refund(
            db,
            payment.id,
            amount=payment.amount + Decimal("1.00"),
            reason="Too much",
            actor=admin_user,
        )


def test_full_refund_marks_payment_refunded(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment
    payment_service.mark_cod_collected(db, payment.id, actor=admin_user)

    refund = payment_service.request_refund(
        db,
        payment.id,
        amount=payment.amount,
        reason="Returned goods",
        actor=admin_user,
    )
    assert refund.status is RefundStatus.REQUESTED

    completed = payment_service.complete_refund(
        db, refund.id, actor=admin_user, provider_refund_id="rf-1"
    )
    assert completed.status is RefundStatus.COMPLETED
    db.refresh(payment)
    assert payment.status is PaymentStatus.REFUNDED


def test_partial_refund_leaves_payment_paid(db, customer_user, admin_user):
    order = make_order(db, customer_user, payment_method="COD")
    payment = order.active_payment
    payment_service.mark_cod_collected(db, payment.id, actor=admin_user)

    refund = payment_service.request_refund(
        db,
        payment.id,
        amount=Decimal("1.00"),
        reason="Goodwill",
        actor=admin_user,
    )
    payment_service.complete_refund(db, refund.id, actor=admin_user)

    db.refresh(payment)
    assert payment.status is PaymentStatus.PAID
