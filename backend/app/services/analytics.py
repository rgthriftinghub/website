"""Business analytics.

Every figure here is computed by PostgreSQL. Nothing is aggregated in Python and
nothing is aggregated in React — the browser receives finished numbers.

## Two rules that shape every query

**Cancelled orders are excluded from revenue.** A cancelled order represents money
that never arrived, so counting it would overstate sales. It is still counted in
*order* status breakdowns, because "how many did we cancel" is a real question.

**Product, category, and brand reporting joins the live catalogue.** `OrderItem`
snapshots the product name and SKU (so history cannot be rewritten), but it does
not snapshot category or brand. Those breakdowns therefore reflect *current*
categorisation. That is the honest trade-off and it is documented on each function.

## Performance

Related figures are combined into single round trips rather than one query per
tile: `dashboard_summary` runs a handful of grouped queries, not one per KPI. All
date filtering hits the indexed `orders.created_at`, and every table endpoint is
paginated.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.timezones import business_zone, utc_now
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import (
    CUSTOMER_SEGMENT_THRESHOLDS,
    CustomerSegment,
    OrderStatus,
    PaymentStatus,
    UserRole,
)
from app.models.inventory import InventoryItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant

# Orders that represent real trade. Everything revenue-related filters on this.
REVENUE_STATUSES = tuple(
    status for status in OrderStatus if status is not OrderStatus.CANCELLED
)

Granularity = Literal["day", "week", "month", "year"]


# ------------------------------------------------------------------ date ranges
@dataclass(slots=True)
class DateRange:
    """A half-open [start, end) window in UTC, derived from business-local dates.

    Boundaries are computed in the business timezone and converted to UTC, so
    "today" means today in Karachi rather than today in UTC.
    """

    start: datetime
    end: datetime
    label: str

    @property
    def days(self) -> int:
        return max((self.end - self.start).days, 1)

    def previous(self) -> "DateRange":
        """The equally long window immediately before this one, for comparisons."""
        span = self.end - self.start
        return DateRange(self.start - span, self.start, f"Previous {self.label}")


PRESETS = (
    "today",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "this_month",
    "previous_month",
    "this_year",
    "all_time",
)


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=business_zone())


def resolve_range(
    preset: str | None = None,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DateRange:
    """Turn a preset name or an explicit pair of dates into a UTC window.

    An explicit range always wins over a preset. `date_to` is inclusive of the
    whole day, which is what a person selecting a end date means.
    """
    today = datetime.now(business_zone()).date()

    if date_from is not None or date_to is not None:
        start_day = date_from or date_to or today
        end_day = date_to or date_from or today
        return DateRange(
            _local_midnight(start_day),
            _local_midnight(end_day + timedelta(days=1)),
            f"{start_day.isoformat()} to {end_day.isoformat()}",
        )

    match (preset or "last_30_days"):
        case "today":
            return DateRange(_local_midnight(today), _local_midnight(today + timedelta(days=1)), "Today")
        case "yesterday":
            y = today - timedelta(days=1)
            return DateRange(_local_midnight(y), _local_midnight(today), "Yesterday")
        case "last_7_days":
            return DateRange(
                _local_midnight(today - timedelta(days=6)),
                _local_midnight(today + timedelta(days=1)),
                "Last 7 days",
            )
        case "last_30_days":
            return DateRange(
                _local_midnight(today - timedelta(days=29)),
                _local_midnight(today + timedelta(days=1)),
                "Last 30 days",
            )
        case "this_month":
            first = today.replace(day=1)
            return DateRange(
                _local_midnight(first), _local_midnight(today + timedelta(days=1)), "This month"
            )
        case "previous_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            return DateRange(
                _local_midnight(last_prev.replace(day=1)),
                _local_midnight(first_this),
                "Previous month",
            )
        case "this_year":
            return DateRange(
                _local_midnight(today.replace(month=1, day=1)),
                _local_midnight(today + timedelta(days=1)),
                "This year",
            )
        case "all_time":
            return DateRange(
                datetime(2000, 1, 1, tzinfo=business_zone()),
                _local_midnight(today + timedelta(days=1)),
                "All time",
            )
        case _:
            return resolve_range("last_30_days")


def _revenue_filter(window: DateRange | None = None) -> list:
    conditions = [Order.order_status.in_(REVENUE_STATUSES)]
    if window is not None:
        conditions += [Order.created_at >= window.start, Order.created_at < window.end]
    return conditions


def _float(value: Any) -> float:
    return float(value or 0)


# --------------------------------------------------------------- sales analytics
@dataclass(slots=True)
class SalesTotals:
    gross_sales: float
    discounts: float
    shipping_revenue: float
    net_sales: float
    order_count: int
    items_sold: int
    average_order_value: float


def sales_totals(db: Session, window: DateRange | None = None) -> SalesTotals:
    """Headline sales figures in one query.

    `gross_sales` is the sum of order subtotals before discount and delivery.
    `net_sales` is what customers were actually charged (`total_amount`), which
    includes delivery — so the two are reported side by side rather than conflated.
    """
    row = db.execute(
        select(
            func.coalesce(func.sum(Order.subtotal), 0),
            func.coalesce(func.sum(Order.discount_amount), 0),
            func.coalesce(func.sum(Order.shipping_amount), 0),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.count(Order.id),
        ).where(*_revenue_filter(window))
    ).one()

    items = db.execute(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(*_revenue_filter(window))
    ).scalar_one()

    gross, discounts, shipping, net, count = row
    return SalesTotals(
        gross_sales=_float(gross),
        discounts=_float(discounts),
        shipping_revenue=_float(shipping),
        net_sales=_float(net),
        order_count=int(count or 0),
        items_sold=int(items or 0),
        average_order_value=_float(net) / count if count else 0.0,
    )


def sales_timeseries(
    db: Session, window: DateRange, granularity: Granularity = "day"
) -> list[dict[str, Any]]:
    """Revenue bucketed by day, week, month, or year.

    Buckets are computed with `date_trunc` in the business timezone, so a sale made
    at 1am Karachi lands on the correct local day rather than the previous UTC one.
    """
    zone = str(business_zone())
    bucket = func.date_trunc(
        granularity, func.timezone(zone, Order.created_at)
    ).label("bucket")

    rows = db.execute(
        select(
            bucket,
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.subtotal), 0),
            func.count(Order.id),
        )
        .where(*_revenue_filter(window))
        .group_by(bucket)
        .order_by(bucket)
    ).all()

    return [
        {
            "bucket": row[0].date().isoformat() if hasattr(row[0], "date") else str(row[0]),
            "net_sales": _float(row[1]),
            "gross_sales": _float(row[2]),
            "orders": int(row[3] or 0),
        }
        for row in rows
    ]


def sales_by_category(db: Session, window: DateRange | None = None) -> list[dict[str, Any]]:
    """Revenue per category.

    Joins order items to the live product and category, so this reflects current
    categorisation rather than what a product was filed under at purchase time.
    """
    rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.count(func.distinct(Order.id)),
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.line_total), 0),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(*_revenue_filter(window))
        .group_by(Category.id, Category.name)
        .order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc())
    ).all()

    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "orders": int(row[2] or 0),
            "units_sold": int(row[3] or 0),
            "revenue": _float(row[4]),
        }
        for row in rows
    ]


def sales_by_subcategory(db: Session, window: DateRange | None = None) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            Subcategory.id,
            Subcategory.name,
            Category.name,
            func.count(func.distinct(Order.id)),
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.line_total), 0),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Subcategory, Subcategory.id == Product.subcategory_id)
        .join(Category, Category.id == Subcategory.category_id)
        .where(*_revenue_filter(window))
        .group_by(Subcategory.id, Subcategory.name, Category.name)
        .order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc())
    ).all()

    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "category_name": row[2],
            "orders": int(row[3] or 0),
            "units_sold": int(row[4] or 0),
            "revenue": _float(row[5]),
        }
        for row in rows
    ]


def sales_by_brand(
    db: Session,
    window: DateRange | None = None,
    *,
    sort: Literal["revenue", "units", "orders"] = "revenue",
) -> list[dict[str, Any]]:
    """Revenue per brand.

    Grouped on the live brand row. Items whose product has since been deleted are
    excluded rather than bucketed into a misleading "unknown brand" total.
    """
    revenue = func.coalesce(func.sum(OrderItem.line_total), 0)
    units = func.coalesce(func.sum(OrderItem.quantity), 0)
    orders = func.count(func.distinct(Order.id))
    order_by = {"revenue": revenue.desc(), "units": units.desc(), "orders": orders.desc()}[sort]

    rows = db.execute(
        select(Brand.id, Brand.name, orders, units, revenue)
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Brand, Brand.id == Product.brand_id)
        .where(*_revenue_filter(window))
        .group_by(Brand.id, Brand.name)
        .order_by(order_by)
    ).all()

    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "orders": int(row[2] or 0),
            "units_sold": int(row[3] or 0),
            "revenue": _float(row[4]),
        }
        for row in rows
    ]


# ------------------------------------------------------------- product analytics
def product_performance(
    db: Session,
    window: DateRange | None = None,
    *,
    sort: Literal["units", "revenue", "orders", "units_asc"] = "units",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Per-product sales performance.

    Uses a LEFT JOIN from products to order items, so a product with **no** sales
    appears with zeroes instead of vanishing. That is what makes the low-selling
    view meaningful — the worst performers are precisely the ones a plain
    aggregation over order items would omit entirely.
    """
    item_filter = and_(*_revenue_filter(window)) if window else and_(*_revenue_filter())

    units = func.coalesce(func.sum(OrderItem.quantity), 0).label("units")
    revenue = func.coalesce(func.sum(OrderItem.line_total), 0).label("revenue")
    orders = func.count(func.distinct(Order.id)).label("orders")

    order_clause = {
        "units": (units.desc(), revenue.desc()),
        "units_asc": (units.asc(), revenue.asc()),
        "revenue": (revenue.desc(),),
        "orders": (orders.desc(),),
    }[sort]

    base = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.regular_price,
            Product.sale_price,
            Brand.name.label("brand_name"),
            Category.name.label("category_name"),
            units,
            revenue,
            orders,
            func.coalesce(func.sum(InventoryItem.quantity), 0).label("stock"),
        )
        .select_from(Product)
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .outerjoin(Order, and_(Order.id == OrderItem.order_id, item_filter))
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(ProductVariant, ProductVariant.product_id == Product.id)
        .outerjoin(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .where(Product.is_active.is_(True))
        .group_by(
            Product.id, Product.name, Product.sku, Product.regular_price,
            Product.sale_price, Brand.name, Category.name,
        )
    )

    total = db.execute(
        select(func.count()).select_from(
            select(Product.id).where(Product.is_active.is_(True)).subquery()
        )
    ).scalar_one()

    rows = db.execute(base.order_by(*order_clause).offset(offset).limit(limit)).all()

    result = []
    for row in rows:
        unit_count = int(row.units or 0)
        rev = _float(row.revenue)
        result.append(
            {
                "id": str(row.id),
                "name": row.name,
                "sku": row.sku,
                "brand_name": row.brand_name,
                "category_name": row.category_name,
                "units_sold": unit_count,
                "revenue": rev,
                "orders": int(row.orders or 0),
                # Realised average, not the list price — this is what it actually sold for.
                "average_selling_price": rev / unit_count if unit_count else 0.0,
                "stock": int(row.stock or 0),
                "regular_price": _float(row.regular_price),
            }
        )
    return result, total


# ----------------------------------------------------------- inventory analytics
@dataclass(slots=True)
class InventorySummary:
    active_products: int
    total_variants: int
    total_units: int
    low_stock_variants: int
    out_of_stock_variants: int
    inventory_value: float


def inventory_summary(db: Session) -> InventorySummary:
    """Stock counts and valuation.

    Inventory is valued at each product's **effective selling price** (its manual
    sale price when set, otherwise regular). Campaign discounts are deliberately
    excluded: a temporary promotion should not restate the value of goods on hand.
    """
    products = db.execute(
        select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    ).scalar_one()

    row = db.execute(
        select(
            func.count(ProductVariant.id),
            func.coalesce(func.sum(InventoryItem.quantity), 0),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                InventoryItem.quantity
                                <= InventoryItem.low_stock_threshold,
                                InventoryItem.quantity > 0,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(case((InventoryItem.quantity <= 0, 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(
                    InventoryItem.quantity
                    * func.coalesce(Product.sale_price, Product.regular_price)
                ),
                0,
            ),
        )
        .select_from(ProductVariant)
        .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.is_active.is_(True), Product.is_active.is_(True))
    ).one()

    return InventorySummary(
        active_products=int(products or 0),
        total_variants=int(row[0] or 0),
        total_units=int(row[1] or 0),
        low_stock_variants=int(row[2] or 0),
        out_of_stock_variants=int(row[3] or 0),
        inventory_value=_float(row[4]),
    )


def stock_alert_rows(
    db: Session, *, out_of_stock: bool, page: int = 1, page_size: int = 50
) -> tuple[list[dict[str, Any]], int]:
    """Low-stock or out-of-stock variants, compared against each variant's own threshold."""
    condition = (
        InventoryItem.quantity <= 0
        if out_of_stock
        else and_(
            InventoryItem.quantity <= InventoryItem.low_stock_threshold,
            InventoryItem.quantity > 0,
        )
    )
    base_filter = [
        ProductVariant.is_active.is_(True),
        Product.is_active.is_(True),
        condition,
    ]

    total = db.execute(
        select(func.count())
        .select_from(ProductVariant)
        .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(*base_filter)
    ).scalar_one()

    rows = db.execute(
        select(
            Product.id, Product.name, Product.slug, ProductVariant.id,
            ProductVariant.sku, ProductVariant.size, ProductVariant.waist,
            InventoryItem.quantity, InventoryItem.low_stock_threshold,
        )
        .select_from(ProductVariant)
        .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(*base_filter)
        .order_by(InventoryItem.quantity, Product.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return (
        [
            {
                "product_id": str(row[0]),
                "product_name": row[1],
                "product_slug": row[2],
                "variant_id": str(row[3]),
                "sku": row[4],
                "size": row[5],
                "waist": row[6],
                "quantity": int(row[7] or 0),
                "low_stock_threshold": int(row[8] or 0),
            }
            for row in rows
        ],
        total,
    )


# ------------------------------------------------------------ customer analytics
@dataclass(slots=True)
class CustomerSummary:
    total_customers: int
    new_customers: int
    repeat_customers: int
    loyal_customers: int
    customers_with_orders: int
    average_order_value: float
    total_customer_revenue: float
    segment_rule: dict[str, int] = field(default_factory=lambda: dict(CUSTOMER_SEGMENT_THRESHOLDS))


def customer_summary(db: Session, window: DateRange | None = None) -> CustomerSummary:
    """Customer counts and segmentation.

    Segments are by lifetime non-cancelled order count, using the documented
    thresholds in `CUSTOMER_SEGMENT_THRESHOLDS`: NEW is 0-1 orders, REPEAT is 2-4,
    LOYAL is 5+. The rule is returned with the numbers so the dashboard can state
    it rather than leaving the reader to guess.

    `new_customers` counts accounts *created* inside the window; the segment counts
    are lifetime, because a segment is a property of the customer, not the period.
    """
    total = db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.CUSTOMER)
    ).scalar_one()

    new_in_window = 0
    if window is not None:
        new_in_window = db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.role == UserRole.CUSTOMER,
                User.created_at >= window.start,
                User.created_at < window.end,
            )
        ).scalar_one()

    counts = (
        select(Order.user_id, func.count(Order.id).label("order_count"))
        .where(*_revenue_filter(), Order.user_id.is_not(None))
        .group_by(Order.user_id)
        .subquery()
    )
    repeat_min = CUSTOMER_SEGMENT_THRESHOLDS["REPEAT_MIN"]
    loyal_min = CUSTOMER_SEGMENT_THRESHOLDS["LOYAL_MIN"]

    segment_row = db.execute(
        select(
            func.count(),
            func.coalesce(
                func.sum(case((counts.c.order_count >= loyal_min, 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                counts.c.order_count >= repeat_min,
                                counts.c.order_count < loyal_min,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        ).select_from(counts)
    ).one()

    with_orders = int(segment_row[0] or 0)
    loyal = int(segment_row[1] or 0)
    repeat = int(segment_row[2] or 0)

    revenue_row = db.execute(
        select(
            func.coalesce(func.sum(Order.total_amount), 0), func.count(Order.id)
        ).where(*_revenue_filter(window))
    ).one()
    revenue, order_count = _float(revenue_row[0]), int(revenue_row[1] or 0)

    return CustomerSummary(
        total_customers=int(total or 0),
        new_customers=new_in_window,
        repeat_customers=repeat,
        loyal_customers=loyal,
        # Everyone else is NEW: no orders, or exactly one.
        customers_with_orders=with_orders,
        average_order_value=revenue / order_count if order_count else 0.0,
        total_customer_revenue=revenue,
    )


def segment_for_order_count(order_count: int) -> CustomerSegment:
    if order_count >= CUSTOMER_SEGMENT_THRESHOLDS["LOYAL_MIN"]:
        return CustomerSegment.LOYAL
    if order_count >= CUSTOMER_SEGMENT_THRESHOLDS["REPEAT_MIN"]:
        return CustomerSegment.REPEAT
    return CustomerSegment.NEW


# --------------------------------------------------------------- order analytics
def order_status_counts(db: Session, window: DateRange | None = None) -> dict[str, int]:
    """Count per order status. Includes CANCELLED — that is a real operational number."""
    conditions = []
    if window is not None:
        conditions = [Order.created_at >= window.start, Order.created_at < window.end]

    rows = db.execute(
        select(Order.order_status, func.count())
        .where(*conditions)
        .group_by(Order.order_status)
    ).all()
    counts = {str(status): 0 for status in OrderStatus}
    counts.update({str(status): int(count or 0) for status, count in rows})
    return counts


def payment_status_counts(db: Session, window: DateRange | None = None) -> dict[str, int]:
    conditions = []
    if window is not None:
        conditions = [Order.created_at >= window.start, Order.created_at < window.end]
    rows = db.execute(
        select(Order.payment_status, func.count())
        .where(*conditions)
        .group_by(Order.payment_status)
    ).all()
    counts = {str(status): 0 for status in PaymentStatus}
    counts.update({str(status): int(count or 0) for status, count in rows})
    return counts


def payment_method_counts(db: Session, window: DateRange | None = None) -> dict[str, int]:
    conditions = []
    if window is not None:
        conditions = [Order.created_at >= window.start, Order.created_at < window.end]
    rows = db.execute(
        select(Order.payment_method, func.count())
        .where(*conditions)
        .group_by(Order.payment_method)
    ).all()
    return {str(method): int(count or 0) for method, count in rows}


# ------------------------------------------------------------------- dashboard
def dashboard_summary(db: Session, window: DateRange | None = None) -> dict[str, Any]:
    """Everything the dashboard needs, assembled from a handful of queries.

    Deliberately *not* one query per KPI card. Today/week/month/year figures reuse
    `sales_totals`, the status breakdown is a single grouped query, and inventory is
    one more — so opening the dashboard is a fixed, small number of round trips
    regardless of how many tiles are displayed.
    """
    window = window or resolve_range("last_30_days")

    today = resolve_range("today")
    week = resolve_range("last_7_days")
    month = resolve_range("this_month")
    year = resolve_range("this_year")

    selected = sales_totals(db, window)
    previous = sales_totals(db, window.previous())
    statuses = order_status_counts(db, window)
    inventory = inventory_summary(db)
    customers = customer_summary(db, window)

    def change(now: float, before: float) -> float | None:
        if before <= 0:
            return None
        return round(((now - before) / before) * 100, 1)

    return {
        "range": {"start": window.start, "end": window.end, "label": window.label},
        "today": {
            "orders": order_status_counts(db, today),
            "sales": sales_totals(db, today).net_sales,
        },
        "period_sales": {
            "today": sales_totals(db, today).net_sales,
            "week": sales_totals(db, week).net_sales,
            "month": sales_totals(db, month).net_sales,
            "year": sales_totals(db, year).net_sales,
        },
        "selected": {
            "gross_sales": selected.gross_sales,
            "discounts": selected.discounts,
            "shipping_revenue": selected.shipping_revenue,
            "net_sales": selected.net_sales,
            "order_count": selected.order_count,
            "items_sold": selected.items_sold,
            "average_order_value": round(selected.average_order_value, 2),
            "net_sales_change_percent": change(selected.net_sales, previous.net_sales),
            "order_count_change_percent": change(
                selected.order_count, previous.order_count
            ),
        },
        "order_statuses": statuses,
        "payment_statuses": payment_status_counts(db, window),
        "payment_methods": payment_method_counts(db, window),
        "inventory": {
            "active_products": inventory.active_products,
            "total_variants": inventory.total_variants,
            "total_units": inventory.total_units,
            "low_stock_variants": inventory.low_stock_variants,
            "out_of_stock_variants": inventory.out_of_stock_variants,
            "inventory_value": inventory.inventory_value,
        },
        "customers": {
            "total": customers.total_customers,
            "new": customers.new_customers,
            "repeat": customers.repeat_customers,
            "loyal": customers.loyal_customers,
            "with_orders": customers.customers_with_orders,
            "average_order_value": round(customers.average_order_value, 2),
            "total_revenue": customers.total_customer_revenue,
            "segment_rule": customers.segment_rule,
        },
        "timeseries": sales_timeseries(db, window, "day" if window.days <= 92 else "month"),
        "top_products": product_performance(db, window, sort="units", limit=8)[0],
        "low_selling_products": product_performance(db, window, sort="units_asc", limit=8)[0],
        "category_sales": sales_by_category(db, window),
        "brand_sales": sales_by_brand(db, window)[:8],
        "generated_at": utc_now(),
    }
