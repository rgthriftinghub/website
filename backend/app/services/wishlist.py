"""Wishlist operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.product import Product
from app.models.variant import ProductVariant
from app.models.wishlist import WishlistItem
from app.services.exceptions import NotFoundError


def list_items(db: Session, user_id: uuid.UUID) -> Sequence[WishlistItem]:
    return (
        db.execute(
            select(WishlistItem)
            .where(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.created_at.desc())
            .options(
                joinedload(WishlistItem.product).selectinload(Product.images),
                joinedload(WishlistItem.product).joinedload(Product.brand),
                joinedload(WishlistItem.product)
                .selectinload(Product.variants)
                .selectinload(ProductVariant.inventory),
            )
        )
        .unique()
        .scalars()
        .all()
    )


def product_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Ids the customer has saved, so the UI can render filled hearts in bulk."""
    rows = (
        db.execute(select(WishlistItem.product_id).where(WishlistItem.user_id == user_id))
        .scalars()
        .all()
    )
    return set(rows)


def add(db: Session, user_id: uuid.UUID, product_id: uuid.UUID) -> WishlistItem:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise NotFoundError("Product not found")

    existing = db.execute(
        select(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
        )
    ).scalar_one_or_none()
    # Idempotent: saving twice is a no-op rather than a duplicate or an error.
    if existing is not None:
        return existing

    item = WishlistItem(user_id=user_id, product_id=product_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove(db: Session, user_id: uuid.UUID, product_id: uuid.UUID) -> None:
    item = db.execute(
        select(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("This product is not in your wishlist")
    db.delete(item)
    db.commit()
