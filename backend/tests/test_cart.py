"""Cart behaviour: variant-level lines, stock validation, ownership."""

from decimal import Decimal

from app.models.enums import UserRole
from tests import factories
from tests.conftest import create_user, sign_in


def test_cart_requires_authentication(client, db):
    _, variant = factories.make_shop_setup(db, stock=5)

    assert client.get("/api/v1/cart").status_code == 401
    assert client.delete("/api/v1/cart").status_code == 401
    add = client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )
    assert add.status_code == 401


def test_empty_cart_is_returned_not_an_error(customer_client, db):
    response = customer_client.get("/api/v1/cart")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["item_count"] == 0
    assert Decimal(body["subtotal"]) == Decimal("0.00")


def test_add_variant_to_cart(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5, price=Decimal("4000.00"))

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 2}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["items"]) == 1
    line = body["items"][0]
    # The line identifies the variant, not just the product.
    assert line["product_variant_id"] == str(variant.id)
    assert line["waist"] == 32
    assert line["quantity"] == 2
    assert Decimal(line["unit_price"]) == Decimal("4000.00")
    assert Decimal(line["line_total"]) == Decimal("8000.00")
    assert Decimal(body["subtotal"]) == Decimal("8000.00")


def test_adding_the_same_variant_twice_increases_quantity(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=9)

    customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 2}
    )
    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 3}
    )

    body = response.json()
    # One line, not two.
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 5


def test_single_piece_item_cannot_be_added_twice(customer_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=(("M", None, 1),))
    product.single_piece = True
    db.commit()
    variant = product.variants[0]

    first = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )
    second = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 400
    assert "single-piece" in second.json()["detail"]


def test_different_variants_of_one_product_are_separate_lines(customer_client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 4), (None, 32, 4))
    )

    for variant in product.variants:
        customer_client.post(
            "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
        )

    body = customer_client.get("/api/v1/cart").json()
    assert len(body["items"]) == 2
    assert {line["waist"] for line in body["items"]} == {30, 32}


def test_cart_uses_the_sale_price(customer_client, db):
    _, variant = factories.make_shop_setup(
        db, price=Decimal("5000.00"), sale_price=Decimal("3500.00")
    )

    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()

    assert Decimal(body["items"][0]["unit_price"]) == Decimal("3500.00")


def test_cannot_add_more_than_available_stock(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=3)

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 4}
    )

    assert response.status_code == 400
    assert "Only 3 left" in response.json()["detail"]


def test_repeated_adds_cannot_exceed_stock_in_total(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=3)
    customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 2}
    )

    # 2 already in the bag plus 2 more exceeds the 3 available.
    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 2}
    )

    assert response.status_code == 400


def test_cannot_add_an_out_of_stock_variant(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=0)

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )

    assert response.status_code == 400
    assert "out of stock" in response.json()["detail"].lower()


def test_cannot_add_an_inactive_variant(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5)
    variant.is_active = False
    db.commit()

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )

    assert response.status_code == 400
    assert "no longer available" in response.json()["detail"]


def test_cannot_add_a_variant_of_an_inactive_product(customer_client, db):
    product, variant = factories.make_shop_setup(db, stock=5)
    product.is_active = False
    db.commit()

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )

    assert response.status_code == 400


def test_cannot_add_an_unknown_variant(customer_client, db):
    import uuid

    response = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(uuid.uuid4()), "quantity": 1}
    )

    assert response.status_code == 404


def test_quantity_must_be_positive(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5)

    for bad in (0, -1):
        response = customer_client.post(
            "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": bad}
        )
        assert response.status_code == 422


def test_update_line_quantity(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=6)
    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()
    item_id = body["items"][0]["id"]

    response = customer_client.put(f"/api/v1/cart/items/{item_id}", json={"quantity": 4})

    assert response.status_code == 200
    assert response.json()["items"][0]["quantity"] == 4


def test_update_beyond_stock_is_rejected(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=2)
    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()
    item_id = body["items"][0]["id"]

    response = customer_client.put(f"/api/v1/cart/items/{item_id}", json={"quantity": 9})

    assert response.status_code == 400


def test_remove_line(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5)
    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()
    item_id = body["items"][0]["id"]

    response = customer_client.delete(f"/api/v1/cart/items/{item_id}")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_clear_cart(customer_client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 4), (None, 32, 4))
    )
    for variant in product.variants:
        customer_client.post(
            "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
        )

    response = customer_client.delete("/api/v1/cart")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["item_count"] == 0


def test_one_customer_cannot_touch_another_customers_cart_item(client, db):
    _, variant = factories.make_shop_setup(db, stock=5)

    owner, owner_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, owner.email, owner_password)
    item_id = client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()["items"][0]["id"]

    # Switch to a different signed-in customer.
    client.cookies.clear()
    intruder, intruder_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, intruder.email, intruder_password)

    assert client.put(f"/api/v1/cart/items/{item_id}", json={"quantity": 5}).status_code == 404
    assert client.delete(f"/api/v1/cart/items/{item_id}").status_code == 404


def test_cart_flags_a_line_that_went_out_of_stock_after_being_added(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5)
    customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 3}
    )

    variant.inventory.quantity = 1
    db.commit()

    body = customer_client.get("/api/v1/cart").json()
    line = body["items"][0]
    assert line["is_available"] is False
    assert "Only 1 left" in line["unavailable_reason"]
    assert body["has_unavailable_items"] is True
    # An unavailable line is excluded from the payable subtotal.
    assert Decimal(body["subtotal"]) == Decimal("0.00")


def test_cart_reprices_when_the_catalogue_price_changes(customer_client, db):
    product, variant = factories.make_shop_setup(db, price=Decimal("5000.00"))
    customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    )

    product.sale_price = Decimal("2500.00")
    db.commit()

    body = customer_client.get("/api/v1/cart").json()
    # Recomputed from the catalogue, not read back from the stored cart price.
    assert Decimal(body["items"][0]["unit_price"]) == Decimal("2500.00")
    assert Decimal(body["subtotal"]) == Decimal("2500.00")


def test_cart_includes_delivery_preview(customer_client, db):
    _, variant = factories.make_shop_setup(db, price=Decimal("4000.00"))

    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 1}
    ).json()

    # The seeded free delivery threshold is PKR 4,000.
    assert Decimal(body["delivery_amount"]) == Decimal("0.00")
    assert Decimal(body["total"]) == Decimal("4000.00")
    assert body["currency"] == "PKR"


def test_delivery_is_free_above_the_configured_threshold(customer_client, db):
    _, variant = factories.make_shop_setup(db, stock=5, price=Decimal("6000.00"))

    body = customer_client.post(
        "/api/v1/cart/items", json={"product_variant_id": str(variant.id), "quantity": 2}
    ).json()

    assert Decimal(body["subtotal"]) == Decimal("12000.00")
    assert Decimal(body["delivery_amount"]) == Decimal("0.00")
    assert Decimal(body["total"]) == Decimal("12000.00")
