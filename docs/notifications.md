# Notifications

## Integration status

| Channel | Status | Notes |
| --- | --- | --- |
| **Email — logging transport** | **LIVE (development)** | Default. Renders the real branded template and logs it. Sends nothing. |
| **Email — SMTP** | **CONFIGURED, NO CREDENTIALS** | Fully implemented. Set `EMAIL_PROVIDER=smtp` plus SMTP credentials to activate. Untested against a live server. |
| **WhatsApp — logging transport** | **LIVE (development)** | Default. Composes the message and logs it. Sends nothing. |
| **WhatsApp — provider API** | **NOT CONFIGURED** | No integration. Needs an approved WhatsApp Business account and Meta-approved templates. |

The SMTP transport is real, working code — it builds a multipart message and
delivers it through `smtplib`. It is marked "no credentials" rather than "live"
because it has never been run against an actual mail server here.

No WhatsApp provider is integrated. Doing so requires an approved WhatsApp Business
account, message templates approved by Meta, and the provider's official API
contract — none of which were available. The abstraction and the event-shaped
methods exist so a provider drops in without touching any caller.

## Architecture

```
app/services/notifications.py    # dispatcher: events → channels
app/notifications/
├── transports.py                # EmailTransport / WhatsAppTransport + implementations
└── templates.py                 # branded HTML + plain-text rendering
```

Order and payment code calls `notify_order_event(...)`. It does not know or care
which channels exist. The dispatcher decides.

The public API is unchanged from Phase 3, so adding email and WhatsApp required no
edits to any calling site.

### The non-negotiable rule

**A notification failure must never break the operation that triggered it.**

`notify_order_event` wraps dispatch in a bare `except` that logs and swallows. A
dead mail server cannot roll back an order that succeeded, and cannot fail a
payment verification. Covered by
`test_notification_failure_never_breaks_the_operation`.

## Events

| Event | Fires when |
| --- | --- |
| `order_created` | Order placed |
| `payment_received` | Payment reaches `PAID` |
| `payment_failed` | Payment reaches `FAILED` |
| `order_processing` | Status → `PROCESSING` |
| `order_packed` | Status → `PACKED` |
| `order_dispatched` | Status → `DISPATCHED` |
| `order_delivered` | Status → `DELIVERED` |
| `order_cancelled` | Status → `CANCELLED` |
| `order_returned` / `order_exchange` | Return or exchange completed |
| `return_requested` | Customer opens a request |
| `return_decided` | Staff decide a request |
| `shipping_updated` | Shipment status changes |

Every event has a template. `test_every_notification_event_renders_a_template`
asserts this, so a new event cannot silently fall back to generic copy.

### Notifications fire once per real change

Both the webhook dedupe layer and the `transition()` no-change guard sit *before*
the notification call, so a replayed webhook produces no duplicate email.
Covered by `test_duplicate_webhook_is_processed_once`.

## Channels

**Email** carries every event.

**WhatsApp** carries only four milestones — `order_created`, `order_dispatched`,
`order_delivered`, `order_cancelled`. The channel is intrusive, so it gets the
events a customer actually wants rather than every internal transition.

## Templates

A single inlined-CSS shell plus per-event bodies, in `templates.py`.

- Every rule is inline — email clients strip stylesheets.
- The palette matches the storefront: ink `#0E0D0C`, gold `#C39A51`, warm paper.
- Playfair-style serif headings via a Georgia fallback stack, since custom fonts
  are unreliable in email.
- The logo is referenced by absolute URL (`{FRONTEND_BASE_URL}/brand/logo.png`), so
  one asset serves the site and the emails with no attachment handling.
- Both HTML and plain-text bodies are produced for every message.
- Tables are used for layout, because that is what email clients render reliably.

`test_template_includes_the_logo_and_brand_palette` asserts the logo URL and the
brand gold are present.

## Configuration

```
FRONTEND_BASE_URL=http://localhost:3000   # used for logo + order links in emails

EMAIL_PROVIDER=log                        # "log" (default) or "smtp"
EMAIL_FROM_NAME=RG Thrifting Hub
EMAIL_FROM_ADDRESS=no-reply@rgthriftinghub.pk
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true

WHATSAPP_PROVIDER=log                     # only "log" is implemented
WHATSAPP_API_KEY=
WHATSAPP_API_URL=
WHATSAPP_SENDER=
```

`EMAIL_PROVIDER=smtp` without `SMTP_HOST` **fails at startup** rather than
silently dropping every message — a misconfigured mail setup that looks like a
working one is worse than a refusal to boot.

An unrecognised `WHATSAPP_PROVIDER` falls back to the logging transport with a
warning, rather than silently doing nothing.

## Honest reporting

Both logging transports return `False` from `send()` and report
`is_live == False`. A development transport never claims it delivered anything.
Covered by `test_logging_transports_report_themselves_as_not_live`.

## Adding a provider

1. Write a class satisfying `EmailTransport` or `WhatsAppTransport`
   (`name`, `is_live`, `send`).
2. Return it from `build_email_transport()` / `build_whatsapp_transport()` for the
   relevant `*_PROVIDER` value.
3. `send()` must not raise into caller code — log and return `False` instead.

Nothing else changes. Tests swap the whole service via
`notifications.set_notification_service(...)`.
