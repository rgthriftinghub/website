"""Brand persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models.brand import Brand


def list_brands(
    db: Session, *, include_inactive: bool = False, page: int = 1, page_size: int = 100
) -> tuple[Sequence[Brand], int]:
    conditions = [] if include_inactive else [Brand.is_active.is_(True)]
    total = db.execute(select(func.count()).select_from(Brand).where(*conditions)).scalar_one()
    stmt = (
        select(Brand)
        .where(*conditions)
        .order_by(Brand.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return db.execute(stmt).scalars().all(), total


def get_by_slug(db: Session, slug: str, *, include_inactive: bool = False) -> Brand | None:
    stmt = select(Brand).where(Brand.slug == slug)
    if not include_inactive:
        stmt = stmt.where(Brand.is_active.is_(True))
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, brand_id: uuid.UUID) -> Brand | None:
    return db.get(Brand, brand_id)


def slug_exists(db: Session, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    conditions = [Brand.slug == slug]
    if exclude_id is not None:
        conditions.append(Brand.id != exclude_id)
    return bool(db.execute(select(exists().where(*conditions))).scalar())
