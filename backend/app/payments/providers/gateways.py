"""Gateway provider boundaries: PayFast and Safepay.

**Status: NOT CONFIGURED. No integration code is implemented for any of these.**

This is deliberate, not an oversight. Building a real payment integration
requires the provider's official documentation — the exact endpoint URLs, the
request field names, the signature/hash construction and its field ordering, the
webhook payload shape, and the signature verification scheme. None of that is
present in this repository or environment, and guessing any part of it would
produce code that looks finished, passes its own invented tests, and fails or
silently mis-handles money against the real gateway.

So each provider below:

* is a real, registered provider in the domain model, so orders and payments can
  already reference it;
* declares exactly which environment variables it needs;
* declares what still has to be obtained from the provider;
* refuses every operation with a clear customer-safe message.

To make one live, replace its class with an implementation written against the
official documentation. It must implement `create_payment`, `verify_payment`,
`parse_callback` and `parse_webhook`, and it must verify the provider's signature
inside `parse_webhook` before returning. Nothing outside this file changes — the
order flow, audit trail, idempotency and admin screens already handle any
provider through `BasePaymentProvider`.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.models.enums import PaymentProvider
from app.payments.base import UnconfiguredGatewayProvider


class PayFastProvider(UnconfiguredGatewayProvider):
    """PayFast (Pakistan) — hosted checkout.

    PayFast's flow is token-based: the merchant obtains an access token using its
    merchant id and secured key, then hands the customer to a hosted page, and is
    notified through a server-to-server call. The precise endpoints, token
    request fields, and notification signature scheme must come from PayFast's
    official merchant integration guide.
    """

    code = PaymentProvider.PAYFAST
    display_name = "PayFast"
    required_settings = (
        "PAYFAST_MERCHANT_ID",
        "PAYFAST_SECURED_KEY",
        "PAYFAST_API_URL",
    )
    integration_checklist = (
        "Merchant account credentials (merchant id and secured key) from PayFast",
        "Official integration guide: token endpoint, hosted-checkout endpoint, sandbox URLs",
        "Exact request field names and ordering for the token/checkout request",
        "Notification (IPN) payload format and its signature verification scheme",
        "Whitelisted return, cancel, and notify URLs registered with PayFast",
    )


class SafepayProvider(UnconfiguredGatewayProvider):
    """Safepay — hosted checkout.

    Safepay creates a tracker/session server-side using an API key, redirects the
    customer to a hosted component, and reports the result through a signed
    webhook. The endpoint paths, payload shape, and webhook signature algorithm
    must come from Safepay's official API reference.
    """

    code = PaymentProvider.SAFEPAY
    display_name = "Safepay"
    required_settings = ("SAFEPAY_API_KEY", "SAFEPAY_API_URL")
    integration_checklist = (
        "API key and (if applicable) webhook signing secret from Safepay",
        "Official API reference for creating a payment session/tracker",
        "Hosted checkout redirect contract",
        "Webhook payload schema and signature verification algorithm",
        "Sandbox credentials for end-to-end testing before go-live",
    )


class JazzCashProvider(UnconfiguredGatewayProvider):
    """JazzCash — mobile wallet and card.

    JazzCash requests are signed with a secure hash derived from the request
    fields and an integrity salt. Both the field set and the exact concatenation
    order used to build that hash are defined by JazzCash's official integration
    document; inventing either would produce requests the gateway rejects, or
    worse, a verification routine that accepts forged callbacks.
    """

    code = PaymentProvider.JAZZCASH
    display_name = "JazzCash"
    required_settings = (
        "JAZZCASH_MERCHANT_ID",
        "JAZZCASH_PASSWORD",
        "JAZZCASH_INTEGRITY_SALT",
    )
    integration_checklist = (
        "Merchant id, password, and integrity salt from JazzCash",
        "Official integration document for the chosen product (wallet / card / hosted)",
        "Exact secure-hash field list and concatenation order",
        "Transaction status enquiry API contract for server-side verification",
        "Sandbox credentials and test wallet numbers",
    )


class EasypaisaProvider(UnconfiguredGatewayProvider):
    """Easypaisa — mobile wallet.

    Easypaisa signs requests using a store id and hash key. As with JazzCash, the
    hash construction is specified by the official merchant documentation and
    must not be guessed.
    """

    code = PaymentProvider.EASYPAISA
    display_name = "Easypaisa"
    required_settings = ("EASYPAISA_STORE_ID", "EASYPAISA_HASH_KEY")
    integration_checklist = (
        "Store id and hash key from Easypaisa",
        "Official merchant integration guide for the chosen product",
        "Exact hash construction and request field names",
        "Callback/IPN format and verification scheme",
        "Sandbox credentials for end-to-end testing",
    )


def build_gateway_providers() -> list[UnconfiguredGatewayProvider]:
    """Instantiate the gateway boundaries with whatever configuration exists.

    Credentials being present is reported separately from the integration being
    implemented, so the admin surface can distinguish "operator has not supplied
    keys" from "this still needs to be built".
    """
    settings = get_settings()
    present = {
        "PAYFAST_MERCHANT_ID": settings.payfast_merchant_id,
        "PAYFAST_SECURED_KEY": settings.payfast_secured_key,
        "PAYFAST_API_URL": settings.payfast_api_url,
        "SAFEPAY_API_KEY": settings.safepay_api_key,
        "SAFEPAY_API_URL": settings.safepay_api_url,
    }
    return [
        PayFastProvider(present),
        SafepayProvider(present),
    ]
