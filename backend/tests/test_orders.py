"""Order history, ownership, admin management, status transitions, cancellation."""

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models.enums import (
    InventoryTransactionType,
    OrderStatus,
    PaymentStatus,
    UserRole,
)
from app.models.inventory_transaction import InventoryTransaction
from tests import factories
from tests.conftest import create_user, sign_in


def place_order(client, db, user, *, stock=5, quantity=1, price=Decimal("4000.00")):
    """Put an item in the user's bag and check out, returning the order body."""
    _, variant = factories.make_shop_setup(db, stock=stock, price=price)
    factories.seed_cart(db, user.id, variant.id, quantity)
    address = factories.make_address(db, user.id)
    response = client.post("/api/v1/checkout", json=factories.checkout_payload(address.id))
    assert response.status_code == 201, response.text
    return response.json(), variant


# ------------------------------------------------------- customer visibility
def test_customer_sees_their_own_orders(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    listing = customer_client.get("/api/v1/customer/orders").json()

    assert listing["total"] == 1
    assert listing["items"][0]["order_number"] == order["order_number"]


def test_order_list_requires_authentication(client, db):
    assert client.get("/api/v1/customer/orders").status_code == 401


def test_customer_cannot_see_another_customers_order(client, db):
    stranger, stranger_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, stranger.email, stranger_password)
    stranger_order, _ = place_order(client, db, stranger)

    client.cookies.clear()
    intruder, intruder_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, intruder.email, intruder_password)

    response = client.get(f"/api/v1/customer/orders/{stranger_order['order_number']}")

    # 404 rather than 403, so order numbers cannot be probed for existence.
    assert response.status_code == 404
    assert client.get("/api/v1/customer/orders").json()["total"] == 0


def test_customer_order_detail_hides_the_internal_note(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    body = customer_client.get(f"/api/v1/customer/orders/{order['order_number']}").json()

    assert "internal_note" not in body


def test_order_detail_includes_a_status_timeline(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    body = customer_client.get(f"/api/v1/customer/orders/{order['order_number']}").json()

    assert len(body["status_events"]) == 1
    assert body["status_events"][0]["status"] == OrderStatus.PENDING


# ------------------------------------------------------------ admin access
def test_customer_cannot_reach_admin_orders(customer_client, db):
    assert customer_client.get("/api/v1/admin/orders").status_code == 403


def test_anonymous_cannot_reach_admin_orders(client, db):
    assert client.get("/api/v1/admin/orders").status_code == 401


def test_admin_sees_all_orders(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    listing = client.get("/api/v1/admin/orders").json()

    assert listing["total"] == 1
    row = listing["items"][0]
    assert row["order_number"] == order["order_number"]
    assert row["customer"]["email"] == buyer.email


def test_staff_can_see_orders(client, db, staff_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    place_order(client, db, buyer)

    client.cookies.clear()
    staff, staff_password = staff_credentials
    sign_in(client, staff.email, staff_password)

    assert client.get("/api/v1/admin/orders").status_code == 200


def test_admin_can_filter_orders(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    assert client.get("/api/v1/admin/orders?status=PENDING").json()["total"] == 1
    assert client.get("/api/v1/admin/orders?status=DELIVERED").json()["total"] == 0
    assert client.get("/api/v1/admin/orders?payment_status=PENDING").json()["total"] == 1
    assert (
        client.get(f"/api/v1/admin/orders?order_number={order['order_number']}").json()["total"]
        == 1
    )
    assert client.get(f"/api/v1/admin/orders?customer={buyer.email}").json()["total"] == 1
    assert client.get("/api/v1/admin/orders?customer=nobody@example.com").json()["total"] == 0


def test_admin_order_detail_includes_customer_and_internal_note(
    client, db, admin_credentials
):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    body = client.get(f"/api/v1/admin/orders/{order['id']}").json()

    assert body["customer"]["email"] == buyer.email
    assert "internal_note" in body


def test_admin_can_set_an_internal_note(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/note",
        json={"internal_note": "Customer asked to deliver after 6pm"},
    )

    assert response.status_code == 200
    assert response.json()["internal_note"] == "Customer asked to deliver after 6pm"


# ------------------------------------------------------- status transitions
def _as_admin(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, variant = place_order(client, db, buyer)
    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)
    return order, variant


def test_admin_can_advance_status_through_the_happy_path(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    for status in ("PROCESSING", "PACKED", "DISPATCHED", "DELIVERED"):
        response = client.put(
            f"/api/v1/admin/orders/{order['id']}/status", json={"status": status}
        )
        assert response.status_code == 200, response.text
        assert response.json()["order_status"] == status


def test_illegal_status_transition_is_rejected(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    # PENDING cannot jump straight to DELIVERED.
    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/status", json={"status": "DELIVERED"}
    )

    assert response.status_code == 400
    assert "Cannot move an order from" in response.json()["detail"]


def test_setting_the_same_status_is_rejected(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/status", json={"status": "PENDING"}
    )

    assert response.status_code == 400
    assert "already" in response.json()["detail"]


def test_status_changes_append_to_the_timeline(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    client.put(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "PROCESSING", "note": "Picking started"},
    )
    body = client.get(f"/api/v1/admin/orders/{order['id']}").json()

    statuses = [event["status"] for event in body["status_events"]]
    assert statuses == [OrderStatus.PENDING, OrderStatus.PROCESSING]
    assert body["status_events"][1]["note"] == "Picking started"


def test_delivered_order_cannot_move_back(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)
    for status in ("PROCESSING", "PACKED", "DISPATCHED", "DELIVERED"):
        client.put(f"/api/v1/admin/orders/{order['id']}/status", json={"status": status})

    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/status", json={"status": "PROCESSING"}
    )

    assert response.status_code == 400


# --------------------------------------------------------- payment statuses
def test_admin_can_mark_payment_paid(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/payment-status",
        json={"payment_status": "PAID", "note": "Cash collected on delivery"},
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == PaymentStatus.PAID


def test_customer_cannot_change_payment_status(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    response = customer_client.put(
        f"/api/v1/admin/orders/{order['id']}/payment-status", json={"payment_status": "PAID"}
    )

    assert response.status_code == 403


# ------------------------------------------------------------- cancellation
def test_customer_can_cancel_a_pending_order_and_stock_is_restored(
    customer_client, db, customer_user
):
    order, variant = place_order(customer_client, db, customer_user, stock=5, quantity=2)
    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 3

    response = customer_client.post(
        f"/api/v1/customer/orders/{order['order_number']}/cancel",
        json={"reason": "Ordered the wrong size"},
    )

    assert response.status_code == 200
    assert response.json()["order_status"] == OrderStatus.CANCELLED
    assert response.json()["cancelled_at"] is not None

    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 5


def test_cancellation_records_an_inventory_transaction(customer_client, db, customer_user):
    order, variant = place_order(customer_client, db, customer_user, stock=4, quantity=1)

    customer_client.post(f"/api/v1/customer/orders/{order['order_number']}/cancel")

    movements = (
        db.execute(
            select(InventoryTransaction)
            .where(InventoryTransaction.product_variant_id == variant.id)
            .order_by(InventoryTransaction.created_at)
        )
        .scalars()
        .all()
    )
    assert [m.type for m in movements] == [
        InventoryTransactionType.SALE,
        InventoryTransactionType.CANCELLED_ORDER,
    ]
    restore = movements[1]
    assert restore.quantity_change == 1
    assert restore.quantity_before == 3
    assert restore.quantity_after == 4


def test_cancelling_twice_is_rejected(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)
    customer_client.post(f"/api/v1/customer/orders/{order['order_number']}/cancel")

    response = customer_client.post(f"/api/v1/customer/orders/{order['order_number']}/cancel")

    assert response.status_code == 400


def test_customer_cannot_cancel_after_dispatch(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)
    for status in ("PROCESSING", "PACKED", "DISPATCHED"):
        client.put(f"/api/v1/admin/orders/{order['id']}/status", json={"status": status})

    client.cookies.clear()
    sign_in(client, buyer.email, buyer_password)
    response = client.post(f"/api/v1/customer/orders/{order['order_number']}/cancel")

    assert response.status_code == 400
    assert "can no longer be cancelled" in response.json()["detail"]


def test_customer_cannot_cancel_another_customers_order(client, db):
    owner, owner_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, owner.email, owner_password)
    order, variant = place_order(client, db, owner)

    client.cookies.clear()
    intruder, intruder_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, intruder.email, intruder_password)

    response = client.post(f"/api/v1/customer/orders/{order['order_number']}/cancel")

    assert response.status_code == 404
    db.refresh(variant.inventory)
    # Stock untouched by the failed attempt.
    assert variant.inventory.quantity == 4


def test_admin_cancellation_restores_stock(client, db, admin_credentials):
    order, variant = _as_admin(client, db, admin_credentials)

    response = client.put(
        f"/api/v1/admin/orders/{order['id']}/status",
        json={"status": "CANCELLED", "note": "Customer phoned to cancel"},
    )

    assert response.status_code == 200
    assert response.json()["order_status"] == OrderStatus.CANCELLED
    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 5


def test_cancelled_order_keeps_its_items_and_snapshots(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    body = customer_client.post(
        f"/api/v1/customer/orders/{order['order_number']}/cancel"
    ).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["product_name_snapshot"]
    assert Decimal(body["total_amount"]) == Decimal(order["total_amount"])


# ----------------------------------------------------------------- inventory
def test_admin_can_see_the_inventory_impact_of_an_order(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    rows = client.get(f"/api/v1/admin/orders/{order['id']}/inventory").json()

    assert len(rows) == 1
    assert rows[0]["quantity_change"] == -1
    assert rows[0]["type"] == "SALE"


def test_order_stats(client, db, admin_credentials):
    order, _ = _as_admin(client, db, admin_credentials)

    stats = client.get("/api/v1/admin/orders/stats").json()

    assert stats["total_orders"] == 1
    assert stats["status_counts"]["PENDING"] == 1
    assert stats["revenue_total"] > 0


def test_unknown_admin_order_id_is_404(client, db, admin_credentials):
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    assert client.get(f"/api/v1/admin/orders/{uuid.uuid4()}").status_code == 404
