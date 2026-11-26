"""Stock movement with locking and history.

Every quantity change goes through :func:`apply_movement`, which writes an
`InventoryTransaction` recording the before and after values. Nothing else in the
codebase mutates `InventoryItem.quantity` directly, so stock and its history can
never drift apart.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.variant import ProductVariant
from app.services.exceptions import InvalidRequestError, NotFoundError


def lock_inventory_for_variants(
    db: Session, variant_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, InventoryItem]:
    """Take row locks on the inventory rows for the given variants.

    `SELECT ... FOR UPDATE` is what prevents overselling: a second transaction
    trying to buy the same variant blocks here until the first commits or rolls
    back, so both cannot read the same "1 remaining" and each decrement it.

    Rows are locked in a deterministic order (by variant id) so two concurrent
    multi-item checkouts that overlap cannot deadlock by grabbing the same two
    rows in opposite orders.

    `populate_existing` is essential and not merely an optimisation. These rows
    are usually already in the session's identity map, loaded through the cart's
    eager-loaded variant relationship. Without it SQLAlchemy would return those
    cached instances and keep their pre-lock `quantity`, so a transaction that
    waited on the lock would go on to read the stale value it saw before
    blocking — and oversell the stock it had just waited for.
    """
    if not variant_ids:
        return {}

    unique_ids = sorted(set(variant_ids), key=str)
    rows = (
        db.execute(
            select(InventoryItem)
            .where(InventoryItem.product_variant_id.in_(unique_ids))
            .order_by(InventoryItem.product_variant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        .scalars()
        .all()
    )
    return {row.product_variant_id: row for row in rows}


def apply_movement(
    db: Session,
    inventory: InventoryItem,
    *,
    quantity_change: int,
    transaction_type: InventoryTransactionType,
    reference_type: str | None = None,
    reference_id: str | None = None,
    note: str | None = None,
) -> InventoryTransaction:
    """Adjust stock by a signed amount and record the movement.

    The caller is responsible for holding a row lock (see
    :func:`lock_inventory_for_variants`) when the change must be race-free.
    """
    if quantity_change == 0:
        raise InvalidRequestError("An inventory movement must change the quantity")

    before = inventory.quantity
    after = before + quantity_change
    if after < 0:
        raise InvalidRequestError(
            f"Insufficient stock: {before} available, tried to remove {abs(quantity_change)}"
        )

    product = db.execute(
        select(Product)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .where(ProductVariant.id == inventory.product_variant_id)
    ).scalar_one()
    if product.single_piece:
        product_stock = db.scalar(
            select(func.coalesce(func.sum(InventoryItem.quantity), 0))
            .join(ProductVariant, ProductVariant.id == InventoryItem.product_variant_id)
            .where(ProductVariant.product_id == product.id)
        ) or 0
        if product_stock + quantity_change > 1:
            raise InvalidRequestError("Single-piece stock cannot exceed one unit")

    inventory.quantity = after
    movement = InventoryTransaction(
        product_variant_id=inventory.product_variant_id,
        type=transaction_type,
        quantity_change=quantity_change,
        quantity_before=before,
        quantity_after=after,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )
    db.add(movement)
    return movement


def set_quantity(
    db: Session,
    variant_id: uuid.UUID,
    quantity: int,
    *,
    note: str | None = None,
) -> InventoryTransaction | None:
    """Set an absolute quantity, recording the delta as an ADJUSTMENT."""
    if quantity < 0:
        raise InvalidRequestError("Quantity cannot be negative")

    locked = lock_inventory_for_variants(db, [variant_id])
    inventory = locked.get(variant_id)
    if inventory is None:
        raise NotFoundError("Inventory record not found for this variant")

    delta = quantity - inventory.quantity
    if delta == 0:
        return None
    return apply_movement(
        db,
        inventory,
        quantity_change=delta,
        transaction_type=InventoryTransactionType.ADJUSTMENT,
        reference_type="MANUAL",
        note=note,
    )


def history_for_variant(
    db: Session, variant_id: uuid.UUID, *, limit: int = 50
) -> Sequence[InventoryTransaction]:
    return (
        db.execute(
            select(InventoryTransaction)
            .where(InventoryTransaction.product_variant_id == variant_id)
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def history_for_order(db: Session, order_id: uuid.UUID) -> Sequence[InventoryTransaction]:
    """Every stock movement caused by one order, for the admin detail view."""
    return (
        db.execute(
            select(InventoryTransaction)
            .where(
                InventoryTransaction.reference_type == "ORDER",
                InventoryTransaction.reference_id == str(order_id),
            )
            .order_by(InventoryTransaction.created_at)
        )
        .scalars()
        .all()
    )
