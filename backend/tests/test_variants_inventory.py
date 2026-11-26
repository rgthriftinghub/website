"""Per-variant stock behaviour.

The rule that matters commercially: a sold-out size must disable only that size,
never the whole product.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.inventory import InventoryItem
from app.models.variant import ProductVariant
from app.services import catalog as catalog_service
from app.services.exceptions import InvalidRequestError
from tests import factories

# The scenario named in the Phase 2 brief.
WAIST_MATRIX = ((None, 30, 5), (None, 32, 8), (None, 34, 0))


def test_stock_is_tracked_per_variant_not_per_product(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=WAIST_MATRIX)

    body = client.get(f"/api/v1/products/{product.slug}").json()

    quantities = {variant["waist"]: variant["quantity"] for variant in body["variants"]}
    assert quantities == {30: 5, 32: 8, 34: 0}


def test_only_the_sold_out_variant_is_unavailable(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=WAIST_MATRIX)

    body = client.get(f"/api/v1/products/{product.slug}").json()

    availability = {variant["waist"]: variant["in_stock"] for variant in body["variants"]}
    assert availability == {30: True, 32: True, 34: False}
    # The product itself stays purchasable and visible.
    assert body["in_stock"] is True
    assert body["is_active"] is True


def test_product_total_stock_is_the_sum_of_its_variants(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=WAIST_MATRIX)

    body = client.get(f"/api/v1/products/{product.slug}").json()

    assert body["total_stock"] == 13


def test_product_is_out_of_stock_only_when_every_variant_is(client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 0), (None, 32, 0))
    )

    body = client.get(f"/api/v1/products/{product.slug}").json()

    assert body["in_stock"] is False
    assert body["total_stock"] == 0
    # Still listed and active — being sold out is not the same as being withdrawn.
    assert body["is_active"] is True
    assert client.get("/api/v1/products").json()["total"] == 1


def test_low_stock_is_flagged_at_or_below_the_threshold(client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=((None, 30, 2), (None, 32, 9), (None, 34, 0))
    )

    body = client.get(f"/api/v1/products/{product.slug}").json()

    low = {variant["waist"]: variant["is_low_stock"] for variant in body["variants"]}
    # Threshold is 3: quantity 2 is low, 9 is not, and 0 is out rather than low.
    assert low == {30: True, 32: False, 34: False}


def test_in_stock_filter_excludes_fully_sold_out_products(client, db):
    category = factories.make_category(db)
    available = factories.make_product(db, category=category, variants=((None, 32, 4),))
    factories.make_product(db, category=category, variants=((None, 32, 0),))

    body = client.get("/api/v1/products?availability=in_stock").json()

    assert body["total"] == 1
    assert body["items"][0]["id"] == str(available.id)


def test_out_of_stock_filter_returns_only_sold_out_products(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, variants=((None, 32, 4),))
    sold_out = factories.make_product(db, category=category, variants=((None, 32, 0),))

    body = client.get("/api/v1/products?availability=out_of_stock").json()

    assert body["total"] == 1
    assert body["items"][0]["id"] == str(sold_out.id)


def test_waist_and_availability_must_be_satisfied_by_the_same_variant(client, db):
    category = factories.make_category(db)
    # Waist 34 is sold out here, though waist 30 has stock. Asking for an
    # in-stock waist 34 must not match this product.
    factories.make_product(db, category=category, variants=((None, 30, 5), (None, 34, 0)))

    sold_out_waist = client.get("/api/v1/products?waist=34&availability=in_stock").json()
    stocked_waist = client.get("/api/v1/products?waist=30&availability=in_stock").json()

    assert sold_out_waist["total"] == 0
    assert stocked_waist["total"] == 1


def test_inactive_variants_are_excluded_from_availability(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 30, 5), (None, 32, 4)))
    product.variants[0].is_active = False
    db.commit()

    body = client.get(f"/api/v1/products/{product.slug}").json()

    assert body["total_stock"] == 4
    disabled = [v for v in body["variants"] if v["waist"] == 30][0]
    assert disabled["is_active"] is False
    assert disabled["in_stock"] is False


# --------------------------------------------------------------- inventory management
def test_setting_a_variant_quantity_updates_availability(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 34, 0),))
    variant = product.variants[0]

    catalog_service.set_variant_quantity(db, variant.id, 6)

    body = client.get(f"/api/v1/products/{product.slug}").json()
    assert body["variants"][0]["quantity"] == 6
    assert body["variants"][0]["in_stock"] is True


def test_negative_quantity_is_rejected_by_the_service(db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 34, 1),))

    with pytest.raises(InvalidRequestError):
        catalog_service.set_variant_quantity(db, product.variants[0].id, -1)


def test_negative_quantity_is_rejected_by_the_database_constraint(db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 34, 1),))
    inventory = product.variants[0].inventory

    inventory.quantity = -5
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_duplicate_variant_sku_is_rejected_by_the_database(db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 30, 1),))
    existing_sku = product.variants[0].sku

    clash = ProductVariant(product_id=product.id, sku=existing_sku, waist=32)
    clash.inventory = InventoryItem(quantity=1)
    db.add(clash)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_duplicate_size_waist_colour_combination_is_rejected(db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, color="Indigo", variants=((None, 30, 1),))

    duplicate = ProductVariant(
        product_id=product.id, sku="DIFFERENT-SKU", waist=30, color="Indigo"
    )
    duplicate.inventory = InventoryItem(quantity=1)
    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_deleting_a_product_cascades_to_variants_and_inventory(db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=((None, 30, 1), (None, 32, 2)))
    variant_ids = [variant.id for variant in product.variants]

    db.delete(product)
    db.commit()

    for variant_id in variant_ids:
        assert db.get(ProductVariant, variant_id) is None


def test_admin_created_variant_reports_out_of_stock_correctly(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id,
        variants=[
            {"sku": "OOS-W30", "waist": 30, "quantity": 5},
            {"sku": "OOS-W32", "waist": 32, "quantity": 8},
            {"sku": "OOS-W34", "waist": 34, "quantity": 0},
        ],
    )

    body = admin_client.post("/api/v1/admin/products", json=payload).json()

    by_waist = {variant["waist"]: variant for variant in body["variants"]}
    assert by_waist[30]["in_stock"] is True
    assert by_waist[32]["in_stock"] is True
    assert by_waist[34]["in_stock"] is False
    assert body["in_stock"] is True


def test_variant_requires_a_distinguishing_attribute(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id, variants=[{"sku": "NO-ATTRS", "quantity": 1}]
    )

    response = admin_client.post("/api/v1/admin/products", json=payload)

    assert response.status_code == 422


def test_duplicate_variant_skus_in_one_request_are_rejected(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id,
        variants=[
            {"sku": "SAME-SKU", "waist": 30, "quantity": 1},
            {"sku": "SAME-SKU", "waist": 32, "quantity": 1},
        ],
    )

    response = admin_client.post("/api/v1/admin/products", json=payload)

    assert response.status_code == 400
    assert "unique" in response.json()["detail"]
