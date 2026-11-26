"""Sale and discount resolution.

## Activation

A sale is live when `is_active` is true **and** the clock is inside its window.
That predicate is evaluated in SQL on every price lookup, so a scheduled campaign
starts and stops entirely on its own — no cron job, no background worker, and no
admin toggling anything. `Sale.is_live()` mirrors the same rule in Python; the two
must stay in step or a listing and a detail page could quote different prices.

## Priority — the exact, deterministic rule

Several sales can cover one product (store-wide 10%, brand 20%, product 30%). The
winner is chosen by comparing, in order:

1. **`priority` descending** — the explicit, admin-controlled field. Highest wins.
2. **Target specificity descending** — PRODUCT > BRAND > SUBCATEGORY > CATEGORY >
   STORE. A rule written for one product is a more deliberate decision than a
   store-wide banner.
3. **Larger resulting discount** — if two rules are equally deliberate, the
   customer gets the better one.
4. **Later `starts_at`** — the more recent campaign supersedes.
5. **Sale id** — an arbitrary but *stable* final tiebreak, so the same inputs
   always produce the same winner. Nothing here is ever random.

## Stacking

Campaigns never stack. Exactly one sale wins and it is computed from
`regular_price`. If the product also carries a manual `sale_price`, the final
price is the **lower** of the two, so a hand-set clearance price is never
silently undercut by a campaign, and a campaign never double-discounts an
already-reduced item.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezones import utc_now
from app.models.enums import (
    SALE_TARGET_SPECIFICITY,
    DiscountType,
    SaleTargetType,
    SaleType,
)
from app.models.product import Product
from app.models.sale import Sale, SaleTarget
from app.services.pricing import money

# Default badge wording when a sale does not override it.
DEFAULT_BADGES: dict[SaleType, str] = {
    SaleType.FLASH: "Flash Sale",
    SaleType.CLEARANCE: "Clearance",
    SaleType.SEASONAL: "Season Sale",
    SaleType.STANDARD: "Sale",
}


@dataclass(slots=True)
class SalePricing:
    """Resolved pricing for one product. Every figure is computed server-side."""

    original_price: Decimal
    final_price: Decimal
    discount_amount: Decimal
    discount_percent: int
    sale_id: uuid.UUID | None = None
    sale_name: str | None = None
    sale_type: SaleType | None = None
    badge_text: str | None = None
    # Drives the storefront countdown. The countdown is presentation only — the
    # backend decides whether the sale applies.
    ends_at: datetime | None = None
    matched_target: SaleTargetType | None = None

    @property
    def has_discount(self) -> bool:
        return self.discount_amount > 0


def active_sales_query() -> Select:
    """Select live sales with their targets eagerly loaded.

    The window predicate is `is_active AND starts_at <= now AND (ends_at IS NULL
    OR ends_at > now)`, evaluated by the database.
    """
    now = utc_now()
    return (
        select(Sale)
        .where(
            Sale.is_active.is_(True),
            Sale.starts_at <= now,
            or_(Sale.ends_at.is_(None), Sale.ends_at > now),
        )
        .options(selectinload(Sale.targets))
        .order_by(Sale.priority.desc(), Sale.starts_at.desc())
    )


def active_sales(db: Session) -> list[Sale]:
    return list(db.execute(active_sales_query()).unique().scalars().all())


def sales_for_products(db: Session, products: Sequence[Product]) -> list[Sale]:
    """Live sales that could touch any of the given products.

    Narrowed in SQL to store-wide rules plus rules naming one of these products,
    their categories, subcategories, or brands — so a catalogue with thousands of
    product-specific campaigns does not load them all to price one page.
    """
    if not products:
        return []

    product_ids = {product.id for product in products}
    category_ids = {product.category_id for product in products if product.category_id}
    subcategory_ids = {
        product.subcategory_id for product in products if product.subcategory_id
    }
    brand_ids = {product.brand_id for product in products if product.brand_id}

    relevant = [SaleTarget.target_type == SaleTargetType.STORE]
    if product_ids:
        relevant.append(SaleTarget.product_id.in_(product_ids))
    if category_ids:
        relevant.append(SaleTarget.category_id.in_(category_ids))
    if subcategory_ids:
        relevant.append(SaleTarget.subcategory_id.in_(subcategory_ids))
    if brand_ids:
        relevant.append(SaleTarget.brand_id.in_(brand_ids))

    stmt = active_sales_query().where(
        Sale.id.in_(select(SaleTarget.sale_id).where(or_(*relevant)))
    )
    return list(db.execute(stmt).unique().scalars().all())


def _matches(target: SaleTarget, product: Product) -> bool:
    match target.target_type:
        case SaleTargetType.STORE:
            return True
        case SaleTargetType.PRODUCT:
            return target.product_id == product.id
        case SaleTargetType.CATEGORY:
            return target.category_id == product.category_id
        case SaleTargetType.SUBCATEGORY:
            return (
                product.subcategory_id is not None
                and target.subcategory_id == product.subcategory_id
            )
        case SaleTargetType.BRAND:
            return product.brand_id is not None and target.brand_id == product.brand_id
    return False


def _best_target(sale: Sale, product: Product) -> SaleTarget | None:
    """The narrowest target on this sale that covers the product."""
    matching = [target for target in sale.targets if _matches(target, product)]
    if not matching:
        return None
    return max(matching, key=lambda target: SALE_TARGET_SPECIFICITY[target.target_type])


def compute_discounted_price(
    regular_price: Decimal, discount_type: DiscountType, discount_value: Decimal
) -> Decimal:
    """Apply one discount to a base price. Never returns a negative price."""
    base = money(regular_price)
    value = money(discount_value)

    match discount_type:
        case DiscountType.PERCENTAGE:
            # Clamped at 100% so a bad value cannot invert the price.
            pct = min(value, Decimal("100"))
            result = base - (base * pct / Decimal("100"))
        case DiscountType.FIXED_AMOUNT:
            result = base - value
        case DiscountType.CUSTOM_PRICE:
            result = value
        case _:
            result = base

    return money(max(result, Decimal("0.00")))


def _pricing_for(product: Product, sale: Sale, target: SaleTarget) -> SalePricing:
    regular = money(product.regular_price)
    campaign_price = compute_discounted_price(
        regular, sale.discount_type, sale.discount_value
    )

    # Campaigns never stack, and a manual sale_price is respected when it is the
    # better price for the customer.
    final = min(campaign_price, money(product.manual_price))
    saving = money(regular - final) if final < regular else Decimal("0.00")
    percent = int(round((saving / regular) * 100)) if regular > 0 and saving > 0 else 0

    return SalePricing(
        original_price=regular,
        final_price=final,
        discount_amount=saving,
        discount_percent=percent,
        sale_id=sale.id,
        sale_name=sale.name,
        sale_type=sale.sale_type,
        badge_text=sale.badge_text or DEFAULT_BADGES.get(sale.sale_type, "Sale"),
        ends_at=sale.ends_at,
        matched_target=target.target_type,
    )


def no_sale_pricing(product: Product) -> SalePricing:
    """Pricing when no campaign applies — the product's own columns."""
    regular = money(product.regular_price)
    final = money(product.manual_price)
    saving = money(regular - final) if final < regular else Decimal("0.00")
    percent = int(round((saving / regular) * 100)) if regular > 0 and saving > 0 else 0
    return SalePricing(
        original_price=regular,
        final_price=final,
        discount_amount=saving,
        discount_percent=percent,
    )


def resolve(product: Product, candidates: Iterable[Sale]) -> SalePricing:
    """Pick the winning sale for one product and compute its pricing.

    Applies the documented five-step tiebreak. Deterministic for identical input.
    """
    scored: list[tuple[tuple, Sale, SaleTarget]] = []

    for sale in candidates:
        target = _best_target(sale, product)
        if target is None:
            continue
        candidate_price = compute_discounted_price(
            product.regular_price, sale.discount_type, sale.discount_value
        )
        discount = money(product.regular_price) - candidate_price
        key = (
            sale.priority,
            SALE_TARGET_SPECIFICITY[target.target_type],
            discount,
            sale.starts_at,
            str(sale.id),  # stable final tiebreak
        )
        scored.append((key, sale, target))

    if not scored:
        return no_sale_pricing(product)

    _, winner, target = max(scored, key=lambda entry: entry[0])
    return _pricing_for(product, winner, target)


def attach_pricing(db: Session, products: Sequence[Product]) -> dict[uuid.UUID, SalePricing]:
    """Resolve and attach campaign pricing to each product in one pass.

    Sets `product.campaign_price`, which `Product.effective_price` consults. This
    is a transient in-memory attribute, never a column, so nothing is persisted
    and the catalogue cannot drift out of step with its campaigns.

    One query for all candidate sales, then in-memory resolution — so pricing a
    page of 24 products costs a single extra round trip.
    """
    if not products:
        return {}

    candidates = sales_for_products(db, products)
    resolved: dict[uuid.UUID, SalePricing] = {}

    for product in products:
        pricing = resolve(product, candidates)
        resolved[product.id] = pricing
        # Only set the override when a campaign actually beats the manual price,
        # so `effective_price` falls back cleanly otherwise.
        product.campaign_price = (
            pricing.final_price if pricing.sale_id is not None else None
        )
        product.sale_pricing = pricing

    return resolved


def attach_pricing_to_product(db: Session, product: Product | None) -> SalePricing | None:
    if product is None:
        return None
    return attach_pricing(db, [product]).get(product.id)


def attach_pricing_for_variants(db: Session, variants: Sequence) -> None:
    """Attach campaign pricing to the products behind a set of variants.

    Used by the cart and checkout so a bag priced mid-campaign charges the campaign
    price, computed by the same resolver the storefront displays.
    """
    products = []
    seen: set[uuid.UUID] = set()
    for variant in variants:
        product = getattr(variant, "product", None)
        if product is not None and product.id not in seen:
            seen.add(product.id)
            products.append(product)
    attach_pricing(db, products)


# --------------------------------------------------------------- admin helpers
def affected_product_count(db: Session, sale: Sale) -> int:
    """How many active products a sale currently covers."""
    conditions = []
    for target in sale.targets:
        match target.target_type:
            case SaleTargetType.STORE:
                conditions.append(Product.id.is_not(None))
            case SaleTargetType.PRODUCT:
                conditions.append(Product.id == target.product_id)
            case SaleTargetType.CATEGORY:
                conditions.append(Product.category_id == target.category_id)
            case SaleTargetType.SUBCATEGORY:
                conditions.append(Product.subcategory_id == target.subcategory_id)
            case SaleTargetType.BRAND:
                conditions.append(Product.brand_id == target.brand_id)
    if not conditions:
        return 0

    from sqlalchemy import func

    return db.execute(
        select(func.count())
        .select_from(Product)
        .where(and_(Product.is_active.is_(True), or_(*conditions)))
    ).scalar_one()
