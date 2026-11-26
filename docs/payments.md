# Payments

## Integration status

This is the authoritative list. Nothing below is described as working unless it
has actually been implemented and tested.

| Provider | Status | Notes |
| --- | --- | --- |
| **Cash on Delivery** | **LIVE** | Fully implemented and tested. No external API involved. |
| **Bank Transfer** | **LIVE** | Fully implemented and tested. Manual reconciliation by staff. |
| **JazzCash** | **LIVE (manual transfer)** | Receiving number from configuration; customer sends screenshot on WhatsApp; staff manually confirms. No gateway API. |
| **Easypaisa** | **LIVE (manual transfer)** | Receiving number from configuration; customer sends screenshot on WhatsApp; staff manually confirms. No gateway API. |
| PayFast | **NOT CONFIGURED** | Architecture boundary only. No integration code. |
| Safepay | **NOT CONFIGURED** | Architecture boundary only. No integration code. |

### Why gateway APIs are not implemented

Building a real payment integration requires the provider's official
documentation: exact endpoint URLs, request field names, the signature/hash
construction *and its field ordering*, the webhook payload shape, and the
signature verification scheme. None of that was available in this repository or
environment.

Guessing any of it would produce code that looks finished, passes its own invented
tests, and then fails — or silently mishandles money — against the real gateway. A
fabricated signature-verification routine is worse still: it would accept forged
callbacks.

PayFast and Safepay remain registered providers in the domain model that **refuse every
operation** with a clear, customer-safe message. They cannot be selected at
checkout, and they can never report a false success.

### Making a gateway live

1. Obtain merchant credentials and the official integration document.
2. Replace the provider class in `backend/app/payments/providers/gateways.py`
   with an implementation written against that document. It must implement
   `create_payment`, `verify_payment`, `parse_callback`, and `parse_webhook`, and
   **must verify the provider's signature inside `parse_webhook`** before
   returning, raising `WebhookVerificationError` when it does not check out.
3. Set the provider's environment variables (listed per provider in that file's
   `required_settings`).
4. Test against the provider's sandbox end to end before go-live.

Nothing outside that one file changes. The order flow, audit trail, idempotency,
admin screens, and notifications already work through `BasePaymentProvider`.

Each boundary also declares an `integration_checklist` naming exactly what still
has to be obtained. `GET /api/v1/payments/providers` surfaces this at runtime, and
the admin payments screen shows it, so no operator can mistake a declared provider
for a working one.

## The rule

**The backend is the only authority on payment state.** A frontend may ask to
*start* a payment; it can never assert the outcome.

Payment status changes originate from exactly four trusted sources:

1. an offline provider's own rules (COD and bank transfer both start `PENDING`),
2. a **verified** provider webhook,
3. a provider verification call made by us, or
4. an explicit, audited staff action.

No request body anywhere accepts an amount, a status, or a transaction id. The
amount always comes from the order the backend computed.

## Architecture

```
app/payments/
├── base.py                  # provider contract, redaction, dataclasses
├── service.py               # registry, transitions, webhooks, refunds
└── providers/
    ├── offline.py           # COD + Bank Transfer + manual JazzCash/Easypaisa (LIVE)
    └── gateways.py          # PayFast and Safepay API boundaries
```

`Payment` holds all gateway-specific detail, never `Order`. An order keeps a
denormalised `payment_status` for listing and filtering; `Payment` remains the
source of truth. This is why adding a provider does not reshape the orders table.

An order may have several payments (a declined attempt, then a successful retry).
`Order.active_payment` resolves the authoritative one, preferring a settled payment
over an unsettled one.

### Models

| Model | Purpose |
| --- | --- |
| `Payment` | One payment attempt: provider, amount, status, gateway ids, bank reference, staff verification. |
| `PaymentTransaction` | Append-only audit trail. Every event that touched a payment. |
| `Refund` | Refund bookkeeping. Recording one does not move money. |
| `WebhookEvent` | Every inbound gateway message, and the idempotency key. |

### Status lifecycle

`PENDING → PROCESSING → PAID → REFUNDED`, with `FAILED` and `CANCELLED` branches.
Transitions are enforced by `PAYMENT_STATUS_TRANSITIONS` in
`app/models/enums.py` — an illegal move raises rather than being silently applied.

`PAID`, `CANCELLED`, and `REFUNDED` are terminal. A late or replayed webhook can
never reopen them.

Order status and payment status are deliberately **separate fields**. An order can
be `DELIVERED` while payment is `PENDING` (unpaid COD), or `DISPATCHED` while
payment is `PAID`.

## Webhook flow

```
Gateway  →  POST /api/v1/payments/{provider}/webhook
              │
              ├─ 1. provider.parse_webhook() verifies the signature
              │       └─ invalid → recorded, rejected, payment untouched
              │
              ├─ 2. WebhookEvent insert on (provider, external_id)
              │       └─ duplicate → short-circuit, no side effects
              │
              ├─ 3. terminal-status guard
              │       └─ already settled → ignored
              │
              └─ 4. transition() + audit entry + notification
```

Webhook endpoints are **not** session-authenticated — a gateway has no cookie.
Their authenticity comes entirely from the provider's signature.

They return HTTP 200 for both accepted and duplicate messages, because gateways
retry on non-2xx and a duplicate is not an error. The response body is terse and
never echoes the payload.

### Idempotency

Two independent layers:

1. **`WebhookEvent`** has a unique constraint on `(provider, external_id)`. A
   replayed delivery hits it, is recognised, and returns before any payment
   update, stock movement, or notification.
2. **`transition()`** returns `False` when the payment already holds the target
   status, so a message that somehow bypasses layer one still cannot double-apply.

Providers that supply no usable event id must return a payload fingerprint as the
dedupe key instead.

Verified by `test_duplicate_webhook_is_processed_once`: three identical deliveries
produce one `WebhookEvent` row, one `VERIFIED` transition, and one notification.

A browser callback (`/callback`) goes through the same verification path. The
customer's browser is not a trusted channel, so a callback is a hint that
something happened — never proof that it succeeded.

## Security

- **Redaction before storage.** `redact()` in `base.py` strips any key matching
  `password`, `secret`, `secured_key`, `api_key`, `token`, `salt`, `signature`,
  `hash`, `authorization`, `cvv`, `card`, `pan`, `pin`, `otp` — case-insensitive,
  substring, recursive. Applied before anything reaches `raw_response`,
  `WebhookEvent.payload`, or the log.
- **No card data is ever stored.** Card and wallet flows, when built, must use the
  provider's hosted page or tokenisation. This system never sees a card number.
- **No customer banking credentials.** Bank transfer stores only the reference
  string the customer quotes.
- **Credentials never logged.** SMTP and gateway failures log the exception
  without the credential values.
- **Customer responses are narrow.** `PaymentRead` does not declare
  `raw_response`, `internal_note`, `verified_by_user_id`, or `proof_url`.
- **Ownership is in the query.** `get_payment_for_user` joins through
  `Order.user_id`, so another customer's payment id is not found rather than
  readable.
- **Admin routes are role-gated at the parent router**, so a new admin route
  cannot be added unprotected by accident.

## Workflows

### Cash on Delivery (LIVE)

1. Order placed → `Payment(provider=COD, status=PENDING)`.
2. Nothing is charged. The payment stays `PENDING` through dispatch and delivery.
3. Courier collects cash; staff record it via
   `POST /admin/payments/{id}/mark-cod-collected` → `PAID`.

COD is never auto-marked paid at order creation.

### Bank Transfer (LIVE)

1. Order placed → `Payment(provider=BANK_TRANSFER, status=PENDING)`.
2. Checkout shows the store's receiving accounts, read from the `bank_accounts`
   table via `GET /payments/bank-accounts` — never hardcoded in the frontend.
3. Customer transfers, then submits their reference via
   `POST /customer/orders/{order_number}/payment/bank-transfer`. This records
   `customer_reference` and `proof_submitted_at`. **It does not mark the payment
   paid** — that would let a customer settle their own order.
4. Staff reconcile against the bank statement and either
   `verify-bank-transfer` → `PAID`, or `reject-bank-transfer` → `FAILED` with a
   reason.

The seeded bank account is a clearly-marked `DEMO` placeholder. **Replace it with
the store's real receiving account before accepting live payments** — a plausible
fake number could receive real money.

## Refunds

`Refund` is a bookkeeping foundation. Recording one does not move money;
automatic gateway refunds need a configured provider API. Staff settle out of
band and mark the refund completed. A payment becomes `REFUNDED` only once the
completed refunds cover its full amount; partial refunds leave it `PAID`.

Refunds cannot exceed the payment, and only a `PAID` payment can be refunded.

## Endpoints

**Public** — `GET /payments/providers` · `GET /payments/bank-accounts` ·
`POST|GET /payments/{provider}/webhook` · `POST|GET /payments/{provider}/callback`

**Customer** — `GET /customer/orders/{order_number}/payment` ·
`POST /customer/orders/{order_number}/payment/bank-transfer`

**Admin** — `GET /admin/payments` · `GET /admin/payments/stats` ·
`GET /admin/payments/{id}` · `POST /admin/payments/{id}/verify-bank-transfer` ·
`POST /admin/payments/{id}/reject-bank-transfer` ·
`POST /admin/payments/{id}/mark-cod-collected` ·
`POST /admin/payments/{id}/refunds` ·
`POST /admin/payments/refunds/{id}/complete`

There is deliberately **no endpoint that sets a gateway payment's status by
hand**.

## Environment variables

None are required for the live COD and bank-transfer flows.

The gateway variables below are read but unused, because no gateway integration
exists. Setting them does **not** make a gateway work — `is_configured` stays
`false` until the integration itself is written.

```
PAYFAST_MERCHANT_ID=
PAYFAST_SECURED_KEY=
PAYFAST_API_URL=

SAFEPAY_API_KEY=
SAFEPAY_API_URL=

JAZZCASH_MERCHANT_ID=
JAZZCASH_PASSWORD=
JAZZCASH_INTEGRITY_SALT=

EASYPAISA_STORE_ID=
EASYPAISA_HASH_KEY=
```

Never commit real credentials. `.env` is gitignored and dockerignored.
