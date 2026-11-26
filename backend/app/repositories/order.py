"""Admin order querying.

All filtering happens in SQL so an admin listing never loads the whole order
table into memory to narrow it down.
"""

from datetime import date, datetime, time

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import OrderStatus, PaymentStatus
from app.models.order import Order
from app.models.user import User
from app.services.orders import order_loads


def _apply_filters(
    stmt: Select,
    *,
    status: OrderStatus | None,
    payment_status: PaymentStatus | None,
    date_from: date | None,
    date_to: date | None,
    customer: str | None,
    order_number: str | None,
) -> Select:
    if status is not None:
        stmt = stmt.where(Order.order_status == status)
    if payment_status is not None:
        stmt = stmt.where(Order.payment_status == payment_status)
    if date_from is not None:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        # Inclusive of the whole end day.
        stmt = stmt.where(Order.created_at <= datetime.combine(date_to, time.max))
    if order_number:
        stmt = stmt.where(func.lower(Order.order_number).like(f"%{order_number.strip().lower()}%"))
    if customer:
        term = f"%{customer.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Order.user_id.in_(
                    select(User.id).where(
                        or_(
                            func.lower(User.email).like(term),
                            func.lower(User.first_name).like(term),
                            func.lower(User.last_name).like(term),
                            func.lower(User.first_name + " " + User.last_name).like(term),
                        )
                    )
                ),
                func.lower(Order.contact_email).like(term),
                func.lower(Order.contact_phone).like(term),
                func.lower(Order.shipping_address_snapshot["full_name"].as_string()).like(term),
            )
        )
    return stmt


def list_orders(
    db: Session,
    *,
    status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    customer: str | None = None,
    order_number: str | None = None,
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[Order], int]:
    filters = {
        "status": status,
        "payment_status": payment_status,
        "date_from": date_from,
        "date_to": date_to,
        "customer": customer,
        "order_number": order_number,
    }
    total = db.execute(
        _apply_filters(select(func.count()).select_from(Order), **filters)
    ).scalar_one()
    if total == 0:
        return [], 0

    rows = (
        db.execute(
            _apply_filters(select(Order), **filters)
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


def status_counts(db: Session) -> dict[str, int]:
    """Order count per status, for the admin dashboard."""
    rows = db.execute(
        select(Order.order_status, func.count()).group_by(Order.order_status)
    ).all()
    return {str(status): count for status, count in rows}


def revenue_total(db: Session) -> float:
    """Total value of orders that are not cancelled."""
    value = db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.order_status != OrderStatus.CANCELLED
        )
    ).scalar_one()
    return float(value)
