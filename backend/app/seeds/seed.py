"""Development seed script.

Idempotent: every record is matched on its natural key (slug or email), so
running it repeatedly updates rather than duplicates.

    python -m app.seeds.seed

Accounts are created with development-only passwords, overridable via
SEED_ADMIN_PASSWORD / SEED_STAFF_PASSWORD / SEED_CUSTOMER_PASSWORD.
"""

import os
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.address import CustomerAddress
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import Gender, ProductCondition, ProductType, UserRole
from app.models.inventory import InventoryItem
from app.models.product import Product, ProductImage
from app.models.user import User
from app.models.variant import ProductVariant
from app.models.shipping import BankAccount, ShippingMethod
from app.seeds.catalog_data import BRANDS, CATEGORIES, PRODUCTS
from app.seeds.commerce_data import BANK_ACCOUNTS, SHIPPING_METHODS
from app.seeds.history import (
    restock_to_catalogue_levels,
    seed_demo_customers,
    seed_order_history,
    seed_sales,
)
from app.seeds.owner_photos import seed_owner_photo_products

# A real, routable-looking domain on purpose: reserved TLDs such as .local and
# .test are rejected by email validation, which would make these demo accounts
# impossible to sign in with.
SEED_ACCOUNTS = (
    ("admin@rgthriftinghub.pk", "Ayesha", "Rahman", UserRole.ADMIN, "SEED_ADMIN_PASSWORD"),
    ("staff@rgthriftinghub.pk", "Bilal", "Khan", UserRole.STAFF, "SEED_STAFF_PASSWORD"),
    ("customer@rgthriftinghub.pk", "Hina", "Malik", UserRole.CUSTOMER, "SEED_CUSTOMER_PASSWORD"),
)
def seed_accounts(db: Session) -> list[User]:
    users: list[User] = []
    for email, first_name, last_name, role, password_env in SEED_ACCOUNTS:
        password = os.getenv(password_env)
        if not password:
            raise RuntimeError(f"{password_env} must be set before running the seed script")
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=hash_password(password))
            db.add(user)
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_active = True
        user.is_verified = True
        users.append(user)
    db.flush()
    return users


def seed_addresses(db: Session, users: list[User]) -> int:
    """Give every seeded account a default delivery address.

    Checkout requires one, so seeding it means the flow is exercisable straight
    after `python -m app.seeds.seed` with no manual setup.
    """
    created = 0
    for user in users:
        existing = db.execute(
            select(CustomerAddress).where(CustomerAddress.user_id == user.id)
        ).scalars().first()
        if existing is not None:
            continue

        db.add(
            CustomerAddress(
                user_id=user.id,
                full_name=f"{user.first_name} {user.last_name}",
                phone="+92 300 1234567",
                address_line_1="House 14, Street 7, Gulberg III",
                address_line_2="Near Main Market",
                city="Lahore",
                province="Punjab",
                postal_code="54660",
                country="Pakistan",
                is_default=True,
            )
        )
        created += 1
    db.flush()
    return created


def seed_shipping_methods(db: Session) -> int:
    """Create the configurable delivery methods.

    Once these exist, checkout prices delivery from the database rather than the
    environment fallback, which is what makes the charge admin-editable.
    """
    for data in SHIPPING_METHODS:
        method = db.execute(
            select(ShippingMethod).where(ShippingMethod.code == data.code)
        ).scalar_one_or_none()
        if method is None:
            method = ShippingMethod(code=data.code)
            db.add(method)
        method.name = data.name
        method.description = data.description
        method.price = data.price
        method.free_threshold = data.free_threshold
        method.estimated_days_min = data.estimated_days_min
        method.estimated_days_max = data.estimated_days_max
        method.sort_order = data.sort_order
        method.is_active = True
    db.flush()
    return len(SHIPPING_METHODS)


def seed_bank_accounts(db: Session) -> int:
    """Create clearly-marked placeholder bank details for the transfer flow."""
    for data in BANK_ACCOUNTS:
        account = db.execute(
            select(BankAccount).where(BankAccount.account_number == data.account_number)
        ).scalar_one_or_none()
        if account is None:
            account = BankAccount(account_number=data.account_number)
            db.add(account)
        account.bank_name = data.bank_name
        account.account_title = data.account_title
        account.iban = data.iban
        account.branch = data.branch
        account.instructions = data.instructions
        account.sort_order = data.sort_order
        account.is_active = True
    db.flush()
    return len(BANK_ACCOUNTS)


def seed_taxonomy(db: Session) -> tuple[dict[str, Category], dict[tuple[str, str], Subcategory]]:
    categories: dict[str, Category] = {}
    subcategories: dict[tuple[str, str], Subcategory] = {}

    for data in CATEGORIES:
        category = db.execute(
            select(Category).where(Category.slug == data.slug)
        ).scalar_one_or_none()
        if category is None:
            category = Category(slug=data.slug)
            db.add(category)
        category.name = data.name
        category.description = data.description
        category.sort_order = data.sort_order
        category.image_url = f"/demo/categories/{data.slug}.png"
        category.is_active = True
        db.flush()
        categories[data.slug] = category

        for sub_data in data.subcategories:
            subcategory = db.execute(
                select(Subcategory).where(
                    Subcategory.category_id == category.id, Subcategory.slug == sub_data.slug
                )
            ).scalar_one_or_none()
            if subcategory is None:
                subcategory = Subcategory(category_id=category.id, slug=sub_data.slug)
                db.add(subcategory)
            subcategory.name = sub_data.name
            subcategory.sort_order = sub_data.sort_order
            subcategory.is_active = True
            db.flush()
            subcategories[(data.slug, sub_data.slug)] = subcategory

    return categories, subcategories


def seed_brands(db: Session) -> dict[str, Brand]:
    brands: dict[str, Brand] = {}
    for data in BRANDS:
        brand = db.execute(select(Brand).where(Brand.slug == data.slug)).scalar_one_or_none()
        if brand is None:
            brand = Brand(slug=data.slug)
            db.add(brand)
        brand.name = data.name
        brand.description = data.description
        brand.logo_url = f"/demo/brands/{data.slug}.png"
        brand.is_active = True
        db.flush()
        brands[data.slug] = brand
    return brands


def seed_products(
    db: Session,
    categories: dict[str, Category],
    subcategories: dict[tuple[str, str], Subcategory],
    brands: dict[str, Brand],
) -> list[Product]:
    products: list[Product] = []

    for data in PRODUCTS:
        product = db.execute(select(Product).where(Product.slug == data.slug)).scalar_one_or_none()
        if product is None:
            product = Product(slug=data.slug)
            db.add(product)

        product.name = data.name
        product.sku = data.sku
        product.barcode = data.barcode
        product.description = data.description
        product.short_description = data.short_description
        product.brand_id = brands[data.brand_slug].id if data.brand_slug else None
        product.category_id = categories[data.category_slug].id
        product.subcategory_id = subcategories[(data.category_slug, data.subcategory_slug)].id
        product.regular_price = data.regular_price
        product.sale_price = data.sale_price
        product.condition = ProductCondition(data.condition)
        product.gender = Gender(data.gender)
        product.product_type = ProductType(data.product_type)
        product.color = data.color
        product.fabric = data.fabric
        product.is_featured = data.is_featured
        product.is_new_arrival = data.is_new_arrival
        product.is_active = True
        db.flush()

        _sync_images(db, product, data.name, data.image_count)
        _sync_variants(db, product, data)
        products.append(product)

    return products


def _sync_images(db: Session, product: Product, name: str, image_count: int) -> None:
    """Replace the image set so re-running the seed cannot accumulate duplicates."""
    for existing in list(product.images):
        db.delete(existing)
    db.flush()

    for index in range(image_count):
        db.add(
            ProductImage(
                product_id=product.id,
                image_url=f"/demo/products/{product.slug}-{index + 1}.png",
                alt_text=f"{name} — view {index + 1}",
                sort_order=index,
                is_primary=index == 0,
            )
        )
    db.flush()


def _sync_variants(db: Session, product: Product, data) -> None:
    wanted_skus = {f"{data.sku}-{variant.sku_suffix}" for variant in data.variants}

    for existing in list(product.variants):
        if existing.sku not in wanted_skus:
            db.delete(existing)
    db.flush()

    for variant_data in data.variants:
        sku = f"{data.sku}-{variant_data.sku_suffix}"
        variant = db.execute(
            select(ProductVariant).where(ProductVariant.sku == sku)
        ).scalar_one_or_none()
        if variant is None:
            variant = ProductVariant(product_id=product.id, sku=sku)
            db.add(variant)

        variant.size = variant_data.size
        variant.waist = variant_data.waist
        variant.color = variant_data.color or data.color
        variant.variant_name = None
        variant.is_active = True
        db.flush()

        if variant.inventory is None:
            variant.inventory = InventoryItem(quantity=variant_data.quantity)
        variant.inventory.quantity = variant_data.quantity
        variant.inventory.low_stock_threshold = variant_data.low_stock_threshold
        db.flush()


def run() -> None:
    if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
        raise RuntimeError("The development seed script cannot run when ENVIRONMENT=production")
    if not os.getenv("SEED_ADMIN_PASSWORD"):
        raise RuntimeError("SEED_ADMIN_PASSWORD must be set before running the seed script")
    db = SessionLocal()
    try:
        users = seed_accounts(db)
        addresses_created = seed_addresses(db, users)
        shipping_methods = seed_shipping_methods(db)
        bank_accounts = seed_bank_accounts(db)
        categories, subcategories = seed_taxonomy(db)
        brands = seed_brands(db)
        products = seed_products(db, categories, subcategories, brands)
        owner_photo_products = seed_owner_photo_products(db, categories, subcategories, brands)
        products.extend(owner_photo_products)
        db.commit()

        # Demo history so the dashboard and analytics have something real to show.
        demo_customers = seed_demo_customers(db)
        campaigns = seed_sales(db)
        history = seed_order_history(db, demo_customers)
        # Demo orders consumed real stock; put it back so the storefront looks
        # healthy and the documented per-waist test matrix still holds.
        restocked = restock_to_catalogue_levels(db)
        db.commit()

        variant_count = sum(len(product.variants) for product in products)
        in_stock = sum(
            1 for product in products for variant in product.variants if variant.quantity > 0
        )
        out_of_stock = variant_count - in_stock
        on_sale = sum(1 for product in products if product.sale_price is not None)
        featured = sum(1 for product in products if product.is_featured)
        new_arrivals = sum(1 for product in products if product.is_new_arrival)
        total_value = sum(
            (product.effective_price for product in products), start=Decimal("0")
        )

        print("Seed complete")
        print(f"  accounts          {len(users)}")
        print(f"  addresses added   {addresses_created}")
        print(f"  categories        {len(categories)}")
        print(f"  subcategories     {len(subcategories)}")
        print(f"  brands            {len(brands)}")
        print(f"  products          {len(products)}")
        print(f"  owner photo items {len(owner_photo_products)}")
        print(f"  variants          {variant_count} ({in_stock} in stock, {out_of_stock} out)")
        print(f"  on sale           {on_sale}")
        print(f"  featured          {featured}")
        print(f"  new arrivals      {new_arrivals}")
        print(f"  catalogue value   PKR {total_value:,}")
        print(f"  shipping methods  {shipping_methods}")
        print(f"  bank accounts     {bank_accounts} (placeholder — replace before go-live)")
        print(f"  demo customers    {len(demo_customers)}")
        print(f"  sale campaigns    {len(campaigns)}")
        print(
            f"  demo orders       {history['orders']}"
            + (f" (skipped, {history['skipped']} already present)" if history["skipped"] else "")
        )
        print(f"  variants restocked {restocked}")
        print()
        print("  Accounts (development only; configure seed passwords via environment):")
        for email, _, _, role, _ in SEED_ACCOUNTS:
            print(f"    {role.value:9} {email}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
