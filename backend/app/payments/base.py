"""Payment provider contract.

Order logic depends only on this interface, so a new gateway is added by writing
one provider class and registering it — `services/orders.py` never changes.

**Nothing in this module or its implementations invents provider API behaviour.**
Where official credentials and documentation are unavailable, the provider
declares itself unconfigured and refuses to start a payment. It does not guess
endpoints, signature algorithms, field names, or webhook formats, and it never
reports a payment as successful without a verified provider response.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.models.enums import PaymentProvider, PaymentStatus
from app.services.exceptions import ServiceError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.order import Order
    from app.models.payment import Payment


class PaymentProviderError(ServiceError):
    """Base class for provider-level failures."""


class ProviderNotConfigured(PaymentProviderError):
    """Credentials or endpoint configuration are missing for this provider."""


class ProviderNotSupported(PaymentProviderError):
    """The requested capability is not offered by this provider."""


class WebhookVerificationError(PaymentProviderError):
    """A callback or webhook failed signature/authenticity verification."""


# Keys whose values must never be written to the database or the log. Matching is
# case-insensitive and substring-based, so `X-Signature` and `merchant_password`
# are both caught.
SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "secured_key",
    "api_key",
    "apikey",
    "token",
    "salt",
    "signature",
    "hash",
    "authorization",
    "auth",
    "cvv",
    "cvc",
    "card",
    "pan",
    "pin",
    "otp",
)

REDACTED = "[redacted]"


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively strip sensitive values from a provider payload.

    Applied before anything is persisted to `raw_response`/`payload` or logged,
    so credentials and card-like data cannot leak into the database or logs even
    if a provider echoes them back.
    """
    if _depth > 6:
        return REDACTED
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
                cleaned[str(key)] = REDACTED
            else:
                cleaned[str(key)] = redact(item, _depth=_depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth=_depth + 1) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def fingerprint(payload: Any) -> str:
    """Stable hash of a payload, used as a dedupe key when no event id exists."""
    try:
        serialised = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialised = str(payload)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class PaymentIntent:
    """What the frontend needs in order to continue a payment.

    Deliberately carries no authoritative status: the frontend cannot conclude a
    payment succeeded from this object, only that it should redirect or display
    instructions.
    """

    payment_id: str
    provider: PaymentProvider
    status: PaymentStatus
    # True when the customer must be sent to a hosted gateway page.
    requires_redirect: bool = False
    redirect_url: str | None = None
    # For gateways that require an auto-submitting POST form rather than a GET.
    form_action: str | None = None
    form_fields: dict[str, str] = field(default_factory=dict)
    # Human-readable next steps, used by COD and bank transfer.
    instructions: str | None = None
    reference: str | None = None


@dataclass(slots=True)
class WebhookOutcome:
    """Result of processing an inbound callback or webhook."""

    accepted: bool
    message: str
    payment_id: str | None = None
    status: PaymentStatus | None = None
    # True when this delivery was already processed; the caller must not repeat
    # any side effect.
    duplicate: bool = False


@dataclass(slots=True)
class VerificationResult:
    """Outcome of asking the provider what really happened to a payment."""

    status: PaymentStatus
    provider_transaction_id: str | None = None
    amount: Decimal | None = None
    failure_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedWebhook:
    """Provider-agnostic view of an inbound webhook, produced by the provider.

    `external_id` is the idempotency key. Providers that supply no usable event
    id must return a payload fingerprint so duplicate deliveries still collapse.
    """

    external_id: str
    payment_reference: str | None
    status: PaymentStatus
    provider_transaction_id: str | None = None
    amount: Decimal | None = None
    failure_reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class BasePaymentProvider(ABC):
    """Contract every payment provider implements."""

    code: PaymentProvider
    display_name: str
    # False for gateways: those settle through a callback/webhook instead.
    settles_offline: bool = False

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True when this provider has everything it needs to run for real."""

    @property
    def configuration_hint(self) -> str:
        """What an operator must supply to make this provider usable."""
        return "No additional configuration required."

    @abstractmethod
    def create_payment(self, db: Session, payment: Payment, order: Order) -> PaymentIntent:
        """Begin a payment and describe how the customer should continue."""

    def verify_payment(self, db: Session, payment: Payment) -> VerificationResult:
        """Ask the provider for the authoritative status of a payment."""
        raise ProviderNotSupported(
            f"{self.display_name} does not support server-side verification."
        )

    def parse_callback(self, params: dict[str, Any]) -> ParsedWebhook:
        """Interpret a browser redirect back from the gateway.

        A callback is a *hint*, never proof: the customer's browser is not a
        trusted channel. Implementations must still verify with the provider.
        """
        raise ProviderNotSupported(f"{self.display_name} has no callback flow.")

    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhook:
        """Verify and interpret a server-to-server webhook.

        Implementations must verify the provider's signature before returning,
        and raise `WebhookVerificationError` when it does not check out.
        """
        raise ProviderNotSupported(f"{self.display_name} has no webhook flow.")

    def refund_payment(
        self, db: Session, payment: Payment, amount: Decimal, reason: str
    ) -> VerificationResult:
        raise ProviderNotSupported(
            f"{self.display_name} refunds are handled outside the system."
        )


class UnconfiguredGatewayProvider(BasePaymentProvider):
    """A declared gateway whose integration is not built.

    This is the honest representation of "we support this provider in the domain
    model, but the official API contract and credentials are not available here".
    Every operation raises a clear error, so the provider can never be selected
    accidentally and can never report a false success.

    Building the real integration means replacing this subclass with one written
    against the provider's official documentation — the surrounding order,
    webhook, and audit machinery needs no changes.
    """

    #: Environment variables that must all be present before the provider is usable.
    required_settings: tuple[str, ...] = ()
    #: What still has to be obtained from the provider before coding can start.
    integration_checklist: tuple[str, ...] = ()

    def __init__(self, present_settings: dict[str, str | None] | None = None) -> None:
        self._present = present_settings or {}

    @property
    def is_configured(self) -> bool:
        # Even with credentials present this stays False: credentials alone do
        # not make an unwritten integration work.
        return False

    @property
    def has_credentials(self) -> bool:
        """Whether the operator has supplied the expected environment values."""
        if not self.required_settings:
            return False
        return all(self._present.get(name) for name in self.required_settings)

    @property
    def configuration_hint(self) -> str:
        missing = [name for name in self.required_settings if not self._present.get(name)]
        if missing:
            return "Missing configuration: " + ", ".join(missing)
        return (
            "Credentials are present, but the integration itself is not implemented. "
            "Official API documentation is required to build it."
        )

    def _unavailable(self) -> ProviderNotConfigured:
        return ProviderNotConfigured(
            f"{self.display_name} payments are not available yet. "
            "Please choose Cash on Delivery or Bank Transfer."
        )

    def create_payment(self, db: Session, payment: Payment, order: Order) -> PaymentIntent:
        raise self._unavailable()

    def verify_payment(self, db: Session, payment: Payment) -> VerificationResult:
        raise self._unavailable()

    def parse_callback(self, params: dict[str, Any]) -> ParsedWebhook:
        raise self._unavailable()

    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhook:
        raise self._unavailable()
