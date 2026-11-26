"""Public product retrieval, filtering, search, sorting, and pagination."""

from decimal import Decimal

from app.models.enums import Gender, ProductCondition, ProductType
from tests import factories


def test_product_detail_is_retrievable_by_slug(client, db):
    category = factories.make_category(db)
    brand = factories.make_brand(db, name="Northbay Denim")
    product = factories.make_product(
        db, category=category, brand=brand, slug="visible-jeans", variants=(("M", None, 4),)
    )

    response = client.get(f"/api/v1/products/{product.slug}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slug"] == "visible-jeans"
    assert body["brand"]["name"] == "Northbay Denim"
    assert body["category"]["id"] == str(category.id)
    assert len(body["variants"]) == 1


def test_unknown_slug_returns_404(client, db):
    assert client.get("/api/v1/products/no-such-product").status_code == 404


def test_inactive_products_are_hidden_from_the_public_api(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, is_active=False)

    assert client.get(f"/api/v1/products/{product.slug}").status_code == 404
    assert client.get("/api/v1/products").json()["total"] == 0


def test_sale_pricing_is_computed_consistently(client, db):
    category = factories.make_category(db)
    product = factories.make_product(
        db,
        category=category,
        regular_price=Decimal("5200.00"),
        sale_price=Decimal("3900.00"),
    )

    body = client.get(f"/api/v1/products/{product.slug}").json()

    assert body["is_on_sale"] is True
    assert Decimal(body["effective_price"]) == Decimal("3900.00")
    assert body["discount_percent"] == 25


def test_product_without_sale_price_reports_no_discount(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category, regular_price=Decimal("2000.00"))

    body = client.get(f"/api/v1/products/{product.slug}").json()

    assert body["is_on_sale"] is False
    assert body["discount_percent"] == 0
    assert Decimal(body["effective_price"]) == Decimal("2000.00")


# -------------------------------------------------------------------------- filtering
def test_filter_by_category_slug(client, db):
    men = factories.make_category(db, name="Men", slug="men")
    women = factories.make_category(db, name="Women", slug="women")
    factories.make_product(db, category=men)
    factories.make_product(db, category=women)

    body = client.get("/api/v1/products?category=men").json()

    assert body["total"] == 1
    assert body["items"][0]["category"]["slug"] == "men"


def test_filter_by_brand_slug_or_name(client, db):
    category = factories.make_category(db)
    brand = factories.make_brand(db, name="Northbay Denim", slug="northbay-denim")
    factories.make_product(db, category=category, brand=brand)
    factories.make_product(db, category=category)

    by_slug = client.get("/api/v1/products?brand=northbay-denim").json()
    by_name = client.get("/api/v1/products?brand=Northbay%20Denim").json()

    assert by_slug["total"] == 1
    assert by_name["total"] == 1


def test_filter_by_condition_and_gender(client, db):
    category = factories.make_category(db)
    factories.make_product(
        db, category=category, condition=ProductCondition.THRIFT, gender=Gender.MEN
    )
    factories.make_product(
        db, category=category, condition=ProductCondition.NEW, gender=Gender.WOMEN
    )

    thrift = client.get("/api/v1/products?condition=THRIFT").json()
    women = client.get("/api/v1/products?gender=WOMEN").json()

    assert thrift["total"] == 1
    assert women["total"] == 1


def test_filter_by_each_thrift_grade_and_legacy_aliases(client, db):
    category = factories.make_category(db)
    grades = [
        ProductCondition.PREMIUM_PLUS,
        ProductCondition.PREMIUM,
        ProductCondition.EXCELLENT,
        ProductCondition.GOOD,
    ]
    for grade in grades:
        factories.make_product(db, category=category, condition=grade)

    for grade in grades:
        response = client.get(f"/api/v1/products?condition={grade.value}")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1

    assert client.get("/api/v1/products?condition=NEW").json()["total"] == 1
    assert client.get("/api/v1/products?condition=EXPORT_QUALITY").json()["total"] == 1
    assert client.get("/api/v1/products?condition=THRIFT").json()["total"] == 1


def test_filter_by_product_type_colour_and_fabric(client, db):
    category = factories.make_category(db)
    factories.make_product(
        db,
        category=category,
        product_type=ProductType.JEANS,
        color="Indigo",
        fabric="Denim",
    )
    factories.make_product(
        db,
        category=category,
        product_type=ProductType.HOODIE,
        color="Olive",
        fabric="Fleece",
    )

    assert client.get("/api/v1/products?product_type=HOODIE").json()["total"] == 1
    # Colour and fabric matching is case-insensitive.
    assert client.get("/api/v1/products?color=indigo").json()["total"] == 1
    assert client.get("/api/v1/products?fabric=FLEECE").json()["total"] == 1


def test_filter_by_featured_and_new_arrival_flags(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, is_featured=True)
    factories.make_product(db, category=category, is_new_arrival=True)
    factories.make_product(db, category=category)

    assert client.get("/api/v1/products?is_featured=true").json()["total"] == 1
    assert client.get("/api/v1/products?is_new_arrival=true").json()["total"] == 1


def test_filter_by_price_range_uses_the_effective_price(client, db):
    category = factories.make_category(db)
    # Discounted below the range floor, so it must be excluded despite a high list price.
    factories.make_product(
        db, category=category, regular_price=Decimal("9000.00"), sale_price=Decimal("1000.00")
    )
    factories.make_product(db, category=category, regular_price=Decimal("4000.00"))

    body = client.get("/api/v1/products?min_price=2000&max_price=5000").json()

    assert body["total"] == 1
    assert Decimal(body["items"][0]["effective_price"]) == Decimal("4000.00")


def test_invalid_price_range_is_rejected(client, db):
    response = client.get("/api/v1/products?min_price=500&max_price=100")
    assert response.status_code == 422


def test_filter_by_size_and_waist(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, variants=((None, 32, 5),))
    factories.make_product(db, category=category, variants=((None, 36, 5),))
    factories.make_product(db, category=category, variants=(("M", None, 5),))

    assert client.get("/api/v1/products?waist=32").json()["total"] == 1
    assert client.get("/api/v1/products?size=M").json()["total"] == 1
    # A valid waist that nothing in the catalogue stocks.
    assert client.get("/api/v1/products?waist=48").json()["total"] == 0


def test_filters_combine_as_an_and(client, db):
    men = factories.make_category(db, name="Men", slug="men")
    brand = factories.make_brand(db, name="Northbay Denim", slug="northbay-denim")
    # The one product satisfying every clause of the documented example query.
    factories.make_product(
        db,
        category=men,
        brand=brand,
        condition=ProductCondition.THRIFT,
        variants=((None, 32, 6),),
    )
    # Right brand and category, wrong waist.
    factories.make_product(
        db, category=men, brand=brand, condition=ProductCondition.THRIFT, variants=((None, 40, 6),)
    )
    # Right everything, wrong condition.
    factories.make_product(
        db, category=men, brand=brand, condition=ProductCondition.NEW, variants=((None, 32, 6),)
    )

    body = client.get(
        "/api/v1/products?category=men&brand=northbay-denim&waist=32&condition=THRIFT"
    ).json()

    assert body["total"] == 1


# ----------------------------------------------------------------------------- search
def test_search_matches_product_name(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, name="Straight Leg Jeans")
    factories.make_product(db, category=category, name="Fleece Hoodie")

    body = client.get("/api/v1/products?search=jeans").json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == "Straight Leg Jeans"


def test_search_matches_sku(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category)

    body = client.get(f"/api/v1/products?search={product.sku}").json()

    assert body["total"] == 1


def test_search_matches_generated_item_code(client, db):
    category = factories.make_category(db)
    product = factories.make_product(db, category=category)

    body = client.get(f"/api/v1/products?search={product.item_code}").json()

    assert body["total"] == 1
    assert body["items"][0]["item_code"] == product.item_code


def test_search_matches_brand_name(client, db):
    category = factories.make_category(db)
    brand = factories.make_brand(db, name="Maison Ruz", slug="maison-ruz")
    factories.make_product(db, category=category, brand=brand, name="Crepe Dress")
    factories.make_product(db, category=category, name="Cotton Tee")

    body = client.get("/api/v1/products?search=maison").json()

    assert body["total"] == 1


def test_search_matches_category_name(client, db):
    accessories = factories.make_category(db, name="Accessories", slug="accessories")
    other = factories.make_category(db, name="Men", slug="men")
    factories.make_product(db, category=accessories, name="Canvas Tote")
    factories.make_product(db, category=other, name="Denim Jacket")

    body = client.get("/api/v1/products?search=accessories").json()

    assert body["total"] == 1


def test_search_is_case_insensitive(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, name="Merino Crew Neck")

    assert client.get("/api/v1/products?search=MERINO").json()["total"] == 1


def test_search_requires_every_word_to_match(client, db):
    category = factories.make_category(db)
    brand = factories.make_brand(db, name="Northbay Denim", slug="northbay-denim")
    factories.make_product(db, category=category, brand=brand, name="Straight Leg Jeans")
    factories.make_product(db, category=category, name="Straight Leg Trousers")

    # "northbay" only matches the first product's brand.
    body = client.get("/api/v1/products?search=northbay%20jeans").json()

    assert body["total"] == 1


# ---------------------------------------------------------------------------- sorting
def test_sort_by_price_ascending_and_descending(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, name="Cheap", regular_price=Decimal("1000.00"))
    factories.make_product(db, category=category, name="Mid", regular_price=Decimal("5000.00"))
    factories.make_product(db, category=category, name="Dear", regular_price=Decimal("9000.00"))

    ascending = client.get("/api/v1/products?sort=price_low").json()
    descending = client.get("/api/v1/products?sort=price_high").json()

    assert [item["name"] for item in ascending["items"]] == ["Cheap", "Mid", "Dear"]
    assert [item["name"] for item in descending["items"]] == ["Dear", "Mid", "Cheap"]


def test_price_sorting_respects_the_sale_price(client, db):
    category = factories.make_category(db)
    factories.make_product(
        db,
        category=category,
        name="Discounted",
        regular_price=Decimal("9000.00"),
        sale_price=Decimal("500.00"),
    )
    factories.make_product(db, category=category, name="Full Price", regular_price=Decimal("1000.00"))

    body = client.get("/api/v1/products?sort=price_low").json()

    assert [item["name"] for item in body["items"]] == ["Discounted", "Full Price"]


def test_default_sort_is_newest_first(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category, name="Older")
    factories.make_product(db, category=category, name="Newer")

    names = [item["name"] for item in client.get("/api/v1/products").json()["items"]]

    assert names[0] == "Newer"


def test_unknown_sort_value_is_rejected(client, db):
    assert client.get("/api/v1/products?sort=most_liked").status_code == 422


# ------------------------------------------------------------------------- pagination
def test_pagination_envelope_and_slicing(client, db):
    category = factories.make_category(db)
    for index in range(7):
        factories.make_product(db, category=category, name=f"Product {index}")

    first = client.get("/api/v1/products?page=1&page_size=3").json()
    last = client.get("/api/v1/products?page=3&page_size=3").json()

    assert set(first) == {"items", "page", "page_size", "total", "total_pages"}
    assert first["total"] == 7
    assert first["total_pages"] == 3
    assert len(first["items"]) == 3
    assert len(last["items"]) == 1


def test_page_beyond_the_end_returns_an_empty_page_not_an_error(client, db):
    category = factories.make_category(db)
    factories.make_product(db, category=category)

    body = client.get("/api/v1/products?page=50&page_size=24").json()

    assert body["items"] == []
    assert body["total"] == 1


def test_empty_catalogue_reports_zero_pages(client, db):
    body = client.get("/api/v1/products").json()

    assert body["total"] == 0
    assert body["total_pages"] == 0
    assert body["items"] == []


def test_page_size_is_capped(client, db):
    assert client.get("/api/v1/products?page_size=5000").status_code == 422


def test_pagination_does_not_duplicate_rows_across_pages(client, db):
    category = factories.make_category(db)
    # Identical prices force the tie-breaker in the sort clause to do real work.
    for index in range(6):
        factories.make_product(
            db, category=category, name=f"Same Price {index}", regular_price=Decimal("2500.00")
        )

    page_one = client.get("/api/v1/products?sort=price_low&page=1&page_size=3").json()
    page_two = client.get("/api/v1/products?sort=price_low&page=2&page_size=3").json()

    ids = [item["id"] for item in page_one["items"] + page_two["items"]]
    assert len(set(ids)) == 6


# ------------------------------------------------------------------- filter options
def test_filter_options_reflect_the_catalogue(client, db):
    category = factories.make_category(db)
    factories.make_product(
        db, category=category, color="Indigo", fabric="Denim", variants=((None, 32, 4), ("M", None, 2))
    )

    body = client.get("/api/v1/products/filter-options").json()

    assert "Indigo" in body["colors"]
    assert "Denim" in body["fabrics"]
    assert 32 in body["waists"]
    assert "M" in body["sizes"]


def test_kids_taxonomy_has_girls_and_boys(db):
    from app.models.category import Category
    from app.seeds.seed import seed_taxonomy

    seed_taxonomy(db)
    kids = db.query(Category).filter_by(slug="kids").one()
    assert {sub.slug for sub in kids.subcategories} == {"girls", "boys"}


def test_guest_wishlist_bulk_resolver_only_returns_active_products(client, db):
    category = factories.make_category(db)
    active = factories.make_product(db, category=category)
    inactive = factories.make_product(db, category=category, is_active=False)
    response = client.get(f"/api/v1/products/by-ids?ids={active.id}&ids={inactive.id}")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [str(active.id)]
