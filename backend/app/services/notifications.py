"""Notification dispatch.

Order and payment code announces an event here; this module decides which
channels carry it. The public functions are unchanged from Phase 3, so no caller
needed updating when email and WhatsApp were added.

Delivery failures are always swallowed and logged: a mail server being down must
never roll back an order that succeeded.
"""

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from app.models.enums import OrderStatus
from app.notifications import templates
from app.notifications.transports import (
    EmailMessagePayload,
    WhatsAppNotifier,
    build_email_transport,
)

if TYPE_CHECKING:
    from app.models.order import Order

logger = logging.getLogger("app.notifications")


class NotificationEvent(StrEnum):
    ORDER_CREATED = "order_created"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    ORDER_PROCESSING = "order_processing"
    ORDER_PACKED = "order_packed"
    ORDER_DISPATCHED = "order_dispatched"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_RETURNED = "order_returned"
    ORDER_EXCHANGE = "order_exchange"
    RETURN_REQUESTED = "return_requested"
    RETURN_APPROVED = "return_approved"
    RETURN_REJECTED = "return_rejected"
    RETURN_DECIDED = "return_decided"
    SHIPPING_UPDATED = "shipping_updated"


# Which event a status change announces. Statuses absent from this map are not
# customer-notifiable.
STATUS_EVENTS: dict[OrderStatus, NotificationEvent] = {
    OrderStatus.PENDING: NotificationEvent.ORDER_CREATED,
    OrderStatus.PROCESSING: NotificationEvent.ORDER_PROCESSING,
    OrderStatus.PACKED: NotificationEvent.ORDER_PACKED,
    OrderStatus.DISPATCHED: NotificationEvent.ORDER_DISPATCHED,
    OrderStatus.DELIVERED: NotificationEvent.ORDER_DELIVERED,
    OrderStatus.CANCELLED: NotificationEvent.ORDER_CANCELLED,
    OrderStatus.RETURNED: NotificationEvent.ORDER_RETURNED,
    OrderStatus.EXCHANGE: NotificationEvent.ORDER_EXCHANGE,
}

# Events that also warrant a WhatsApp message. Deliberately a short list: the
# channel is intrusive, so only the milestones a customer actually wants.
WHATSAPP_EVENTS = frozenset(
    {
        NotificationEvent.ORDER_CREATED,
        NotificationEvent.ORDER_DISPATCHED,
        NotificationEvent.ORDER_DELIVERED,
        NotificationEvent.ORDER_CANCELLED,
    }
)


class NotificationService(Protocol):
    """Transport contract. Implementations must not raise into caller code."""

    def notify(
        self, event: NotificationEvent, *, recipient: str, context: dict[str, Any]
    ) -> None: ...


class LoggingNotificationService:
    """Records the notification and sends nothing. Used by tests."""

    def __init__(self) -> None:
        self.sent: list[tuple[NotificationEvent, str, dict[str, Any]]] = []

    def notify(
        self, event: NotificationEvent, *, recipient: str, context: dict[str, Any]
    ) -> None:
        self.sent.append((event, recipient, context))
        logger.info("notification event=%s recipient=%s", event.value, recipient)


class ChannelNotificationService:
    """Default service: renders a branded email and, for milestones, a WhatsApp message."""

    def __init__(self) -> None:
        self._email = build_email_transport()
        self._whatsapp = WhatsAppNotifier()

    @property
    def channels(self) -> dict[str, bool]:
        return {"email": self._email.is_live, "whatsapp": self._whatsapp.is_live}

    def notify(
        self, event: NotificationEvent, *, recipient: str, context: dict[str, Any]
    ) -> None:
        rendered = templates.render(event.value, context)
        if recipient:
            self._email.send(
                EmailMessagePayload(
                    to=recipient,
                    subject=rendered.subject,
                    html_body=rendered.html,
                    text_body=rendered.text,
                )
            )

        if event in WHATSAPP_EVENTS:
            phone = context.get("contact_phone")
            order_number = str(context.get("order_number", ""))
            total = str(context.get("total_amount", ""))
            if event is NotificationEvent.ORDER_CREATED:
                self._whatsapp.send_order_confirmation(phone, order_number, total)
            elif event is NotificationEvent.ORDER_DISPATCHED:
                self._whatsapp.send_dispatch_notification(
                    phone, order_number, context.get("tracking_number")
                )
            elif event is NotificationEvent.ORDER_DELIVERED:
                self._whatsapp.send_delivery_notification(phone, order_number)
            elif event is NotificationEvent.ORDER_CANCELLED:
                self._whatsapp.send_cancellation_notification(phone, order_number)


_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = ChannelNotificationService()
    return _service


def set_notification_service(service: NotificationService | None) -> None:
    """Swap the transport. Used by tests and by a future provider integration."""
    global _service
    _service = service


PAYMENT_METHOD_LABELS = {
    "COD": "Cash on Delivery",
    "BANK_TRANSFER": "Bank Transfer",
    "PAYFAST": "PayFast",
    "SAFEPAY": "Safepay",
    "JAZZCASH": "JazzCash",
    "EASYPAISA": "Easypaisa",
}


def _order_context(order: "Order") -> dict[str, Any]:
    """Everything a template might need, drawn from the order's own snapshots."""
    currency = "PKR"
    shipment = getattr(order, "shipment", None)
    context: dict[str, Any] = {
        "order_number": order.order_number,
        "order_status": str(order.order_status),
        "payment_status": str(order.payment_status),
        "payment_method": str(order.payment_method),
        "payment_method_label": PAYMENT_METHOD_LABELS.get(
            str(order.payment_method), str(order.payment_method)
        ),
        "total_amount": f"{currency} {order.total_amount:,.0f}",
        "contact_phone": order.contact_phone,
        "customer_name": (order.shipping_address_snapshot or {}).get("full_name"),
    }
    try:
        context["items"] = [
            {
                "name": item.product_name_snapshot,
                "variant": item.variant_label,
                "quantity": item.quantity,
                "line_total": f"{currency} {item.line_total:,.0f}",
            }
            for item in order.items
        ]
    except Exception:  # noqa: BLE001 - context building must never break a notification
        context["items"] = []

    if shipment is not None:
        context["tracking_number"] = shipment.tracking_number
        context["shipping_status"] = str(shipment.shipping_status)
    return context


def notify_order_event(event: NotificationEvent, order: "Order", **extra: Any) -> None:
    """Announce an order event.

    Delivery failures are logged, never raised: a notification problem must not
    roll back or fail the order operation that triggered it.
    """
    context = _order_context(order)
    context.update({key: value for key, value in extra.items() if value is not None})
    try:
        get_notification_service().notify(
            event, recipient=order.contact_email or "", context=context
        )
    except Exception:  # noqa: BLE001 - deliberately swallowed
        logger.exception("Failed to dispatch notification %s", event.value)


def notify_status_change(order: "Order", **extra: Any) -> None:
    event = STATUS_EVENTS.get(order.order_status)
    if event is not None:
        notify_order_event(event, order, **extra)
