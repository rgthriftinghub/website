"""Role enforcement on the admin API."""

import pytest

from tests import factories

ADMIN_READ_ENDPOINTS = (
    "/api/v1/admin/products",
    "/api/v1/admin/categories",
    "/api/v1/admin/brands",
    "/api/v1/admin/subcategories",
)


@pytest.mark.parametrize("endpoint", ADMIN_READ_ENDPOINTS)
def test_anonymous_users_are_rejected(client, db, endpoint):
    assert client.get(endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ADMIN_READ_ENDPOINTS)
def test_customers_are_forbidden(customer_client, db, endpoint):
    response = customer_client.get(endpoint)

    assert response.status_code == 403
    assert "permission" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ADMIN_READ_ENDPOINTS)
def test_admins_are_allowed(admin_client, db, endpoint):
    assert admin_client.get(endpoint).status_code == 200


@pytest.mark.parametrize("endpoint", ADMIN_READ_ENDPOINTS)
def test_staff_are_allowed(staff_client, db, endpoint):
    assert staff_client.get(endpoint).status_code == 200


def test_customer_cannot_create_a_product(customer_client, db):
    category = factories.make_category(db)

    response = customer_client.post(
        "/api/v1/admin/products", json=factories.product_payload(category_id=category.id)
    )

    assert response.status_code == 403


def test_anonymous_cannot_create_a_product(client, db):
    category = factories.make_category(db)

    response = client.post(
        "/api/v1/admin/products", json=factories.product_payload(category_id=category.id)
    )

    assert response.status_code == 401


def test_customer_cannot_deactivate_a_product(customer_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category)

    response = customer_client.delete(f"/api/v1/admin/products/{product.id}")

    assert response.status_code == 403
    db.refresh(product)
    assert product.is_active is True
