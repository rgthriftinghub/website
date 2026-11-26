"""Strongly typed catalogue, account, and order enumerations.

These are persisted as native PostgreSQL enum types. Adding a new member is a
deliberate schema change (an Alembic migration), which is intentional: it keeps
filter values validated at the database boundary rather than free-form strings.
"""

from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


class ProductCondition(StrEnum):
    PREMIUM_PLUS = "PREMIUM_PLUS"
    PREMIUM = "PREMIUM"
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"

    # Backwards-compatible names for existing callers. They serialize as the
    # new thrift-grade values, while legacy query/import strings are normalized
    # at their input boundaries.
    NEW = "PREMIUM_PLUS"
    EXPORT_QUALITY = "PREMIUM"
    THRIFT = "GOOD"


def parse_product_condition(value: ProductCondition | str) -> ProductCondition:
    """Parse new grade values plus the original API/import labels."""
    if isinstance(value, ProductCondition):
        return value
    candidate = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    legacy = {
        "NEW": ProductCondition.PREMIUM_PLUS,
        "EXPORT_QUALITY": ProductCondition.PREMIUM,
        "THRIFT": ProductCondition.GOOD,
    }
    if candidate in legacy:
        return legacy[candidate]
    return ProductCondition(candidate)


class Gender(StrEnum):
    MEN = "MEN"
    WOMEN = "WOMEN"
    UNISEX = "UNISEX"
    KIDS = "KIDS"


class ProductType(StrEnum):
    SHIRT = "SHIRT"
    T_SHIRT = "T_SHIRT"
    POLO = "POLO"
    JEANS = "JEANS"
    TROUSERS = "TROUSERS"
    SHORTS = "SHORTS"
    JACKET = "JACKET"
    HOODIE = "HOODIE"
    SWEATER = "SWEATER"
    DRESS = "DRESS"
    KURTA = "KURTA"
    ABAYA = "ABAYA"
    SKIRT = "SKIRT"
    ACTIVEWEAR = "ACTIVEWEAR"
    FOOTWEAR = "FOOTWEAR"
    ACCESSORY = "ACCESSORY"


class PaymentMethod(StrEnum):
    """How the customer intends to pay.

    Only COD and BANK_TRANSFER are selectable today. The gateway members are
    declared now so adding those integrations later is a service-layer change
    plus one enum value — it does not reshape orders or payments.
    """

    COD = "COD"
    BANK_TRANSFER = "BANK_TRANSFER"
    JAZZCASH = "JAZZCASH"
    EASYPAISA = "EASYPAISA"
    PAYFAST = "PAYFAST"
    SAFEPAY = "SAFEPAY"


# Methods a customer may actually choose in this phase. Everything else is
# reserved for a later gateway integration.
SELECTABLE_PAYMENT_METHODS: frozenset[PaymentMethod] = frozenset(
    {PaymentMethod.COD, PaymentMethod.BANK_TRANSFER}
)


class PaymentProvider(StrEnum):
    """Who actually moves the money.

    Distinct from `PaymentMethod`: the method is what the customer chose, the
    provider is the integration that settles it. They coincide today but a
    method could later be routed through more than one provider.
    """

    COD = "COD"
    BANK_TRANSFER = "BANK_TRANSFER"
    PAYFAST = "PAYFAST"
    SAFEPAY = "SAFEPAY"
    JAZZCASH = "JAZZCASH"
    EASYPAISA = "EASYPAISA"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


# Payment lifecycle, kept as data for the same reason as order status. FAILED is
# allowed back to PENDING so a customer can retry a declined gateway payment.
PAYMENT_STATUS_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {
            PaymentStatus.PROCESSING,
            PaymentStatus.PAID,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        }
    ),
    PaymentStatus.PROCESSING: frozenset(
        {PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.CANCELLED}
    ),
    PaymentStatus.PAID: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset({PaymentStatus.PENDING, PaymentStatus.CANCELLED}),
    PaymentStatus.CANCELLED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
}

# Reaching one of these means the payment is settled and must never be
# re-processed, which is what makes duplicate webhooks harmless.
TERMINAL_PAYMENT_STATUSES: frozenset[PaymentStatus] = frozenset(
    {PaymentStatus.PAID, PaymentStatus.CANCELLED, PaymentStatus.REFUNDED}
)


class PaymentTransactionEvent(StrEnum):
    """Audit trail entries. Append-only; nothing here is ever updated."""

    INITIATED = "INITIATED"
    REDIRECTED = "REDIRECTED"
    CALLBACK_RECEIVED = "CALLBACK_RECEIVED"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    WEBHOOK_DUPLICATE = "WEBHOOK_DUPLICATE"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PROOF_SUBMITTED = "PROOF_SUBMITTED"
    MANUALLY_VERIFIED = "MANUALLY_VERIFIED"
    MANUALLY_REJECTED = "MANUALLY_REJECTED"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUNDED = "REFUNDED"


class RefundStatus(StrEnum):
    REQUESTED = "REQUESTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CourierProvider(StrEnum):
    """MANUAL means staff key in the tracking number from the courier's own portal.

    The named couriers are declared so a shipment can record which one carried
    it even before any API integration exists.
    """

    MANUAL = "MANUAL"
    TCS = "TCS"
    LEOPARDS = "LEOPARDS"
    MP = "MP"
    TRAX = "TRAX"
    POSTEX = "POSTEX"


class ShippingStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class SaleType(StrEnum):
    """What kind of campaign this is. Presentation differs; the maths does not."""

    STANDARD = "STANDARD"
    FLASH = "FLASH"
    CLEARANCE = "CLEARANCE"
    SEASONAL = "SEASONAL"


class DiscountType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"
    CUSTOM_PRICE = "CUSTOM_PRICE"


class SaleTargetType(StrEnum):
    """What a sale applies to.

    Ordered least to most specific; `SALE_TARGET_SPECIFICITY` below turns that
    into the tiebreak used when two sales share a priority.
    """

    STORE = "STORE"
    CATEGORY = "CATEGORY"
    SUBCATEGORY = "SUBCATEGORY"
    BRAND = "BRAND"
    PRODUCT = "PRODUCT"


# Tiebreak when two applicable sales have equal priority: the narrower target
# wins, because a rule written for one product is a more deliberate decision than
# a store-wide banner.
SALE_TARGET_SPECIFICITY: dict[SaleTargetType, int] = {
    SaleTargetType.PRODUCT: 4,
    SaleTargetType.BRAND: 3,
    SaleTargetType.SUBCATEGORY: 2,
    SaleTargetType.CATEGORY: 1,
    SaleTargetType.STORE: 0,
}


class Permission(StrEnum):
    """Granular staff permissions.

    ADMIN implicitly holds all of them; STAFF holds only what is explicitly
    granted. Deliberately a short, flat list rather than a role/scope IAM system.
    """

    PRODUCT_VIEW = "PRODUCT_VIEW"
    PRODUCT_CREATE = "PRODUCT_CREATE"
    PRODUCT_UPDATE = "PRODUCT_UPDATE"
    PRODUCT_DELETE = "PRODUCT_DELETE"
    ORDER_VIEW = "ORDER_VIEW"
    ORDER_UPDATE = "ORDER_UPDATE"
    INVENTORY_VIEW = "INVENTORY_VIEW"
    INVENTORY_UPDATE = "INVENTORY_UPDATE"
    CUSTOMER_VIEW = "CUSTOMER_VIEW"
    CUSTOMER_UPDATE = "CUSTOMER_UPDATE"
    SALES_VIEW = "SALES_VIEW"
    SALES_MANAGE = "SALES_MANAGE"
    REPORTS_VIEW = "REPORTS_VIEW"
    PAYMENT_VIEW = "PAYMENT_VIEW"
    PAYMENT_MANAGE = "PAYMENT_MANAGE"
    SETTINGS_MANAGE = "SETTINGS_MANAGE"


# What a brand-new STAFF account can do before anyone grants anything: look, not
# touch. Chosen so a mis-provisioned staff account cannot change data.
DEFAULT_STAFF_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.PRODUCT_VIEW,
        Permission.ORDER_VIEW,
        Permission.INVENTORY_VIEW,
    }
)


class AdminNotificationType(StrEnum):
    NEW_ORDER = "NEW_ORDER"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    RETURN_REQUEST = "RETURN_REQUEST"
    EXCHANGE_REQUEST = "EXCHANGE_REQUEST"
    SHIPPING_ISSUE = "SHIPPING_ISSUE"


class AdminNotificationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ImportStatus(StrEnum):
    """An upload is parsed and validated before it can ever be committed."""

    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CustomerSegment(StrEnum):
    """Segmentation by completed order count. Thresholds are documented, not magic.

    NEW      - 0 or 1 delivered/paid orders
    REPEAT   - 2 to 4
    LOYAL    - 5 or more
    """

    NEW = "NEW"
    REPEAT = "REPEAT"
    LOYAL = "LOYAL"


#: Order-count boundaries for `CustomerSegment`. Exposed so the analytics endpoint
#: can report the rule alongside the numbers rather than leaving it implicit.
CUSTOMER_SEGMENT_THRESHOLDS = {"REPEAT_MIN": 2, "LOYAL_MIN": 5}


SHIPPING_STATUS_TRANSITIONS: dict[ShippingStatus, frozenset[ShippingStatus]] = {
    ShippingStatus.PENDING: frozenset({ShippingStatus.READY, ShippingStatus.CANCELLED}),
    ShippingStatus.READY: frozenset({ShippingStatus.DISPATCHED, ShippingStatus.CANCELLED}),
    ShippingStatus.DISPATCHED: frozenset({ShippingStatus.IN_TRANSIT, ShippingStatus.RETURNED}),
    ShippingStatus.IN_TRANSIT: frozenset(
        {ShippingStatus.OUT_FOR_DELIVERY, ShippingStatus.DELIVERED, ShippingStatus.RETURNED}
    ),
    ShippingStatus.OUT_FOR_DELIVERY: frozenset(
        {ShippingStatus.DELIVERED, ShippingStatus.RETURNED}
    ),
    ShippingStatus.DELIVERED: frozenset({ShippingStatus.RETURNED}),
    ShippingStatus.RETURNED: frozenset(),
    ShippingStatus.CANCELLED: frozenset(),
}


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PACKED = "PACKED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"
    EXCHANGE = "EXCHANGE"


class DeliveryMethod(StrEnum):
    """Only standard delivery exists today; courier tiers arrive with Phase 4."""

    STANDARD = "STANDARD"


class InventoryTransactionType(StrEnum):
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"
    RESTOCK = "RESTOCK"
    CANCELLED_ORDER = "CANCELLED_ORDER"
    RETURN = "RETURN"


class ReturnRequestType(StrEnum):
    RETURN = "RETURN"
    EXCHANGE = "EXCHANGE"


class ReturnRequestStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


# ---------------------------------------------------------------- status machine
# Allowed order status transitions. Keeping this as data rather than scattered
# `if` statements means an illegal transition is impossible to request and the
# rules are reviewable in one place.
ORDER_STATUS_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.PROCESSING, OrderStatus.CANCELLED}),
    OrderStatus.PROCESSING: frozenset({OrderStatus.PACKED, OrderStatus.CANCELLED}),
    OrderStatus.PACKED: frozenset({OrderStatus.DISPATCHED, OrderStatus.CANCELLED}),
    OrderStatus.DISPATCHED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.RETURNED, OrderStatus.EXCHANGE}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.RETURNED: frozenset(),
    OrderStatus.EXCHANGE: frozenset(),
}

# Statuses a customer may cancel from. Once an order is packed it is physically
# in motion, so cancellation becomes a staff decision or a return request.
CUSTOMER_CANCELLABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.PENDING, OrderStatus.PROCESSING}
)

# Statuses whose reserved stock is still held by the order. Moving out of these
# into CANCELLED must give the stock back.
STOCK_HOLDING_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
        OrderStatus.PACKED,
        OrderStatus.DISPATCHED,
        OrderStatus.DELIVERED,
    }
)
