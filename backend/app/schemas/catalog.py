"""Catalogue schemas: brands, categories, subcategories, products, variants, inventory."""

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import Gender, ProductCondition, ProductType, SaleType, parse_product_condition

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


# --------------------------------------------------------------------------- brand
class BrandBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class BrandRead(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class BrandSummary(BaseModel):
    """Compact brand reference embedded in product payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


# ---------------------------------------------------------------------- subcategory
class SubcategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class SubcategoryCreate(SubcategoryBase):
    category_id: uuid.UUID


class SubcategoryUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class SubcategoryRead(SubcategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SubcategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


# ------------------------------------------------------------------------- category
class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=140, pattern=SLUG_PATTERN)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CategoryDetail(CategoryRead):
    subcategories: list[SubcategoryRead] = Field(default_factory=list)


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


# -------------------------------------------------------------------- product image
class ProductImageInput(BaseModel):
    image_url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=200)
    sort_order: int = 0
    is_primary: bool = False


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_url: str
    alt_text: str | None
    sort_order: int
    is_primary: bool


# ------------------------------------------------------------------ product variant
class ProductVariantInput(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    size: str | None = Field(default=None, max_length=30)
    waist: int | None = Field(default=None, gt=0, le=80)
    color: str | None = Field(default=None, max_length=60)
    variant_name: str | None = Field(default=None, max_length=120)
    price_override: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    sale_price_override: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_active: bool = True
    quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=3, ge=0)

    @model_validator(mode="after")
    def require_a_distinguishing_attribute(self) -> "ProductVariantInput":
        if self.size is None and self.waist is None and self.color is None:
            raise ValueError("a variant needs at least one of size, waist, or color")
        return self


class ProductVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    size: str | None
    waist: int | None
    color: str | None
    variant_name: str | None
    price_override: Decimal | None
    sale_price_override: Decimal | None
    is_active: bool
    label: str
    quantity: int
    in_stock: bool
    is_low_stock: bool


# -------------------------------------------------------------------------- product
class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=50000)
    short_description: str | None = Field(default=None, max_length=50000)
    seo_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=50000)
    sku: str = Field(min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID
    subcategory_id: uuid.UUID | None = None
    regular_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    condition: ProductCondition
    gender: Gender
    product_type: ProductType
    fabric: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    is_featured: bool = False
    is_new_arrival: bool = False
    is_active: bool = True
    single_piece: bool = False

    @field_validator("condition", mode="before")
    @classmethod
    def normalize_condition(cls, value):
        return parse_product_condition(value)

    @field_validator("description", "short_description", "meta_description", mode="before")
    @classmethod
    def sanitize_description(cls, value):
        if value is None:
            return None
        text = re.sub(r"<[^>]*>", "", str(value)).strip()
        return text or None

    @model_validator(mode="after")
    def sale_price_below_regular(self) -> "ProductBase":
        if self.sale_price is not None and self.sale_price >= self.regular_price:
            raise ValueError("sale_price must be lower than regular_price")
        return self


class ProductCreate(ProductBase):
    images: list[ProductImageInput] = Field(default_factory=list)
    variants: list[ProductVariantInput] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Partial update. Only supplied fields are changed.

    Supplying `images` or `variants` replaces that whole collection; omitting
    them leaves the existing rows untouched.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=220, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=50000)
    short_description: str | None = Field(default=None, max_length=50000)
    seo_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=50000)
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    item_code: str | None = Field(default=None, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    single_piece: bool | None = None
    barcode: str | None = Field(default=None, max_length=64)
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    regular_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    condition: ProductCondition | None = None
    gender: Gender | None = None
    product_type: ProductType | None = None
    fabric: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    is_featured: bool | None = None
    is_new_arrival: bool | None = None
    is_active: bool | None = None
    images: list[ProductImageInput] | None = None
    variants: list[ProductVariantInput] | None = None

    @field_validator("condition", mode="before")
    @classmethod
    def normalize_condition(cls, value):
        return None if value is None else parse_product_condition(value)

    @field_validator("description", "short_description", "meta_description", mode="before")
    @classmethod
    def sanitize_description(cls, value):
        if value is None:
            return None
        text = re.sub(r"<[^>]*>", "", str(value)).strip()
        return text or None


class ProductListItem(BaseModel):
    """Shape used by grid/listing views — deliberately lighter than the detail view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    short_description: str | None
    sku: str
    item_code: str
    single_piece: bool
    regular_price: Decimal
    sale_price: Decimal | None
    effective_price: Decimal
    is_on_sale: bool
    discount_percent: int
    condition: ProductCondition
    gender: Gender
    product_type: ProductType
    color: str | None
    fabric: str | None
    is_featured: bool
    is_new_arrival: bool
    is_active: bool
    in_stock: bool
    total_stock: int
    created_at: datetime
    brand: BrandSummary | None
    category: CategorySummary
    subcategory: SubcategorySummary | None
    images: list[ProductImageRead]
    # Attached by services.sales at the repository choke point. Null when no
    # campaign covers this product; `effective_price` above already reflects it.
    sale_pricing: "SalePricingRead | None" = None
    average_rating: float = 0
    review_count: int = 0


class ProductDetail(ProductListItem):
    description: str | None
    seo_title: str | None
    meta_description: str | None
    barcode: str | None
    updated_at: datetime
    variants: list[ProductVariantRead]


class ProductAdminRead(ProductDetail):
    """Admin view. Includes the raw foreign keys needed to populate edit forms."""

    brand_id: uuid.UUID | None
    category_id: uuid.UUID
    subcategory_id: uuid.UUID | None
    has_past_orders: bool = False


class SalePricingRead(BaseModel):
    """Campaign metadata for a product, all computed server-side.

    `effective_price` on the product already reflects the winning campaign, so a
    client never needs to apply a discount itself. This carries the extra detail a
    badge or countdown needs.
    """

    model_config = ConfigDict(from_attributes=True)

    original_price: Decimal
    final_price: Decimal
    discount_amount: Decimal
    discount_percent: int
    sale_id: uuid.UUID | None = None
    sale_name: str | None = None
    sale_type: SaleType | None = None
    badge_text: str | None = None
    # Drives the storefront countdown. Presentation only — the backend decides
    # whether the sale still applies.
    ends_at: datetime | None = None
