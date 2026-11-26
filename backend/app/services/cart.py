"""Cart operations.

Every mutation revalidates the variant against the live catalogue and inventory.
Prices are always recomputed here; a price supplied by a client is never read.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.variant import ProductVariant
from app.schemas.cart import CartItemRead, CartRead, GuestCartPreviewRequest
from app.services import pricing, sales
from app.services.exceptions import InvalidRequestError, NotFoundError


def _variant_loads() -> tuple:
    return (
        selectinload(Cart.items)
        .joinedload(CartItem.variant)
        .joinedload(ProductVariant.product)
        .selectinload(Product.images),
        selectinload(Cart.items)
        .joinedload(CartItem.variant)
        .joinedload(ProductVariant.product)
        .joinedload(Product.brand),
        selectinload(Cart.items).joinedload(CartItem.variant).joinedload(ProductVariant.inventory),
    )


def get_cart(db: Session, user_id: uuid.UUID) -> Cart | None:
    return db.execute(
        select(Cart).where(Cart.user_id == user_id).options(*_variant_loads())
    ).unique().scalar_one_or_none()


def get_or_create_cart(db: Session, user_id: uuid.UUID) -> Cart:
    cart = get_cart(db, user_id)
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


def _load_variant(db: Session, variant_id: uuid.UUID) -> ProductVariant:
    """Load a variant with everything needed to validate and price it."""
    variant = db.execute(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(
            joinedload(ProductVariant.product).selectinload(Product.images),
            joinedload(ProductVariant.product).joinedload(Product.brand),
            joinedload(ProductVariant.inventory),
        )
    ).unique().scalar_one_or_none()
    if variant is None:
        raise NotFoundError("Product variant not found")
    return variant


def _assert_purchasable(variant: ProductVariant, quantity: int) -> None:
    """The full validation chain a cart addition must pass."""
    product = variant.product
    if product is None:
        raise NotFoundError("Product not found")
    if not product.is_active:
        raise InvalidRequestError("This product is no longer available")
    if not variant.is_active:
        raise InvalidRequestError("This size is no longer available")

    settings = get_settings()
    if quantity < 1:
        raise InvalidRequestError("Quantity must be at least 1")
    if quantity > settings.max_quantity_per_item:
        raise InvalidRequestError(
            f"You can order at most {settings.max_quantity_per_item} of one size"
        )
    if product.single_piece and quantity > 1:
        raise InvalidRequestError("Only one unit of this single-piece item can be purchased")

    available = variant.quantity
    if available <= 0:
        raise InvalidRequestError(f"{variant.label} is out of stock")
    if quantity > available:
        raise InvalidRequestError(
            f"Only {available} left in {variant.label}. Please reduce the quantity."
        )


def add_item(
    db: Session, user_id: uuid.UUID, variant_id: uuid.UUID, quantity: int
) -> Cart:
    variant = _load_variant(db, variant_id)
    sales.attach_pricing_for_variants(db, [variant])
    cart = get_or_create_cart(db, user_id)

    existing = db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.product_variant_id == variant_id
        )
    ).scalar_one_or_none()

    # Adding a variant already in the cart raises its quantity rather than
    # creating a duplicate line.
    target_quantity = (existing.quantity if existing else 0) + quantity
    _assert_purchasable(variant, target_quantity)

    unit_price = pricing.variant_unit_price(variant)
    if existing is not None:
        existing.quantity = target_quantity
        existing.unit_price = unit_price
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_variant_id=variant_id,
                quantity=target_quantity,
                unit_price=unit_price,
            )
        )

    db.commit()
    return get_or_create_cart(db, user_id)


def update_item_quantity(
    db: Session, user_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> Cart:
    item = _owned_item(db, user_id, item_id)
    variant = _load_variant(db, item.product_variant_id)
    sales.attach_pricing_for_variants(db, [variant])
    _assert_purchasable(variant, quantity)

    item.quantity = quantity
    item.unit_price = pricing.variant_unit_price(variant)
    db.commit()
    return get_or_create_cart(db, user_id)


def remove_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> Cart:
    item = _owned_item(db, user_id, item_id)
    db.delete(item)
    db.commit()
    return get_or_create_cart(db, user_id)


def clear_cart(db: Session, user_id: uuid.UUID) -> Cart:
    cart = get_cart(db, user_id)
    if cart is not None:
        for item in list(cart.items):
            db.delete(item)
        db.commit()
    return get_or_create_cart(db, user_id)


def _owned_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> CartItem:
    """Fetch a cart item, scoped to the requesting user's own cart.

    Joining through `Cart.user_id` means another customer's item id resolves to
    "not found" rather than being editable.
    """
    item = db.execute(
        select(CartItem).join(Cart).where(CartItem.id == item_id, Cart.user_id == user_id)
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Cart item not found")
    return item


# ------------------------------------------------------------------ presentation
def _primary_image_url(product: Product) -> str | None:
    if not product.images:
        return None
    primary = next((image for image in product.images if image.is_primary), product.images[0])
    return primary.image_url


def serialise_cart(cart: Cart | None, db: Session | None = None) -> CartRead:
    """Build the cart response, repricing every line from the catalogue.

    Passing the session lets delivery use the admin-configured shipping method,
    so the bag preview and the checkout summary quote the same charge.
    """
    settings = get_settings()
    # Reprice against live campaigns so a bag opened mid-sale shows and charges the
    # campaign price, resolved by the same engine the storefront displays.
    if db is not None and cart is not None:
        sales.attach_pricing_for_variants(db, [item.variant for item in cart.items])
    items: list[CartItemRead] = []
    subtotal = Decimal("0.00")

    for item in cart.items if cart else []:
        variant = item.variant
        product = variant.product
        available = variant.quantity

        reason: str | None = None
        if product is None or not product.is_active:
            reason = "This product is no longer available"
        elif not variant.is_active:
            reason = "This size is no longer available"
        elif available <= 0:
            reason = "Out of stock"
        elif item.quantity > available:
            reason = f"Only {available} left"

        unit_price = pricing.variant_unit_price(variant)
        line_total = pricing.money(unit_price * item.quantity)
        if reason is None:
            subtotal += line_total

        items.append(
            CartItemRead(
                id=item.id,
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                brand_name=product.brand.name if product.brand else None,
                image_url=_primary_image_url(product),
                product_variant_id=variant.id,
                variant_label=variant.label,
                sku=variant.sku,
                size=variant.size,
                waist=variant.waist,
                color=variant.color,
                unit_price=unit_price,
                quantity=item.quantity,
                line_total=line_total,
                available_stock=available,
                is_available=reason is None,
                unavailable_reason=reason,
            )
        )

    totals = pricing.compute_totals(subtotal, db=db)
    return CartRead(
        id=cart.id if cart else None,
        items=items,
        item_count=sum(entry.quantity for entry in items if entry.is_available),
        subtotal=totals.subtotal,
        delivery_amount=totals.shipping_amount,
        total=totals.total_amount,
        currency=settings.currency_code,
        has_unavailable_items=any(not entry.is_available for entry in items),
    )


def preview_guest_cart(db: Session, payload: GuestCartPreviewRequest) -> CartRead:
    """Price a browser-held guest bag from current catalogue and inventory data."""
    settings = get_settings()
    if not payload.items:
        totals = pricing.compute_totals(Decimal("0.00"), db=db)
        return CartRead(
            id=None, items=[], item_count=0, subtotal=totals.subtotal,
            delivery_amount=totals.shipping_amount, total=totals.total_amount,
            currency=settings.currency_code, has_unavailable_items=False,
        )

    variant_ids = [line.product_variant_id for line in payload.items]
    variants = db.execute(
        select(ProductVariant)
        .where(ProductVariant.id.in_(variant_ids))
        .options(
            joinedload(ProductVariant.product).selectinload(Product.images),
            joinedload(ProductVariant.product).joinedload(Product.brand),
            joinedload(ProductVariant.inventory),
        )
    ).unique().scalars().all()
    by_id = {variant.id: variant for variant in variants}
    if len(by_id) != len(variant_ids):
        raise NotFoundError("One of the products in your bag could not be found")
    ordered_variants = [by_id[variant_id] for variant_id in variant_ids]
    sales.attach_pricing_for_variants(db, ordered_variants)

    items: list[CartItemRead] = []
    subtotal = Decimal("0.00")
    max_quantity = settings.max_quantity_per_item
    for line in payload.items:
        variant = by_id[line.product_variant_id]
        product = variant.product
        if product is None:
            raise NotFoundError("One of the products in your bag could not be found")
        available = variant.quantity
        reason = None
        if not product.is_active:
            reason = "This product is no longer available"
        elif not variant.is_active:
            reason = "This size is no longer available"
        elif available <= 0:
            reason = "Out of stock"
        elif line.quantity > max_quantity:
            reason = f"You can order at most {max_quantity} of one size"
        elif product.single_piece and line.quantity > 1:
            reason = "Only one unit of this single-piece item can be purchased"
        elif line.quantity > available:
            reason = f"Only {available} left"

        unit_price = pricing.variant_unit_price(variant)
        line_total = pricing.money(unit_price * line.quantity)
        if reason is None:
            subtotal += line_total
        items.append(CartItemRead(
            id=variant.id, product_id=product.id, product_name=product.name,
            product_slug=product.slug, brand_name=product.brand.name if product.brand else None,
            image_url=_primary_image_url(product), product_variant_id=variant.id,
            variant_label=variant.label, sku=variant.sku, size=variant.size,
            waist=variant.waist, color=variant.color, unit_price=unit_price,
            quantity=line.quantity, line_total=line_total, available_stock=available,
            is_available=reason is None, unavailable_reason=reason,
        ))

    totals = pricing.compute_totals(subtotal, db=db)
    return CartRead(
        id=None, items=items,
        item_count=sum(item.quantity for item in items if item.is_available),
        subtotal=totals.subtotal, delivery_amount=totals.shipping_amount,
        total=totals.total_amount, currency=settings.currency_code,
        has_unavailable_items=any(not item.is_available for item in items),
    )
