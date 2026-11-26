"""Schemas for the Phase 5 admin surface: analytics, sales, bulk ops, activity."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    AdminNotificationSeverity,
    AdminNotificationType,
    DiscountType,
    Permission,
    SaleTargetType,
    SaleType,
)


# ------------------------------------------------------------------- analytics
class DateRangeParams(BaseModel):
    """Shared date filtering. An explicit from/to pair overrides the preset."""

    preset: Literal[
        "today", "yesterday", "last_7_days", "last_30_days",
        "this_month", "previous_month", "this_year", "all_time",
    ] | None = None
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def ordered(self) -> "DateRangeParams":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to cannot be before date_from")
        return self


class SalesAnalyticsQuery(DateRangeParams):
    """Sales analytics filters.

    Extra options live **inside** the model rather than beside it: FastAPI stops
    expanding a Pydantic query-params model as soon as another scalar `Query`
    parameter sits alongside it, which silently turns every request into a 422.
    """

    granularity: Literal["day", "week", "month", "year"] = "day"
    brand_sort: Literal["revenue", "units", "orders"] = "revenue"


class ProductAnalyticsQuery(DateRangeParams):
    sort: Literal["units", "revenue", "orders", "units_asc"] = "units"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class InventoryAlertQuery(BaseModel):
    out_of_stock: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class ExportQuery(DateRangeParams):
    granularity: Literal["day", "week", "month", "year"] = "day"
    include_inactive: bool = False


class ActivityQuery(BaseModel):
    action: str | None = Field(default=None, max_length=60)
    entity_type: str | None = Field(default=None, max_length=40)
    user_id: uuid.UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class NotificationQuery(BaseModel):
    unread_only: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)


class SaleListQuery(BaseModel):
    status: Literal["live", "scheduled", "expired", "inactive"] | None = None
    search: str | None = Field(default=None, max_length=120)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class CustomerListQuery(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class RangeRead(BaseModel):
    start: datetime
    end: datetime
    label: str


class SalesTotalsRead(BaseModel):
    gross_sales: float
    discounts: float
    shipping_revenue: float
    net_sales: float
    order_count: int
    items_sold: int
    average_order_value: float


class TimeseriesPoint(BaseModel):
    bucket: str
    net_sales: float
    gross_sales: float
    orders: int


class GroupedSalesRow(BaseModel):
    id: str
    name: str
    orders: int
    units_sold: int
    revenue: float
    category_name: str | None = None


class ProductPerformanceRow(BaseModel):
    id: str
    name: str
    sku: str
    brand_name: str | None
    category_name: str | None
    units_sold: int
    revenue: float
    orders: int
    average_selling_price: float
    stock: int
    regular_price: float


class InventorySummaryRead(BaseModel):
    active_products: int
    total_variants: int
    total_units: int
    low_stock_variants: int
    out_of_stock_variants: int
    inventory_value: float


class StockAlertRow(BaseModel):
    product_id: str
    product_name: str
    product_slug: str
    variant_id: str
    sku: str
    size: str | None
    waist: int | None
    quantity: int
    low_stock_threshold: int


class CustomerSummaryRead(BaseModel):
    total_customers: int
    new_customers: int
    repeat_customers: int
    loyal_customers: int
    customers_with_orders: int
    average_order_value: float
    total_customer_revenue: float
    #: The documented order-count boundaries behind the segment counts above.
    segment_rule: dict[str, int]


class SalesAnalyticsRead(BaseModel):
    range: RangeRead
    totals: SalesTotalsRead
    timeseries: list[TimeseriesPoint]
    by_category: list[GroupedSalesRow]
    by_subcategory: list[GroupedSalesRow]
    by_brand: list[GroupedSalesRow]


class OrderAnalyticsRead(BaseModel):
    range: RangeRead
    order_statuses: dict[str, int]
    payment_statuses: dict[str, int]
    payment_methods: dict[str, int]
    total_orders: int


# ----------------------------------------------------------------------- sales
class SaleTargetInput(BaseModel):
    target_type: SaleTargetType
    product_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None


class SaleTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: SaleTargetType
    product_id: uuid.UUID | None
    category_id: uuid.UUID | None
    subcategory_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    label: str | None = None


class SaleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = None
    sale_type: SaleType = SaleType.STANDARD
    discount_type: DiscountType
    discount_value: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    priority: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True
    starts_at: datetime
    ends_at: datetime | None = None
    badge_text: str | None = Field(default=None, max_length=40)
    targets: list[SaleTargetInput] = Field(min_length=1)

    @model_validator(mode="after")
    def check_rules(self) -> "SaleCreate":
        if self.discount_type is DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("A percentage discount cannot exceed 100")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("The end time must be after the start time")
        # A flash sale without an end time is not a flash sale.
        if self.sale_type is SaleType.FLASH and self.ends_at is None:
            raise ValueError("A flash sale must have an end time")
        return self


class SaleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = None
    sale_type: SaleType | None = None
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    priority: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    badge_text: str | None = Field(default=None, max_length=40)
    targets: list[SaleTargetInput] | None = None


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    sale_type: SaleType
    discount_type: DiscountType
    discount_value: Decimal
    priority: int
    is_active: bool
    starts_at: datetime
    ends_at: datetime | None
    badge_text: str | None
    created_at: datetime
    updated_at: datetime
    targets: list[SaleTargetRead] = Field(default_factory=list)
    # Computed: whether the campaign is running right now, per the same predicate
    # the pricing engine uses.
    is_live: bool = False
    is_scheduled: bool = False
    affected_product_count: int = 0


# ------------------------------------------------------------------- bulk ops
class BulkAttributeUpdate(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    is_active: bool | None = None
    is_featured: bool | None = None
    is_new_arrival: bool | None = None
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None


class BulkSelection(BaseModel):
    """Either explicit ids, or a category/brand filter. Ids win when both are given."""

    product_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None


class BulkPriceRequest(BulkSelection):
    mode: Literal[
        "increase_amount", "decrease_amount", "increase_percent", "decrease_percent", "set"
    ]
    value: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    field: Literal["regular_price", "sale_price"] = "regular_price"


class PricePreviewRowRead(BaseModel):
    product_id: str
    name: str
    sku: str
    current_price: float
    new_price: float
    change: float


class PricePreviewRead(BaseModel):
    rows: list[PricePreviewRowRead]
    affected: int
    total_before: float
    total_after: float
    total_change: float


class StockAdjustmentInput(BaseModel):
    variant_id: uuid.UUID
    mode: Literal["add", "remove", "set"]
    quantity: int = Field(ge=0)


class BulkStockRequest(BaseModel):
    adjustments: list[StockAdjustmentInput] = Field(min_length=1, max_length=500)
    #: Mandatory. An unexplained stock change cannot be reconciled later.
    reason: str = Field(min_length=3, max_length=500)


class BulkResultRead(BaseModel):
    affected: int
    detail: str


# --------------------------------------------------------- activity + alerts
class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    description: str
    metadata_json: dict[str, Any] | None
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: AdminNotificationType
    severity: AdminNotificationSeverity
    title: str
    body: str | None
    link: str | None
    is_read: bool
    created_at: datetime


class NotificationListRead(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int


# ----------------------------------------------------------------- permissions
class StaffPermissionsUpdate(BaseModel):
    permissions: list[Permission]


class StaffMemberRead(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    permissions: list[Permission]
    #: True for ADMIN, who implicitly hold everything and cannot be restricted.
    holds_all: bool


# ------------------------------------------------------------------ customers
class CustomerNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CustomerNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    author_email: str | None
    created_at: datetime


class CustomerRow(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    order_count: int
    total_spent: float
    last_order_at: datetime | None
    segment: str
    created_at: datetime


class CustomerOrderRow(BaseModel):
    id: uuid.UUID
    order_number: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    item_count: int
    created_at: datetime


class CustomerDetailRead(CustomerRow):
    """Full customer profile for the admin detail page.

    Carries no password hash and no authentication material of any kind.
    """

    is_active: bool
    is_verified: bool
    last_login_at: datetime | None
    addresses: list[Any] = Field(default_factory=list)
    orders: list[CustomerOrderRow] = Field(default_factory=list)
    wishlist: list[str] = Field(default_factory=list)
    notes: list["CustomerNoteRead"] = Field(default_factory=list)
