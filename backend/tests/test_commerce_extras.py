"""Addresses, wishlist, return requests, and invoices."""

import uuid

from app.models.enums import ReturnRequestStatus, UserRole
from tests import factories
from tests.conftest import create_user, sign_in
from tests.test_orders import place_order


# --------------------------------------------------------------- addresses
def test_addresses_require_authentication(client, db):
    assert client.get("/api/v1/customer/addresses").status_code == 401
    assert client.post("/api/v1/customer/addresses", json=factories.address_payload()).status_code == 401


def test_create_and_list_addresses(customer_client, db):
    response = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload()
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["city"] == "Karachi"
    # The first saved address becomes the default automatically.
    assert created["is_default"] is True

    listing = customer_client.get("/api/v1/customer/addresses").json()
    assert len(listing) == 1


def test_only_one_address_can_be_default(customer_client, db):
    first = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload(city="Karachi")
    ).json()
    second = customer_client.post(
        "/api/v1/customer/addresses",
        json=factories.address_payload(city="Lahore", is_default=True),
    ).json()

    listing = customer_client.get("/api/v1/customer/addresses").json()
    defaults = [row for row in listing if row["is_default"]]

    assert len(defaults) == 1
    assert defaults[0]["id"] == second["id"]
    assert first["id"] != second["id"]


def test_update_address(customer_client, db):
    created = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload()
    ).json()

    response = customer_client.put(
        f"/api/v1/customer/addresses/{created['id']}", json={"city": "Faisalabad"}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "Faisalabad"


def test_delete_address(customer_client, db):
    created = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload()
    ).json()

    assert customer_client.delete(f"/api/v1/customer/addresses/{created['id']}").status_code == 204
    assert customer_client.get("/api/v1/customer/addresses").json() == []


def test_deleting_the_default_promotes_another(customer_client, db):
    first = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload(city="Karachi")
    ).json()
    customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload(city="Lahore")
    )

    customer_client.delete(f"/api/v1/customer/addresses/{first['id']}")

    listing = customer_client.get("/api/v1/customer/addresses").json()
    assert len(listing) == 1
    assert listing[0]["is_default"] is True


def test_cannot_read_or_edit_another_customers_address(client, db):
    owner, owner_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, owner.email, owner_password)
    address = client.post(
        "/api/v1/customer/addresses", json=factories.address_payload()
    ).json()

    client.cookies.clear()
    intruder, intruder_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, intruder.email, intruder_password)

    assert client.get(f"/api/v1/customer/addresses/{address['id']}").status_code == 404
    assert (
        client.put(
            f"/api/v1/customer/addresses/{address['id']}", json={"city": "Hacked"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/customer/addresses/{address['id']}").status_code == 404


def test_blank_required_address_field_is_rejected(customer_client, db):
    response = customer_client.post(
        "/api/v1/customer/addresses", json=factories.address_payload(city="   ")
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- wishlist
def test_wishlist_requires_authentication(client, db):
    assert client.get("/api/v1/wishlist").status_code == 401


def test_add_and_list_wishlist(customer_client, db):
    product, _ = factories.make_shop_setup(db)

    response = customer_client.post(f"/api/v1/wishlist/{product.id}")

    assert response.status_code == 201
    body = customer_client.get("/api/v1/wishlist").json()
    assert body["total"] == 1
    # The full listing shape, so the page can reuse the product card.
    assert body["items"][0]["product"]["slug"] == product.slug


def test_adding_twice_is_idempotent(customer_client, db):
    product, _ = factories.make_shop_setup(db)

    customer_client.post(f"/api/v1/wishlist/{product.id}")
    second = customer_client.post(f"/api/v1/wishlist/{product.id}")

    assert second.status_code == 201
    assert customer_client.get("/api/v1/wishlist").json()["total"] == 1


def test_wishlist_ids_endpoint(customer_client, db):
    product, _ = factories.make_shop_setup(db)
    customer_client.post(f"/api/v1/wishlist/{product.id}")

    ids = customer_client.get("/api/v1/wishlist/ids").json()

    assert ids == [str(product.id)]


def test_remove_from_wishlist(customer_client, db):
    product, _ = factories.make_shop_setup(db)
    customer_client.post(f"/api/v1/wishlist/{product.id}")

    assert customer_client.delete(f"/api/v1/wishlist/{product.id}").status_code == 200
    assert customer_client.get("/api/v1/wishlist").json()["total"] == 0


def test_removing_something_not_saved_is_404(customer_client, db):
    product, _ = factories.make_shop_setup(db)
    assert customer_client.delete(f"/api/v1/wishlist/{product.id}").status_code == 404


def test_cannot_wishlist_an_unknown_product(customer_client, db):
    assert customer_client.post(f"/api/v1/wishlist/{uuid.uuid4()}").status_code == 404


def test_wishlists_are_per_customer(client, db):
    product, _ = factories.make_shop_setup(db)

    owner, owner_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, owner.email, owner_password)
    client.post(f"/api/v1/wishlist/{product.id}")

    client.cookies.clear()
    other, other_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, other.email, other_password)

    assert client.get("/api/v1/wishlist").json()["total"] == 0


# --------------------------------------------------------- return requests
def _deliver(client, db, admin_credentials, buyer, buyer_password):
    order, variant = place_order(client, db, buyer)
    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)
    for status in ("PROCESSING", "PACKED", "DISPATCHED", "DELIVERED"):
        client.put(f"/api/v1/admin/orders/{order['id']}/status", json={"status": status})
    client.cookies.clear()
    sign_in(client, buyer.email, buyer_password)
    return order, variant


def test_return_request_requires_a_delivered_order(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    response = customer_client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    )

    assert response.status_code == 400
    assert "delivered" in response.json()["detail"]


def test_customer_can_request_a_return_on_a_delivered_order(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)

    response = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit", "description": "Too tight at the waist"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == ReturnRequestStatus.REQUESTED
    assert response.json()["type"] == "RETURN"


def test_exchange_request_is_supported(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)

    response = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "EXCHANGE", "reason": "Wrong size ordered"},
    )

    assert response.status_code == 201
    assert response.json()["type"] == "EXCHANGE"


def test_only_one_open_request_per_order(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)
    client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    )

    second = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Changed my mind"},
    )

    assert second.status_code == 409


def test_return_request_appears_on_the_order(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)
    client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    )

    body = client.get(f"/api/v1/customer/orders/{order['order_number']}").json()

    assert len(body["return_requests"]) == 1


def test_admin_can_list_and_decide_requests(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)
    request_id = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    ).json()["id"]

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    listing = client.get("/api/v1/admin/orders/returns").json()
    assert listing["total"] == 1
    assert listing["items"][0]["order_number"] == order["order_number"]

    decision = client.put(
        f"/api/v1/admin/orders/returns/{request_id}",
        json={"status": "APPROVED", "resolution_note": "Approved, collect on next run"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == ReturnRequestStatus.APPROVED


def test_completing_a_return_moves_the_order_to_returned(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)
    request_id = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    ).json()["id"]

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)
    client.put(f"/api/v1/admin/orders/returns/{request_id}", json={"status": "COMPLETED"})

    body = client.get(f"/api/v1/admin/orders/{order['id']}").json()
    assert body["order_status"] == "RETURNED"


def test_customer_cannot_decide_a_return_request(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = _deliver(client, db, admin_credentials, buyer, buyer_password)
    request_id = client.post(
        f"/api/v1/customer/orders/{order['order_number']}/returns",
        json={"type": "RETURN", "reason": "Does not fit"},
    ).json()["id"]

    response = client.put(
        f"/api/v1/admin/orders/returns/{request_id}", json={"status": "APPROVED"}
    )

    assert response.status_code == 403


# ----------------------------------------------------------------- invoices
def test_customer_can_download_their_invoice(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    response = customer_client.get(
        f"/api/v1/customer/orders/{order['order_number']}/invoice"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 1000
    assert order["order_number"] in response.headers["content-disposition"]


def test_customer_cannot_download_another_customers_invoice(client, db):
    owner, owner_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, owner.email, owner_password)
    order, _ = place_order(client, db, owner)

    client.cookies.clear()
    intruder, intruder_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, intruder.email, intruder_password)

    response = client.get(f"/api/v1/customer/orders/{order['order_number']}/invoice")

    assert response.status_code == 404


def test_invoice_requires_authentication(client, db, customer_credentials):
    buyer, buyer_password = customer_credentials
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)
    client.cookies.clear()

    response = client.get(f"/api/v1/customer/orders/{order['order_number']}/invoice")

    assert response.status_code == 401


def test_admin_can_download_any_invoice(client, db, admin_credentials):
    buyer, buyer_password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, buyer.email, buyer_password)
    order, _ = place_order(client, db, buyer)

    client.cookies.clear()
    admin, admin_password = admin_credentials
    sign_in(client, admin.email, admin_password)

    response = client.get(f"/api/v1/admin/orders/{order['id']}/invoice")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_customer_cannot_use_the_admin_invoice_endpoint(customer_client, db, customer_user):
    order, _ = place_order(customer_client, db, customer_user)

    assert customer_client.get(f"/api/v1/admin/orders/{order['id']}/invoice").status_code == 403


def test_invoice_renders_for_a_multi_item_order(customer_client, db, customer_user):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 4), (None, 32, 4))
    )
    for variant in product.variants:
        factories.seed_cart(db, customer_user.id, variant.id, 2)
    address = factories.make_address(db, customer_user.id)
    order = customer_client.post(
        "/api/v1/checkout", json=factories.checkout_payload(address.id)
    ).json()

    response = customer_client.get(
        f"/api/v1/customer/orders/{order['order_number']}/invoice"
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
