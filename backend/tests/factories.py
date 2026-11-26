"""Helpers for building catalogue rows in tests."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.address import CustomerAddress
from app.models.brand import Brand
from app.models.cart import Cart
from app.models.category import Category, Subcategory
from app.models.enums import Gender, ProductCondition, ProductType
from app.models.inventory import InventoryItem
from app.models.product import Product, ProductImage
from app.models.variant import ProductVariant


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def make_category(db: Session, *, name: str = "Men", slug: str | None = None) -> Category:
    category = Category(name=name, slug=slug or f"{name.lower()}-{_suffix()}", is_active=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def make_subcategory(
    db: Session, category: Category, *, name: str = "Jeans", slug: str | None = None
) -> Subcategory:
    subcategory = Subcategory(
        category_id=category.id,
        name=name,
        slug=slug or f"{name.lower()}-{_suffix()}",
        is_active=True,
    )
    db.add(subcategory)
    db.commit()
    db.refresh(subcategory)
    return subcategory


def make_brand(db: Session, *, name: str = "Northbay Denim", slug: str | None = None) -> Brand:
    brand = Brand(name=name, slug=slug or f"brand-{_suffix()}", is_active=True)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def make_product(
    db: Session,
    *,
    category: Category,
    name: str = "Straight Leg Jeans",
    slug: str | None = None,
    brand: Brand | None = None,
    subcategory: Subcategory | None = None,
    regular_price: Decimal = Decimal("5000.00"),
    sale_price: Decimal | None = None,
    condition: ProductCondition = ProductCondition.THRIFT,
    gender: Gender = Gender.MEN,
    product_type: ProductType = ProductType.JEANS,
    color: str | None = "Indigo",
    fabric: str | None = "Denim",
    is_featured: bool = False,
    is_new_arrival: bool = False,
    is_active: bool = True,
    variants: tuple[tuple[str | None, int | None, int], ...] = (),
    image_count: int = 1,
) -> Product:
    """Create a product.

    `variants` entries are `(size, waist, quantity)` triples, which is the shape
    the per-size stock tests care about.
    """
    unique = _suffix()
    product = Product(
        name=name,
        slug=slug or f"product-{unique}",
        sku=f"SKU-{unique}",
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
        brand_id=brand.id if brand else None,
        regular_price=regular_price,
        sale_price=sale_price,
        condition=condition,
        gender=gender,
        product_type=product_type,
        color=color,
        fabric=fabric,
        is_featured=is_featured,
        is_new_arrival=is_new_arrival,
        is_active=is_active,
        short_description="Test product",
    )

    for index in range(image_count):
        product.images.append(
            ProductImage(
                image_url=f"/demo/products/{product.slug}-{index + 1}.png",
                alt_text=f"{name} view {index + 1}",
                sort_order=index,
                is_primary=index == 0,
            )
        )

    for position, (size, waist, quantity) in enumerate(variants):
        variant = ProductVariant(
            sku=f"SKU-{unique}-V{position}",
            size=size,
            waist=waist,
            color=color,
            is_active=True,
        )
        variant.inventory = InventoryItem(quantity=quantity, low_stock_threshold=3)
        product.variants.append(variant)

    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def make_address(
    db: Session,
    user_id: uuid.UUID,
    *,
    city: str = "Lahore",
    is_default: bool = True,
    full_name: str = "Test Customer",
) -> CustomerAddress:
    address = CustomerAddress(
        user_id=user_id,
        full_name=full_name,
        phone="+92 300 1234567",
        address_line_1="House 14, Street 7",
        address_line_2="Gulberg III",
        city=city,
        province="Punjab",
        postal_code="54660",
        country="Pakistan",
        is_default=is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def address_payload(**overrides) -> dict:
    """A valid POST /customer/addresses body."""
    payload = {
        "full_name": "Hina Malik",
        "phone": "+92 300 7654321",
        "address_line_1": "Flat 3B, Sea Breeze Apartments",
        "address_line_2": "Clifton Block 5",
        "city": "Karachi",
        "province": "Sindh",
        "postal_code": "75600",
        "country": "Pakistan",
        "is_default": False,
    }
    payload.update(overrides)
    return payload


def make_shop_setup(
    db: Session,
    *,
    stock: int = 5,
    price: Decimal = Decimal("5000.00"),
    sale_price: Decimal | None = None,
) -> tuple[Product, ProductVariant]:
    """A category, brand, and a single-variant product ready to be bought."""
    category = make_category(db)
    brand = make_brand(db)
    product = make_product(
        db,
        category=category,
        brand=brand,
        regular_price=price,
        sale_price=sale_price,
        variants=((None, 32, stock),),
    )
    return product, product.variants[0]


def seed_cart(db: Session, user_id: uuid.UUID, variant_id: uuid.UUID, quantity: int = 1) -> Cart:
    """Put a variant in a user's cart, going through the service so validation runs."""
    from app.services import cart as cart_service

    return cart_service.add_item(db, user_id, variant_id, quantity)


def checkout_payload(address_id: uuid.UUID, **overrides) -> dict:
    payload = {"address_id": str(address_id), "payment_method": "COD"}
    payload.update(overrides)
    return payload


def make_order(
    db: Session,
    user,
    *,
    payment_method: str = "COD",
    stock: int = 5,
    price: Decimal = Decimal("5000.00"),
    quantity: int = 1,
    variant=None,
):
    """Place a real order through the checkout service.

    Goes through `place_order` rather than inserting rows, so the order under test
    has been through the same validation, pricing, stock locking, and payment
    creation as a live purchase.
    """
    from app.schemas.order import CheckoutRequest
    from app.services import orders as order_service

    if variant is None:
        _, variant = make_shop_setup(db, stock=stock, price=price)
    address = make_address(db, user.id)
    seed_cart(db, user.id, variant.id, quantity)

    payload = CheckoutRequest(address_id=address.id, payment_method=payment_method)
    return order_service.place_order(db, user, payload)


def make_shipping_method(
    db: Session,
    *,
    price: Decimal = Decimal("250.00"),
    free_threshold: Decimal | None = Decimal("10000.00"),
    is_active: bool = True,
):
    """An admin-configured delivery method, which pricing prefers over settings."""
    from app.models.enums import DeliveryMethod
    from app.models.shipping import ShippingMethod

    existing = (
        db.query(ShippingMethod).filter(ShippingMethod.code == DeliveryMethod.STANDARD).first()
    )
    method = existing or ShippingMethod(code=DeliveryMethod.STANDARD)
    method.name = "Standard Delivery"
    method.price = price
    method.free_threshold = free_threshold
    method.is_active = is_active
    if existing is None:
        db.add(method)
    db.commit()
    db.refresh(method)
    return method


def make_bank_account(db: Session, *, is_active: bool = True):
    from app.models.shipping import BankAccount

    account = BankAccount(
        bank_name="Test Bank",
        account_title="RG Thrifting Hub",
        account_number=f"ACC-{_suffix()}",
        iban="PK00TEST0000000000000000",
        instructions="Quote your order number.",
        is_active=is_active,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def product_payload(
    *,
    category_id: uuid.UUID,
    brand_id: uuid.UUID | None = None,
    subcategory_id: uuid.UUID | None = None,
    slug: str | None = None,
    sku: str | None = None,
    **overrides,
) -> dict:
    """A valid POST /admin/products body."""
    unique = _suffix()
    payload = {
        "name": "Admin Created Jeans",
        "slug": slug or f"admin-jeans-{unique}",
        "sku": sku or f"ADM-{unique}",
        "short_description": "Created through the admin API",
        "description": "A longer description.",
        "category_id": str(category_id),
        "regular_price": "4500.00",
        "condition": "THRIFT",
        "gender": "MEN",
        "product_type": "JEANS",
        "color": "Indigo",
        "fabric": "Denim",
        "images": [
            {"image_url": "/demo/products/placeholder-1.png", "alt_text": "front", "is_primary": True}
        ],
        "variants": [
            {"sku": f"ADM-{unique}-W30", "waist": 30, "quantity": 4},
            {"sku": f"ADM-{unique}-W32", "waist": 32, "quantity": 0},
        ],
    }
    if brand_id is not None:
        payload["brand_id"] = str(brand_id)
    if subcategory_id is not None:
        payload["subcategory_id"] = str(subcategory_id)
    payload.update(overrides)
    return payload
