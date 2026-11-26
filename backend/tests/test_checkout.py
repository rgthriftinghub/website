"""Checkout: atomic order creation, price recalculation, stock deduction, rollback."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import (
    InventoryTransactionType,
    OrderStatus,
    PaymentStatus,
    UserRole,
)
from app.models.inventory_transaction import InventoryTransaction
from app.models.order import Order, OrderItem
from tests import factories
from tests.conftest import create_user, sign_in


def _prepare(db, user_id, *, stock=5, quantity=1, price=Decimal("4000.00"), sale_price=None):
    product, variant = factories.make_shop_setup(
        db, stock=stock, price=price, sale_price=sale_price
    )
    factories.seed_cart(db, user_id, variant.id, quantity)
    address = factories.make_address(db, user_id)
    return product, variant, address


# ------------------------------------------------------------------- config
def test_checkout_config_is_public_and_exposes_delivery_pricing(client, db):
    response = client.get("/api/v1/checkout/config")

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["standard_delivery_charge"]) == Decimal("250.00")
    assert body["currency"] == "PKR"
    # Only the methods this phase supports are offered.
    assert sorted(body["payment_methods"]) == ["BANK_TRANSFER", "COD"]
    assert body["delivery_methods"] == ["STANDARD"]


# ------------------------------------------------------------------ success
def test_cod_order_is_created(customer_client, db, customer_user):
    _, variant, address = _prepare(db, customer_user.id, quantity=2, price=Decimal("3000.00"))

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_status"] == OrderStatus.PENDING
    assert body["payment_method"] == "COD"
    # Cash has not been collected yet, so nothing is marked paid.
    assert body["payment_status"] == PaymentStatus.PENDING
    assert Decimal(body["subtotal"]) == Decimal("6000.00")
    assert Decimal(body["shipping_amount"]) == Decimal("0.00")
    assert Decimal(body["total_amount"]) == Decimal("6000.00")
    assert body["item_count"] == 2


def test_bank_transfer_order_is_created_and_starts_unpaid(customer_client, db, customer_user):
    _, _, address = _prepare(db, customer_user.id)

    body = customer_client.post(
        "/api/v1/checkout",
        json=factories.checkout_payload(address.id, payment_method="BANK_TRANSFER"),
    ).json()

    assert body["payment_method"] == "BANK_TRANSFER"
    # A transfer needs human reconciliation before it counts as paid.
    assert body["payment_status"] == PaymentStatus.PENDING


def test_order_number_is_human_friendly_and_unique(customer_client, db, customer_user):
    address = factories.make_address(db, customer_user.id)
    numbers = []

    for _ in range(3):
        _, variant = factories.make_shop_setup(db, stock=3)
        factories.seed_cart(db, customer_user.id, variant.id, 1)
        body = customer_client.post(
            "/api/v1/checkout", json=factories.checkout_payload(address.id)
        ).json()
        numbers.append(body["order_number"])

    assert len(set(numbers)) == 3
    for number in numbers:
        assert number.startswith("RG-")
        prefix, stamp, suffix = number.split("-")
        assert len(stamp) == 8 and stamp.isdigit()
        assert len(suffix) == 4 and suffix.isdigit()
    # Sequential within the day.
    assert sorted(numbers) == numbers


def test_order_stores_an_address_snapshot_that_survives_later_edits(
    customer_client, db, customer_user
):
    _, _, address = _prepare(db, customer_user.id)
    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()
    order_number = body["order_number"]
    assert body["shipping_address_snapshot"]["city"] == "Lahore"

    address.city = "Islamabad"
    address.address_line_1 = "Completely different street"
    db.commit()

    refetched = customer_client.get(f"/api/v1/customer/orders/{order_number}").json()
    # History is unchanged by the edit.
    assert refetched["shipping_address_snapshot"]["city"] == "Lahore"
    assert refetched["shipping_address_snapshot"]["address_line_1"] == "House 14, Street 7"


def test_order_items_snapshot_product_details(customer_client, db, customer_user):
    product, _, address = _prepare(db, customer_user.id, price=Decimal("4000.00"))
    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()
    order_number = body["order_number"]
    original_name = product.name

    product.name = "Renamed After Purchase"
    product.regular_price = Decimal("99999.00")
    db.commit()

    refetched = customer_client.get(f"/api/v1/customer/orders/{order_number}").json()
    item = refetched["items"][0]
    assert item["product_name_snapshot"] == original_name
    assert Decimal(item["unit_price"]) == Decimal("4000.00")
    assert Decimal(refetched["total_amount"]) == Decimal("4000.00")


def test_variant_snapshot_records_the_size_bought(customer_client, db, customer_user):
    _, _, address = _prepare(db, customer_user.id)

    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()

    snapshot = body["items"][0]["variant_snapshot"]
    assert snapshot["waist"] == 32
    assert body["items"][0]["variant_label"] == "Waist 32"


def test_price_is_recalculated_from_the_catalogue_not_the_cart(
    customer_client, db, customer_user
):
    """A stale cart price must not carry into the order."""
    product, variant, address = _prepare(db, customer_user.id, price=Decimal("5000.00"))

    # Simulate the catalogue changing after the item was added.
    product.sale_price = Decimal("2000.00")
    db.commit()

    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()

    assert Decimal(body["items"][0]["unit_price"]) == Decimal("2000.00")
    assert Decimal(body["subtotal"]) == Decimal("2000.00")


def test_checkout_empties_the_cart(customer_client, db, customer_user):
    _, _, address = _prepare(db, customer_user.id)

    customer_client.post("/api/v1/checkout", json=factories.checkout_payload(address.id))

    assert customer_client.get("/api/v1/cart").json()["items"] == []


def test_free_delivery_threshold_applies_at_checkout(customer_client, db, customer_user):
    _, _, address = _prepare(db, customer_user.id, quantity=2, price=Decimal("6000.00"), stock=4)

    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()

    assert Decimal(body["subtotal"]) == Decimal("12000.00")
    assert Decimal(body["shipping_amount"]) == Decimal("0.00")
    assert Decimal(body["total_amount"]) == Decimal("12000.00")


# ------------------------------------------------------------------ failures
def test_checkout_requires_authentication(client, db):
    assert client.post(
        "/api/v1/checkout", json=factories.checkout_payload(uuid.uuid4())
    ).status_code == 401


def test_checkout_with_an_empty_cart_is_rejected(customer_client, db, customer_user):
    address = factories.make_address(db, customer_user.id)

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_checkout_with_an_unknown_address_is_rejected(customer_client, db, customer_user):
    _, variant = factories.make_shop_setup(db, stock=5)
    factories.seed_cart(db, customer_user.id, variant.id, 1)

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(uuid.uuid4())
    )

    assert response.status_code == 404


def test_cannot_check_out_to_another_customers_address(client, db):
    _, variant = factories.make_shop_setup(db, stock=5)
    stranger, _ = create_user(db, UserRole.CUSTOMER)
    stranger_address = factories.make_address(db, stranger.id, city="Multan")

    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    factories.seed_cart(db, buyer.id, variant.id, 1)

    response = client.post(
        "/api/v1/checkout", json=factories.checkout_payload(stranger_address.id)
    )

    assert response.status_code == 404


def test_unavailable_payment_method_is_rejected(customer_client, db, customer_user):
    _, _, address = _prepare(db, customer_user.id)

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id, payment_method="JAZZCASH")
    )

    assert response.status_code == 422
    assert "not available yet" in response.text


def test_checkout_fails_when_stock_dropped_below_the_cart_quantity(
    customer_client, db, customer_user
):
    _, variant, address = _prepare(db, customer_user.id, stock=5, quantity=3)

    variant.inventory.quantity = 1
    db.commit()

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    )

    assert response.status_code == 400
    assert "Only 1 left" in response.json()["detail"]


def test_checkout_fails_when_the_product_was_deactivated(customer_client, db, customer_user):
    product, _, address = _prepare(db, customer_user.id)
    product.is_active = False
    db.commit()

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    )

    assert response.status_code == 400
    assert "no longer available" in response.json()["detail"]


def test_a_failed_checkout_creates_nothing_and_keeps_the_cart(
    customer_client, db, customer_user
):
    """The whole transaction rolls back: no order, no stock change, bag intact."""
    _, variant, address = _prepare(db, customer_user.id, stock=5, quantity=3)
    variant.inventory.quantity = 1
    db.commit()

    orders_before = db.execute(select(func.count()).select_from(Order)).scalar_one()
    movements_before = db.execute(
        select(func.count()).select_from(InventoryTransaction)
    ).scalar_one()

    response = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    )
    assert response.status_code == 400

    assert db.execute(select(func.count()).select_from(Order)).scalar_one() == orders_before
    assert (
        db.execute(select(func.count()).select_from(OrderItem)).scalar_one() == 0
    )
    assert (
        db.execute(select(func.count()).select_from(InventoryTransaction)).scalar_one()
        == movements_before
    )
    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 1
    # The bag survives so the customer can fix the quantity and retry.
    assert len(customer_client.get("/api/v1/cart").json()["items"]) == 1


# ----------------------------------------------------------------- inventory
def test_stock_is_deducted_and_recorded(customer_client, db, customer_user):
    _, variant, address = _prepare(db, customer_user.id, stock=10, quantity=3)

    customer_client.post("/api/v1/checkout", json=factories.checkout_payload(address.id))

    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 7

    movement = db.execute(
        select(InventoryTransaction).where(
            InventoryTransaction.product_variant_id == variant.id
        )
    ).scalar_one()
    assert movement.type is InventoryTransactionType.SALE
    assert movement.quantity_change == -3
    assert movement.quantity_before == 10
    assert movement.quantity_after == 7
    assert movement.reference_type == "ORDER"


def test_buying_the_last_unit_leaves_the_variant_out_of_stock(
    customer_client, db, customer_user
):
    product, variant, address = _prepare(db, customer_user.id, stock=1, quantity=1)

    customer_client.post("/api/v1/checkout", json=factories.checkout_payload(address.id))

    db.refresh(variant.inventory)
    assert variant.inventory.quantity == 0

    detail = customer_client.get(f"/api/v1/products/{product.slug}").json()
    assert detail["variants"][0]["in_stock"] is False
    # The product itself stays listed; only that size is unavailable.
    assert detail["is_active"] is True


def test_single_piece_cannot_be_purchased_again_after_checkout(customer_client, db, customer_user):
    product, variant, address = _prepare(db, customer_user.id, stock=1, quantity=1)
    product.single_piece = True
    db.commit()
    placed = customer_client.post("/api/v1/checkout", json=factories.checkout_payload(address.id))
    assert placed.status_code == 201, placed.text
    second = customer_client.post("/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1})
    assert second.status_code == 400
    assert customer_client.get(f"/api/v1/products/{product.slug}").json()["in_stock"] is False


def test_multi_item_checkout_deducts_every_line(customer_client, db, customer_user):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 5), (None, 32, 5))
    )
    for variant in product.variants:
        factories.seed_cart(db, customer_user.id, variant.id, 2)
    address = factories.make_address(db, customer_user.id)

    body = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()

    assert len(body["items"]) == 2
    for variant in product.variants:
        db.refresh(variant.inventory)
        assert variant.inventory.quantity == 3

    movements = db.execute(select(func.count()).select_from(InventoryTransaction)).scalar_one()
    assert movements == 2
