"""Admin activity log and operational notifications.

Both are deliberately lightweight: append a row, read it back, mark it read. No
queue, no worker, no external service.

Logging must never break the action it records — a failed log write is swallowed
and reported to the application log, exactly as notifications are.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timezones import utc_now
from app.models.admin import AdminActivityLog, AdminNotification
from app.models.enums import AdminNotificationSeverity, AdminNotificationType
from app.models.user import User
from app.payments.base import redact

logger = logging.getLogger("app.activity")

# Action names. Constants rather than free strings so the log stays filterable and
# a typo cannot silently create a new category.
PRODUCT_CREATED = "PRODUCT_CREATED"
PRODUCT_UPDATED = "PRODUCT_UPDATED"
PRODUCT_DEACTIVATED = "PRODUCT_DEACTIVATED"
PRODUCT_BULK_UPDATED = "PRODUCT_BULK_UPDATED"
PRICE_CHANGED = "PRICE_CHANGED"
STOCK_CHANGED = "STOCK_CHANGED"
SALE_CREATED = "SALE_CREATED"
SALE_UPDATED = "SALE_UPDATED"
SALE_DELETED = "SALE_DELETED"
ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
PAYMENT_VERIFIED = "PAYMENT_VERIFIED"
PAYMENT_REJECTED = "PAYMENT_REJECTED"
REFUND_REQUESTED = "REFUND_REQUESTED"
SHIPPING_UPDATED = "SHIPPING_UPDATED"
CUSTOMER_UPDATED = "CUSTOMER_UPDATED"
CUSTOMER_NOTE_ADDED = "CUSTOMER_NOTE_ADDED"
PERMISSIONS_CHANGED = "PERMISSIONS_CHANGED"
IMPORT_COMMITTED = "IMPORT_COMMITTED"
CATEGORY_UPDATED = "CATEGORY_UPDATED"
BRAND_UPDATED = "BRAND_UPDATED"


def log(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    description: str,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AdminActivityLog | None:
    """Record an admin action.

    `metadata` passes through the payment layer's `redact()` so a caller cannot
    accidentally log a secret. The actor's email is denormalised so the entry stays
    readable after an account is removed.
    """
    try:
        entry = AdminActivityLog(
            user_id=actor.id if actor else None,
            user_email=actor.email if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            description=description[:500],
            metadata_json=redact(metadata) if metadata else None,
        )
        db.add(entry)
        if commit:
            db.commit()
        else:
            db.flush()
        return entry
    except Exception:  # noqa: BLE001 - logging must not break the recorded action
        logger.exception("Failed to write activity log for %s", action)
        return None


def list_activity(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AdminActivityLog], int]:
    conditions = []
    if action:
        conditions.append(AdminActivityLog.action == action)
    if entity_type:
        conditions.append(AdminActivityLog.entity_type == entity_type)
    if user_id:
        conditions.append(AdminActivityLog.user_id == user_id)

    total = db.execute(
        select(func.count()).select_from(AdminActivityLog).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(AdminActivityLog)
            .where(*conditions)
            .order_by(AdminActivityLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


# ---------------------------------------------------------------- notifications
def notify(
    db: Session,
    *,
    type: AdminNotificationType,
    title: str,
    dedupe_key: str,
    body: str | None = None,
    link: str | None = None,
    severity: AdminNotificationSeverity = AdminNotificationSeverity.INFO,
    commit: bool = True,
) -> AdminNotification | None:
    """Raise an operational alert, at most once per `dedupe_key`.

    Re-detecting the same condition is a no-op rather than a new row, so a variant
    that has been low on stock for a week produces one alert, not hundreds.
    """
    existing = db.execute(
        select(AdminNotification).where(AdminNotification.dedupe_key == dedupe_key)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    notification = AdminNotification(
        type=type,
        severity=severity,
        title=title[:200],
        body=body,
        link=link,
        dedupe_key=dedupe_key[:200],
    )
    db.add(notification)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        # Lost a race against a concurrent detector; the other row stands.
        db.rollback()
        return None
    return notification


def list_notifications(
    db: Session, *, unread_only: bool = False, page: int = 1, page_size: int = 30
) -> tuple[list[AdminNotification], int, int]:
    conditions = [AdminNotification.is_read.is_(False)] if unread_only else []
    total = db.execute(
        select(func.count()).select_from(AdminNotification).where(*conditions)
    ).scalar_one()
    unread = db.execute(
        select(func.count())
        .select_from(AdminNotification)
        .where(AdminNotification.is_read.is_(False))
    ).scalar_one()
    rows = (
        db.execute(
            select(AdminNotification)
            .where(*conditions)
            .order_by(AdminNotification.is_read, AdminNotification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total, unread


def mark_read(db: Session, notification_id: uuid.UUID, *, actor: User) -> bool:
    result = db.execute(
        update(AdminNotification)
        .where(
            AdminNotification.id == notification_id,
            AdminNotification.is_read.is_(False),
        )
        .values(is_read=True, read_at=utc_now(), read_by_user_id=actor.id)
    )
    db.commit()
    return result.rowcount > 0


def mark_all_read(db: Session, *, actor: User) -> int:
    result = db.execute(
        update(AdminNotification)
        .where(AdminNotification.is_read.is_(False))
        .values(is_read=True, read_at=utc_now(), read_by_user_id=actor.id)
    )
    db.commit()
    return result.rowcount


def scan_stock_alerts(db: Session, *, commit: bool = True) -> dict[str, int]:
    """Raise low/out-of-stock alerts for active variants.

    Compares each variant against its own `low_stock_threshold` rather than a
    global number, because a staple and a one-off thrift piece do not warrant the
    same reorder point.

    Dedupe keys are per variant and per condition, so a variant that goes from low
    to out raises a distinct, more severe alert.
    """
    from app.models.inventory import InventoryItem
    from app.models.product import Product
    from app.models.variant import ProductVariant

    rows = db.execute(
        select(ProductVariant, InventoryItem, Product)
        .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.is_active.is_(True),
            Product.is_active.is_(True),
            InventoryItem.quantity <= InventoryItem.low_stock_threshold,
        )
    ).all()

    raised = {"low_stock": 0, "out_of_stock": 0}
    for variant, inventory, product in rows:
        out = inventory.quantity <= 0
        key = f"{'oos' if out else 'low'}:{variant.id}"
        created = notify(
            db,
            type=(
                AdminNotificationType.OUT_OF_STOCK
                if out
                else AdminNotificationType.LOW_STOCK
            ),
            severity=(
                AdminNotificationSeverity.CRITICAL
                if out
                else AdminNotificationSeverity.WARNING
            ),
            title=(
                f"Out of stock: {product.name} ({variant.label})"
                if out
                else f"Low stock: {product.name} ({variant.label})"
            ),
            body=(
                f"SKU {variant.sku} · {inventory.quantity} left "
                f"(threshold {inventory.low_stock_threshold})"
            ),
            link="/admin/inventory",
            dedupe_key=key,
            commit=False,
        )
        if created is not None and created.dedupe_key == key:
            raised["out_of_stock" if out else "low_stock"] += 1

    if commit:
        db.commit()
    return raised
