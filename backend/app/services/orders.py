"""Order placement and lifecycle.

Placement is a single database transaction. Nothing is committed until every
validation has passed, prices have been recomputed from the catalogue, stock has
been decremented under row locks, and the cart has been emptied. Any failure
raises and rolls the whole thing back, so a partial order cannot exist.
"""

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.core.timezones import business_date_stamp
from app.models.address import CustomerAddress
from app.models.cart import Cart, CartItem
from app.models.enums import (
    CUSTOMER_CANCELLABLE_STATUSES,
    ORDER_STATUS_TRANSITIONS,
    STOCK_HOLDING_STATUSES,
    InventoryTransactionType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.inventory_transaction import REFERENCE_ORDER
from app.models.inventory_transaction import InventoryTransaction
from app.models.order import Order, OrderItem, OrderStatusEvent
from app.models.coupon import Coupon
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.schemas.address import AddressSnapshot
from app.schemas.order import CheckoutRequest, GuestCheckoutRequest
from app.services import inventory as inventory_service
from app.services import notifications, pricing, sales
from app.services.exceptions import ConflictError, InvalidRequestError, NotFoundError

ORDER_NUMBER_PREFIX = "RG"
_SUFFIX_PATTERN = re.compile(r"-(\d+)$")


def order_loads() -> tuple:
    from app.models.payment import Payment
    from app.models.shipping import Shipment

    return (
        selectinload(Order.items),
        selectinload(Order.status_events),
        selectinload(Order.return_requests),
        selectinload(Order.payments).selectinload(Payment.transactions),
        selectinload(Order.shipment).selectinload(Shipment.events),
    )


# ------------------------------------------------------------- order numbering
def generate_order_number(db: Session, *, now: datetime | None = None) -> str:
    """Produce the next human-friendly order number, e.g. RG-20260812-0001.

    The date is the *business* local date, not UTC: an order placed at 2am in
    Karachi belongs to that trading day, and staff reading the number expect it
    to match the day they took the order.

    A transaction-scoped advisory lock serialises concurrent callers so two
    orders placed at the same moment cannot compute the same suffix. The unique
    constraint on `order_number` remains the final backstop.
    """
    stamp = business_date_stamp(now)
    prefix = f"{ORDER_NUMBER_PREFIX}-{stamp}-"

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Constant key: all order-number generation contends on one lock, which
        # is cheap because the critical section is a single indexed query.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('rg_order_number'))"))

    existing = (
        db.execute(select(Order.order_number).where(Order.order_number.like(f"{prefix}%")))
        .scalars()
        .all()
    )
    highest = 0
    for number in existing:
        match = _SUFFIX_PATTERN.search(number)
        if match:
            highest = max(highest, int(match.group(1)))

    return f"{prefix}{highest + 1:04d}"


# ------------------------------------------------------------------- placement
def _load_cart_for_checkout(db: Session, user_id: uuid.UUID) -> Cart:
    cart = db.execute(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.items)
            .joinedload(CartItem.variant)
            .joinedload(ProductVariant.product)
            .selectinload(Product.images),
            selectinload(Cart.items)
            .joinedload(CartItem.variant)
            .joinedload(ProductVariant.product)
            .joinedload(Product.brand),
        )
    ).unique().scalar_one_or_none()

    if cart is None or not cart.items:
        raise InvalidRequestError("Your bag is empty")
    return cart


def _resolve_address(db: Session, user: User, address_id: uuid.UUID) -> CustomerAddress:
    address = db.execute(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id, CustomerAddress.user_id == user.id
        )
    ).scalar_one_or_none()
    if address is None:
        # Scoped by user_id, so another customer's address id is simply not found.
        raise NotFoundError("Delivery address not found")
    return address


def _variant_snapshot(variant: ProductVariant) -> dict[str, object]:
    return {
        "label": variant.label,
        "size": variant.size,
        "waist": variant.waist,
        "color": variant.color,
        "variant_name": variant.variant_name,
    }


def _primary_image_url(product: Product) -> str | None:
    if not product.images:
        return None
    primary = next((image for image in product.images if image.is_primary), product.images[0])
    return primary.image_url


def _initial_payment_status(method: PaymentMethod) -> PaymentStatus:
    """Neither COD nor bank transfer is ever assumed paid at placement.

    Cash arrives at the door; a bank transfer needs a human to reconcile it. Both
    therefore start PENDING and only staff can mark them PAID.
    """
    return PaymentStatus.PENDING


def place_order(db: Session, user: User, payload: CheckoutRequest) -> Order:
    """Create an order from the user's cart, atomically.

    Ordering of the steps matters: locks are taken before any validation that
    depends on stock, so the quantities checked are the quantities decremented.
    """
    cart = _load_cart_for_checkout(db, user.id)
    address = _resolve_address(db, user, payload.address_id)
    return _create_order_from_lines(
        db,
        [(item.variant, item.quantity) for item in cart.items],
        user_id=user.id,
        contact_email=str(payload.contact_email or user.email),
        contact_phone=(payload.contact_phone or address.phone).strip(),
        address_snapshot=address.as_snapshot(),
        payload=payload,
        cart=cart,
    )


def place_guest_order(db: Session, payload: GuestCheckoutRequest) -> Order:
    """Create a COD order from a guest's browser-held bag."""
    ids = [line.product_variant_id for line in payload.items]
    variants = db.execute(
        select(ProductVariant)
        .where(ProductVariant.id.in_(ids))
        .options(
            joinedload(ProductVariant.product).selectinload(Product.images),
            joinedload(ProductVariant.product).joinedload(Product.brand),
            joinedload(ProductVariant.inventory),
        )
    ).unique().scalars().all()
    by_id = {variant.id: variant for variant in variants}
    if len(by_id) != len(ids):
        raise NotFoundError("One of the products in your bag could not be found")

    address = payload.delivery
    snapshot = AddressSnapshot(
        full_name=address.full_name,
        phone=address.phone,
        address_line_1=address.address_line_1,
        address_line_2=address.address_line_2,
        city=address.city,
        province=address.province or address.city,
        postal_code=address.postal_code,
        country=address.country,
    ).model_dump()
    return _create_order_from_lines(
        db,
        [(by_id[line.product_variant_id], line.quantity) for line in payload.items],
        user_id=None,
        contact_email=str(payload.contact_email) if payload.contact_email else None,
        contact_phone=address.phone,
        address_snapshot=snapshot,
        payload=payload,
    )


def _create_order_from_lines(
    db: Session,
    lines: list[tuple[ProductVariant | None, int]],
    *,
    user_id: uuid.UUID | None,
    contact_email: str | None,
    contact_phone: str,
    address_snapshot: dict,
    payload: CheckoutRequest | GuestCheckoutRequest,
    cart: Cart | None = None,
) -> Order:
    """Shared authoritative stock, price, payment, and order transaction."""
    if not lines:
        raise InvalidRequestError("Your bag is empty")

    # Resolve live campaigns before any price is read, so the order is frozen at
    # the campaign price the customer was shown.
    variants = [variant for variant, _ in lines if variant is not None]
    sales.attach_pricing_for_variants(db, variants)

    variant_ids = [variant.id for variant in variants]
    locked_inventory = inventory_service.lock_inventory_for_variants(db, variant_ids)

    subtotal = Decimal("0.00")
    prepared: list[tuple[ProductVariant, int, Decimal, Decimal]] = []

    for variant, quantity in lines:
        product = variant.product if variant else None

        if variant is None or product is None:
            raise InvalidRequestError("An item in your bag is no longer available")
        if not product.is_active:
            raise InvalidRequestError(f"{product.name} is no longer available")
        if not variant.is_active:
            raise InvalidRequestError(f"{product.name} ({variant.label}) is no longer available")

        stock = locked_inventory.get(variant.id)
        if stock is None:
            raise InvalidRequestError(f"{product.name} ({variant.label}) has no stock record")
        if stock.quantity < quantity:
            raise InvalidRequestError(
                f"Only {stock.quantity} left of {product.name} ({variant.label}). "
                "Please update your bag."
            )
        if quantity > get_settings().max_quantity_per_item:
            raise InvalidRequestError(
                f"You can order at most {get_settings().max_quantity_per_item} of one size"
            )
        if product.single_piece and quantity > 1:
            raise InvalidRequestError("Only one unit of this single-piece item can be purchased")

        # Recomputed from the catalogue, never taken from the cart row or client.
        unit_price = pricing.variant_unit_price(variant)
        line_total = pricing.money(unit_price * quantity)
        subtotal += line_total
        prepared.append((variant, quantity, unit_price, line_total))

    coupon = None
    coupon_discount = Decimal("0.00")
    coupon_code = (payload.coupon_code or "").strip().upper() or None
    if coupon_code:
        from datetime import UTC, datetime
        coupon = db.execute(select(Coupon).where(Coupon.code == coupon_code).with_for_update()).scalar_one_or_none()
        now = datetime.now(UTC)
        if coupon is None or not coupon.is_active:
            raise InvalidRequestError("That coupon code is not valid")
        if coupon.starts_at and coupon.starts_at > now:
            raise InvalidRequestError("That coupon is not active yet")
        if coupon.ends_at and coupon.ends_at <= now:
            raise InvalidRequestError("That coupon has expired")
        if coupon.max_redemptions is not None and coupon.redemption_count >= coupon.max_redemptions:
            raise InvalidRequestError("That coupon has reached its redemption limit")
        if subtotal < coupon.minimum_order:
            raise InvalidRequestError(f"This coupon requires a minimum order of PKR {coupon.minimum_order}")
        coupon_discount = (subtotal * coupon.discount_value / Decimal("100")) if coupon.discount_type == "PERCENTAGE" else coupon.discount_value
        coupon_discount = pricing.money(min(subtotal, coupon_discount))

    totals = pricing.compute_totals(subtotal, discount_amount=coupon_discount, db=db)

    order = Order(
        order_number=generate_order_number(db),
        user_id=user_id,
        contact_email=contact_email,
        contact_phone=contact_phone.strip(),
        shipping_address_snapshot=address_snapshot,
        billing_address_snapshot=None,
        payment_method=payload.payment_method,
        coupon_code=coupon.code if coupon else None,
        payment_status=_initial_payment_status(payload.payment_method),
        order_status=OrderStatus.PENDING,
        delivery_method=payload.delivery_method,
        subtotal=totals.subtotal,
        discount_amount=totals.discount_amount,
        shipping_amount=totals.shipping_amount,
        total_amount=totals.total_amount,
        customer_note=payload.customer_note,
    )
    db.add(order)
    if coupon is not None:
        coupon.redemption_count += 1
    db.flush()  # assign order.id before referencing it

    for variant, quantity, unit_price, line_total in prepared:
        product = variant.product
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_variant_id=variant.id,
                product_name_snapshot=product.name,
                product_slug_snapshot=product.slug,
                brand_name_snapshot=product.brand.name if product.brand else None,
                sku_snapshot=variant.sku,
                variant_snapshot=_variant_snapshot(variant),
                image_url_snapshot=_primary_image_url(product),
                unit_price=unit_price,
                quantity=quantity,
                line_total=line_total,
            )
        )
        inventory_service.apply_movement(
            db,
            locked_inventory[variant.id],
            quantity_change=-quantity,
            transaction_type=InventoryTransactionType.SALE,
            reference_type=REFERENCE_ORDER,
            reference_id=str(order.id),
            note=f"Order {order.order_number}",
        )

    db.add(
        OrderStatusEvent(
            order_id=order.id, status=OrderStatus.PENDING, note="Order placed"
        )
    )

    # Payment and shipment records are created inside the same transaction. A
    # provider that refuses to start (an unconfigured gateway) therefore rolls the
    # whole order back rather than leaving an order with no payment attached.
    from app.payments import service as payment_service
    from app.shipping_ops import service as shipping_service

    order.payments = []
    payment, intent = payment_service.create_payment_for_order(db, order)
    order.payment_status = payment.status
    shipping_service.ensure_shipment(db, order)

    # The cart is emptied inside the same transaction: a rollback leaves the
    # customer's bag intact.
    if cart is not None:
        for item in list(cart.items):
            db.delete(item)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Could not place the order because it conflicted with another. Please try again."
        ) from exc

    db.refresh(order)
    notifications.notify_order_event(
        notifications.NotificationEvent.ORDER_CREATED,
        order,
        payment_instructions=intent.instructions,
    )
    return get_order_by_id(db, order.id)  # type: ignore[return-value]


# --------------------------------------------------------------------- reading
def get_order_by_id(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.execute(
        select(Order).where(Order.id == order_id).options(*order_loads())
    ).unique().scalar_one_or_none()


def get_order_for_user(db: Session, user_id: uuid.UUID, order_number: str) -> Order:
    """Fetch one of the requesting customer's own orders.

    The user filter is part of the query rather than a check afterwards, so
    another customer's order number cannot be read even by guessing it.
    """
    order = db.execute(
        select(Order)
        .where(Order.order_number == order_number, Order.user_id == user_id)
        .options(*order_loads())
    ).unique().scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")
    return order


def list_orders_for_user(
    db: Session, user_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[Order], int]:
    total = db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user_id)
    ).scalar_one()
    rows = (
        db.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(*order_loads())
        )
        .unique()
        .scalars()
        .all()
    )
    return list(rows), total


# ------------------------------------------------------------- status changes
def _record_status(
    db: Session,
    order: Order,
    status: OrderStatus,
    *,
    note: str | None,
    changed_by: uuid.UUID | None,
) -> None:
    order.order_status = status
    db.add(
        OrderStatusEvent(
            order_id=order.id, status=status, note=note, changed_by_user_id=changed_by
        )
    )


def update_order_status(
    db: Session,
    order_id: uuid.UUID,
    new_status: OrderStatus,
    *,
    actor: User,
    note: str | None = None,
) -> Order:
    """Move an order to a new status, enforcing the transition table."""
    order = get_order_by_id(db, order_id)
    if order is None:
        raise NotFoundError("Order not found")

    current = order.order_status
    if new_status == current:
        raise InvalidRequestError(f"The order is already {current}")

    allowed = ORDER_STATUS_TRANSITIONS.get(current, frozenset())
    if new_status not in allowed:
        permitted = ", ".join(sorted(str(s) for s in allowed)) or "no further changes"
        raise InvalidRequestError(
            f"Cannot move an order from {current} to {new_status}. Allowed: {permitted}"
        )

    if new_status is OrderStatus.CANCELLED:
        return _cancel(db, order, actor=actor, note=note)

    _record_status(db, order, new_status, note=note, changed_by=actor.id)
    db.commit()
    db.refresh(order)
    notifications.notify_status_change(order)
    return get_order_by_id(db, order.id)  # type: ignore[return-value]


def delete_unpaid_order(db: Session, order_id: uuid.UUID) -> None:
    """Delete an unpaid pending/cancelled order and restore any reserved stock."""
    order = get_order_by_id(db, order_id)
    if order is None:
        raise NotFoundError("Order not found")

    if order.order_status not in {OrderStatus.PENDING, OrderStatus.CANCELLED}:
        raise InvalidRequestError(
            "Only pending or cancelled orders can be deleted. Orders in fulfilment must be kept."
        )
    if order.payment_status not in {
        PaymentStatus.PENDING,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    }:
        raise InvalidRequestError("Paid, processing, or refunded orders cannot be deleted.")

    if order.order_status in STOCK_HOLDING_STATUSES:
        variant_ids = [
            item.product_variant_id
            for item in order.items
            if item.product_variant_id is not None
        ]
        locked = inventory_service.lock_inventory_for_variants(db, variant_ids)
        for item in order.items:
            if item.product_variant_id is None:
                continue
            stock = locked.get(item.product_variant_id)
            if stock is None:
                continue
            inventory_service.apply_movement(
                db,
                stock,
                quantity_change=item.quantity,
                transaction_type=InventoryTransactionType.CANCELLED_ORDER,
                reference_type=REFERENCE_ORDER,
                reference_id=str(order.id),
                note=f"Restocked after deleting unpaid order {order.order_number}",
            )

    db.delete(order)
    db.commit()


def delete_all_test_orders(db: Session) -> tuple[int, int]:
    """Delete every order and restore the net stock deducted by those orders.

    This is an explicit admin operation for a catalogue whose order history is
    known to be test data. Per-order inventory movements make restoration
    idempotent for cancelled orders that already returned their reserved stock.
    """
    from app.models.enums import InventoryTransactionType

    orders = list(
        db.execute(select(Order).options(*order_loads()).order_by(Order.created_at, Order.id))
        .unique()
        .scalars()
        .all()
    )
    if not orders:
        return 0, 0

    order_ids = [order.id for order in orders]
    order_references = [str(order_id) for order_id in order_ids]
    net_movements = db.execute(
        select(
            InventoryTransaction.product_variant_id,
            func.sum(InventoryTransaction.quantity_change),
        )
        .where(
            InventoryTransaction.reference_type == REFERENCE_ORDER,
            InventoryTransaction.reference_id.in_(order_references),
        )
        .group_by(InventoryTransaction.product_variant_id)
    ).all()
    restock = {
        variant_id: -int(net_quantity)
        for variant_id, net_quantity in net_movements
        if net_quantity is not None and net_quantity < 0
    }

    # Lock every affected stock row before changing any quantities. A single
    # aggregate adjustment per variant avoids double-restocking cancelled orders.
    locked = inventory_service.lock_inventory_for_variants(db, list(restock))
    reset_reference = f"TEST_ORDER_RESET:{uuid.uuid4()}"
    restored_variant_count = 0
    for variant_id, quantity in restock.items():
        stock = locked.get(variant_id)
        if stock is None:
            continue
        inventory_service.apply_movement(
            db,
            stock,
            quantity_change=quantity,
            transaction_type=InventoryTransactionType.CANCELLED_ORDER,
            reference_type="MANUAL",
            reference_id=reset_reference,
            note=f"Restocked after deleting {len(orders)} test orders",
        )
        restored_variant_count += 1

    # Discard the test orders' old movement rows after writing the reset
    # adjustment, so the inventory history does not retain dangling order IDs.
    db.execute(
        delete(InventoryTransaction).where(
            InventoryTransaction.reference_type == REFERENCE_ORDER,
            InventoryTransaction.reference_id.in_(order_references),
        )
    )
    for order in orders:
        db.delete(order)
    db.commit()
    return len(orders), restored_variant_count


def cancel_order_as_customer(
    db: Session, user_id: uuid.UUID, order_number: str, *, reason: str | None = None
) -> Order:
    order = get_order_for_user(db, user_id, order_number)
    if order.order_status not in CUSTOMER_CANCELLABLE_STATUSES:
        raise InvalidRequestError(
            f"An order that is {order.order_status} can no longer be cancelled here. "
            "Please open a return or exchange request instead."
        )
    return _cancel(db, order, actor=order.user, note=reason)


def _cancel(db: Session, order: Order, *, actor: User | None, note: str | None) -> Order:
    """Cancel an order and give its reserved stock back, in one transaction."""
    if order.order_status is OrderStatus.CANCELLED:
        raise InvalidRequestError("This order is already cancelled")

    restore_stock = order.order_status in STOCK_HOLDING_STATUSES
    if restore_stock:
        variant_ids = [item.product_variant_id for item in order.items if item.product_variant_id]
        locked = inventory_service.lock_inventory_for_variants(db, variant_ids)
        for item in order.items:
            if item.product_variant_id is None:
                continue
            stock = locked.get(item.product_variant_id)
            if stock is None:
                # The variant was deleted after purchase; there is nothing to
                # restore, and the snapshot keeps the order readable.
                continue
            inventory_service.apply_movement(
                db,
                stock,
                quantity_change=item.quantity,
                transaction_type=InventoryTransactionType.CANCELLED_ORDER,
                reference_type=REFERENCE_ORDER,
                reference_id=str(order.id),
                note=f"Cancelled order {order.order_number}",
            )

    order.cancelled_at = datetime.now(UTC)
    _record_status(
        db,
        order,
        OrderStatus.CANCELLED,
        note=note or "Order cancelled",
        changed_by=actor.id if actor else None,
    )
    db.commit()
    db.refresh(order)
    notifications.notify_status_change(order, reason=note)
    return get_order_by_id(db, order.id)  # type: ignore[return-value]


def update_payment_status(
    db: Session,
    order_id: uuid.UUID,
    payment_status: PaymentStatus,
    *,
    actor: User,
    note: str | None = None,
) -> Order:
    """Set the payment status through the payment service.

    Kept as a thin shim so the admin order endpoint from Phase 3 keeps working,
    but all state changes now go through one audited path in
    `app.payments.service`, which validates the transition and writes the trail.
    """
    from app.models.enums import PaymentTransactionEvent
    from app.payments import service as payment_service

    order = get_order_by_id(db, order_id)
    if order is None:
        raise NotFoundError("Order not found")

    payment = order.active_payment
    if payment is None:
        raise InvalidRequestError("This order has no payment record")

    changed = payment_service.transition(
        db,
        payment,
        payment_status,
        event=PaymentTransactionEvent.MANUALLY_VERIFIED
        if payment_status is PaymentStatus.PAID
        else PaymentTransactionEvent.MANUALLY_REJECTED,
        message=note or f"Set to {payment_status} by {actor.email}",
        actor=actor,
    )
    if not changed:
        raise InvalidRequestError(f"Payment is already {payment_status}")

    db.add(
        OrderStatusEvent(
            order_id=order.id,
            status=order.order_status,
            note=note or f"Payment marked {payment_status}",
            changed_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(order)
    if payment_status is PaymentStatus.PAID:
        notifications.notify_order_event(
            notifications.NotificationEvent.PAYMENT_RECEIVED, order
        )
    return get_order_by_id(db, order.id)  # type: ignore[return-value]


def set_internal_note(db: Session, order_id: uuid.UUID, note: str | None) -> Order:
    order = get_order_by_id(db, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    order.internal_note = note
    db.commit()
    db.refresh(order)
    return get_order_by_id(db, order.id)  # type: ignore[return-value]
