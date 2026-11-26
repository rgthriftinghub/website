"""Historical demo orders and sale campaigns.

Analytics are meaningless against one order, so this backfills a spread of orders
across the last ~120 days. Orders are built directly rather than through checkout,
because `place_order` would stamp everything with today's date and empty a cart that
does not exist.

Stock is still decremented through the inventory service, so the seeded history has a
matching `InventoryTransaction` trail exactly like real trade — otherwise the
inventory-history screen would look empty while stock had visibly moved.

All data is fictional. Quantities and dates are derived from a fixed seed so repeated
runs produce the same history rather than drifting.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezones import utc_now
from app.models.address import CustomerAddress
from app.models.enums import (
    DiscountType,
    InventoryTransactionType,
    OrderStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    SaleTargetType,
    SaleType,
    ShippingStatus,
    UserRole,
)
from app.models.inventory import InventoryItem
from app.models.order import Order, OrderItem, OrderStatusEvent
from app.models.payment import Payment
from app.models.product import Product
from app.models.sale import Sale, SaleTarget
from app.models.shipping import Shipment
from app.models.user import User
from app.models.variant import ProductVariant
from app.services import inventory as inventory_service
from app.services.pricing import money

#: Fixed so the demo history is reproducible.
RANDOM_SEED = 20260812
HISTORY_DAYS = 120
TARGET_ORDERS = 90

# Demo customers, clearly fictional. Real customer data is never used.
DEMO_CUSTOMERS = (
    ("aisha.n@example.com", "Aisha", "Nadeem", "Lahore", "Punjab"),
    ("bilal.r@example.com", "Bilal", "Raza", "Karachi", "Sindh"),
    ("sana.k@example.com", "Sana", "Khalid", "Islamabad", "Islamabad"),
    ("usman.t@example.com", "Usman", "Tariq", "Faisalabad", "Punjab"),
    ("meher.s@example.com", "Meher", "Siddiqui", "Multan", "Punjab"),
    ("hamza.a@example.com", "Hamza", "Ali", "Rawalpindi", "Punjab"),
    ("zoya.f@example.com", "Zoya", "Farooq", "Peshawar", "KPK"),
    ("daniyal.m@example.com", "Daniyal", "Mahmood", "Quetta", "Balochistan"),
)

# Weighted so most history is delivered trade with a realistic tail of problems.
STATUS_WEIGHTS = (
    (OrderStatus.DELIVERED, 58),
    (OrderStatus.DISPATCHED, 10),
    (OrderStatus.PACKED, 6),
    (OrderStatus.PROCESSING, 8),
    (OrderStatus.PENDING, 6),
    (OrderStatus.CANCELLED, 9),
    (OrderStatus.RETURNED, 3),
)


def _demo_password_hash() -> str:
    from app.core.security import hash_password
    from app.seeds.seed import DEFAULT_SEED_PASSWORD

    return hash_password(DEFAULT_SEED_PASSWORD)


def seed_demo_customers(db: Session) -> list[User]:
    """Create the demo shoppers, each with a default address."""
    shared_hash = _demo_password_hash()
    users: list[User] = []

    for email, first, last, city, province in DEMO_CUSTOMERS:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=shared_hash)
            db.add(user)
        user.first_name = first
        user.last_name = last
        user.role = UserRole.CUSTOMER
        user.is_active = True
        user.is_verified = True
        db.flush()

        has_address = db.execute(
            select(CustomerAddress.id).where(CustomerAddress.user_id == user.id)
        ).first()
        if not has_address:
            db.add(
                CustomerAddress(
                    user_id=user.id,
                    full_name=f"{first} {last}",
                    phone=f"+92 3{random.randint(10, 49)} {random.randint(1000000, 9999999)}",
                    address_line_1=f"House {random.randint(1, 400)}, Street {random.randint(1, 40)}",
                    city=city,
                    province=province,
                    country="Pakistan",
                    is_default=True,
                )
            )
        users.append(user)

    db.flush()
    return users


def seed_sales(db: Session) -> list[Sale]:
    """Create demo campaigns covering every discount type and target shape.

    Includes a live flash sale, an open-ended clearance rail, a scheduled campaign
    that has not started, and an expired one — so the admin list and the storefront
    both have something real to show in each state.
    """
    now = utc_now()
    category = db.execute(select(Product.category_id).limit(1)).scalar()
    brand = db.execute(
        select(Product.brand_id).where(Product.brand_id.is_not(None)).limit(1)
    ).scalar()

    definitions = [
        {
            "name": "Weekend Flash Sale",
            "slug": "weekend-flash-sale",
            "sale_type": SaleType.FLASH,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": Decimal("25"),
            "priority": 60,
            "starts_at": now - timedelta(hours=6),
            "ends_at": now + timedelta(days=2),
            "badge_text": "Flash 25%",
            "target": (SaleTargetType.STORE, {}),
        },
        {
            "name": "End of Line Clearance",
            "slug": "end-of-line-clearance",
            "sale_type": SaleType.CLEARANCE,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": Decimal("40"),
            "priority": 80,
            "starts_at": now - timedelta(days=10),
            "ends_at": None,
            "badge_text": "Clearance",
            "target": (
                (SaleTargetType.BRAND, {"brand_id": brand})
                if brand
                else (SaleTargetType.STORE, {})
            ),
        },
        {
            "name": "Denim Days",
            "slug": "denim-days",
            "sale_type": SaleType.SEASONAL,
            "discount_type": DiscountType.FIXED_AMOUNT,
            "discount_value": Decimal("600"),
            "priority": 30,
            "starts_at": now - timedelta(days=3),
            "ends_at": now + timedelta(days=7),
            "badge_text": None,
            "target": (
                (SaleTargetType.CATEGORY, {"category_id": category})
                if category
                else (SaleTargetType.STORE, {})
            ),
        },
        {
            "name": "Eid Preview (scheduled)",
            "slug": "eid-preview-scheduled",
            "sale_type": SaleType.SEASONAL,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": Decimal("15"),
            "priority": 40,
            "starts_at": now + timedelta(days=14),
            "ends_at": now + timedelta(days=21),
            "badge_text": None,
            "target": (SaleTargetType.STORE, {}),
        },
        {
            "name": "Winter Closeout (ended)",
            "slug": "winter-closeout-ended",
            "sale_type": SaleType.STANDARD,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": Decimal("30"),
            "priority": 20,
            "starts_at": now - timedelta(days=60),
            "ends_at": now - timedelta(days=30),
            "badge_text": None,
            "target": (SaleTargetType.STORE, {}),
        },
    ]

    created: list[Sale] = []
    for spec in definitions:
        target_type, target_kwargs = spec.pop("target")  # type: ignore[misc]
        sale = db.execute(
            select(Sale).where(Sale.slug == spec["slug"])
        ).scalar_one_or_none()
        if sale is None:
            sale = Sale(slug=spec["slug"])
            db.add(sale)
        for key, value in spec.items():
            setattr(sale, key, value)
        sale.is_active = True
        db.flush()

        # Replace targets so re-running does not accumulate duplicates.
        for existing in list(sale.targets):
            db.delete(existing)
        db.flush()
        db.add(SaleTarget(sale_id=sale.id, target_type=target_type, **target_kwargs))
        created.append(sale)

    db.flush()
    return created


def seed_order_history(db: Session, customers: list[User]) -> dict[str, int]:
    """Backfill orders across the last `HISTORY_DAYS` days.

    Skips entirely if history already exists, so re-running the seed does not double
    the numbers on every dashboard.
    """
    existing = db.execute(
        select(func.count()).select_from(Order).where(Order.order_number.like("RG-DEMO-%"))
    ).scalar_one()
    if existing:
        return {"orders": 0, "skipped": existing}

    rng = random.Random(RANDOM_SEED)
    now = utc_now()

    variants = list(
        db.execute(
            select(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.is_active.is_(True), Product.is_active.is_(True))
            .options(
                selectinload(ProductVariant.product).selectinload(Product.images),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.inventory),
            )
        )
        .unique()
        .scalars()
        .all()
    )
    if not variants or not customers:
        return {"orders": 0, "skipped": 0}

    addresses = {
        address.user_id: address
        for address in db.execute(select(CustomerAddress)).scalars().all()
    }

    statuses: list[OrderStatus] = []
    for status, weight in STATUS_WEIGHTS:
        statuses.extend([status] * weight)

    created = 0
    for index in range(TARGET_ORDERS):
        # Bias recent days so the last 30 look busier than three months ago, which
        # is what a growing store's chart looks like.
        day_offset = int(HISTORY_DAYS * (rng.random() ** 1.7))
        placed_at = now - timedelta(
            days=day_offset, hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )

        customer = rng.choice(customers)
        address = addresses.get(customer.id)
        if address is None:
            continue

        status = rng.choice(statuses)
        line_variants = rng.sample(variants, k=min(rng.randint(1, 3), len(variants)))

        items: list[tuple[ProductVariant, int, Decimal]] = []
        subtotal = Decimal("0.00")
        for variant in line_variants:
            quantity = rng.randint(1, 2)
            unit_price = money(variant.product.manual_price)
            subtotal += money(unit_price * quantity)
            items.append((variant, quantity, unit_price))

        if not items:
            continue

        shipping = Decimal("0.00") if subtotal >= Decimal("10000") else Decimal("250.00")
        total = money(subtotal + shipping)
        method = rng.choice(
            [PaymentMethod.COD] * 7 + [PaymentMethod.BANK_TRANSFER] * 3
        )

        # Delivered orders are usually paid; a small tail is not, which is realistic
        # for COD and gives the payments screen something to work on.
        if status is OrderStatus.DELIVERED:
            payment_status = (
                PaymentStatus.PAID if rng.random() > 0.12 else PaymentStatus.PENDING
            )
        elif status is OrderStatus.CANCELLED:
            payment_status = PaymentStatus.CANCELLED
        elif status is OrderStatus.RETURNED:
            payment_status = PaymentStatus.REFUNDED
        elif status in (OrderStatus.DISPATCHED, OrderStatus.PACKED):
            payment_status = (
                PaymentStatus.PAID if rng.random() > 0.5 else PaymentStatus.PENDING
            )
        else:
            payment_status = PaymentStatus.PENDING

        order = Order(
            order_number=f"RG-DEMO-{placed_at.strftime('%Y%m%d')}-{index + 1:04d}",
            user_id=customer.id,
            contact_email=customer.email,
            contact_phone=address.phone,
            shipping_address_snapshot=address.as_snapshot(),
            payment_method=method,
            payment_status=payment_status,
            order_status=status,
            subtotal=money(subtotal),
            discount_amount=Decimal("0.00"),
            shipping_amount=shipping,
            total_amount=total,
            created_at=placed_at,
            updated_at=placed_at,
        )
        if status is OrderStatus.CANCELLED:
            order.cancelled_at = placed_at + timedelta(hours=rng.randint(1, 48))
        db.add(order)
        db.flush()

        for variant, quantity, unit_price in items:
            product = variant.product
            primary = next(
                (image for image in product.images if image.is_primary),
                product.images[0] if product.images else None,
            )
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_variant_id=variant.id,
                    product_name_snapshot=product.name,
                    product_slug_snapshot=product.slug,
                    brand_name_snapshot=product.brand.name if product.brand else None,
                    sku_snapshot=variant.sku,
                    variant_snapshot={
                        "label": variant.label,
                        "size": variant.size,
                        "waist": variant.waist,
                        "color": variant.color,
                    },
                    image_url_snapshot=primary.image_url if primary else None,
                    unit_price=unit_price,
                    quantity=quantity,
                    line_total=money(unit_price * quantity),
                    created_at=placed_at,
                )
            )

            # Non-cancelled history moved real stock, so record the movement.
            if status is not OrderStatus.CANCELLED and variant.inventory is not None:
                available = variant.inventory.quantity
                taken = min(quantity, available)
                if taken > 0:
                    inventory_service.apply_movement(
                        db,
                        variant.inventory,
                        quantity_change=-taken,
                        transaction_type=InventoryTransactionType.SALE,
                        reference_type="ORDER",
                        reference_id=str(order.id),
                        note=f"Demo order {order.order_number}",
                    )

        db.add(
            OrderStatusEvent(
                order_id=order.id,
                status=OrderStatus.PENDING,
                note="Order placed",
                created_at=placed_at,
            )
        )
        if status is not OrderStatus.PENDING:
            db.add(
                OrderStatusEvent(
                    order_id=order.id,
                    status=status,
                    note="Demo history",
                    created_at=placed_at + timedelta(hours=rng.randint(2, 72)),
                )
            )

        db.add(
            Payment(
                order_id=order.id,
                provider=(
                    PaymentProvider.COD
                    if method is PaymentMethod.COD
                    else PaymentProvider.BANK_TRANSFER
                ),
                payment_method=method,
                amount=total,
                currency="PKR",
                status=payment_status,
                paid_at=(
                    placed_at + timedelta(days=rng.randint(1, 5))
                    if payment_status is PaymentStatus.PAID
                    else None
                ),
                created_at=placed_at,
                updated_at=placed_at,
            )
        )

        shipping_status = {
            OrderStatus.DELIVERED: ShippingStatus.DELIVERED,
            OrderStatus.DISPATCHED: ShippingStatus.IN_TRANSIT,
            OrderStatus.PACKED: ShippingStatus.READY,
            OrderStatus.RETURNED: ShippingStatus.RETURNED,
            OrderStatus.CANCELLED: ShippingStatus.CANCELLED,
        }.get(status, ShippingStatus.PENDING)

        db.add(
            Shipment(
                order_id=order.id,
                shipping_status=shipping_status,
                tracking_number=(
                    f"DEMO{rng.randint(100000000, 999999999)}"
                    if shipping_status
                    not in (ShippingStatus.PENDING, ShippingStatus.CANCELLED)
                    else None
                ),
                shipped_at=(
                    placed_at + timedelta(days=1)
                    if shipping_status
                    in (
                        ShippingStatus.IN_TRANSIT,
                        ShippingStatus.DELIVERED,
                        ShippingStatus.RETURNED,
                    )
                    else None
                ),
                delivered_at=(
                    placed_at + timedelta(days=rng.randint(2, 6))
                    if shipping_status is ShippingStatus.DELIVERED
                    else None
                ),
                created_at=placed_at,
                updated_at=placed_at,
            )
        )
        created += 1

    db.flush()
    return {"orders": created, "skipped": 0}


def restock_to_catalogue_levels(db: Session) -> int:
    """Return every variant to its catalogue-defined quantity after backfilling.

    Ninety demo orders drain real stock, which would leave the storefront looking
    sold out and would break the documented per-waist test matrix
    (waist 30 = 5, waist 32 = 8, waist 34 = 0).

    Restocking is recorded as a normal RESTOCK movement rather than a silent write,
    so the inventory-history screen shows the sell-then-replenish cycle a real shop
    has, and stock still reconciles against its transaction trail.
    """
    from app.seeds.catalog_data import PRODUCTS
    from app.seeds.owner_photos import OWNER_PHOTO_PRODUCTS

    wanted: dict[str, int] = {}
    for product in PRODUCTS:
        for variant in product.variants:
            wanted[f"{product.sku}-{variant.sku_suffix}"] = variant.quantity
    for product in OWNER_PHOTO_PRODUCTS:
        wanted[f"{product.sku}-ONE"] = 1

    if not wanted:
        return 0

    rows = list(
        db.execute(
            select(ProductVariant, InventoryItem)
            .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
            .where(ProductVariant.sku.in_(list(wanted)))
        ).all()
    )

    adjusted = 0
    for variant, inventory in rows:
        target = wanted.get(variant.sku)
        if target is None or inventory.quantity == target:
            continue
        delta = target - inventory.quantity
        inventory_service.apply_movement(
            db,
            inventory,
            quantity_change=delta,
            transaction_type=(
                InventoryTransactionType.RESTOCK
                if delta > 0
                else InventoryTransactionType.ADJUSTMENT
            ),
            reference_type="MANUAL",
            note="Replenished to catalogue level after demo history",
        )
        adjusted += 1

    db.flush()
    return adjusted
