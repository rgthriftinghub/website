"""Order invoice PDF.

Rendered server-side with ReportLab, which ships pure-Python wheels and needs no
system libraries in the slim container image. Deliberately a single-page,
single-purpose document — not a templating system.

Every value comes from the order's own snapshots, so an invoice reprinted a year
later shows exactly what was bought and where it was sent, even if the catalogue
or the customer's address book has changed since.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph

from app.core.config import get_settings
from app.core.timezones import to_business_time
from app.models.order import Order

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"

# Brand colours, matching the storefront design system.
INK = colors.HexColor("#0E0D0C")
GOLD = colors.HexColor("#C39A51")
MUTED = colors.HexColor("#6B655D")
LINE = colors.HexColor("#D8D2C6")

# Store details are placeholders until the client supplies registered particulars.
STORE_NAME = "RG Thrifting Hub"
STORE_LINES = (
    "Lahore, Pakistan",
    "hello@rgthriftinghub.pk",
    "+92 300 000 0000",
)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def invoice_filename(order: Order) -> str:
    return f"invoice-{order.order_number}.pdf"


def _money(value: Decimal, currency: str) -> str:
    return f"{currency} {value:,.2f}"


def _draw_header(c: pdf_canvas.Canvas, order: Order, y: float) -> float:
    if LOGO_PATH.exists():
        logo_height = 26 * mm
        logo_width = logo_height * (1122 / 1402)  # preserve the artwork's ratio
        c.drawImage(
            str(LOGO_PATH),
            MARGIN,
            y - logo_height,
            width=logo_width,
            height=logo_height,
            preserveAspectRatio=True,
            mask="auto",
        )

    right = PAGE_WIDTH - MARGIN
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(right, y - 6 * mm, "INVOICE")

    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    text_y = y - 13 * mm
    for line in (STORE_NAME, *STORE_LINES):
        c.drawRightString(right, text_y, line)
        text_y -= 4.4 * mm

    y = min(y - 32 * mm, text_y - 3 * mm)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.4)
    c.line(MARGIN, y, right, y)
    return y - 9 * mm


def _draw_meta(c: pdf_canvas.Canvas, order: Order, y: float) -> float:
    """Order metadata on the left, delivery address on the right."""
    column = CONTENT_WIDTH / 2
    label_style = ("Helvetica-Bold", 8)
    value_style = ("Helvetica", 9.5)

    rows = [
        ("ORDER NUMBER", order.order_number),
        # Business-local, so the printed date always matches the date encoded in
        # the order number above it.
        ("ORDER DATE", to_business_time(order.created_at).strftime("%d %B %Y")),
        ("PAYMENT METHOD", str(order.payment_method).replace("_", " ").title()),
        ("PAYMENT STATUS", str(order.payment_status).title()),
        ("ORDER STATUS", str(order.order_status).title()),
    ]

    left_y = y
    for label, value in rows:
        c.setFont(*label_style)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, left_y, label)
        c.setFont(*value_style)
        c.setFillColor(INK)
        c.drawString(MARGIN + 32 * mm, left_y, value)
        left_y -= 5.6 * mm

    address = order.shipping_address_snapshot or {}
    right_x = MARGIN + column + 6 * mm
    right_y = y
    c.setFont(*label_style)
    c.setFillColor(MUTED)
    c.drawString(right_x, right_y, "DELIVER TO")
    right_y -= 5.6 * mm

    address_lines = [
        address.get("full_name"),
        address.get("phone"),
        address.get("address_line_1"),
        address.get("address_line_2"),
        ", ".join(part for part in (address.get("city"), address.get("province")) if part),
        ", ".join(
            part for part in (address.get("postal_code"), address.get("country")) if part
        ),
        order.contact_email,
    ]
    c.setFont(*value_style)
    c.setFillColor(INK)
    for line in address_lines:
        if not line:
            continue
        c.drawString(right_x, right_y, str(line)[:52])
        right_y -= 5 * mm

    return min(left_y, right_y) - 6 * mm


def _draw_items(c: pdf_canvas.Canvas, order: Order, y: float, currency: str) -> float:
    # Numeric columns are right-aligned to fixed right edges. Left-aligning the
    # unit price let a wide amount run into the line total beside it.
    columns = {
        "item": MARGIN,
        "qty_right": MARGIN + 112 * mm,
        "price_right": MARGIN + 143 * mm,
        "total_right": PAGE_WIDTH - MARGIN - 2 * mm,
    }

    c.setFillColor(colors.HexColor("#F3EFE8"))
    c.rect(MARGIN, y - 7 * mm, CONTENT_WIDTH, 7 * mm, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(MUTED)
    header_y = y - 4.8 * mm
    c.drawString(columns["item"] + 2 * mm, header_y, "ITEM")
    c.drawRightString(columns["qty_right"], header_y, "QTY")
    c.drawRightString(columns["price_right"], header_y, "UNIT PRICE")
    c.drawRightString(columns["total_right"], header_y, "LINE TOTAL")
    y -= 11 * mm

    name_style = ParagraphStyle(
        "item", fontName="Helvetica", fontSize=9.5, leading=11.5, textColor=INK
    )
    detail_style = ParagraphStyle(
        "detail", fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED
    )

    for item in order.items:
        detail_bits = [f"SKU {item.sku_snapshot}", item.variant_label]
        if item.brand_name_snapshot:
            detail_bits.insert(0, item.brand_name_snapshot)

        name = Paragraph(item.product_name_snapshot, name_style)
        detail = Paragraph(" · ".join(bit for bit in detail_bits if bit), detail_style)
        # Narrower than the qty column's left edge, so long names wrap rather
        # than running under the numbers.
        name_width = 92 * mm
        name_height = name.wrap(name_width, 40 * mm)[1]
        detail_height = detail.wrap(name_width, 20 * mm)[1]
        row_height = name_height + detail_height + 3 * mm

        # Start a new page if this row would run off the bottom.
        if y - row_height < MARGIN + 55 * mm:
            c.showPage()
            y = PAGE_HEIGHT - MARGIN

        name.drawOn(c, columns["item"] + 2 * mm, y - name_height)
        detail.drawOn(c, columns["item"] + 2 * mm, y - name_height - detail_height - 1 * mm)

        c.setFont("Helvetica", 9.5)
        c.setFillColor(INK)
        c.drawRightString(columns["qty_right"], y - name_height, str(item.quantity))
        c.drawRightString(
            columns["price_right"], y - name_height, _money(item.unit_price, currency)
        )
        c.drawRightString(
            columns["total_right"], y - name_height, _money(item.line_total, currency)
        )

        y -= row_height
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
        y -= 4 * mm

    return y


def _draw_totals(c: pdf_canvas.Canvas, order: Order, y: float, currency: str) -> float:
    label_x = PAGE_WIDTH - MARGIN - 62 * mm
    value_x = PAGE_WIDTH - MARGIN

    rows: list[tuple[str, Decimal, bool]] = [
        ("Subtotal", order.subtotal, False),
        ("Delivery", order.shipping_amount, False),
    ]
    if order.discount_amount and order.discount_amount > 0:
        rows.insert(1, ("Discount", -order.discount_amount, False))
    rows.append(("Total", order.total_amount, True))

    for label, value, emphasise in rows:
        if emphasise:
            y -= 2 * mm
            c.setStrokeColor(INK)
            c.setLineWidth(0.9)
            c.line(label_x, y + 5 * mm, value_x, y + 5 * mm)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(INK)
        else:
            c.setFont("Helvetica", 9.5)
            c.setFillColor(MUTED)
        c.drawString(label_x, y, label)
        if emphasise:
            c.setFillColor(INK)
        c.drawRightString(value_x, y, _money(value, currency))
        y -= 6.4 * mm

    return y


def _draw_footer(c: pdf_canvas.Canvas, order: Order, currency: str) -> None:
    y = MARGIN + 20 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, y + 8 * mm, PAGE_WIDTH - MARGIN, y + 8 * mm)

    note = {
        "COD": "Payable in cash on delivery.",
        "BANK_TRANSFER": "Please quote the order number with your bank transfer.",
    }.get(str(order.payment_method), "")

    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    if note:
        c.drawString(MARGIN, y + 2 * mm, note)
    c.drawString(
        MARGIN, y - 3 * mm, f"Thank you for shopping with {STORE_NAME}."
    )
    c.setFillColor(GOLD)
    c.drawRightString(
        PAGE_WIDTH - MARGIN, y - 3 * mm, f"{order.order_number} · {_money(order.total_amount, currency)}"
    )


def render_invoice_pdf(order: Order) -> bytes:
    """Render a one-page invoice and return the PDF bytes."""
    currency = get_settings().currency_code
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Invoice {order.order_number}")
    c.setAuthor(STORE_NAME)
    c.setSubject(f"Invoice for order {order.order_number}")

    y = PAGE_HEIGHT - MARGIN
    y = _draw_header(c, order, y)
    y = _draw_meta(c, order, y)
    y = _draw_items(c, order, y, currency)
    _draw_totals(c, order, y, currency)

    if order.customer_note:
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, MARGIN + 32 * mm, f"Note: {order.customer_note[:120]}")

    _draw_footer(c, order, currency)
    c.showPage()
    c.save()
    return buffer.getvalue()
