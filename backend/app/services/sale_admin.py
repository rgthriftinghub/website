"""Sale management (admin side).

Creating a sale writes the rule plus its targets in one transaction. Nothing here
touches product rows — a campaign is never baked into the catalogue, so ending it
restores the original prices instantly.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezones import utc_now
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import SaleTargetType
from app.models.product import Product
from app.models.sale import Sale, SaleTarget
from app.models.user import User
from app.services import activity, sales
from app.services.exceptions import ConflictError, InvalidRequestError, NotFoundError


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "sale"


def _unique_slug(db: Session, base: str, *, exclude_id: uuid.UUID | None = None) -> str:
    slug = slugify(base)
    candidate = slug
    suffix = 2
    while True:
        stmt = select(Sale.id).where(Sale.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Sale.id != exclude_id)
        if db.execute(stmt).first() is None:
            return candidate
        candidate = f"{slug}-{suffix}"
        suffix += 1


def _validate_targets(db: Session, targets: Sequence[dict]) -> list[SaleTarget]:
    """Turn target payloads into rows, checking each referenced entity exists.

    A target naming a missing category would silently match nothing, so it is
    rejected up front rather than becoming a campaign that appears to do nothing.
    """
    if not targets:
        raise InvalidRequestError(
            "A sale needs at least one target. Use STORE to cover the whole catalogue."
        )

    rows: list[SaleTarget] = []
    for entry in targets:
        target_type = SaleTargetType(entry["target_type"])
        kwargs: dict[str, uuid.UUID] = {}

        match target_type:
            case SaleTargetType.STORE:
                pass
            case SaleTargetType.PRODUCT:
                product_id = entry.get("product_id")
                if not product_id or db.get(Product, product_id) is None:
                    raise NotFoundError("Product target not found")
                kwargs["product_id"] = product_id
            case SaleTargetType.CATEGORY:
                category_id = entry.get("category_id")
                if not category_id or db.get(Category, category_id) is None:
                    raise NotFoundError("Category target not found")
                kwargs["category_id"] = category_id
            case SaleTargetType.SUBCATEGORY:
                subcategory_id = entry.get("subcategory_id")
                if not subcategory_id or db.get(Subcategory, subcategory_id) is None:
                    raise NotFoundError("Subcategory target not found")
                kwargs["subcategory_id"] = subcategory_id
            case SaleTargetType.BRAND:
                brand_id = entry.get("brand_id")
                if not brand_id or db.get(Brand, brand_id) is None:
                    raise NotFoundError("Brand target not found")
                kwargs["brand_id"] = brand_id

        rows.append(SaleTarget(target_type=target_type, **kwargs))
    return rows


def sale_loads() -> tuple:
    return (
        selectinload(Sale.targets).joinedload(SaleTarget.product),
        selectinload(Sale.targets).joinedload(SaleTarget.category),
        selectinload(Sale.targets).joinedload(SaleTarget.subcategory),
        selectinload(Sale.targets).joinedload(SaleTarget.brand),
    )


def list_sales(
    db: Session,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Sale], int]:
    """List campaigns, optionally filtered by live/scheduled/expired/inactive.

    The status filter uses the same time predicate the pricing engine uses, so the
    admin list and the storefront can never disagree about what is running.
    """
    now = utc_now()
    conditions = []

    match status:
        case "live":
            conditions += [
                Sale.is_active.is_(True),
                Sale.starts_at <= now,
                or_(Sale.ends_at.is_(None), Sale.ends_at > now),
            ]
        case "scheduled":
            conditions += [Sale.is_active.is_(True), Sale.starts_at > now]
        case "expired":
            conditions += [Sale.ends_at.is_not(None), Sale.ends_at <= now]
        case "inactive":
            conditions.append(Sale.is_active.is_(False))
    if search:
        conditions.append(func.lower(Sale.name).like(f"%{search.strip().lower()}%"))

    total = db.execute(select(func.count()).select_from(Sale).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Sale)
            .where(*conditions)
            .order_by(Sale.priority.desc(), Sale.starts_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(*sale_loads())
        )
        .unique()
        .scalars()
        .all()
    )
    return list(rows), total


def get_sale(db: Session, sale_id: uuid.UUID) -> Sale:
    sale = (
        db.execute(select(Sale).where(Sale.id == sale_id).options(*sale_loads()))
        .unique()
        .scalar_one_or_none()
    )
    if sale is None:
        raise NotFoundError("Sale not found")
    return sale


def create_sale(db: Session, payload: dict, *, actor: User) -> Sale:
    targets = _validate_targets(db, payload.get("targets") or [])

    if payload["ends_at"] is not None and payload["ends_at"] <= payload["starts_at"]:
        raise InvalidRequestError("The end time must be after the start time")

    sale = Sale(
        name=payload["name"],
        slug=_unique_slug(db, payload.get("slug") or payload["name"]),
        description=payload.get("description"),
        sale_type=payload["sale_type"],
        discount_type=payload["discount_type"],
        discount_value=payload["discount_value"],
        priority=payload.get("priority", 0),
        is_active=payload.get("is_active", True),
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        badge_text=payload.get("badge_text"),
        created_by_user_id=actor.id,
    )
    sale.targets = targets
    db.add(sale)

    activity.log(
        db,
        actor=actor,
        action=activity.SALE_CREATED,
        entity_type="Sale",
        entity_id=sale.id,
        description=f"Created sale {sale.name}",
        metadata={
            "discount_type": str(sale.discount_type),
            "discount_value": str(sale.discount_value),
            "priority": sale.priority,
            "targets": [str(target.target_type) for target in targets],
        },
        commit=False,
    )
    db.commit()
    return get_sale(db, sale.id)


def update_sale(db: Session, sale_id: uuid.UUID, payload: dict, *, actor: User) -> Sale:
    sale = get_sale(db, sale_id)
    changes = {key: value for key, value in payload.items() if value is not None}

    if "targets" in payload and payload["targets"] is not None:
        # Replace wholesale, so the edit screen is declarative rather than additive.
        sale.targets = _validate_targets(db, payload["targets"])
        changes["targets"] = [str(t.target_type) for t in sale.targets]

    for field in (
        "name", "description", "sale_type", "discount_type", "discount_value",
        "priority", "is_active", "starts_at", "ends_at", "badge_text",
    ):
        if field in payload and payload[field] is not None:
            setattr(sale, field, payload[field])

    if "name" in changes and payload.get("slug"):
        sale.slug = _unique_slug(db, payload["slug"], exclude_id=sale.id)

    if sale.ends_at is not None and sale.ends_at <= sale.starts_at:
        raise InvalidRequestError("The end time must be after the start time")

    activity.log(
        db,
        actor=actor,
        action=activity.SALE_UPDATED,
        entity_type="Sale",
        entity_id=sale.id,
        description=f"Updated sale {sale.name}",
        metadata={"fields": sorted(changes)},
        commit=False,
    )
    db.commit()
    return get_sale(db, sale.id)


def set_active(db: Session, sale_id: uuid.UUID, active: bool, *, actor: User) -> Sale:
    sale = get_sale(db, sale_id)
    if sale.is_active == active:
        raise InvalidRequestError(f"This sale is already {'active' if active else 'inactive'}")
    sale.is_active = active
    activity.log(
        db,
        actor=actor,
        action=activity.SALE_UPDATED,
        entity_type="Sale",
        entity_id=sale.id,
        description=f"{'Activated' if active else 'Deactivated'} sale {sale.name}",
        commit=False,
    )
    db.commit()
    return get_sale(db, sale.id)


def delete_sale(db: Session, sale_id: uuid.UUID, *, actor: User) -> None:
    """Remove a campaign.

    Safe to hard-delete: a sale never mutated product rows, and orders keep their
    own price snapshots, so removing it cannot rewrite history.
    """
    sale = get_sale(db, sale_id)
    name = sale.name
    db.delete(sale)
    activity.log(
        db,
        actor=actor,
        action=activity.SALE_DELETED,
        entity_type="Sale",
        entity_id=sale_id,
        description=f"Deleted sale {name}",
        commit=False,
    )
    db.commit()


def affected_products(
    db: Session, sale_id: uuid.UUID, *, page: int = 1, page_size: int = 25
) -> tuple[list[Product], int]:
    """Products a campaign currently covers, with its pricing applied."""
    sale = get_sale(db, sale_id)
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
        return [], 0

    where = [Product.is_active.is_(True), or_(*conditions)]
    total = db.execute(select(func.count()).select_from(Product).where(*where)).scalar_one()
    rows = list(
        db.execute(
            select(Product)
            .where(*where)
            .order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Product.images), selectinload(Product.variants))
        )
        .unique()
        .scalars()
        .all()
    )
    sales.attach_pricing(db, rows)
    return rows, total
