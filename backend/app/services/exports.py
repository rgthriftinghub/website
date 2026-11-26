"""CSV and Excel export.

CSV is **streamed** row by row through a generator, so exporting 50,000 orders never
builds the whole file in memory. Excel cannot be streamed the same way (the format
needs a complete workbook), so those exports are bounded by `MAX_EXCEL_ROWS` and
say so rather than quietly truncating.

Customer exports carry contact details because that is their purpose, but no export
anywhere includes a password hash, a payment gateway payload, or a staff note.
Every export route requires REPORTS_VIEW.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezones import to_business_time
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.inventory import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.services import analytics

# Excel has to be assembled whole, so it is capped. CSV has no cap because it streams.
MAX_EXCEL_ROWS = 20_000

# Rows fetched per database round trip while streaming.
STREAM_CHUNK = 500

INK = "FF0E0D0C"
GOLD = "FFC39A51"


def _stamp(moment: datetime | None) -> str:
    return to_business_time(moment).strftime("%Y-%m-%d %H:%M") if moment else ""


def timestamped_filename(prefix: str, extension: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M')}.{extension}"


# --------------------------------------------------------------------- datasets
def product_rows(db: Session, *, include_inactive: bool = False) -> tuple[list[str], Iterator[list[Any]]]:
    """One row per variant, which is the level stock actually lives at."""
    header = [
        "SKU", "Item Code", "Single Piece", "Product Name", "Slug", "Brand", "Category", "Subcategory",
        "Variant", "Size", "Waist", "Colour", "Fabric", "Condition", "Gender",
        "Product Type", "Regular Price", "Sale Price", "Stock", "Low Stock Threshold",
        "Featured", "New Arrival", "Status",
    ]

    stmt = (
        select(Product, ProductVariant, InventoryItem, Brand, Category, Subcategory)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .outerjoin(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(Subcategory, Subcategory.id == Product.subcategory_id)
        .order_by(Product.name, ProductVariant.sku)
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    def rows() -> Iterator[list[Any]]:
        for product, variant, inventory, brand, category, subcategory in db.execute(
            stmt
        ).yield_per(STREAM_CHUNK):
            yield [
                variant.sku,
                product.item_code,
                "Yes" if product.single_piece else "No",
                product.name,
                product.slug,
                brand.name if brand else "",
                category.name if category else "",
                subcategory.name if subcategory else "",
                variant.label,
                variant.size or "",
                variant.waist if variant.waist is not None else "",
                variant.color or "",
                product.fabric or "",
                str(product.condition),
                str(product.gender),
                str(product.product_type),
                float(product.regular_price),
                float(product.sale_price) if product.sale_price is not None else "",
                inventory.quantity if inventory else 0,
                inventory.low_stock_threshold if inventory else 0,
                "Yes" if product.is_featured else "No",
                "Yes" if product.is_new_arrival else "No",
                "Active" if product.is_active else "Inactive",
            ]

    return header, rows()


def inventory_rows(db: Session) -> tuple[list[str], Iterator[list[Any]]]:
    header = [
        "SKU", "Product", "Variant", "Size", "Waist",
        "Current Stock", "Threshold", "Status",
    ]
    stmt = (
        select(Product, ProductVariant, InventoryItem)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .where(Product.is_active.is_(True), ProductVariant.is_active.is_(True))
        .order_by(InventoryItem.quantity, Product.name)
    )

    def rows() -> Iterator[list[Any]]:
        for product, variant, inventory in db.execute(stmt).yield_per(STREAM_CHUNK):
            if inventory.quantity <= 0:
                status = "Out of stock"
            elif inventory.quantity <= inventory.low_stock_threshold:
                status = "Low stock"
            else:
                status = "In stock"
            yield [
                variant.sku, product.name, variant.label,
                variant.size or "", variant.waist if variant.waist is not None else "",
                inventory.quantity, inventory.low_stock_threshold, status,
            ]

    return header, rows()


def order_rows(
    db: Session, window: analytics.DateRange | None = None
) -> tuple[list[str], Iterator[list[Any]]]:
    header = [
        "Order Number", "Date", "Customer", "Email", "Phone", "City",
        "Items", "Subtotal", "Discount", "Shipping", "Total",
        "Payment Method", "Payment Status", "Order Status", "Tracking Number",
    ]
    conditions = []
    if window is not None:
        conditions = [Order.created_at >= window.start, Order.created_at < window.end]

    stmt = (
        select(Order)
        .where(*conditions)
        .order_by(Order.created_at.desc())
        .options(selectinload(Order.items), selectinload(Order.shipment))
    )

    def rows() -> Iterator[list[Any]]:
        for order in db.execute(stmt).unique().scalars().yield_per(STREAM_CHUNK):
            address = order.shipping_address_snapshot or {}
            yield [
                order.order_number,
                _stamp(order.created_at),
                address.get("full_name", ""),
                order.contact_email,
                order.contact_phone,
                address.get("city", ""),
                order.item_count,
                float(order.subtotal),
                float(order.discount_amount),
                float(order.shipping_amount),
                float(order.total_amount),
                str(order.payment_method),
                str(order.payment_status),
                str(order.order_status),
                order.shipment.tracking_number if order.shipment else "",
            ]

    return header, rows()


def order_item_rows(
    db: Session, window: analytics.DateRange | None = None
) -> tuple[list[str], Iterator[list[Any]]]:
    """Line-level export, for reconciling what actually sold."""
    header = [
        "Order Number", "Date", "Order Status", "Product", "SKU", "Brand",
        "Variant", "Unit Price", "Quantity", "Line Total",
    ]
    conditions = []
    if window is not None:
        conditions = [Order.created_at >= window.start, Order.created_at < window.end]

    stmt = (
        select(Order, OrderItem)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(*conditions)
        .order_by(Order.created_at.desc())
    )

    def rows() -> Iterator[list[Any]]:
        for order, item in db.execute(stmt).yield_per(STREAM_CHUNK):
            yield [
                order.order_number, _stamp(order.created_at), str(order.order_status),
                item.product_name_snapshot, item.sku_snapshot,
                item.brand_name_snapshot or "", item.variant_label,
                float(item.unit_price), item.quantity, float(item.line_total),
            ]

    return header, rows()


def customer_rows(db: Session) -> tuple[list[str], Iterator[list[Any]]]:
    """Customer export. Contact details are included; password hashes never are."""
    header = [
        "Name", "Email", "Phone", "Orders", "Total Spent",
        "Last Order", "Segment", "Verified", "Joined",
    ]
    spend = (
        select(
            Order.user_id,
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .where(Order.order_status.in_(analytics.REVENUE_STATUSES))
        .group_by(Order.user_id)
        .subquery()
    )
    from app.models.enums import UserRole

    stmt = (
        select(
            User, func.coalesce(spend.c.order_count, 0),
            func.coalesce(spend.c.total_spent, 0), spend.c.last_order_at,
        )
        .outerjoin(spend, spend.c.user_id == User.id)
        .where(User.role == UserRole.CUSTOMER)
        .order_by(func.coalesce(spend.c.total_spent, 0).desc())
    )

    def rows() -> Iterator[list[Any]]:
        for user, order_count, total_spent, last_order in db.execute(stmt).yield_per(
            STREAM_CHUNK
        ):
            yield [
                f"{user.first_name} {user.last_name}".strip(),
                user.email,
                user.phone or "",
                int(order_count or 0),
                float(total_spent or 0),
                _stamp(last_order),
                str(analytics.segment_for_order_count(int(order_count or 0))),
                "Yes" if user.is_verified else "No",
                _stamp(user.created_at),
            ]

    return header, rows()


def inventory_history_rows(
    db: Session, window: analytics.DateRange | None = None
) -> tuple[list[str], Iterator[list[Any]]]:
    header = [
        "Date", "Product", "SKU", "Variant", "Type",
        "Change", "Before", "After", "Reference", "Note",
    ]
    conditions = []
    if window is not None:
        conditions = [
            InventoryTransaction.created_at >= window.start,
            InventoryTransaction.created_at < window.end,
        ]

    stmt = (
        select(InventoryTransaction, ProductVariant, Product)
        .join(ProductVariant, ProductVariant.id == InventoryTransaction.product_variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(*conditions)
        .order_by(InventoryTransaction.created_at.desc())
    )

    def rows() -> Iterator[list[Any]]:
        for movement, variant, product in db.execute(stmt).yield_per(STREAM_CHUNK):
            yield [
                _stamp(movement.created_at), product.name, variant.sku, variant.label,
                str(movement.type), movement.quantity_change,
                movement.quantity_before, movement.quantity_after,
                movement.reference_type or "", movement.note or "",
            ]

    return header, rows()


def sales_report_rows(
    db: Session, window: analytics.DateRange, granularity: str = "day"
) -> tuple[list[str], Iterator[list[Any]]]:
    header = ["Period", "Orders", "Gross Sales", "Net Sales"]
    points = analytics.sales_timeseries(db, window, granularity)  # type: ignore[arg-type]

    def rows() -> Iterator[list[Any]]:
        for point in points:
            yield [point["bucket"], point["orders"], point["gross_sales"], point["net_sales"]]

    return header, rows()


DATASETS = {
    "products": "Products and variants",
    "inventory": "Current stock levels",
    "inventory_history": "Stock movement history",
    "orders": "Orders",
    "order_items": "Order line items",
    "customers": "Customers",
    "sales": "Sales by period",
}


def build_dataset(
    db: Session,
    dataset: str,
    *,
    window: analytics.DateRange | None = None,
    granularity: str = "day",
    include_inactive: bool = False,
) -> tuple[list[str], Iterator[list[Any]]]:
    match dataset:
        case "products":
            return product_rows(db, include_inactive=include_inactive)
        case "inventory":
            return inventory_rows(db)
        case "inventory_history":
            return inventory_history_rows(db, window)
        case "orders":
            return order_rows(db, window)
        case "order_items":
            return order_item_rows(db, window)
        case "customers":
            return customer_rows(db)
        case "sales":
            return sales_report_rows(
                db, window or analytics.resolve_range("last_30_days"), granularity
            )
    from app.services.exceptions import InvalidRequestError

    raise InvalidRequestError(f"Unknown dataset: {dataset}")


# ------------------------------------------------------------------------- CSV
def stream_csv(header: Sequence[str], rows: Iterator[Sequence[Any]]) -> Iterator[str]:
    """Yield CSV text incrementally.

    A fresh `StringIO` per row keeps memory flat regardless of row count, which is
    what makes this safe for a full order history.

    The BOM is deliberate: without it Excel on Windows misreads UTF-8 accented
    characters in product names.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    yield "﻿"

    writer.writerow(header)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


# ----------------------------------------------------------------------- Excel
def build_excel(
    header: Sequence[str], rows: Iterator[Sequence[Any]], *, title: str
) -> tuple[bytes, bool]:
    """Build a styled single-sheet workbook.

    Returns the bytes plus whether the row cap was hit, so the caller can tell the
    user the file is partial instead of letting them believe it is complete.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31] or "Export"

    sheet.append(list(header))
    head_font = Font(bold=True, color="FFFAF8F4", size=10)
    head_fill = PatternFill("solid", fgColor=INK)
    for cell in sheet[1]:
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")
    sheet.freeze_panes = "A2"

    widths = [len(str(value)) for value in header]
    truncated = False
    count = 0

    for row in rows:
        if count >= MAX_EXCEL_ROWS:
            truncated = True
            break
        sheet.append(list(row))
        for index, value in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], min(len(str(value)), 48))
        count += 1

    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width + 3

    if truncated:
        sheet.append([])
        note = sheet.cell(
            row=sheet.max_row + 1,
            column=1,
            value=(
                f"Truncated at {MAX_EXCEL_ROWS:,} rows. "
                "Use the CSV export for the complete dataset."
            ),
        )
        note.font = Font(bold=True, color=GOLD)

    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue(), truncated
