"""Discount engine and permission tests.

The priority rule is the part most likely to be quietly wrong, so each of its five
tiebreak steps is asserted separately rather than through one composite scenario.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.timezones import utc_now
from app.models.enums import (
    DEFAULT_STAFF_PERMISSIONS,
    DiscountType,
    Permission,
    SaleTargetType,
    SaleType,
    UserRole,
)
from app.models.sale import Sale, SaleTarget
from app.services import permissions as permission_service
from app.services import sale_admin, sales
from app.services.exceptions import InvalidRequestError
from tests.conftest import create_user
from tests.factories import make_brand, make_category, make_product, make_subcategory


@pytest.fixture
def shop(db):
    category = make_category(db)
    subcategory = make_subcategory(db, category)
    brand = make_brand(db)
    product = make_product(
        db,
        category=category,
        subcategory=subcategory,
        brand=brand,
        regular_price=Decimal("5000.00"),
        sale_price=None,
        variants=((None, 32, 5),),
    )
    return {"category": category, "subcategory": subcategory, "brand": brand, "product": product}


def make_sale(
    db,
    *,
    name: str,
    discount_type=DiscountType.PERCENTAGE,
    value: str = "10",
    priority: int = 0,
    target_type=SaleTargetType.STORE,
    sale_type=SaleType.STANDARD,
    starts_delta=timedelta(hours=-1),
    ends_delta=timedelta(days=1),
    is_active: bool = True,
    **target_kwargs,
) -> Sale:
    now = utc_now()
    sale = Sale(
        name=name,
        slug=name.lower().replace(" ", "-"),
        sale_type=sale_type,
        discount_type=discount_type,
        discount_value=Decimal(value),
        priority=priority,
        is_active=is_active,
        starts_at=now + starts_delta,
        ends_at=(now + ends_delta) if ends_delta is not None else None,
    )
    db.add(sale)
    db.flush()
    db.add(SaleTarget(sale_id=sale.id, target_type=target_type, **target_kwargs))
    db.commit()
    db.refresh(sale)
    return sale


# ------------------------------------------------------------------ discount maths
@pytest.mark.parametrize(
    "discount_type,value,expected",
    [
        (DiscountType.PERCENTAGE, "20", "4000.00"),
        (DiscountType.PERCENTAGE, "0", "5000.00"),
        (DiscountType.PERCENTAGE, "100", "0.00"),
        (DiscountType.FIXED_AMOUNT, "1000", "4000.00"),
        (DiscountType.CUSTOM_PRICE, "2499", "2499.00"),
    ],
)
def test_discount_types(discount_type, value, expected):
    result = sales.compute_discounted_price(
        Decimal("5000.00"), discount_type, Decimal(value)
    )
    assert result == Decimal(expected)


def test_discount_never_produces_a_negative_price():
    """A bad fixed amount must floor at zero, not invert the price."""
    assert sales.compute_discounted_price(
        Decimal("1000.00"), DiscountType.FIXED_AMOUNT, Decimal("99999")
    ) == Decimal("0.00")


def test_percentage_above_100_is_clamped():
    assert sales.compute_discounted_price(
        Decimal("1000.00"), DiscountType.PERCENTAGE, Decimal("500")
    ) == Decimal("0.00")


# --------------------------------------------------------------------- targeting
def test_store_wide_sale_covers_every_product(db, shop):
    make_sale(db, name="Store wide", value="10")
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.final_price == Decimal("4500.00")
    assert pricing.matched_target is SaleTargetType.STORE


def test_product_targeted_sale(db, shop):
    make_sale(
        db, name="Just this", value="25",
        target_type=SaleTargetType.PRODUCT, product_id=shop["product"].id,
    )
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.final_price == Decimal("3750.00")


def test_category_targeted_sale(db, shop):
    make_sale(
        db, name="Category", value="20",
        target_type=SaleTargetType.CATEGORY, category_id=shop["category"].id,
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].final_price == Decimal("4000.00")


def test_subcategory_targeted_sale(db, shop):
    make_sale(
        db, name="Subcat", value="30",
        target_type=SaleTargetType.SUBCATEGORY, subcategory_id=shop["subcategory"].id,
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].final_price == Decimal("3500.00")


def test_brand_targeted_sale(db, shop):
    make_sale(
        db, name="Brand", value="40",
        target_type=SaleTargetType.BRAND, brand_id=shop["brand"].id,
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].final_price == Decimal("3000.00")


def test_sale_targeting_another_brand_does_not_apply(db, shop):
    other = make_brand(db, name="Unrelated Brand")
    make_sale(
        db, name="Other brand", value="50",
        target_type=SaleTargetType.BRAND, brand_id=other.id,
    )
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.sale_id is None
    assert pricing.final_price == Decimal("5000.00")


# ---------------------------------------------------------------------- priority
def test_higher_priority_wins(db, shop):
    """The documented primary rule."""
    make_sale(db, name="Low priority big discount", value="60", priority=1)
    make_sale(
        db, name="High priority small discount", value="5", priority=9,
        target_type=SaleTargetType.PRODUCT, product_id=shop["product"].id,
    )
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.sale_name == "High priority small discount"
    assert pricing.final_price == Decimal("4750.00")


def test_priority_beats_specificity(db, shop):
    """A store-wide rule with higher priority outranks a product-specific one."""
    make_sale(db, name="Store high", value="30", priority=50)
    make_sale(
        db, name="Product low", value="35", priority=1,
        target_type=SaleTargetType.PRODUCT, product_id=shop["product"].id,
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].matched_target is SaleTargetType.STORE


def test_equal_priority_falls_back_to_specificity(db, shop):
    make_sale(db, name="Store equal", value="45", priority=5)
    make_sale(
        db, name="Product equal", value="10", priority=5,
        target_type=SaleTargetType.PRODUCT, product_id=shop["product"].id,
    )
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.matched_target is SaleTargetType.PRODUCT
    assert pricing.sale_name == "Product equal"


def test_equal_priority_and_specificity_prefers_the_bigger_discount(db, shop):
    make_sale(db, name="Store small", value="10", priority=3)
    make_sale(db, name="Store big", value="40", priority=3)
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.sale_name == "Store big"


def test_resolution_is_deterministic(db, shop):
    """Identical inputs must always produce the same winner — never random."""
    make_sale(db, name="A", value="20", priority=4)
    make_sale(db, name="B", value="20", priority=4)
    winners = {
        sales.attach_pricing(db, [shop["product"]])[shop["product"].id].sale_name
        for _ in range(8)
    }
    assert len(winners) == 1


# ---------------------------------------------------------------- scheduling
def test_future_sale_is_not_applied(db, shop):
    make_sale(
        db, name="Upcoming", value="70",
        starts_delta=timedelta(days=1), ends_delta=timedelta(days=2),
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].sale_id is None


def test_expired_sale_is_not_applied(db, shop):
    make_sale(
        db, name="Finished", value="70",
        starts_delta=timedelta(days=-5), ends_delta=timedelta(days=-1),
    )
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].sale_id is None


def test_inactive_sale_is_not_applied(db, shop):
    make_sale(db, name="Disabled", value="70", is_active=False)
    assert sales.attach_pricing(db, [shop["product"]])[shop["product"].id].sale_id is None


def test_open_ended_sale_applies(db, shop):
    """A clearance rail with no end date should run indefinitely."""
    make_sale(db, name="Permanent clearance", value="15", ends_delta=None,
              sale_type=SaleType.CLEARANCE)
    pricing = sales.attach_pricing(db, [shop["product"]])[shop["product"].id]
    assert pricing.final_price == Decimal("4250.00")
    assert pricing.sale_type is SaleType.CLEARANCE


def test_is_live_matches_the_sql_predicate(db, shop):
    """The Python and SQL activation rules must agree, or pages disagree on price."""
    live = make_sale(db, name="Live now", value="10")
    future = make_sale(db, name="Later", value="10", starts_delta=timedelta(days=3),
                       ends_delta=timedelta(days=4))
    now = utc_now()
    active_ids = {sale.id for sale in sales.active_sales(db)}
    assert live.is_live(now) is True and live.id in active_ids
    assert future.is_live(now) is False and future.id not in active_ids


# ------------------------------------------------------------------- stacking
def test_campaign_never_undercuts_a_better_manual_price(db):
    """A hand-set clearance price must win when it is cheaper than the campaign."""
    category = make_category(db)
    product = make_product(
        db, category=category,
        regular_price=Decimal("5000.00"), sale_price=Decimal("2000.00"),
        variants=((None, 32, 3),),
    )
    make_sale(db, name="Modest 10", value="10")  # -> 4500, worse than 2000
    pricing = sales.attach_pricing(db, [product])[product.id]
    assert pricing.final_price == Decimal("2000.00")


def test_campaign_applies_when_better_than_the_manual_price(db):
    category = make_category(db)
    product = make_product(
        db, category=category,
        regular_price=Decimal("5000.00"), sale_price=Decimal("4800.00"),
        variants=((None, 32, 3),),
    )
    make_sale(db, name="Deep 50", value="50")  # -> 2500, better than 4800
    assert sales.attach_pricing(db, [product])[product.id].final_price == Decimal("2500.00")


def test_effective_price_property_reflects_the_campaign(db, shop):
    """Every consumer reads price through this property, so the wiring matters."""
    product = shop["product"]
    make_sale(db, name="Twenty", value="20")
    sales.attach_pricing(db, [product])
    assert product.effective_price == Decimal("4000.00")
    assert product.is_on_sale is True
    assert product.discount_percent == 20
    assert product.discount_amount == Decimal("1000.00")


def test_public_product_endpoint_returns_sale_pricing(db, client, shop):
    make_sale(db, name="Api 25", value="25")
    response = client.get(f"/api/v1/products/{shop['product'].slug}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["effective_price"] == "3750.00"
    assert body["sale_pricing"]["discount_percent"] == 25
    assert body["sale_pricing"]["sale_name"] == "Api 25"


# ------------------------------------------------------------ sale validation
def test_flash_sale_requires_an_end_time():
    from pydantic import ValidationError

    from app.schemas.admin_ops import SaleCreate

    with pytest.raises(ValidationError, match="flash sale must have an end time"):
        SaleCreate(
            name="Bad flash",
            sale_type=SaleType.FLASH,
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10"),
            starts_at=utc_now(),
            ends_at=None,
            targets=[{"target_type": "STORE"}],
        )


def test_sale_end_must_follow_start(db, admin_user):
    now = utc_now()
    with pytest.raises(InvalidRequestError, match="after the start"):
        sale_admin.create_sale(
            db,
            {
                "name": "Backwards",
                "slug": None,
                "description": None,
                "sale_type": SaleType.STANDARD,
                "discount_type": DiscountType.PERCENTAGE,
                "discount_value": Decimal("10"),
                "priority": 0,
                "is_active": True,
                "starts_at": now,
                "ends_at": now - timedelta(hours=1),
                "badge_text": None,
                "targets": [{"target_type": "STORE"}],
            },
            actor=admin_user,
        )


def test_sale_requires_at_least_one_target(db, admin_user):
    with pytest.raises(InvalidRequestError, match="at least one target"):
        sale_admin.create_sale(
            db,
            {
                "name": "No targets", "slug": None, "description": None,
                "sale_type": SaleType.STANDARD,
                "discount_type": DiscountType.PERCENTAGE,
                "discount_value": Decimal("10"),
                "priority": 0, "is_active": True,
                "starts_at": utc_now(), "ends_at": None,
                "badge_text": None, "targets": [],
            },
            actor=admin_user,
        )


def test_deleting_a_sale_restores_original_prices(db, shop, admin_user):
    """A campaign is a rule, so removing it must not need a catalogue update."""
    product = shop["product"]
    sale = make_sale(db, name="Temporary", value="30")
    assert sales.attach_pricing(db, [product])[product.id].final_price == Decimal("3500.00")

    sale_admin.delete_sale(db, sale.id, actor=admin_user)
    db.expire(product)
    assert sales.attach_pricing(db, [product])[product.id].final_price == Decimal("5000.00")


# ---------------------------------------------------------------- permissions
def test_admin_holds_every_permission(db, admin_user):
    held = permission_service.permissions_for(db, admin_user)
    assert held == permission_service.ALL_PERMISSIONS


def test_customer_holds_no_admin_permissions(db, customer_user):
    assert permission_service.permissions_for(db, customer_user) == frozenset()


def test_new_staff_starts_read_only(db):
    staff, _ = create_user(db, UserRole.STAFF)
    permission_service.apply_default_grants(db, staff)
    held = permission_service.permissions_for(db, staff)
    assert held == DEFAULT_STAFF_PERMISSIONS
    assert Permission.PRODUCT_UPDATE not in held


def test_granting_permissions_replaces_rather_than_accumulates(db):
    staff, _ = create_user(db, UserRole.STAFF)
    permission_service.grant(db, staff.id, [Permission.PRODUCT_VIEW, Permission.PRODUCT_UPDATE])
    permission_service.grant(db, staff.id, [Permission.ORDER_VIEW])
    held = permission_service.permissions_for(db, staff)
    assert held == {Permission.ORDER_VIEW}


def test_admin_cannot_be_given_partial_permissions(db, admin_user):
    with pytest.raises(InvalidRequestError, match="already hold every permission"):
        permission_service.grant(db, admin_user.id, [Permission.PRODUCT_VIEW])


def test_customer_cannot_be_granted_staff_permissions(db, customer_user):
    with pytest.raises(InvalidRequestError, match="Only staff"):
        permission_service.grant(db, customer_user.id, [Permission.PRODUCT_VIEW])


def test_staff_without_permission_is_refused_by_the_api(db, staff_client, staff_credentials):
    """Route-level enforcement, not just the service layer."""
    staff, _ = staff_credentials
    permission_service.grant(db, staff.id, [Permission.ORDER_VIEW])

    response = staff_client.get("/api/v1/admin/analytics/dashboard")
    assert response.status_code == 403
    assert "REPORTS_VIEW" in response.text


def test_staff_with_permission_is_allowed_by_the_api(db, staff_client, staff_credentials):
    staff, _ = staff_credentials
    permission_service.grant(db, staff.id, [Permission.REPORTS_VIEW])
    assert staff_client.get("/api/v1/admin/analytics/dashboard").status_code == 200


def test_admin_reaches_analytics_without_explicit_grants(admin_client):
    assert admin_client.get("/api/v1/admin/analytics/dashboard").status_code == 200


def test_customer_cannot_reach_admin_analytics(customer_client):
    assert customer_client.get("/api/v1/admin/analytics/dashboard").status_code == 403


def test_anonymous_cannot_reach_admin_analytics(client):
    assert client.get("/api/v1/admin/analytics/dashboard").status_code == 401
