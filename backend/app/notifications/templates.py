"""Branded HTML email templates.

Built as a single inlined-CSS shell plus per-event bodies. Email clients strip
stylesheets, so every rule is inline; the palette matches the storefront design
system (ink, gold #C39A51, warm paper).

The logo is referenced by absolute URL rather than embedded, so the same asset
serves the storefront and the emails and no attachment handling is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

INK = "#0E0D0C"
GOLD = "#C39A51"
GOLD_DEEP = "#A37F3C"
PAPER = "#FAF8F4"
LINE = "#E4DED4"
MUTED = "#4A453F"
STONE = "#8C847A"


def _urls() -> tuple[str, str]:
    base = get_settings().frontend_base_url.rstrip("/")
    return base, f"{base}/brand/logo.png"


@dataclass(slots=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _shell(*, heading: str, preheader: str, body_html: str, cta: tuple[str, str] | None) -> str:
    base, logo = _urls()
    cta_html = ""
    if cta:
        label, href = cta
        cta_html = f"""
        <tr><td style="padding:28px 32px 0 32px;">
          <a href="{href}" style="display:inline-block;background:{INK};color:{PAPER};
             text-decoration:none;padding:14px 28px;font-size:12px;letter-spacing:0.14em;
             text-transform:uppercase;font-weight:600;font-family:Helvetica,Arial,sans-serif;">
            {label}</a>
        </td></tr>"""

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{heading}</title></head>
<body style="margin:0;padding:0;background:{PAPER};">
<div style="display:none;font-size:1px;color:{PAPER};max-height:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:{PAPER};padding:24px 12px;">
 <tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:600px;background:#FFFFFF;border:1px solid {LINE};">
   <tr><td style="background:{INK};padding:10px;text-align:center;">
     <span style="color:{GOLD};font-size:10px;letter-spacing:0.16em;
                  font-family:Helvetica,Arial,sans-serif;">
       HAND-PICKED PIECES &middot; RG THRIFTING HUB</span>
   </td></tr>
   <tr><td style="padding:28px 32px 0 32px;">
     <img src="{logo}" width="64" alt="RG Thrifting Hub"
          style="display:block;border:0;width:64px;height:auto;">
   </td></tr>
   <tr><td style="padding:24px 32px 0 32px;">
     <div style="height:2px;width:40px;background:{GOLD};"></div>
     <h1 style="margin:16px 0 0 0;font-family:Georgia,'Times New Roman',serif;
                font-size:26px;line-height:1.2;font-weight:500;color:{INK};">{heading}</h1>
   </td></tr>
   <tr><td style="padding:16px 32px 0 32px;font-family:Helvetica,Arial,sans-serif;
                  font-size:15px;line-height:1.6;color:{MUTED};">{body_html}</td></tr>
   {cta_html}
   <tr><td style="padding:32px 32px 28px 32px;">
     <div style="border-top:1px solid {LINE};padding-top:16px;
                 font-family:Helvetica,Arial,sans-serif;font-size:12px;
                 line-height:1.6;color:{STONE};">
       RG Thrifting Hub &middot; Lahore, Pakistan<br>
       <a href="{base}" style="color:{GOLD_DEEP};text-decoration:none;">{base.replace('https://','').replace('http://','')}</a>
     </div>
   </td></tr>
  </table>
 </td></tr>
</table>
</body></html>"""


def _items_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = "".join(
        f"""<tr>
          <td style="padding:8px 0;border-bottom:1px solid {LINE};
                     font-family:Helvetica,Arial,sans-serif;font-size:14px;color:{INK};">
            {item.get('name', '')}<br>
            <span style="font-size:12px;color:{STONE};">
              {item.get('variant', '')} &middot; Qty {item.get('quantity', 1)}</span>
          </td>
          <td align="right" style="padding:8px 0;border-bottom:1px solid {LINE};
                     font-family:Helvetica,Arial,sans-serif;font-size:14px;color:{INK};
                     white-space:nowrap;">{item.get('line_total', '')}</td>
        </tr>"""
        for item in items
    )
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                      style="margin-top:20px;">{rows}</table>"""


def _summary(context: dict[str, Any]) -> str:
    pairs = [
        ("Order number", context.get("order_number")),
        ("Total", context.get("total_amount")),
        ("Payment", context.get("payment_method_label")),
    ]
    if context.get("tracking_number"):
        pairs.append(("Tracking", context["tracking_number"]))
    rows = "".join(
        f"""<tr><td style="padding:4px 0;font-family:Helvetica,Arial,sans-serif;
                   font-size:13px;color:{STONE};">{label}</td>
            <td align="right" style="padding:4px 0;font-family:Helvetica,Arial,sans-serif;
                   font-size:13px;color:{INK};font-weight:600;">{value}</td></tr>"""
        for label, value in pairs
        if value
    )
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
        style="margin-top:20px;background:{PAPER};padding:0;">{rows}</table>"""


#: subject line and lead paragraph per event.
COPY: dict[str, tuple[str, str, str]] = {
    "order_created": (
        "Order {order_number} placed successfully",
        "Thank you for your order",
        "Your order has been successfully placed. We’ll email you again when it is being prepared. Here is what you ordered:",
    ),
    "payment_received": (
        "Order confirmed: {order_number}",
        "Your order is confirmed",
        "Your payment has been confirmed and your order is now being prepared.",
    ),
    "payment_failed": (
        "Payment could not be completed for {order_number}",
        "Payment unsuccessful",
        "We could not confirm your payment. Your order is on hold — you can retry from your order page.",
    ),
    "order_processing": (
        "Order confirmed: {order_number}",
        "Your order is confirmed",
        "Our team has confirmed your order and is preparing it.",
    ),
    "order_packed": (
        "Order {order_number} is packed",
        "Packed and ready",
        "Your parcel is packed and waiting for the courier.",
    ),
    "order_dispatched": (
        "Your order has been shipped: {order_number}",
        "Your order has been shipped",
        "Your parcel has been handed to the courier and is on its way to you.",
    ),
    "order_delivered": (
        "Order {order_number} delivered",
        "Delivered",
        "Your order has been delivered. We hope you love it.",
    ),
    "order_cancelled": (
        "Order {order_number} cancelled",
        "Order cancelled",
        "Your order has been cancelled and any reserved stock has been released.",
    ),
    "order_returned": (
        "Return completed for {order_number}",
        "Return completed",
        "Your return has been processed.",
    ),
    "order_exchange": (
        "Exchange completed for {order_number}",
        "Exchange completed",
        "Your exchange has been processed.",
    ),
    "return_requested": (
        "Return request received for {order_number}",
        "Request received",
        "We have your return request and will review it shortly.",
    ),
    "return_decided": (
        "Update on your request for {order_number}",
        "Request updated",
        "There is an update on your return or exchange request.",
    ),
    "shipping_updated": (
        "Shipping update for {order_number}",
        "Shipping update",
        "The delivery status of your order has changed.",
    ),
}

DEFAULT_COPY = (
    "Update on order {order_number}",
    "Order update",
    "There is an update on your order.",
)


def render(event: str, context: dict[str, Any]) -> RenderedEmail:
    """Render one event into subject, HTML and plain-text bodies."""
    base, _ = _urls()
    order_number = str(context.get("order_number", ""))
    subject_template, heading, lead = COPY.get(event, DEFAULT_COPY)
    subject = subject_template.format(order_number=order_number)

    extra = ""
    if context.get("reason"):
        extra += (
            f'<p style="margin:12px 0 0 0;color:{MUTED};">Reason: {context["reason"]}</p>'
        )
    if context.get("payment_instructions"):
        extra += (
            f'<p style="margin:16px 0 0 0;padding:12px;background:{PAPER};'
            f'border-left:2px solid {GOLD};white-space:pre-line;">'
            f'{context["payment_instructions"]}</p>'
        )

    body_html = (
        f'<p style="margin:0;">{lead}</p>'
        + _items_table(list(context.get("items") or []))
        + _summary(context)
        + extra
    )

    cta = None
    if order_number:
        cta = ("View your order", f"{base}/account/orders/{order_number}")

    text_lines = [heading, "", lead, ""]
    for item in context.get("items") or []:
        text_lines.append(
            f"- {item.get('name', '')} ({item.get('variant', '')}) x{item.get('quantity', 1)}"
            f"  {item.get('line_total', '')}"
        )
    if order_number:
        text_lines += ["", f"Order number: {order_number}"]
    if context.get("total_amount"):
        text_lines.append(f"Total: {context['total_amount']}")
    if context.get("tracking_number"):
        text_lines.append(f"Tracking: {context['tracking_number']}")
    if context.get("reason"):
        text_lines.append(f"Reason: {context['reason']}")
    if order_number:
        text_lines += ["", f"{base}/account/orders/{order_number}"]
    text_lines += ["", "RG Thrifting Hub, Lahore, Pakistan"]

    return RenderedEmail(
        subject=subject,
        html=_shell(heading=heading, preheader=lead, body_html=body_html, cta=cta),
        text="\n".join(text_lines),
    )
