"""Catalogue write operations.

Uniqueness is validated here so the API can return a clear 409 instead of
surfacing a raw database integrity error.
"""

import uuid
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.inventory import InventoryItem
from app.models.product import Product, ProductImage
from app.core.config import get_settings
from app.models.variant import ProductVariant
from app.models.user import User
from app.repositories import brand as brand_repo
from app.repositories import category as category_repo
from app.repositories import product as product_repo
from app.schemas.catalog import (
    BrandCreate,
    BrandUpdate,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductImageInput,
    ProductUpdate,
    ProductVariantInput,
    SubcategoryCreate,
    SubcategoryUpdate,
)
from app.services.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.services.inventory import set_quantity as set_inventory_quantity


# ---------------------------------------------------------------------------- brand
def create_brand(db: Session, payload: BrandCreate) -> Brand:
    if brand_repo.slug_exists(db, payload.slug):
        raise ConflictError(f"A brand with slug '{payload.slug}' already exists")
    brand = Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def update_brand(db: Session, brand_id: uuid.UUID, payload: BrandUpdate) -> Brand:
    brand = brand_repo.get_by_id(db, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found")

    changes = payload.model_dump(exclude_unset=True)
    new_slug = changes.get("slug")
    if new_slug and brand_repo.slug_exists(db, new_slug, exclude_id=brand_id):
        raise ConflictError(f"A brand with slug '{new_slug}' already exists")

    for field, value in changes.items():
        setattr(brand, field, value)
    db.commit()
    db.refresh(brand)
    return brand


def deactivate_brand(db: Session, brand_id: uuid.UUID) -> Brand:
    """Soft delete: brands are deactivated so historical product links survive."""
    brand = brand_repo.get_by_id(db, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found")
    brand.is_active = False
    db.commit()
    db.refresh(brand)
    return brand


# ------------------------------------------------------------------------- category
def create_category(db: Session, payload: CategoryCreate) -> Category:
    if category_repo.slug_exists(db, payload.slug):
        raise ConflictError(f"A category with slug '{payload.slug}' already exists")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: uuid.UUID, payload: CategoryUpdate) -> Category:
    category = category_repo.get_by_id(db, category_id)
    if category is None:
        raise NotFoundError("Category not found")

    changes = payload.model_dump(exclude_unset=True)
    new_slug = changes.get("slug")
    if new_slug and category_repo.slug_exists(db, new_slug, exclude_id=category_id):
        raise ConflictError(f"A category with slug '{new_slug}' already exists")

    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


def deactivate_category(db: Session, category_id: uuid.UUID) -> Category:
    category = category_repo.get_by_id(db, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    category.is_active = False
    db.commit()
    db.refresh(category)
    return category


# ---------------------------------------------------------------------- subcategory
def create_subcategory(db: Session, payload: SubcategoryCreate) -> Subcategory:
    if category_repo.get_by_id(db, payload.category_id) is None:
        raise NotFoundError("Parent category not found")
    if category_repo.subcategory_slug_exists(db, payload.category_id, payload.slug):
        raise ConflictError(
            f"Subcategory slug '{payload.slug}' already exists in this category"
        )
    subcategory = Subcategory(**payload.model_dump())
    db.add(subcategory)
    db.commit()
    db.refresh(subcategory)
    return subcategory


def update_subcategory(
    db: Session, subcategory_id: uuid.UUID, payload: SubcategoryUpdate
) -> Subcategory:
    subcategory = category_repo.get_subcategory_by_id(db, subcategory_id)
    if subcategory is None:
        raise NotFoundError("Subcategory not found")

    changes = payload.model_dump(exclude_unset=True)
    target_category_id = changes.get("category_id", subcategory.category_id)
    if "category_id" in changes and category_repo.get_by_id(db, target_category_id) is None:
        raise NotFoundError("Parent category not found")

    target_slug = changes.get("slug", subcategory.slug)
    if category_repo.subcategory_slug_exists(
        db, target_category_id, target_slug, exclude_id=subcategory_id
    ):
        raise ConflictError(f"Subcategory slug '{target_slug}' already exists in this category")

    for field, value in changes.items():
        setattr(subcategory, field, value)
    db.commit()
    db.refresh(subcategory)
    return subcategory


def deactivate_subcategory(db: Session, subcategory_id: uuid.UUID) -> Subcategory:
    subcategory = category_repo.get_subcategory_by_id(db, subcategory_id)
    if subcategory is None:
        raise NotFoundError("Subcategory not found")
    subcategory.is_active = False
    db.commit()
    db.refresh(subcategory)
    return subcategory


# --------------------------------------------------------------------------- product
def _validate_product_relations(
    db: Session, *, category_id: uuid.UUID, subcategory_id: uuid.UUID | None, brand_id: uuid.UUID | None
) -> None:
    if category_repo.get_by_id(db, category_id) is None:
        raise NotFoundError("Category not found")
    if brand_id is not None and brand_repo.get_by_id(db, brand_id) is None:
        raise NotFoundError("Brand not found")
    if subcategory_id is not None:
        subcategory = category_repo.get_subcategory_by_id(db, subcategory_id)
        if subcategory is None:
            raise NotFoundError("Subcategory not found")
        if subcategory.category_id != category_id:
            raise InvalidRequestError("Subcategory does not belong to the selected category")


def _check_image_primaries(images: list[ProductImageInput]) -> None:
    if sum(1 for image in images if image.is_primary) > 1:
        raise InvalidRequestError("Only one image can be marked as primary")


def _check_variant_uniqueness(variants: list[ProductVariantInput]) -> None:
    skus = [variant.sku.strip().casefold() for variant in variants]
    if len(set(skus)) != len(skus):
        raise InvalidRequestError("Variant SKUs must be unique within a product")

    combinations = [
        (
            v.size.strip().casefold() if v.size else None,
            v.waist,
            v.color.strip().casefold() if v.color else None,
        )
        for v in variants
    ]
    if len(set(combinations)) != len(combinations):
        raise InvalidRequestError("Variants must have distinct size/waist/colour combinations")


def _build_images(images: list[ProductImageInput]) -> list[ProductImage]:
    rows = [ProductImage(**image.model_dump()) for image in images]
    # Guarantee a primary image so the storefront always has a thumbnail.
    if rows and not any(row.is_primary for row in rows):
        rows[0].is_primary = True
    return rows


def _build_variants(variants: list[ProductVariantInput]) -> list[ProductVariant]:
    rows: list[ProductVariant] = []
    for payload in variants:
        data = payload.model_dump()
        quantity = data.pop("quantity")
        low_stock_threshold = data.pop("low_stock_threshold")
        variant = ProductVariant(**data)
        # Every variant gets an inventory row, so stock is always a real record
        # rather than an absence that has to be interpreted.
        variant.inventory = InventoryItem(
            quantity=quantity, low_stock_threshold=low_stock_threshold
        )
        rows.append(variant)
    return rows


def create_product(db: Session, payload: ProductCreate) -> Product:
    if product_repo.slug_exists(db, payload.slug):
        raise ConflictError(f"A product with slug '{payload.slug}' already exists")
    if product_repo.sku_exists(db, payload.sku):
        raise ConflictError(f"A product with SKU '{payload.sku}' already exists")

    _validate_product_relations(
        db,
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        brand_id=payload.brand_id,
    )
    _check_image_primaries(payload.images)
    _check_variant_uniqueness(payload.variants)
    if payload.single_piece and (
        len(payload.variants) != 1 or sum(variant.quantity for variant in payload.variants) > 1
    ):
        raise InvalidRequestError("A single-piece product needs one variant and at most one unit in stock")

    for variant in payload.variants:
        if product_repo.variant_sku_exists(db, variant.sku):
            raise ConflictError(f"A variant with SKU '{variant.sku}' already exists")

    fields = payload.model_dump(exclude={"images", "variants"})
    if not fields.get("item_code"):
        prefix = get_settings().item_code_prefix.strip().upper() or "JS"
        for _ in range(10):
            code = f"{prefix}-{secrets.randbelow(90000) + 10000}"
            if db.query(Product.id).filter(Product.item_code == code).first() is None:
                fields["item_code"] = code
                break
        if fields.get("item_code") is None:
            raise ConflictError("Could not generate a unique item code; please retry")
    elif db.query(Product.id).filter(Product.item_code == fields["item_code"]).first():
        raise ConflictError(f"A product with item code '{fields['item_code']}' already exists")
    # Assign an ID explicitly for every create operation. This guarantees that
    # a new product never reuses an ID already associated with a primary image.
    product = Product(id=uuid.uuid4(), **fields)
    product.images = _build_images(payload.images)
    product.variants = _build_variants(payload.variants)

    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "The product conflicts with existing catalogue data. Check its slug, SKU, item code, and primary image, then try again."
        ) from exc
    return product_repo.get_by_id(db, product.id)  # type: ignore[return-value]


def update_product(db: Session, product_id: uuid.UUID, payload: ProductUpdate) -> Product:
    product = product_repo.get_by_id(db, product_id)
    if product is None:
        raise NotFoundError("Product not found")

    changes = payload.model_dump(exclude_unset=True, exclude={"images", "variants"})

    if changes.get("item_code") and db.query(Product.id).filter(
        Product.item_code == changes["item_code"], Product.id != product_id
    ).first():
        raise ConflictError(f"A product with item code '{changes['item_code']}' already exists")
    if changes.get("single_piece") is True and payload.variants is None and product.total_stock > 1:
        raise InvalidRequestError("Reduce stock to one unit before marking this a single-piece product")

    new_slug = changes.get("slug")
    if new_slug and product_repo.slug_exists(db, new_slug, exclude_id=product_id):
        raise ConflictError(f"A product with slug '{new_slug}' already exists")
    new_sku = changes.get("sku")
    if new_sku and product_repo.sku_exists(db, new_sku, exclude_id=product_id):
        raise ConflictError(f"A product with SKU '{new_sku}' already exists")

    _validate_product_relations(
        db,
        category_id=changes.get("category_id", product.category_id),
        subcategory_id=changes.get("subcategory_id", product.subcategory_id),
        brand_id=changes.get("brand_id", product.brand_id),
    )

    for field, value in changes.items():
        setattr(product, field, value)

    # Cross-field rule re-checked against the merged state, since a partial
    # update may change only one side of the comparison.
    effective_sale = changes.get("sale_price", product.sale_price)
    effective_regular = changes.get("regular_price", product.regular_price)
    if effective_sale is not None and effective_sale >= effective_regular:
        raise InvalidRequestError("sale_price must be lower than regular_price")

    if payload.images is not None:
        _check_image_primaries(payload.images)
        # Free the partial unique index on the current primary image before
        # inserting its replacement. SQLAlchemy may otherwise INSERT the new
        # row before it DELETEs the old orphan during the same flush.
        replacement_images = _build_images(payload.images)
        product.images.clear()
        db.flush()
        product.images = replacement_images

    if payload.variants is not None:
        if changes.get("single_piece", product.single_piece) and (
            len(payload.variants) != 1 or sum(variant.quantity for variant in payload.variants) > 1
        ):
            raise InvalidRequestError("A single-piece product needs one variant and at most one unit in stock")
        _check_variant_uniqueness(payload.variants)
        for variant in payload.variants:
            if product_repo.variant_sku_exists(db, variant.sku, exclude_product_id=product_id):
                raise ConflictError(f"A variant with SKU '{variant.sku}' already exists")

        # The product editor resends existing variants (including their SKUs).
        # Replacing those rows with new objects can INSERT a duplicate SKU before
        # SQLAlchemy deletes the old rows. Update matching variants in place so
        # their IDs, orders, and inventory history remain intact.
        existing_variants = list(product.variants)
        used_variant_ids: set[uuid.UUID] = set()
        for variant_payload in payload.variants:
            data = variant_payload.model_dump()
            quantity = data.pop("quantity")
            low_stock_threshold = data.pop("low_stock_threshold")

            variant = next(
                (row for row in existing_variants if row.id not in used_variant_ids and row.sku == data["sku"]),
                None,
            )
            if variant is None:
                incoming_combination = (data.get("size"), data.get("waist"), data.get("color"))
                variant = next(
                    (
                        row for row in existing_variants
                        if row.id not in used_variant_ids
                        and (row.size, row.waist, row.color) == incoming_combination
                    ),
                    None,
                )

            if variant is None:
                variant = ProductVariant(**data)
                variant.inventory = InventoryItem(
                    quantity=quantity, low_stock_threshold=low_stock_threshold
                )
                product.variants.append(variant)
            else:
                used_variant_ids.add(variant.id)
                for field, value in data.items():
                    setattr(variant, field, value)
                if variant.inventory is None:
                    variant.inventory = InventoryItem(
                        quantity=quantity, low_stock_threshold=low_stock_threshold
                    )
                else:
                    variant.inventory.low_stock_threshold = low_stock_threshold
                    set_inventory_quantity(
                        db, variant.id, quantity, note="Updated through the product editor"
                    )

        # Keep omitted variants and their order/inventory history, but make
        # them unavailable instead of physically deleting referenced records.
        for variant in existing_variants:
            if variant.id not in used_variant_ids:
                variant.is_active = False

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "The product update conflicts with existing catalogue data. Check its slug, SKU, item code, variant SKUs, and primary image, then try again."
        ) from exc
    return product_repo.get_by_id(db, product_id)  # type: ignore[return-value]


def deactivate_product(db: Session, product_id: uuid.UUID) -> Product:
    """Soft delete.

    Catalogue rows are deactivated rather than removed: a thrift item is often
    one-of-a-kind and its record stays useful after it stops being sellable.
    """
    product = product_repo.get_by_id(db, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    product.is_active = False
    db.commit()
    db.refresh(product)
    return product


def permanently_delete_product(db: Session, product_id: uuid.UUID, *, actor: User) -> None:
    """Delete a product and dependent catalogue rows in one transaction.

    Order snapshots must remain linked to their historical catalogue IDs, so any
    product that appears in an order is retained and must be archived instead.
    The activity entry is flushed before the product is deleted, then committed
    with the deletion so either both operations persist or neither does.
    """
    from sqlalchemy import or_, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import selectinload

    from app.models.order import OrderItem
    from app.models.variant import ProductVariant
    from app.services import activity

    product = db.execute(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
        )
    ).unique().scalar_one_or_none()
    if product is None:
        raise NotFoundError("Product not found")

    variant_ids = select(ProductVariant.id).where(ProductVariant.product_id == product.id)
    has_orders = db.execute(
        select(
            select(OrderItem.id)
            .where(
                or_(
                    OrderItem.product_id == product.id,
                    OrderItem.product_variant_id.in_(variant_ids),
                )
            )
            .exists()
        )
    ).scalar_one()
    if has_orders:
        raise ConflictError("This product has past orders. Archive it instead.")

    stock_details = [
        {
            "sku": variant.sku,
            "size": variant.size,
            "waist": variant.waist,
            "color": variant.color,
            "remaining_stock": variant.inventory.quantity if variant.inventory else 0,
        }
        for variant in product.variants
    ]
    logged = activity.log(
        db,
        actor=actor,
        action=activity.PRODUCT_PERMANENTLY_DELETED,
        entity_type="product",
        entity_id=product.id,
        description=(
            f"Permanently deleted {product.item_code} — {product.name}; "
            f"SKUs and remaining stock: {stock_details}"
        ),
        metadata={
            "item_code": product.item_code,
            "name": product.name,
            "variants": stock_details,
        },
        commit=False,
    )
    if logged is None:
        db.rollback()
        raise RuntimeError("Could not record the product deletion in the activity log")

    try:
        db.delete(product)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "This product is still referenced by existing records and could not be deleted."
        ) from exc
    except Exception:
        db.rollback()
        raise


def set_variant_quantity(db: Session, variant_id: uuid.UUID, quantity: int) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise NotFoundError("Product variant not found")
    if quantity < 0:
        raise InvalidRequestError("Quantity cannot be negative")

    if variant.inventory is None:
        variant.inventory = InventoryItem(quantity=quantity)
    else:
        variant.inventory.quantity = quantity
    db.commit()
    db.refresh(variant)
    return variant
