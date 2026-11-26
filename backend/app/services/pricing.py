"""Price and total calculation.

Single source of truth for money. The cart preview, the checkout summary, and the
persisted order all call these functions, so the three can never disagree — and
no amount ever originates from a client request.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.models.variant import ProductVariant

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

TWO_PLACES = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    """Quantise to two decimal places, rounding half up as invoices expect."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def variant_unit_price(variant: ProductVariant) -> Decimal:
    """Authoritative selling price for one unit of a variant.

    Resolution order: the variant's sale override, then its price override, then
    the product's sale price, then the product's regular price.
    """
    if variant.sale_price_override is not None:
        return money(variant.sale_price_override)
    if variant.price_override is not None:
        return money(variant.price_override)
    return money(variant.product.effective_price)


def delivery_charge(subtotal: Decimal, db: "Session | None" = None) -> Decimal:
    """Delivery cost for a subtotal.

    Prefers the admin-configured `ShippingMethod` row when a session is supplied,
    and falls back to environment settings otherwise — so a fresh database with no
    shipping methods still prices correctly, and neither path is ever hardcoded in
    the frontend.
    """
    if db is not None:
        # Imported lazily: shipping_ops depends on models and notifications, and
        # pricing is imported very early by the cart.
        from app.shipping_ops.service import delivery_charge as configured_charge

        return money(configured_charge(db, money(subtotal)))

    settings = get_settings()
    if subtotal <= 0:
        return money(0)
    threshold = settings.free_delivery_threshold
    if threshold > 0 and subtotal >= threshold:
        return money(0)
    return money(settings.standard_delivery_charge)


class OrderTotals:
    """Computed money for a basket. Discounts are wired through at zero for now."""

    __slots__ = ("subtotal", "discount_amount", "shipping_amount", "total_amount")

    def __init__(self, subtotal: Decimal, discount_amount: Decimal, shipping_amount: Decimal):
        self.subtotal = money(subtotal)
        self.discount_amount = money(discount_amount)
        self.shipping_amount = money(shipping_amount)
        self.total_amount = money(self.subtotal - self.discount_amount + self.shipping_amount)


def compute_totals(
    subtotal: Decimal,
    *,
    discount_amount: Decimal | None = None,
    db: "Session | None" = None,
) -> OrderTotals:
    subtotal = money(subtotal)
    discount = money(discount_amount or 0)
    if discount > subtotal:
        discount = subtotal
    # Delivery is charged on the discounted subtotal so a future coupon that
    # crosses the free-delivery threshold behaves predictably.
    return OrderTotals(subtotal, discount, delivery_charge(subtotal - discount, db))
