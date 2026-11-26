"""Delete all test orders after a verified database backup.

Run with the backend virtualenv from /var/www/backend. The script lists every
order and related stock impact, then requires an exact count confirmation.
Order-related inventory movements remain in the audit ledger; a balancing
adjustment restores the stock impact of the deleted test orders.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.coupon import Coupon
from app.models.enums import InventoryTransactionType
from app.models.inventory_transaction import InventoryTransaction, REFERENCE_ORDER
from app.models.order import Order
from app.services import inventory as inventory_service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True, help="Verified, non-empty PostgreSQL dump")
    args = parser.parse_args()
    backup = Path(args.backup)
    if not backup.is_file() or backup.stat().st_size == 0:
        parser.error("backup file is missing or empty; refusing to delete orders")

    with SessionLocal() as db:
        orders = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.created_at, Order.order_number)
            .with_for_update()
        ).all()
        if not orders:
            print("No orders found; nothing was deleted.")
            return 0

        order_ids = [order.id for order in orders]
        order_id_strings = [str(order_id) for order_id in order_ids]
        statuses = Counter((str(order.order_status), str(order.payment_status)) for order in orders)
        coupon_uses = Counter(order.coupon_code for order in orders if order.coupon_code)

        movement_rows = db.execute(
            select(
                InventoryTransaction.product_variant_id,
                func.coalesce(func.sum(InventoryTransaction.quantity_change), 0),
            )
            .where(
                InventoryTransaction.reference_type == REFERENCE_ORDER,
                InventoryTransaction.reference_id.in_(order_id_strings),
            )
            .group_by(InventoryTransaction.product_variant_id)
        ).all()
        net_by_variant = {variant_id: int(net) for variant_id, net in movement_rows}
        locked = inventory_service.lock_inventory_for_variants(db, list(net_by_variant))

        stock_changes: list[tuple[object, int, int, int]] = []
        for variant_id, net_change in net_by_variant.items():
            stock = locked.get(variant_id)
            if stock is None:
                parser.error(f"missing inventory row for variant {variant_id}; no orders deleted")
            reversal = -net_change
            if reversal == 0:
                continue
            after = stock.quantity + reversal
            if after < 0:
                parser.error(
                    f"stock reconciliation would make variant {variant_id} negative; "
                    "no orders deleted"
                )
            stock_changes.append((variant_id, stock.quantity, reversal, after))

        print(f"Verified backup: {backup} ({backup.stat().st_size} bytes)")
        print(f"Orders to delete: {len(orders)}")
        print("Order/payment status counts:")
        for (order_status, payment_status), count in sorted(statuses.items()):
            print(f"  {order_status} / {payment_status}: {count}")
        print("Order numbers:")
        for order in orders:
            print(f"  {order.order_number}")
        print("Inventory quantity reversals:")
        if stock_changes:
            for variant_id, before, change, after in stock_changes:
                print(f"  {variant_id}: {before} {change:+d} -> {after}")
        else:
            print("  none")

        required = f"DELETE ALL {len(orders)} ORDERS"
        if input(f"Type exactly '{required}' to proceed: ").strip() != required:
            print("Confirmation did not match; no orders were deleted.")
            return 1

        try:
            batch_id = datetime.now(UTC).strftime("test-order-reset-%Y%m%dT%H%M%SZ")
            for variant_id, _before, change, _after in stock_changes:
                stock = locked[variant_id]
                inventory_service.apply_movement(
                    db,
                    stock,
                    quantity_change=change,
                    transaction_type=InventoryTransactionType.ADJUSTMENT,
                    reference_type="MANUAL",
                    reference_id=batch_id,
                    note="Restored stock impact when clearing test order history",
                )

            for code, uses in coupon_uses.items():
                coupon = db.scalar(select(Coupon).where(Coupon.code == code).with_for_update())
                if coupon is not None:
                    coupon.redemption_count = max(0, coupon.redemption_count - uses)

            for order in orders:
                db.delete(order)
            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"Deleted all {len(orders)} orders and their linked order/payment/shipment/return records.")
    print("Restored the net stock impact and adjusted coupon redemption counts.")
    print("Order inventory audit entries were preserved with balancing adjustments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
