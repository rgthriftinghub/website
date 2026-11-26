"""Product persistence and catalogue querying.

All filtering, searching, sorting, and pagination is expressed as SQL so the
database does the work and only one page of rows is ever transferred.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.inventory import InventoryItem
from app.models.product import Product
from app.models.variant import ProductVariant
from app.schemas.query import Availability, ProductQuery, ProductSort
from app.services import sales
from app.models.review import ProductReview
from app.models.order import Order, OrderItem
from app.models.enums import OrderStatus

# Effective selling price: the sale price when present, otherwise the regular price.
EFFECTIVE_PRICE = func.coalesce(Product.sale_price, Product.regular_price)

# Adding a sort option is a one-line change here plus one enum member.
SORT_CLAUSES: dict[ProductSort, tuple[ColumnElement, ...]] = {
    ProductSort.NEWEST: (Product.created_at.desc(), Product.id.desc()),
    ProductSort.PRICE_LOW: (EFFECTIVE_PRICE.asc(), Product.id.desc()),
    ProductSort.PRICE_HIGH: (EFFECTIVE_PRICE.desc(), Product.id.desc()),
    ProductSort.BEST_SELLING: (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.product_id == Product.id, Order.order_status != OrderStatus.CANCELLED)
        .correlate(Product)
        .scalar_subquery()
        .desc(),
        Product.id.desc(),
    ),
    ProductSort.HIGHEST_RATED: (func.coalesce(func.avg(ProductReview.rating), 0).desc(), Product.id.desc()),
}


def _eager_loads() -> tuple:
    """Load images and variants up front to avoid per-row follow-up queries."""
    return (
        selectinload(Product.images),
        selectinload(Product.variants).selectinload(ProductVariant.inventory),
    )


def _variant_conditions(query: ProductQuery) -> list[ColumnElement[bool]]:
    """Variant-level predicates, applied to a single correlated EXISTS.

    Combining them into one EXISTS is what makes "waist 32 and in stock" mean
    *the same variant* is both waist 32 and in stock, rather than the product
    merely having some waist-32 variant and some other in-stock variant.
    """
    conditions: list[ColumnElement[bool]] = [ProductVariant.is_active.is_(True)]
    if query.size is not None:
        conditions.append(func.lower(ProductVariant.size) == query.size.strip().lower())
    if query.waist is not None:
        conditions.append(ProductVariant.waist == query.waist)
    if query.availability is Availability.IN_STOCK:
        conditions.append(InventoryItem.quantity > 0)
    return conditions


def _apply_filters(stmt: Select, query: ProductQuery, *, include_inactive: bool) -> Select:
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    if query.category:
        stmt = stmt.where(
            Product.category_id.in_(
                select(Category.id).where(func.lower(Category.slug) == query.category.strip().lower())
            )
        )
    if query.subcategory:
        stmt = stmt.where(
            Product.subcategory_id.in_(
                select(Subcategory.id).where(
                    func.lower(Subcategory.slug) == query.subcategory.strip().lower()
                )
            )
        )
    if query.brand:
        term = query.brand.strip().lower()
        stmt = stmt.where(
            Product.brand_id.in_(
                select(Brand.id).where(
                    or_(func.lower(Brand.slug) == term, func.lower(Brand.name) == term)
                )
            )
        )

    if query.gender is not None:
        stmt = stmt.where(Product.gender == query.gender)
    if query.condition is not None:
        stmt = stmt.where(Product.condition == query.condition)
    if query.product_type is not None:
        stmt = stmt.where(Product.product_type == query.product_type)
    if query.color:
        stmt = stmt.where(func.lower(Product.color) == query.color.strip().lower())
    if query.fabric:
        stmt = stmt.where(func.lower(Product.fabric) == query.fabric.strip().lower())

    if query.is_featured is not None:
        stmt = stmt.where(Product.is_featured.is_(query.is_featured))
    if query.is_new_arrival is not None:
        stmt = stmt.where(Product.is_new_arrival.is_(query.is_new_arrival))

    if query.min_price is not None:
        stmt = stmt.where(EFFECTIVE_PRICE >= query.min_price)
    if query.max_price is not None:
        stmt = stmt.where(EFFECTIVE_PRICE <= query.max_price)

    # One correlated EXISTS covering size, waist, and in-stock availability.
    variant_conditions = _variant_conditions(query)
    needs_variant_clause = (
        query.size is not None
        or query.waist is not None
        or query.availability is not None
    )
    if needs_variant_clause:
        variant_exists = (
            select(ProductVariant.id)
            .outerjoin(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
            .where(ProductVariant.product_id == Product.id, and_(*variant_conditions))
            .exists()
        )
        if query.availability is Availability.OUT_OF_STOCK:
            # No active variant with stock -> the product as a whole is unavailable.
            in_stock_exists = (
                select(ProductVariant.id)
                .join(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
                .where(
                    ProductVariant.product_id == Product.id,
                    ProductVariant.is_active.is_(True),
                    InventoryItem.quantity > 0,
                )
                .exists()
            )
            stmt = stmt.where(~in_stock_exists)
            if query.size is not None or query.waist is not None:
                stmt = stmt.where(variant_exists)
        else:
            stmt = stmt.where(variant_exists)

    if query.search:
        stmt = _apply_search(stmt, query.search)

    return stmt


def _apply_search(stmt: Select, raw_term: str) -> Select:
    """Case-insensitive search over names, product/variant SKUs, brands, and categories.

    Each whitespace-separated word must match at least one of those fields, so
    "levis jeans" finds a Levi's product of type jeans. Plain ILIKE keeps this
    inside PostgreSQL with no extra search infrastructure.
    """
    words = [word for word in raw_term.strip().split() if word]
    for word in words:
        pattern = f"%{word.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name).like(pattern),
                func.lower(Product.sku).like(pattern),
                func.lower(Product.item_code).like(pattern),
                Product.id.in_(select(ProductVariant.product_id).where(func.lower(ProductVariant.sku).like(pattern))),
                Product.brand_id.in_(
                    select(Brand.id).where(func.lower(Brand.name).like(pattern))
                ),
                Product.category_id.in_(
                    select(Category.id).where(func.lower(Category.name).like(pattern))
                ),
            )
        )
    return stmt


def list_products(
    db: Session, query: ProductQuery, *, include_inactive: bool = False
) -> tuple[Sequence[Product], int]:
    """Return one page of products plus the total number of matches."""
    count_stmt = _apply_filters(
        select(func.count()).select_from(Product), query, include_inactive=include_inactive
    )
    total = db.execute(count_stmt).scalar_one()

    if total == 0:
        return [], 0

    items_stmt = _apply_filters(select(Product), query, include_inactive=include_inactive)
    if query.sort is ProductSort.HIGHEST_RATED:
        items_stmt = items_stmt.outerjoin(ProductReview, ProductReview.product_id == Product.id).group_by(Product.id)
    items_stmt = (
        items_stmt.order_by(*SORT_CLAUSES[query.sort])
        .offset(query.offset)
        .limit(query.page_size)
        .options(*_eager_loads())
    )
    items = db.execute(items_stmt).unique().scalars().all()
    # Resolve campaign pricing here, at the single choke point every product read
    # passes through, so listings, detail pages, the cart, and admin views are all
    # sale-aware without any call site knowing about sales.
    sales.attach_pricing(db, items)
    rows = db.execute(select(ProductReview.product_id, func.avg(ProductReview.rating), func.count(ProductReview.id)).where(ProductReview.product_id.in_([p.id for p in items])).group_by(ProductReview.product_id)).all() if items else []
    stats = {product_id: (average, count) for product_id, average, count in rows}
    for item in items:
        avg, count = stats.get(item.id, (None, 0))
        item.average_rating = round(float(avg or 0), 1)
        item.review_count = count
    return items, total


def get_by_slug(db: Session, slug: str, *, include_inactive: bool = False) -> Product | None:
    stmt = select(Product).where(Product.slug == slug).options(*_eager_loads())
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    product = db.execute(stmt).unique().scalar_one_or_none()
    sales.attach_pricing_to_product(db, product)
    if product:
        avg, count = db.execute(select(func.avg(ProductReview.rating), func.count(ProductReview.id)).where(ProductReview.product_id == product.id)).one()
        product.average_rating = round(float(avg or 0), 1)
        product.review_count = count
    return product


def get_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
    stmt = select(Product).where(Product.id == product_id).options(*_eager_loads())
    product = db.execute(stmt).unique().scalar_one_or_none()
    sales.attach_pricing_to_product(db, product)
    return product


def get_active_by_ids(db: Session, product_ids: Sequence[uuid.UUID]) -> list[Product]:
    if not product_ids:
        return []
    rows = db.execute(
        select(Product).where(Product.is_active.is_(True), Product.id.in_(product_ids))
        .options(*_eager_loads())
    ).unique().scalars().all()
    by_id = {row.id: row for row in rows}
    products = [by_id[item_id] for item_id in product_ids if item_id in by_id]
    sales.attach_pricing(db, products)
    return products


def slug_exists(db: Session, slug: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(exists().where(Product.slug == slug))
    if exclude_id is not None:
        stmt = select(exists().where(Product.slug == slug, Product.id != exclude_id))
    return bool(db.execute(stmt).scalar())


def sku_exists(db: Session, sku: str, *, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(exists().where(Product.sku == sku))
    if exclude_id is not None:
        stmt = select(exists().where(Product.sku == sku, Product.id != exclude_id))
    return bool(db.execute(stmt).scalar())


def variant_sku_exists(db: Session, sku: str, *, exclude_product_id: uuid.UUID | None = None) -> bool:
    stmt = select(exists().where(ProductVariant.sku == sku))
    if exclude_product_id is not None:
        stmt = select(
            exists().where(
                ProductVariant.sku == sku, ProductVariant.product_id != exclude_product_id
            )
        )
    return bool(db.execute(stmt).scalar())


def distinct_filter_values(db: Session) -> dict[str, list]:
    """Distinct colours, fabrics, sizes, and waists present on active products.

    Used to populate the storefront filter sidebar with real options instead of
    a hardcoded list.
    """
    colors = db.execute(
        select(Product.color)
        .where(Product.is_active.is_(True), Product.color.is_not(None))
        .distinct()
        .order_by(Product.color)
    ).scalars().all()
    fabrics = db.execute(
        select(Product.fabric)
        .where(Product.is_active.is_(True), Product.fabric.is_not(None))
        .distinct()
        .order_by(Product.fabric)
    ).scalars().all()
    sizes = db.execute(
        select(ProductVariant.size)
        .where(ProductVariant.is_active.is_(True), ProductVariant.size.is_not(None))
        .distinct()
        .order_by(ProductVariant.size)
    ).scalars().all()
    waists = db.execute(
        select(ProductVariant.waist)
        .where(ProductVariant.is_active.is_(True), ProductVariant.waist.is_not(None))
        .distinct()
        .order_by(ProductVariant.waist)
    ).scalars().all()
    price_bounds = db.execute(
        select(func.min(EFFECTIVE_PRICE), func.max(EFFECTIVE_PRICE)).where(
            Product.is_active.is_(True)
        )
    ).one()

    return {
        "colors": list(colors),
        "fabrics": list(fabrics),
        "sizes": list(sizes),
        "waists": list(waists),
        "min_price": price_bounds[0],
        "max_price": price_bounds[1],
    }
