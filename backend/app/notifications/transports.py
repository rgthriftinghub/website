"""Email and WhatsApp transports.

Both are chosen by name from configuration, so swapping a provider is an
environment change rather than a code change. The default for each is a logging
transport that records what *would* be sent and sends nothing — appropriate for
development and honest about not being wired to a real provider.

No credentials are invented. A transport that lacks configuration refuses to
claim it delivered anything.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger("app.notifications.transport")


@dataclass(slots=True)
class EmailMessagePayload:
    to: str
    subject: str
    html_body: str
    text_body: str


class EmailTransport(Protocol):
    name: str

    @property
    def is_live(self) -> bool: ...

    def send(self, message: EmailMessagePayload) -> bool: ...


class LoggingEmailTransport:
    """Development transport. Records the message; delivers nothing."""

    name = "log"

    @property
    def is_live(self) -> bool:
        return False

    def send(self, message: EmailMessagePayload) -> bool:
        logger.info(
            "email (not sent: logging transport) to=%s subject=%r chars=%d",
            message.to,
            message.subject,
            len(message.html_body),
        )
        return False


class SmtpEmailTransport:
    """Real SMTP delivery.

    Only selected when EMAIL_PROVIDER=smtp, which the settings validator already
    requires SMTP_HOST for. Failures are logged and reported as not-sent; they
    never propagate into the order flow that triggered them.
    """

    name = "smtp"

    @property
    def is_live(self) -> bool:
        settings = get_settings()
        return bool(settings.smtp_host)

    def send(self, message: EmailMessagePayload) -> bool:
        settings = get_settings()
        if not settings.smtp_host:
            logger.error("SMTP transport selected but SMTP_HOST is not set")
            return False

        email = EmailMessage()
        email["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.text_body)
        email.add_alternative(message.html_body, subtype="html")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(email)
        except Exception:
            # Credentials are never included in the log record.
            logger.exception("SMTP delivery failed for %s", message.to)
            return False

        logger.info("email sent to=%s subject=%r", message.to, message.subject)
        return True


def build_email_transport() -> EmailTransport:
    settings = get_settings()
    if settings.email_provider == "smtp":
        return SmtpEmailTransport()
    return LoggingEmailTransport()


# --------------------------------------------------------------------- whatsapp
@dataclass(slots=True)
class WhatsAppMessagePayload:
    to: str
    body: str
    template: str | None = None


class WhatsAppTransport(Protocol):
    name: str

    @property
    def is_live(self) -> bool: ...

    def send(self, message: WhatsAppMessagePayload) -> bool: ...


class LoggingWhatsAppTransport:
    """Development transport.

    No paid WhatsApp Business provider is configured. Integrating one requires an
    approved WhatsApp Business account, message templates approved by Meta, and
    the provider's official API contract — none of which are available here, so
    this records the message instead of inventing an API call.
    """

    name = "log"

    @property
    def is_live(self) -> bool:
        return False

    def send(self, message: WhatsAppMessagePayload) -> bool:
        logger.info(
            "whatsapp (not sent: logging transport) to=%s template=%s body=%r",
            message.to,
            message.template,
            message.body[:200],
        )
        return False


def build_whatsapp_transport() -> WhatsAppTransport:
    """Return the configured transport.

    Only the logging transport exists. An unrecognised WHATSAPP_PROVIDER falls
    back to logging with a warning rather than silently doing nothing.
    """
    settings = get_settings()
    if settings.whatsapp_provider not in ("log", "", None):
        logger.warning(
            "WHATSAPP_PROVIDER=%r has no implementation; falling back to the logging transport",
            settings.whatsapp_provider,
        )
    return LoggingWhatsAppTransport()


class WhatsAppNotifier:
    """Event-shaped WhatsApp API, mirroring the spec's method names."""

    def __init__(self, transport: WhatsAppTransport | None = None) -> None:
        self._transport = transport or build_whatsapp_transport()

    @property
    def is_live(self) -> bool:
        return self._transport.is_live

    def _send(self, to: str | None, body: str, template: str) -> bool:
        if not to:
            return False
        return self._transport.send(
            WhatsAppMessagePayload(to=to, body=body, template=template)
        )

    def send_order_confirmation(self, to: str | None, order_number: str, total: str) -> bool:
        return self._send(
            to,
            f"RG Thrifting Hub: your order {order_number} is confirmed. Total {total}.",
            "order_confirmation",
        )

    def send_dispatch_notification(
        self, to: str | None, order_number: str, tracking: str | None
    ) -> bool:
        suffix = f" Tracking: {tracking}." if tracking else ""
        return self._send(
            to,
            f"RG Thrifting Hub: order {order_number} has been dispatched.{suffix}",
            "order_dispatched",
        )

    def send_delivery_notification(self, to: str | None, order_number: str) -> bool:
        return self._send(
            to,
            f"RG Thrifting Hub: order {order_number} has been delivered. Thank you!",
            "order_delivered",
        )

    def send_cancellation_notification(self, to: str | None, order_number: str) -> bool:
        return self._send(
            to,
            f"RG Thrifting Hub: order {order_number} has been cancelled.",
            "order_cancelled",
        )
