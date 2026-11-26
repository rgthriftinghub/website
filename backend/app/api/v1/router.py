from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user, require_staff
from app.api.v1.endpoints.admin import analytics as admin_analytics
from app.api.v1.endpoints.admin import coupons as admin_coupons
from app.api.v1.endpoints.admin import inventory as admin_inventory
from app.api.v1.endpoints.admin import operations as admin_operations
from app.api.v1.endpoints.admin import reports as admin_reports
from app.api.v1.endpoints.admin import orders as admin_orders
from app.api.v1.endpoints.admin import sales as admin_sales
from app.api.v1.endpoints.admin import payments as admin_payments
from app.api.v1.endpoints.admin import products as admin_products
from app.api.v1.endpoints.admin import taxonomy as admin_taxonomy
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.brands import router as brands_router
from app.api.v1.endpoints.cart import router as cart_router
from app.api.v1.endpoints.categories import router as categories_router
from app.api.v1.endpoints.content import router as content_router, admin_router as admin_content_router
from app.api.v1.endpoints.checkout import router as checkout_router
from app.api.v1.endpoints.customer import addresses as customer_addresses
from app.api.v1.endpoints.customer import orders as customer_orders
from app.api.v1.endpoints.customer import payments as customer_payments
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.payments import router as payments_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.reviews import router as reviews_router
from app.api.v1.endpoints.tracking import router as tracking_router
from app.api.v1.endpoints.wishlist import router as wishlist_router

api_router = APIRouter()

# ---- public ----------------------------------------------------------------
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(products_router, prefix="/products", tags=["products"])
api_router.include_router(reviews_router, prefix="/products", tags=["reviews"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(content_router, prefix="/content", tags=["content"])
# Checkout config and guest cart previews are public. The account checkout
# route declares its own authentication dependency; guest orders are rate-limited.
api_router.include_router(checkout_router, prefix="/checkout", tags=["checkout"])
# Payment webhooks and callbacks are authenticated by provider signature, not by
# session — a gateway has no cookie. Provider/bank-account listings are public
# read-only configuration.
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
# Public tracking, gated on order number plus a matching contact detail.
api_router.include_router(tracking_router, prefix="/track-order", tags=["tracking"])

# ---- authenticated customer ------------------------------------------------
# The dependency is attached to the parent router, so a route added here later
# cannot accidentally ship unauthenticated. Ownership is enforced inside each
# service by scoping every query to the requesting user's id.
customer_router = APIRouter(dependencies=[Depends(get_current_user)])
customer_router.include_router(cart_router, prefix="/cart", tags=["cart"])
customer_router.include_router(wishlist_router, prefix="/wishlist", tags=["wishlist"])
customer_router.include_router(
    customer_addresses.router, prefix="/customer/addresses", tags=["customer: addresses"]
)
customer_router.include_router(
    customer_orders.router, prefix="/customer/orders", tags=["customer: orders"]
)
customer_router.include_router(
    customer_payments.router, prefix="/customer/orders", tags=["customer: payments"]
)
api_router.include_router(customer_router)

# ---- admin -----------------------------------------------------------------
admin_router = APIRouter(prefix="/admin", dependencies=[Depends(require_staff)])
admin_router.include_router(admin_products.router, prefix="/products", tags=["admin: products"])
admin_router.include_router(admin_content_router, prefix="/content", tags=["admin: content"])
admin_router.include_router(admin_coupons.router, prefix="/coupons", tags=["admin: coupons"])
admin_router.include_router(
    admin_taxonomy.categories_router, prefix="/categories", tags=["admin: categories"]
)
admin_router.include_router(
    admin_taxonomy.subcategories_router, prefix="/subcategories", tags=["admin: subcategories"]
)
admin_router.include_router(admin_taxonomy.brands_router, prefix="/brands", tags=["admin: brands"])
admin_router.include_router(admin_orders.router, prefix="/orders", tags=["admin: orders"])
admin_router.include_router(admin_payments.router, prefix="/payments", tags=["admin: payments"])
admin_router.include_router(
    admin_payments.shipping_router, prefix="/shipping", tags=["admin: shipping"]
)
# Analytics and reporting. Every figure is aggregated by PostgreSQL.
admin_router.include_router(
    admin_analytics.router, prefix="/analytics", tags=["admin: analytics"]
)
# Sale campaigns. A sale is a rule, never a copy of the catalogue.
admin_router.include_router(admin_sales.router, prefix="/sales", tags=["admin: sales"])
# Reports, CSV/Excel export, and product import.
admin_router.include_router(admin_reports.router, prefix="/reports", tags=["admin: reports"])
# Stock levels, single-variant adjustment, and movement history.
admin_router.include_router(
    admin_inventory.router, prefix="/inventory", tags=["admin: inventory"]
)
# Bulk operations, activity log, and staff permissions. Each route declares the
# specific permission it needs rather than relying on a blanket admin gate.
admin_router.include_router(admin_operations.router, tags=["admin: operations"])
admin_router.include_router(
    admin_operations.notifications_router,
    prefix="/notifications",
    tags=["admin: notifications"],
)
admin_router.include_router(
    admin_operations.staff_router, prefix="/staff", tags=["admin: staff"]
)
admin_router.include_router(
    admin_operations.customers_router, prefix="/customers", tags=["admin: customers"]
)

api_router.include_router(admin_router)
