"""Bulk catalogue operations.

Two rules run through everything here:

**Preview before apply.** Price changes compute their effect and return it without
writing, so an admin sees the actual before/after for every affected product before
committing. A percentage applied to the wrong selection is expensive to undo.

**Stock moves through the inventory service.** Bulk stock changes call
`inventory.apply_movement`, so every adjustment writes an `InventoryTransaction`
with before/after quantities exactly like a sale does. There is no bulk path that
bypasses the audit trail.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryItem
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.services import activity
from app.services import inventory as inventory_service
from app.services.exceptions import InvalidRequestError, NotFoundError
from app.services.pricing import money

MAX_BULK_SELECTION = 500

PriceMode = Literal[
    "increase_amount", "decrease_amount", "increase_percent", "decrease_percent", "set"
]
StockMode = Literal["add", "remove", "set"]


def _load_products(db: Session, product_ids: Sequence[uuid.UUID]) -> list[Product]:
    if not product_ids:
        raise InvalidRequestError("Select at least one product")
    if len(product_ids) > MAX_BULK_SELECTION:
        raise InvalidRequestError(
            f"Select at most {MAX_BULK_SELECTION} products in one operation"
        )
    products = list(
        db.execute(
            select(Product)
            .where(Product.id.in_(list(product_ids)))
            .options(selectinload(Product.variants))
        )
        .unique()
        .scalars()
        .all()
    )
    if not products:
        raise NotFoundError("No matching products found")
    return products


def resolve_selection(
    db: Session,
    *,
    product_ids: Sequence[uuid.UUID] | None = None,
    category_id: uuid.UUID | None = None,
    subcategory_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> list[Product]:
    """Turn an explicit id list or a category/brand filter into products.

    Explicit ids win when supplied, so a filter can be used to build a selection
    and then refined by hand without the filter silently re-widening it.
    """
    if product_ids:
        return _load_products(db, product_ids)

    conditions = []
    if category_id:
        conditions.append(Product.category_id == category_id)
    if subcategory_id:
        conditions.append(Product.subcategory_id == subcategory_id)
    if brand_id:
        conditions.append(Product.brand_id == brand_id)
    if not conditions:
        raise InvalidRequestError(
            "Provide product ids, or a category, subcategory, or brand to select by"
        )
    if not include_inactive:
        conditions.append(Product.is_active.is_(True))

    return list(
        db.execute(
            select(Product).where(*conditions).options(selectinload(Product.variants))
        )
        .unique()
        .scalars()
        .all()
    )


# ------------------------------------------------------------------ attributes
@dataclass(slots=True)
class BulkResult:
    affected: int
    detail: str


def bulk_update_attributes(
    db: Session,
    product_ids: Sequence[uuid.UUID],
    *,
    actor: User,
    is_active: bool | None = None,
    is_featured: bool | None = None,
    is_new_arrival: bool | None = None,
    category_id: uuid.UUID | None = None,
    subcategory_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
) -> BulkResult:
    """Apply flag and taxonomy changes to a selection.

    Relationships are validated before anything is written: a subcategory must
    belong to the category it is being applied alongside, otherwise the product
    would end up filed under a subcategory of a different category.
    """
    products = _load_products(db, product_ids)

    target_category: Category | None = None
    if category_id is not None:
        target_category = db.get(Category, category_id)
        if target_category is None:
            raise NotFoundError("Category not found")

    if subcategory_id is not None:
        subcategory = db.get(Subcategory, subcategory_id)
        if subcategory is None:
            raise NotFoundError("Subcategory not found")
        # Validate against the new category when one is being set, otherwise
        # against each product's existing category.
        if category_id is not None:
            if subcategory.category_id != category_id:
                raise InvalidRequestError(
                    "That subcategory does not belong to the selected category"
                )
        else:
            mismatched = [
                product.name
                for product in products
                if product.category_id != subcategory.category_id
            ]
            if mismatched:
                raise InvalidRequestError(
                    "That subcategory belongs to a different category than "
                    f"{len(mismatched)} of the selected products"
                )

    if brand_id is not None and db.get(Brand, brand_id) is None:
        raise NotFoundError("Brand not found")

    changes: dict[str, object] = {}
    for name, value in (
        ("is_active", is_active),
        ("is_featured", is_featured),
        ("is_new_arrival", is_new_arrival),
        ("category_id", category_id),
        ("subcategory_id", subcategory_id),
        ("brand_id", brand_id),
    ):
        if value is not None:
            changes[name] = value

    if not changes:
        raise InvalidRequestError("No changes were requested")

    for product in products:
        for name, value in changes.items():
            setattr(product, name, value)

    activity.log(
        db,
        actor=actor,
        action=activity.PRODUCT_BULK_UPDATED,
        entity_type="Product",
        description=f"Bulk updated {len(products)} products: {', '.join(sorted(changes))}",
        metadata={"product_count": len(products), "changes": {k: str(v) for k, v in changes.items()}},
        commit=False,
    )
    db.commit()
    return BulkResult(len(products), f"Updated {len(products)} products")


# ----------------------------------------------------------------------- price
@dataclass(slots=True)
class PricePreviewRow:
    product_id: str
    name: str
    sku: str
    current_price: float
    new_price: float
    change: float


def _apply_price_mode(current: Decimal, mode: PriceMode, value: Decimal) -> Decimal:
    match mode:
        case "increase_amount":
            result = current + value
        case "decrease_amount":
            result = current - value
        case "increase_percent":
            result = current * (Decimal("1") + value / Decimal("100"))
        case "decrease_percent":
            result = current * (Decimal("1") - value / Decimal("100"))
        case "set":
            result = value
        case _:
            raise InvalidRequestError(f"Unknown price mode: {mode}")
    # Never allow a bulk operation to produce a zero or negative price.
    return money(max(result, Decimal("0.01")))


def preview_price_update(
    db: Session,
    products: Sequence[Product],
    *,
    mode: PriceMode,
    value: Decimal,
    field: Literal["regular_price", "sale_price"] = "regular_price",
) -> tuple[list[PricePreviewRow], dict[str, float]]:
    """Compute the effect of a price change without writing anything."""
    if value < 0:
        raise InvalidRequestError("Value cannot be negative")
    if mode in ("increase_percent", "decrease_percent") and value > 100:
        raise InvalidRequestError("Percentage must be between 0 and 100")

    rows: list[PricePreviewRow] = []
    total_before = Decimal("0")
    total_after = Decimal("0")

    for product in products:
        current = getattr(product, field)
        if current is None:
            # No existing sale price to adjust; only "set" is meaningful.
            if mode != "set":
                continue
            current = product.regular_price
        current = money(current)
        new_price = _apply_price_mode(current, mode, money(value))

        # A sale price at or above the regular price is not a sale.
        if field == "sale_price" and new_price >= money(product.regular_price):
            continue

        total_before += current
        total_after += new_price
        rows.append(
            PricePreviewRow(
                product_id=str(product.id),
                name=product.name,
                sku=product.sku,
                current_price=float(current),
                new_price=float(new_price),
                change=float(new_price - current),
            )
        )

    return rows, {
        "affected": len(rows),
        "total_before": float(total_before),
        "total_after": float(total_after),
        "total_change": float(total_after - total_before),
    }


def apply_price_update(
    db: Session,
    products: Sequence[Product],
    *,
    mode: PriceMode,
    value: Decimal,
    field: Literal["regular_price", "sale_price"] = "regular_price",
    actor: User,
) -> BulkResult:
    """Apply a previewed price change.

    Recomputes from the same function the preview used, so what was shown is what
    is written even if the request arrives a moment later.
    """
    rows, summary = preview_price_update(db, products, mode=mode, value=value, field=field)
    by_id = {row.product_id: row for row in rows}

    for product in products:
        row = by_id.get(str(product.id))
        if row is None:
            continue
        setattr(product, field, money(Decimal(str(row.new_price))))

    activity.log(
        db,
        actor=actor,
        action=activity.PRICE_CHANGED,
        entity_type="Product",
        description=f"Bulk {mode} of {value} on {field} for {len(by_id)} products",
        metadata={"mode": mode, "value": str(value), "field": field, **summary},
        commit=False,
    )
    db.commit()
    return BulkResult(len(by_id), f"Updated prices on {len(by_id)} products")


# ----------------------------------------------------------------------- stock
@dataclass(slots=True)
class StockAdjustment:
    variant_id: uuid.UUID
    mode: StockMode
    quantity: int


def apply_stock_update(
    db: Session,
    adjustments: Sequence[StockAdjustment],
    *,
    reason: str,
    actor: User,
) -> BulkResult:
    """Adjust stock at the **variant** level, recording every movement.

    Each change goes through `inventory.apply_movement`, so an
    `InventoryTransaction` with before/after quantities is written for every line.
    A reason is mandatory — an unexplained stock change is impossible to reconcile
    later.
    """
    if not adjustments:
        raise InvalidRequestError("No adjustments were provided")
    if not reason.strip():
        raise InvalidRequestError("A reason is required for a stock adjustment")

    variant_ids = [entry.variant_id for entry in adjustments]
    locked = inventory_service.lock_inventory_for_variants(db, variant_ids)

    applied = 0
    for entry in adjustments:
        stock = locked.get(entry.variant_id)
        if stock is None:
            raise NotFoundError(f"No inventory record for variant {entry.variant_id}")
        if entry.quantity < 0:
            raise InvalidRequestError("Quantity cannot be negative")

        match entry.mode:
            case "add":
                delta = entry.quantity
                movement_type = InventoryTransactionType.RESTOCK
            case "remove":
                delta = -entry.quantity
                movement_type = InventoryTransactionType.ADJUSTMENT
            case "set":
                delta = entry.quantity - stock.quantity
                movement_type = InventoryTransactionType.ADJUSTMENT
            case _:
                raise InvalidRequestError(f"Unknown stock mode: {entry.mode}")

        if delta == 0:
            continue

        inventory_service.apply_movement(
            db,
            stock,
            quantity_change=delta,
            transaction_type=movement_type,
            reference_type="MANUAL",
            reference_id=str(actor.id),
            note=reason.strip()[:500],
        )
        applied += 1

    activity.log(
        db,
        actor=actor,
        action=activity.STOCK_CHANGED,
        entity_type="ProductVariant",
        description=f"Bulk stock adjustment on {applied} variants: {reason.strip()[:200]}",
        metadata={"variant_count": applied, "reason": reason.strip()[:200]},
        commit=False,
    )
    db.commit()
    return BulkResult(applied, f"Adjusted stock on {applied} variants")


def variant_rows_for_products(
    db: Session, product_ids: Sequence[uuid.UUID]
) -> list[dict[str, object]]:
    """Variants of a selection, so a bulk stock screen can list what it will change."""
    rows = db.execute(
        select(
            ProductVariant.id,
            ProductVariant.sku,
            ProductVariant.size,
            ProductVariant.waist,
            Product.name,
            func.coalesce(InventoryItem.quantity, 0),
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .where(ProductVariant.product_id.in_(list(product_ids)))
        .order_by(Product.name, ProductVariant.sku)
    ).all()

    return [
        {
            "variant_id": str(row[0]),
            "sku": row[1],
            "size": row[2],
            "waist": row[3],
            "product_name": row[4],
            "quantity": int(row[5] or 0),
        }
        for row in rows
    ]
