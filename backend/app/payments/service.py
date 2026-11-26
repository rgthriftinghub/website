"""Payment orchestration.

The backend is the only authority on payment state. A frontend can ask to *start*
a payment; it can never assert the outcome. Every status change here originates
from one of exactly four trusted sources:

1. an offline provider's own rules (COD/bank transfer start PENDING),
2. a verified provider webhook,
3. a provider verification call made by us, or
4. an explicit, audited staff action.

Every change is validated against `PAYMENT_STATUS_TRANSITIONS`, recorded in
`PaymentTransaction`, and mirrored onto the order's denormalised
`payment_status`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import (
    PAYMENT_STATUS_TRANSITIONS,
    TERMINAL_PAYMENT_STATUSES,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionEvent,
    RefundStatus,
)
from app.models.order import Order
from app.models.payment import Payment, PaymentTransaction, Refund, WebhookEvent
from app.models.user import User
from app.payments.base import (
    BasePaymentProvider,
    ParsedWebhook,
    PaymentIntent,
    ProviderNotConfigured,
    WebhookOutcome,
    WebhookVerificationError,
    fingerprint,
    redact,
)
from app.payments.providers.gateways import build_gateway_providers
from app.payments.providers.offline import (
    BankTransferProvider, CashOnDeliveryProvider, EasypaisaManualProvider, JazzCashManualProvider,
)
from app.services import notifications
from app.services.exceptions import ConflictError, InvalidRequestError, NotFoundError

logger = logging.getLogger("app.payments")

# Which provider settles which method. One-to-one today; the indirection exists so
# a method could later be routed to a different provider without touching orders.
METHOD_TO_PROVIDER: dict[PaymentMethod, PaymentProvider] = {
    PaymentMethod.COD: PaymentProvider.COD,
    PaymentMethod.BANK_TRANSFER: PaymentProvider.BANK_TRANSFER,
    PaymentMethod.PAYFAST: PaymentProvider.PAYFAST,
    PaymentMethod.SAFEPAY: PaymentProvider.SAFEPAY,
    PaymentMethod.JAZZCASH: PaymentProvider.JAZZCASH,
    PaymentMethod.EASYPAISA: PaymentProvider.EASYPAISA,
}


def _build_registry() -> dict[PaymentProvider, BasePaymentProvider]:
    providers: list[BasePaymentProvider] = [
        CashOnDeliveryProvider(),
        BankTransferProvider(),
        JazzCashManualProvider(),
        EasypaisaManualProvider(),
        *build_gateway_providers(),
    ]
    return {provider.code: provider for provider in providers}


_registry: dict[PaymentProvider, BasePaymentProvider] | None = None


def registry() -> dict[PaymentProvider, BasePaymentProvider]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def reset_registry() -> None:
    """Drop the cached registry. Used by tests that swap provider configuration."""
    global _registry
    _registry = None


def get_provider(code: PaymentProvider) -> BasePaymentProvider:
    provider = registry().get(code)
    if provider is None:
        raise NotFoundError(f"Unknown payment provider: {code}")
    return provider


def provider_for_method(method: PaymentMethod) -> BasePaymentProvider:
    return get_provider(METHOD_TO_PROVIDER[method])


def available_providers() -> list[BasePaymentProvider]:
    """Providers a customer may actually select right now."""
    return [provider for provider in registry().values() if provider.is_configured]


def selectable_methods() -> set[PaymentMethod]:
    """Payment methods whose provider is actually able to run.

    This is the single source of truth for what checkout accepts. Deriving it from
    the registry rather than a hardcoded list means an unconfigured gateway is
    automatically unselectable, and a newly implemented one becomes selectable
    without editing a validator.
    """
    usable = {provider.code for provider in available_providers()}
    return {
        method
        for method, provider_code in METHOD_TO_PROVIDER.items()
        if provider_code in usable
    }


# ------------------------------------------------------------------ audit trail
def record_transaction(
    db: Session,
    payment: Payment,
    event: PaymentTransactionEvent,
    *,
    message: str | None = None,
    response_data: dict[str, Any] | None = None,
    provider_transaction_id: str | None = None,
    amount: Decimal | None = None,
) -> PaymentTransaction:
    """Append an audit entry. Payloads are redacted before they are stored."""
    entry = PaymentTransaction(
        payment_id=payment.id,
        event_type=event,
        provider_transaction_id=provider_transaction_id or payment.provider_transaction_id,
        amount=amount,
        status=payment.status,
        response_data=redact(response_data) if response_data is not None else None,
        message=(message or "")[:500] or None,
    )
    db.add(entry)
    return entry


# ------------------------------------------------------------- state transitions
def transition(
    db: Session,
    payment: Payment,
    new_status: PaymentStatus,
    *,
    event: PaymentTransactionEvent,
    message: str | None = None,
    provider_transaction_id: str | None = None,
    raw_response: dict[str, Any] | None = None,
    failure_reason: str | None = None,
    actor: User | None = None,
) -> bool:
    """Move a payment to a new status, or report that it was already there.

    Returns False when the payment is already in `new_status`, which is what makes
    replayed webhooks harmless: the caller skips its side effects rather than
    repeating them.
    """
    if payment.status == new_status:
        record_transaction(
            db,
            payment,
            PaymentTransactionEvent.WEBHOOK_DUPLICATE,
            message=f"Already {new_status}; no change applied",
            response_data=raw_response,
        )
        return False

    allowed = PAYMENT_STATUS_TRANSITIONS.get(payment.status, frozenset())
    if new_status not in allowed:
        permitted = ", ".join(sorted(str(s) for s in allowed)) or "no further changes"
        raise InvalidRequestError(
            f"Cannot move a payment from {payment.status} to {new_status}. Allowed: {permitted}"
        )

    payment.status = new_status
    if provider_transaction_id:
        payment.provider_transaction_id = provider_transaction_id
    if raw_response is not None:
        payment.raw_response = redact(raw_response)
    if failure_reason is not None:
        payment.failure_reason = failure_reason[:500]
    if new_status is PaymentStatus.PAID:
        payment.paid_at = datetime.now(UTC)
        payment.failure_reason = None
    if actor is not None:
        payment.verified_by_user_id = actor.id
        payment.verified_at = datetime.now(UTC)

    # Keep the order's denormalised copy in step within the same transaction.
    payment.order.payment_status = new_status

    record_transaction(
        db,
        payment,
        event,
        message=message,
        response_data=raw_response,
        provider_transaction_id=provider_transaction_id,
        amount=payment.amount,
    )
    return True


# -------------------------------------------------------------------- creation
def create_payment_for_order(db: Session, order: Order) -> tuple[Payment, PaymentIntent]:
    """Create the pending payment for a freshly placed order.

    Called inside the checkout transaction, so a provider that refuses to start
    rolls the whole order back rather than leaving an order with no payment.
    """
    provider = provider_for_method(order.payment_method)
    if not provider.is_configured:
        raise ProviderNotConfigured(
            f"{provider.display_name} payments are not available yet. "
            "Please choose Cash on Delivery or Bank Transfer."
        )

    payment = Payment(
        order_id=order.id,
        provider=provider.code,
        payment_method=order.payment_method,
        # Amount comes from the order the backend computed, never from a request.
        amount=order.total_amount,
        currency="PKR",
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.flush()
    payment.order = order

    intent = provider.create_payment(db, payment, order)
    record_transaction(
        db,
        payment,
        PaymentTransactionEvent.INITIATED,
        message=f"{provider.display_name} payment initiated",
    )
    if intent.requires_redirect:
        record_transaction(
            db, payment, PaymentTransactionEvent.REDIRECTED, message="Customer sent to gateway"
        )
    return payment, intent


# ------------------------------------------------------------------- retrieval
def payment_loads() -> tuple:
    return (
        selectinload(Payment.transactions),
        selectinload(Payment.refunds),
        joinedload(Payment.order).joinedload(Order.user),
    )


def get_payment(db: Session, payment_id: uuid.UUID) -> Payment | None:
    return (
        db.execute(select(Payment).where(Payment.id == payment_id).options(*payment_loads()))
        .unique()
        .scalar_one_or_none()
    )


def get_payment_for_user(db: Session, user_id: uuid.UUID, payment_id: uuid.UUID) -> Payment:
    """Fetch a payment belonging to the requesting customer.

    Ownership is part of the query, so another customer's payment id is simply
    not found rather than being readable.
    """
    payment = (
        db.execute(
            select(Payment)
            .join(Order)
            .where(Payment.id == payment_id, Order.user_id == user_id)
            .options(*payment_loads())
        )
        .unique()
        .scalar_one_or_none()
    )
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


def active_payment_for_order(db: Session, order: Order) -> Payment | None:
    return order.active_payment


# --------------------------------------------------------- bank transfer flow
def submit_bank_transfer_proof(
    db: Session,
    user_id: uuid.UUID,
    order_number: str,
    *,
    reference: str,
    note: str | None = None,
    proof_url: str | None = None,
) -> Payment:
    """Record what the customer says they transferred.

    This never marks the payment paid. It only queues it for staff verification.
    """
    order = (
        db.execute(
            select(Order)
            .where(Order.order_number == order_number, Order.user_id == user_id)
            .options(selectinload(Order.payments))
        )
        .unique()
        .scalar_one_or_none()
    )
    if order is None:
        raise NotFoundError("Order not found")

    payment = order.active_payment
    if payment is None or payment.provider is not PaymentProvider.BANK_TRANSFER:
        raise InvalidRequestError("This order was not placed with bank transfer")
    if payment.status is PaymentStatus.PAID:
        raise InvalidRequestError("This payment has already been verified")
    if payment.status in TERMINAL_PAYMENT_STATUSES:
        raise InvalidRequestError(f"This payment is {payment.status} and cannot be updated")

    payment.customer_reference = reference.strip()[:120]
    payment.customer_note = note
    payment.proof_url = proof_url
    payment.proof_submitted_at = datetime.now(UTC)

    record_transaction(
        db,
        payment,
        PaymentTransactionEvent.PROOF_SUBMITTED,
        message=f"Customer submitted reference {payment.customer_reference}",
    )
    db.commit()
    db.refresh(payment)
    return payment


def verify_bank_transfer(
    db: Session, payment_id: uuid.UUID, *, actor: User, note: str | None = None
) -> Payment:
    """Staff confirm the money arrived. This is a trusted, audited action."""
    payment = get_payment(db, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.provider is not PaymentProvider.BANK_TRANSFER:
        raise InvalidRequestError("Only bank transfers are verified manually")

    changed = transition(
        db,
        payment,
        PaymentStatus.PAID,
        event=PaymentTransactionEvent.MANUALLY_VERIFIED,
        message=note or f"Verified by {actor.email}",
        actor=actor,
    )
    if note:
        payment.internal_note = note
    db.commit()
    db.refresh(payment)
    if changed:
        notifications.notify_order_event(
            notifications.NotificationEvent.PAYMENT_RECEIVED, payment.order
        )
    return payment


def reject_bank_transfer(
    db: Session, payment_id: uuid.UUID, *, actor: User, reason: str
) -> Payment:
    payment = get_payment(db, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.provider is not PaymentProvider.BANK_TRANSFER:
        raise InvalidRequestError("Only bank transfers are rejected manually")

    changed = transition(
        db,
        payment,
        PaymentStatus.FAILED,
        event=PaymentTransactionEvent.MANUALLY_REJECTED,
        message=reason,
        failure_reason=reason,
        actor=actor,
    )
    db.commit()
    db.refresh(payment)
    if changed:
        notifications.notify_order_event(
            notifications.NotificationEvent.PAYMENT_FAILED, payment.order, reason=reason
        )
    return payment


def mark_cod_collected(
    db: Session, payment_id: uuid.UUID, *, actor: User, note: str | None = None
) -> Payment:
    """Staff record that the courier collected the cash."""
    payment = get_payment(db, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.provider is not PaymentProvider.COD:
        raise InvalidRequestError("This payment is not cash on delivery")

    changed = transition(
        db,
        payment,
        PaymentStatus.PAID,
        event=PaymentTransactionEvent.MANUALLY_VERIFIED,
        message=note or f"Cash collected, recorded by {actor.email}",
        actor=actor,
    )
    db.commit()
    db.refresh(payment)
    if changed:
        notifications.notify_order_event(
            notifications.NotificationEvent.PAYMENT_RECEIVED, payment.order
        )
    return payment


# ---------------------------------------------------------------- gateway inbound
def _resolve_payment(db: Session, parsed: ParsedWebhook) -> Payment | None:
    """Find the payment a webhook refers to, by our id or the provider's."""
    reference = (parsed.payment_reference or "").strip()
    if reference:
        try:
            candidate = get_payment(db, uuid.UUID(reference))
            if candidate is not None:
                return candidate
        except ValueError:
            # Not a UUID; treat it as an order number instead.
            order = (
                db.execute(
                    select(Order)
                    .where(Order.order_number == reference)
                    .options(selectinload(Order.payments))
                )
                .unique()
                .scalar_one_or_none()
            )
            if order is not None:
                return order.active_payment
    if parsed.provider_transaction_id:
        return (
            db.execute(
                select(Payment)
                .where(Payment.provider_transaction_id == parsed.provider_transaction_id)
                .options(*payment_loads())
            )
            .unique()
            .scalar_one_or_none()
        )
    return None


def process_inbound(
    db: Session,
    provider_code: PaymentProvider,
    *,
    raw_body: bytes,
    headers: dict[str, str],
    query_params: dict[str, Any] | None = None,
    is_callback: bool = False,
) -> WebhookOutcome:
    """Verify and apply one inbound gateway message, exactly once.

    Idempotency has two layers:

    1. A `WebhookEvent` row keyed on (provider, external_id). A replayed delivery
       hits that unique constraint, is recognised, and returns early — before any
       payment update, stock movement, or notification.
    2. `transition()` returns False when the payment already holds the target
       status, so even a message that slips past layer one cannot double-apply.
    """
    provider = get_provider(provider_code)

    # 1. Verify authenticity and interpret. A verification failure is recorded and
    #    rejected; it never touches a payment.
    try:
        parsed = (
            provider.parse_callback(query_params or {})
            if is_callback
            else provider.parse_webhook(raw_body, headers)
        )
    except WebhookVerificationError as exc:
        logger.warning("Rejected %s webhook: signature invalid", provider_code)
        db.add(
            WebhookEvent(
                provider=provider_code,
                external_id=f"rejected:{fingerprint(raw_body.decode('utf-8', 'replace'))}",
                payload_fingerprint=fingerprint(raw_body.decode("utf-8", "replace")),
                signature_valid=False,
                result="rejected: invalid signature",
                processed_at=datetime.now(UTC),
            )
        )
        db.commit()
        return WebhookOutcome(accepted=False, message=str(exc))
    except ProviderNotConfigured as exc:
        # A message for a provider we have not integrated. Logged, not applied.
        logger.warning("Inbound message for unconfigured provider %s", provider_code)
        return WebhookOutcome(accepted=False, message=str(exc))

    # 2. Dedupe on the provider's event id.
    event = WebhookEvent(
        provider=provider_code,
        external_id=parsed.external_id,
        payload_fingerprint=fingerprint(parsed.payload),
        payload=redact(parsed.payload),
        signature_valid=True,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info("Duplicate %s webhook %s ignored", provider_code, parsed.external_id)
        return WebhookOutcome(
            accepted=True,
            duplicate=True,
            message="Already processed",
        )

    payment = _resolve_payment(db, parsed)
    if payment is None:
        event.processed_at = datetime.now(UTC)
        event.result = "no matching payment"
        db.commit()
        return WebhookOutcome(accepted=False, message="No matching payment")

    event.payment_id = payment.id

    if parsed.amount is not None and parsed.amount != payment.amount:
        event.processed_at = datetime.now(UTC)
        event.result = "rejected: amount mismatch"
        db.commit()
        return WebhookOutcome(
            accepted=False,
            payment_id=str(payment.id),
            status=payment.status,
            message="Webhook amount does not match the payment amount",
        )

    # 3. Apply, guarded by the transition rules.
    inbound_event = (
        PaymentTransactionEvent.CALLBACK_RECEIVED
        if is_callback
        else PaymentTransactionEvent.WEBHOOK_RECEIVED
    )
    record_transaction(
        db,
        payment,
        inbound_event,
        message=f"{provider.display_name} reported {parsed.status}",
        response_data=parsed.payload,
        provider_transaction_id=parsed.provider_transaction_id,
    )

    # A settled payment is never re-opened by a late or replayed message.
    if payment.status in TERMINAL_PAYMENT_STATUSES and payment.status != parsed.status:
        event.processed_at = datetime.now(UTC)
        event.result = f"ignored: payment already {payment.status}"
        db.commit()
        return WebhookOutcome(
            accepted=True,
            duplicate=True,
            payment_id=str(payment.id),
            status=payment.status,
            message=f"Payment already {payment.status}",
        )

    changed = transition(
        db,
        payment,
        parsed.status,
        event=PaymentTransactionEvent.VERIFIED
        if parsed.status is PaymentStatus.PAID
        else PaymentTransactionEvent.FAILED,
        message=f"Verified via {provider.display_name}",
        provider_transaction_id=parsed.provider_transaction_id,
        raw_response=parsed.payload,
        failure_reason=parsed.failure_reason,
    )

    event.processed_at = datetime.now(UTC)
    event.result = f"applied: {parsed.status}" if changed else "no change"
    db.commit()
    db.refresh(payment)

    # Notifications only fire on a real change, so replays stay silent.
    if changed:
        if parsed.status is PaymentStatus.PAID:
            notifications.notify_order_event(
                notifications.NotificationEvent.PAYMENT_RECEIVED, payment.order
            )
        elif parsed.status is PaymentStatus.FAILED:
            notifications.notify_order_event(
                notifications.NotificationEvent.PAYMENT_FAILED,
                payment.order,
                reason=parsed.failure_reason,
            )

    return WebhookOutcome(
        accepted=True,
        duplicate=not changed,
        payment_id=str(payment.id),
        status=payment.status,
        message=event.result or "processed",
    )


# ---------------------------------------------------------------------- refunds
def request_refund(
    db: Session,
    payment_id: uuid.UUID,
    *,
    amount: Decimal,
    reason: str,
    actor: User,
) -> Refund:
    """Record a refund request.

    This does not move money. Automatic gateway refunds require a configured
    provider API; until one exists a refund is a bookkeeping record that staff
    settle out of band and then mark completed.
    """
    payment = get_payment(db, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.status is not PaymentStatus.PAID:
        raise InvalidRequestError("Only a paid payment can be refunded")
    if amount <= 0:
        raise InvalidRequestError("Refund amount must be positive")

    already = sum(
        (refund.amount for refund in payment.refunds if refund.status != RefundStatus.FAILED),
        start=Decimal("0.00"),
    )
    if already + amount > payment.amount:
        raise ConflictError(
            f"Refunds would exceed the payment. Already recorded: {already} of {payment.amount}."
        )

    refund = Refund(
        payment_id=payment.id,
        order_id=payment.order_id,
        amount=amount,
        reason=reason,
        status=RefundStatus.REQUESTED,
        requested_by_user_id=actor.id,
    )
    db.add(refund)
    record_transaction(
        db,
        payment,
        PaymentTransactionEvent.REFUND_REQUESTED,
        message=f"Refund of {amount} requested: {reason}",
        amount=amount,
    )
    db.commit()
    db.refresh(refund)
    return refund


def complete_refund(
    db: Session, refund_id: uuid.UUID, *, actor: User, provider_refund_id: str | None = None
) -> Refund:
    """Mark a refund settled, and the payment REFUNDED once fully returned."""
    refund = db.get(Refund, refund_id)
    if refund is None:
        raise NotFoundError("Refund not found")
    if refund.status is RefundStatus.COMPLETED:
        raise InvalidRequestError("This refund is already completed")

    refund.status = RefundStatus.COMPLETED
    refund.provider_refund_id = provider_refund_id

    payment = get_payment(db, refund.payment_id)
    if payment is not None:
        completed = sum(
            (
                entry.amount
                for entry in payment.refunds
                if entry.status is RefundStatus.COMPLETED or entry.id == refund.id
            ),
            start=Decimal("0.00"),
        )
        if completed >= payment.amount and payment.status is PaymentStatus.PAID:
            transition(
                db,
                payment,
                PaymentStatus.REFUNDED,
                event=PaymentTransactionEvent.REFUNDED,
                message=f"Fully refunded by {actor.email}",
                actor=actor,
            )
        else:
            record_transaction(
                db,
                payment,
                PaymentTransactionEvent.REFUNDED,
                message=f"Partial refund of {refund.amount} completed",
                amount=refund.amount,
            )

    db.commit()
    db.refresh(refund)
    return refund
