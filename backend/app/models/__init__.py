"""SQLAlchemy models.

Every model is imported here so that importing `app.models` registers the full
set of tables on `Base.metadata`, which is what Alembic autogenerate inspects.
"""

from app.models.address import CustomerAddress
from app.models.admin import (
    AdminActivityLog,
    AdminNotification,
    CustomerNote,
    ImportBatch,
    StaffPermissionGrant,
)
from app.models.brand import Brand
from app.models.cart import Cart, CartItem
from app.models.category import Category, Subcategory
from app.models.coupon import Coupon
from app.models.enums import (
    AdminNotificationSeverity,
    AdminNotificationType,
    CustomerSegment,
    DiscountType,
    ImportStatus,
    Permission,
    SaleTargetType,
    SaleType,
    CourierProvider,
    DeliveryMethod,
    Gender,
    InventoryTransactionType,
    OrderStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentTransactionEvent,
    ProductCondition,
    ProductType,
    RefundStatus,
    ReturnRequestStatus,
    ReturnRequestType,
    ShippingStatus,
    UserRole,
)
from app.models.inventory import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.order import Order, OrderItem, OrderStatusEvent
from app.models.payment import Payment, PaymentTransaction, Refund, WebhookEvent
from app.models.product import Product, ProductImage
from app.models.review import ProductReview
from app.models.returns import ReturnRequest
from app.models.sale import Sale, SaleTarget
from app.models.store_content import StoreContent
from app.models.shipping import BankAccount, Shipment, ShipmentEvent, ShippingMethod
from app.models.user import User
from app.models.variant import ProductVariant
from app.models.wishlist import WishlistItem

__all__ = [
    "AdminActivityLog",
    "AdminNotification",
    "AdminNotificationSeverity",
    "AdminNotificationType",
    "CustomerNote",
    "CustomerSegment",
    "DiscountType",
    "ImportBatch",
    "ImportStatus",
    "Permission",
    "Sale",
    "SaleTarget",
    "StoreContent",
    "SaleTargetType",
    "SaleType",
    "StaffPermissionGrant",
    "BankAccount",
    "Brand",
    "Cart",
    "CartItem",
    "Category",
    "CourierProvider",
    "CustomerAddress",
    "Coupon",
    "DeliveryMethod",
    "Gender",
    "InventoryItem",
    "InventoryTransaction",
    "InventoryTransactionType",
    "Order",
    "OrderItem",
    "OrderStatus",
    "OrderStatusEvent",
    "Payment",
    "PaymentMethod",
    "PaymentProvider",
    "PaymentStatus",
    "PaymentTransaction",
    "PaymentTransactionEvent",
    "Product",
    "ProductCondition",
    "ProductImage",
    "ProductReview",
    "ProductType",
    "ProductVariant",
    "Refund",
    "RefundStatus",
    "ReturnRequest",
    "ReturnRequestStatus",
    "ReturnRequestType",
    "Shipment",
    "ShipmentEvent",
    "ShippingMethod",
    "ShippingStatus",
    "Subcategory",
    "User",
    "UserRole",
    "WebhookEvent",
    "WishlistItem",
]
