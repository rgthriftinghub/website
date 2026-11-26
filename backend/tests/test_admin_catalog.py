"""Admin CRUD for products, categories, subcategories, and brands."""

from decimal import Decimal

from tests import factories


# --------------------------------------------------------------------------- products
def test_product_import_template_includes_item_code_and_single_piece(admin_client):
    response = admin_client.get("/api/v1/admin/import/template.csv")

    assert response.status_code == 200
    assert "SKU,Item Code,Single Piece," in response.text


def test_admin_creates_a_product_with_images_and_variants(admin_client, db):
    category = factories.make_category(db)
    brand = factories.make_brand(db)
    subcategory = factories.make_subcategory(db, category)
    payload = factories.product_payload(
        category_id=category.id, brand_id=brand.id, subcategory_id=subcategory.id
    )

    response = admin_client.post("/api/v1/admin/products", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == payload["slug"]
    assert body["brand"]["id"] == str(brand.id)
    assert body["category"]["id"] == str(category.id)
    assert len(body["images"]) == 1
    assert len(body["variants"]) == 2
    # Money must survive as an exact decimal string, not a float.
    assert Decimal(body["regular_price"]) == Decimal("4500.00")


def test_created_variants_each_get_an_inventory_row(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(category_id=category.id)

    body = admin_client.post("/api/v1/admin/products", json=payload).json()

    quantities = {variant["waist"]: variant["quantity"] for variant in body["variants"]}
    assert quantities == {30: 4, 32: 0}
    in_stock = {variant["waist"]: variant["in_stock"] for variant in body["variants"]}
    assert in_stock == {30: True, 32: False}


def test_first_image_becomes_primary_when_none_is_flagged(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id,
        images=[
            {"image_url": "/demo/products/a.png", "is_primary": False},
            {"image_url": "/demo/products/b.png", "is_primary": False},
        ],
    )

    body = admin_client.post("/api/v1/admin/products", json=payload).json()

    primary = [image for image in body["images"] if image["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["image_url"] == "/demo/products/a.png"


def test_two_primary_images_are_rejected(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id,
        images=[
            {"image_url": "/demo/products/a.png", "is_primary": True},
            {"image_url": "/demo/products/b.png", "is_primary": True},
        ],
    )

    response = admin_client.post("/api/v1/admin/products", json=payload)

    assert response.status_code == 400
    assert "primary" in response.json()["detail"]


def test_duplicate_product_slug_is_rejected(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(category_id=category.id, slug="clashing-slug")
    assert admin_client.post("/api/v1/admin/products", json=payload).status_code == 201

    second = factories.product_payload(category_id=category.id, slug="clashing-slug")
    response = admin_client.post("/api/v1/admin/products", json=second)

    assert response.status_code == 409
    assert "slug" in response.json()["detail"]


def test_duplicate_product_sku_is_rejected(admin_client, db):
    category = factories.make_category(db)
    assert (
        admin_client.post(
            "/api/v1/admin/products",
            json=factories.product_payload(category_id=category.id, sku="SHARED-SKU"),
        ).status_code
        == 201
    )

    response = admin_client.post(
        "/api/v1/admin/products",
        json=factories.product_payload(category_id=category.id, sku="SHARED-SKU"),
    )

    assert response.status_code == 409
    assert "SKU" in response.json()["detail"]


def test_sale_price_above_regular_price_is_rejected(admin_client, db):
    category = factories.make_category(db)
    payload = factories.product_payload(
        category_id=category.id, regular_price="1000.00", sale_price="2000.00"
    )

    response = admin_client.post("/api/v1/admin/products", json=payload)

    assert response.status_code == 422


def test_subcategory_from_another_category_is_rejected(admin_client, db):
    category = factories.make_category(db, name="Men")
    other_category = factories.make_category(db, name="Women")
    foreign_subcategory = factories.make_subcategory(db, other_category, name="Dresses")

    response = admin_client.post(
        "/api/v1/admin/products",
        json=factories.product_payload(
            category_id=category.id, subcategory_id=foreign_subcategory.id
        ),
    )

    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"]


def test_unknown_category_is_rejected(admin_client, db):
    import uuid

    response = admin_client.post(
        "/api/v1/admin/products", json=factories.product_payload(category_id=uuid.uuid4())
    )

    assert response.status_code == 404


def test_admin_updates_a_product(admin_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=(("M", None, 3),))

    response = admin_client.put(
        f"/api/v1/admin/products/{product.id}",
        json={"name": "Renamed Product", "is_featured": True, "sale_price": "3999.00"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Renamed Product"
    assert body["is_featured"] is True
    assert body["is_on_sale"] is True
    assert Decimal(body["sale_price"]) == Decimal("3999.00")


def test_partial_update_leaves_untouched_collections_intact(admin_client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db, category=category, variants=(("M", None, 3), ("L", None, 5)), image_count=2
    )

    body = admin_client.put(
        f"/api/v1/admin/products/{product.id}", json={"name": "Only The Name"}
    ).json()

    assert len(body["variants"]) == 2
    assert len(body["images"]) == 2


def test_update_replaces_variants_when_supplied(admin_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, variants=(("M", None, 3),))

    body = admin_client.put(
        f"/api/v1/admin/products/{product.id}",
        json={
            "variants": [
                {"sku": "REPLACED-W30", "waist": 30, "quantity": 7},
                {"sku": "REPLACED-W32", "waist": 32, "quantity": 1},
            ]
        },
    ).json()

    assert {v["sku"] for v in body["variants"]} == {"REPLACED-W30", "REPLACED-W32"}
    assert {v["quantity"] for v in body["variants"]} == {7, 1}


def test_update_rejects_a_sale_price_above_the_existing_regular_price(admin_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, regular_price=Decimal("1000.00"))

    response = admin_client.put(
        f"/api/v1/admin/products/{product.id}", json={"sale_price": "5000.00"}
    )

    assert response.status_code == 400


def test_delete_deactivates_rather_than_removing(admin_client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category)

    response = admin_client.delete(f"/api/v1/admin/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    # Still retrievable by id in the admin area.
    assert admin_client.get(f"/api/v1/admin/products/{product.id}").status_code == 200
    # But gone from the public catalogue.
    assert admin_client.get(f"/api/v1/products/{product.slug}").status_code == 404


def test_admin_list_includes_deactivated_products(admin_client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, is_active=False)

    body = admin_client.get("/api/v1/admin/products").json()

    assert body["total"] == 1


def test_admin_list_can_exclude_deactivated_products(admin_client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, is_active=False)
    factories.make_product(db, category=category, is_active=True)

    body = admin_client.get("/api/v1/admin/products?include_inactive=false").json()

    assert body["total"] == 1


# ------------------------------------------------------------------------- categories
def test_admin_creates_and_updates_a_category(admin_client, db):
    create = admin_client.post(
        "/api/v1/admin/categories",
        json={"name": "Footwear", "slug": "footwear", "sort_order": 4},
    )
    assert create.status_code == 201, create.text
    category_id = create.json()["id"]

    update = admin_client.put(
        f"/api/v1/admin/categories/{category_id}", json={"name": "Shoes & Boots"}
    )

    assert update.status_code == 200
    assert update.json()["name"] == "Shoes & Boots"
    assert update.json()["slug"] == "footwear"


def test_duplicate_category_slug_is_rejected(admin_client, db):
    admin_client.post("/api/v1/admin/categories", json={"name": "Bags", "slug": "bags"})

    response = admin_client.post(
        "/api/v1/admin/categories", json={"name": "Bags Again", "slug": "bags"}
    )

    assert response.status_code == 409


def test_invalid_slug_format_is_rejected(admin_client, db):
    response = admin_client.post(
        "/api/v1/admin/categories", json={"name": "Bad", "slug": "Not A Slug"}
    )
    assert response.status_code == 422


def test_deactivating_a_category_hides_it_from_the_public_list(admin_client, db):
    created = admin_client.post(
        "/api/v1/admin/categories", json={"name": "Seasonal", "slug": "seasonal"}
    ).json()

    admin_client.delete(f"/api/v1/admin/categories/{created['id']}")

    public_slugs = [row["slug"] for row in admin_client.get("/api/v1/categories").json()]
    assert "seasonal" not in public_slugs


# ---------------------------------------------------------------------- subcategories
def test_same_subcategory_slug_allowed_in_different_categories(admin_client, db):
    men = factories.make_category(db, name="Men")
    women = factories.make_category(db, name="Women")

    first = admin_client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": str(men.id), "name": "Jeans", "slug": "jeans"},
    )
    second = admin_client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": str(women.id), "name": "Jeans", "slug": "jeans"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


def test_duplicate_subcategory_slug_within_a_category_is_rejected(admin_client, db):
    category = factories.make_category(db)
    admin_client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": str(category.id), "name": "Jeans", "slug": "jeans"},
    )

    response = admin_client.post(
        "/api/v1/admin/subcategories",
        json={"category_id": str(category.id), "name": "Denim", "slug": "jeans"},
    )

    assert response.status_code == 409


# ----------------------------------------------------------------------------- brands
def test_admin_brand_crud(admin_client, db):
    create = admin_client.post(
        "/api/v1/admin/brands", json={"name": "Vertex Sport", "slug": "vertex-sport"}
    )
    assert create.status_code == 201, create.text
    brand_id = create.json()["id"]

    assert admin_client.get(f"/api/v1/admin/brands/{brand_id}").status_code == 200

    update = admin_client.put(
        f"/api/v1/admin/brands/{brand_id}", json={"description": "Performance layers."}
    )
    assert update.json()["description"] == "Performance layers."

    deactivated = admin_client.delete(f"/api/v1/admin/brands/{brand_id}")
    assert deactivated.json()["is_active"] is False
    assert "vertex-sport" not in [row["slug"] for row in admin_client.get("/api/v1/brands").json()]


def test_duplicate_brand_slug_is_rejected(admin_client, db):
    admin_client.post("/api/v1/admin/brands", json={"name": "Dup", "slug": "dup-brand"})

    response = admin_client.post(
        "/api/v1/admin/brands", json={"name": "Dup Two", "slug": "dup-brand"}
    )

    assert response.status_code == 409
