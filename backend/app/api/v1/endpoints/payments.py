"""Payment webhooks, callbacks, and public payment configuration.

Webhook endpoints are intentionally **unauthenticated by session** — a gateway has
no cookie. Their authenticity comes from the provider's signature, verified inside
the provider's `parse_webhook` before anything is applied. An unverifiable message
is recorded and rejected; it never touches a payment.

These endpoints always return 200 for a message they have accepted *or* recognised
as a duplicate, because gateways retry on non-2xx and a duplicate is not an error.
"""

import logging
import uuid

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.session import get_db
from app.api.v1.dependencies import require_staff
from app.models.enums import PaymentProvider
from app.models.user import User
from app.payments import service as payment_service
from app.services import orders as order_service
from app.payments.base import UnconfiguredGatewayProvider
from app.schemas.payment import BankAccountRead, ProviderStatusRead
from app.schemas.order import OrderAdminRead, PaymentStatusUpdate
from app.shipping_ops import service as shipping_service

logger = logging.getLogger("app.payments.webhooks")

router = APIRouter()


@router.post("/manual-status/{order_id}", response_model=OrderAdminRead)
def manually_update_order_payment(
    order_id: uuid.UUID,
    payload: PaymentStatusUpdate,
    actor: User = Depends(require_staff),
    db: Session = Depends(get_db),
) -> OrderAdminRead:
    """Staff confirmation/rejection for offline wallet and other payments."""
    order = order_service.update_payment_status(
        db, order_id, payload.payment_status, actor=actor, note=payload.note
    )
    return OrderAdminRead.model_validate(order)

# Providers that expose an inbound endpoint. Kept explicit so a typo in a URL
# cannot address an arbitrary enum member.
WEBHOOK_PROVIDERS: dict[str, PaymentProvider] = {
    "payfast": PaymentProvider.PAYFAST,
    "safepay": PaymentProvider.SAFEPAY,
    "jazzcash": PaymentProvider.JAZZCASH,
    "easypaisa": PaymentProvider.EASYPAISA,
}


class WebhookAck(BaseModel):
    """Minimal acknowledgement. Never echoes payload or internal detail back."""

    received: bool
    duplicate: bool = False
    detail: str


@router.get(
    "/providers",
    response_model=list[ProviderStatusRead],
    summary="Payment providers and their configuration state",
)
def list_providers() -> list[ProviderStatusRead]:
    """Which providers are usable, and what the others still need.

    `is_live` is only true for a provider with a working implementation, so this
    never implies a gateway is ready when only its boundary exists.
    """
    rows: list[ProviderStatusRead] = []
    for provider in payment_service.registry().values():
        checklist: list[str] = []
        # Offline cash, bank, and mobile-wallet methods can be selectable and
        # configured without representing a live payment gateway.
        has_credentials = provider.has_credentials if isinstance(provider, UnconfiguredGatewayProvider) else False
        if isinstance(provider, UnconfiguredGatewayProvider):
            checklist = list(provider.integration_checklist)
            has_credentials = provider.has_credentials
        if provider.code in {PaymentProvider.JAZZCASH, PaymentProvider.EASYPAISA}:
            checklist = ["Manual wallet transfer only; no gateway API is connected.", "Staff confirms the order after checking the WhatsApp screenshot."]
        rows.append(
            ProviderStatusRead(
                code=str(provider.code),
                display_name=provider.display_name,
                is_live=provider.is_configured and provider.code not in {PaymentProvider.JAZZCASH, PaymentProvider.EASYPAISA},
                has_credentials=has_credentials,
                configuration_hint=provider.configuration_hint,
                integration_checklist=checklist,
            )
        )
    return rows


@router.get(
    "/bank-accounts",
    response_model=list[BankAccountRead],
    summary="Store bank details for manual transfer",
)
def list_bank_accounts(db: Session = Depends(get_db)) -> list[BankAccountRead]:
    """The store's own receiving accounts, shown to customers at checkout."""
    return [
        BankAccountRead.model_validate(account)
        for account in shipping_service.active_bank_accounts(db)
    ]


async def _handle_inbound(
    provider_slug: str,
    request: Request,
    db: Session,
    *,
    is_callback: bool,
) -> WebhookAck:
    provider_code = WEBHOOK_PROVIDERS.get(provider_slug)
    if provider_code is None:
        # Unknown slug: acknowledge without detail rather than confirming which
        # providers exist.
        logger.warning("Inbound payment message for unknown provider slug %r", provider_slug)
        return WebhookAck(received=False, detail="Unknown provider")

    if provider_code in {PaymentProvider.JAZZCASH, PaymentProvider.EASYPAISA}:
        # These methods intentionally use manual screenshot review. Do not call
        # the gateway parser for wallet webhook URLs.
        return WebhookAck(received=False, detail="Manual transfer does not accept webhooks")

    raw_body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    query_params = dict(request.query_params)

    outcome = payment_service.process_inbound(
        db,
        provider_code,
        raw_body=raw_body,
        headers=headers,
        query_params=query_params,
        is_callback=is_callback,
    )
    # Deliberately terse: nothing about internal state leaves this endpoint.
    return WebhookAck(
        received=outcome.accepted,
        duplicate=outcome.duplicate,
        detail=outcome.message,
    )


@router.post(
    "/{provider_slug}/webhook",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Provider server-to-server webhook",
)
async def provider_webhook(
    provider_slug: str, request: Request, db: Session = Depends(get_db)
) -> WebhookAck:
    """Verified, idempotent, transaction-safe webhook intake.

    Duplicate deliveries are recognised by the (provider, external_id) unique
    constraint and short-circuit before any payment update, stock movement, or
    notification.
    """
    return await _handle_inbound(provider_slug, request, db, is_callback=False)


@router.post(
    "/{provider_slug}/callback",
    response_model=WebhookAck,
    summary="Provider browser callback (treated as a hint, never as proof)",
)
async def provider_callback(
    provider_slug: str, request: Request, db: Session = Depends(get_db)
) -> WebhookAck:
    """A redirect arriving via the customer's browser.

    The browser is not a trusted channel, so this is processed through the same
    verification path as a webhook and is never sufficient on its own.
    """
    return await _handle_inbound(provider_slug, request, db, is_callback=True)


@router.get(
    "/{provider_slug}/callback",
    response_model=WebhookAck,
    summary="Provider browser callback via GET",
)
async def provider_callback_get(
    provider_slug: str, request: Request, db: Session = Depends(get_db)
) -> WebhookAck:
    return await _handle_inbound(provider_slug, request, db, is_callback=True)
