"""Safely remove unpaid pending/cancelled orders after a verified DB backup.

Run from /var/www/backend with the production virtualenv and pass the path to a
non-empty pg_dump backup. Eligible orders are deleted through the application
service so pending reservations are restored and inventory movements recorded.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.enums import OrderStatus, PaymentStatus
from app.models.order import Order
from app.services.orders import delete_unpaid_order


SAFE_ORDER_STATUSES = {OrderStatus.PENDING, OrderStatus.CANCELLED}
SAFE_PAYMENT_STATUSES = {
    PaymentStatus.PENDING,
    PaymentStatus.FAILED,
    PaymentStatus.CANCELLED,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True, help="Path to a verified, non-empty pg_dump file")
    args = parser.parse_args()
    backup = Path(args.backup)
    if not backup.is_file() or backup.stat().st_size == 0:
        parser.error("backup file is missing or empty; refusing to delete any orders")

    with SessionLocal() as db:
        candidates = db.scalars(
            select(Order)
            .options(selectinload(Order.payments))
            .where(
                Order.order_status.in_(SAFE_ORDER_STATUSES),
                Order.payment_status.in_(SAFE_PAYMENT_STATUSES),
            )
            .order_by(Order.created_at, Order.order_number)
        ).all()

        # Do not trust only the denormalized order payment status. Keep any order
        # that has a processing/paid/refunded payment attempt attached to it.
        eligible = [
            order
            for order in candidates
            if all(payment.status in SAFE_PAYMENT_STATUSES for payment in order.payments)
        ]
        protected_count = len(candidates) - len(eligible)
        order_ids = [order.id for order in eligible]
        print(f"Verified backup: {backup} ({backup.stat().st_size} bytes)")
        print(f"Eligible unpaid pending/cancelled orders: {len(eligible)}")
        print(f"Protected because a linked payment is processing/paid/refunded: {protected_count}")
        for order in eligible[:100]:
            print(f"  {order.order_number} | {order.order_status} | {order.payment_status}")
        if len(eligible) > 100:
            print(f"  ... and {len(eligible) - 100} more")

    if not order_ids:
        print("No eligible orders found; nothing was deleted.")
        return 0

    required = f"DELETE {len(order_ids)} UNPAID ORDERS"
    if input(f"Type exactly '{required}' to proceed: ").strip() != required:
        print("Confirmation did not match; no orders were deleted.")
        return 1

    deleted = 0
    for order_id in order_ids:
        with SessionLocal() as db:
            delete_unpaid_order(db, order_id)
        deleted += 1
        print(f"Deleted {deleted}/{len(order_ids)}")

    print(f"Deleted {deleted} unpaid orders. Pending reserved stock was restored by the service.")
    print("Paid/processing/refunded and fulfilment-stage orders were left untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
