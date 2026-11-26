"""Product and product image models."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import Gender, ProductCondition, ProductType
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.variant import ProductVariant

# Money is always Numeric, never float: binary floating point cannot represent
# decimal currency amounts exactly.
MONEY = Numeric(10, 2)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A catalogue item.

    Stock never lives here. Quantities belong to :class:`ProductVariant` via
    :class:`InventoryItem`, because a thrift garment's availability differs per
    size/waist. Extra descriptive attributes should be added as columns here or
    as a new related table, not as an EAV key/value store.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("regular_price >= 0", name="ck_product_regular_price_non_negative"),
        CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0", name="ck_product_sale_price_non_negative"
        ),
        CheckConstraint(
            "sale_price IS NULL OR sale_price < regular_price",
            name="ck_product_sale_price_below_regular",
        ),
        # Composite index matching the storefront's default listing query:
        # active products ordered by newest first.
        Index("ix_product_active_created", "is_active", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(400), nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(320), nullable=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    item_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        default=lambda: f"JS-{uuid.uuid4().int % 90000 + 10000}",
    )
    single_piece: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Nullable and unique: many thrift items simply have no barcode, and
    # PostgreSQL permits multiple NULLs under a unique constraint.
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    # Unbranded thrift items are common, so brand is optional.
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    regular_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    condition: Mapped[ProductCondition] = mapped_column(
        Enum(ProductCondition, name="product_condition"), nullable=False, index=True
    )
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"), nullable=False, index=True)
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, name="product_type"), nullable=False, index=True
    )
    fabric: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)

    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_new_arrival: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    brand: Mapped[Brand | None] = relationship(back_populates="products", lazy="joined")
    category: Mapped[Category] = relationship(back_populates="products", lazy="joined")
    subcategory: Mapped[Subcategory | None] = relationship(back_populates="products", lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.waist, ProductVariant.size",
    )

    @property
    def manual_price(self) -> Decimal:
        """Price from this product's own columns, ignoring any campaign."""
        return self.sale_price if self.sale_price is not None else self.regular_price

    @property
    def effective_price(self) -> Decimal:
        """The authoritative selling price, campaign included.

        A resolved `Sale` is attached transiently by `services.sales` before
        serialisation. Routing it through this one property means every existing
        consumer — listings, detail pages, the cart, and checkout — became
        sale-aware without a single call site changing.
        """
        campaign = getattr(self, "campaign_price", None)
        if campaign is not None:
            return campaign
        return self.manual_price

    @property
    def is_on_sale(self) -> bool:
        return self.effective_price < self.regular_price

    @property
    def discount_amount(self) -> Decimal:
        saving = self.regular_price - self.effective_price
        return saving if saving > 0 else Decimal("0")

    @property
    def discount_percent(self) -> int:
        if self.regular_price <= 0 or self.discount_amount <= 0:
            return 0
        return int(round((self.discount_amount / self.regular_price) * 100))

    @property
    def total_stock(self) -> int:
        """Sum of stock across active variants, read from the inventory rows."""
        return sum(v.quantity for v in self.variants if v.is_active)

    @property
    def in_stock(self) -> bool:
        return self.total_stock > 0

    def __repr__(self) -> str:
        return f"<Product {self.slug}>"


class ProductImage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An image belonging to a product.

    Only the URL is stored for now; object-storage upload can be added later
    without touching this table's shape. No maximum image count is encoded here.
    """

    __tablename__ = "product_images"
    __table_args__ = (
        # At most one primary image per product, enforced by a partial unique index.
        Index(
            "uq_product_image_single_primary",
            "product_id",
            unique=True,
            postgresql_where="is_primary",
            sqlite_where="is_primary",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product: Mapped[Product] = relationship(back_populates="images")

    def __repr__(self) -> str:
        return f"<ProductImage {self.image_url}>"
