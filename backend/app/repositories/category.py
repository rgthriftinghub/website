"""Category and subcategory persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.category import Category, Subcategory


def list_categories(db: Session, *, include_inactive: bool = False) -> Sequence[Category]:
    stmt = (
        select(Category)
        .order_by(Category.sort_order, Category.name)
        .options(selectinload(Category.subcategories))
    )
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return db.execute(stmt).unique().scalars().all()


def get_by_slug(db: Session, slug: str, *, include_inactive: bool = False) -> Category | None:
    stmt = (
        select(Category).where(Category.slug == slug).options(selectinload(Category.subcategories))
    )
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return db.execute(stmt).unique().scalar_one_or_none()


def get_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    return db.get(Category, category_id)


def slug_exists(db: Session, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    conditions = [Category.slug == slug]
    if exclude_id is not None:
        conditions.append(Category.id != exclude_id)
    return bool(db.execute(select(exists().where(*conditions))).scalar())


def count_products(db: Session, category_id: uuid.UUID) -> int:
    from app.models.product import Product

    return db.execute(
        select(func.count())
        .select_from(Product)
        .where(Product.category_id == category_id, Product.is_active.is_(True))
    ).scalar_one()


# ---------------------------------------------------------------------- subcategory
def list_subcategories(
    db: Session, *, category_id: uuid.UUID | None = None, include_inactive: bool = False
) -> Sequence[Subcategory]:
    stmt = select(Subcategory).order_by(Subcategory.sort_order, Subcategory.name)
    if category_id is not None:
        stmt = stmt.where(Subcategory.category_id == category_id)
    if not include_inactive:
        stmt = stmt.where(Subcategory.is_active.is_(True))
    return db.execute(stmt).scalars().all()


def get_subcategory_by_id(db: Session, subcategory_id: uuid.UUID) -> Subcategory | None:
    return db.get(Subcategory, subcategory_id)


def subcategory_slug_exists(
    db: Session, category_id: uuid.UUID, slug: str, *, exclude_id: uuid.UUID | None = None
) -> bool:
    conditions = [Subcategory.category_id == category_id, Subcategory.slug == slug]
    if exclude_id is not None:
        conditions.append(Subcategory.id != exclude_id)
    return bool(db.execute(select(exists().where(*conditions))).scalar())
