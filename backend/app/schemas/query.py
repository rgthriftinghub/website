"""Query parameter schemas for catalogue listing endpoints."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import Gender, ProductCondition, ProductType, parse_product_condition
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class ProductSort(StrEnum):
    """Sort options.

    New options (best selling, highest rated) are added by extending this enum
    and adding one entry to `SORT_CLAUSES` in the product repository — the
    endpoint itself does not change.
    """

    NEWEST = "newest"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    BEST_SELLING = "best_selling"
    HIGHEST_RATED = "highest_rated"


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


class ProductQuery(BaseModel):
    """Combinable catalogue filters.

    Every field is optional and all supplied fields are ANDed together, so
    `?category=men&brand=levis&waist=32&condition=THRIFT` narrows progressively.
    All filtering is translated to SQL; nothing is filtered in Python.
    """

    # Relationship filters accept a slug (brand also accepts its display name).
    category: str | None = Field(default=None, max_length=140)
    subcategory: str | None = Field(default=None, max_length=140)
    brand: str | None = Field(default=None, max_length=140)

    gender: Gender | None = None
    condition: ProductCondition | None = None
    product_type: ProductType | None = None
    color: str | None = Field(default=None, max_length=60)
    fabric: str | None = Field(default=None, max_length=80)

    is_featured: bool | None = None
    is_new_arrival: bool | None = None

    min_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    # Variant-level filters.
    size: str | None = Field(default=None, max_length=30)
    waist: int | None = Field(default=None, gt=0, le=80)
    availability: Availability | None = None

    search: str | None = Field(default=None, max_length=120)
    sort: ProductSort = ProductSort.NEWEST

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @field_validator("condition", mode="before")
    @classmethod
    def normalize_condition(cls, value):
        return None if value is None else parse_product_condition(value)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @model_validator(mode="after")
    def check_price_range(self) -> "ProductQuery":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must not exceed max_price")
        return self


class AdminProductQuery(ProductQuery):
    """Admin listing filters.

    `include_inactive` lives on the model rather than as a separate endpoint
    argument because FastAPI stops expanding a Pydantic query-params model into
    individual parameters as soon as another scalar query parameter is declared
    beside it.
    """

    include_inactive: bool = True
