"""Sales and discount campaigns.

A `Sale` is a rule, not a copy of the catalogue. Products are never duplicated to
put them on sale; a `SaleTarget` row points at whatever the campaign covers — one
product, a category, a subcategory, a brand, or the whole store.

**Scheduling is time-based in SQL, not a flag someone has to flip.** A sale is
active when `is_active` is true *and* the current time falls inside its window, so
a campaign starts and stops on its own with no cron job and no admin action.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DiscountType, SaleTargetType, SaleType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.brand import Brand
    from app.models.category import Category, Subcategory
    from app.models.product import Product

MONEY = Numeric(10, 2)


class Sale(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_sale_slug"),
        CheckConstraint("discount_value >= 0", name="ck_sale_discount_non_negative"),
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name="ck_sale_window_ordered"
        ),
        # A percentage discount above 100 would produce a negative price.
        CheckConstraint(
            "discount_type <> 'PERCENTAGE' OR discount_value <= 100",
            name="ck_sale_percentage_within_range",
        ),
        # The predicate every price lookup filters on.
        Index("ix_sale_active_window", "is_active", "starts_at", "ends_at"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sale_type: Mapped[SaleType] = mapped_column(
        Enum(SaleType, name="sale_type"), nullable=False, default=SaleType.STANDARD, index=True
    )
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type"), nullable=False
    )
    # Percent for PERCENTAGE, rupees off for FIXED_AMOUNT, absolute price for
    # CUSTOM_PRICE. One column because exactly one interpretation applies at a time.
    discount_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    # Higher wins. The primary, explicit conflict resolver.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null means open-ended, which suits a permanent clearance rail.
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Overrides the default badge wording on product cards.
    badge_text: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    targets: Mapped[list["SaleTarget"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )

    def is_live(self, now: datetime) -> bool:
        """Whether this sale applies at `now`.

        Mirrors the SQL predicate in `sales.active_sales_query` exactly; the two
        must agree or a price would differ between a listing and a detail page.
        """
        if not self.is_active or self.starts_at > now:
            return False
        return self.ends_at is None or self.ends_at > now

    @property
    def is_scheduled(self) -> bool:
        """Configured and enabled, but its start time has not arrived."""
        from app.core.timezones import utc_now

        return self.is_active and self.starts_at > utc_now()

    @property
    def targets_whole_store(self) -> bool:
        return any(target.target_type is SaleTargetType.STORE for target in self.targets)

    def __repr__(self) -> str:
        return f"<Sale {self.name} {self.discount_type}={self.discount_value}>"


class SaleTarget(UUIDPrimaryKeyMixin, Base):
    """What one sale applies to.

    Exactly one of the foreign keys is set, matching `target_type` — enforced by a
    check constraint so a malformed target cannot be stored and then silently
    match nothing (or everything).
    """

    __tablename__ = "sale_targets"
    __table_args__ = (
        CheckConstraint(
            """
            (target_type = 'STORE'
                AND product_id IS NULL AND category_id IS NULL
                AND subcategory_id IS NULL AND brand_id IS NULL)
            OR (target_type = 'PRODUCT' AND product_id IS NOT NULL)
            OR (target_type = 'CATEGORY' AND category_id IS NOT NULL)
            OR (target_type = 'SUBCATEGORY' AND subcategory_id IS NOT NULL)
            OR (target_type = 'BRAND' AND brand_id IS NOT NULL)
            """,
            name="ck_sale_target_shape",
        ),
        # The same sale must not name the same product twice.
        UniqueConstraint(
            "sale_id", "target_type", "product_id", "category_id", "subcategory_id",
            "brand_id",
            name="uq_sale_target_unique",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_sale_target_product", "product_id"),
        Index("ix_sale_target_brand", "brand_id"),
        Index("ix_sale_target_category", "category_id"),
        Index("ix_sale_target_subcategory", "subcategory_id"),
    )

    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[SaleTargetType] = mapped_column(
        Enum(SaleTargetType, name="sale_target_type"), nullable=False, index=True
    )

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brands.id", ondelete="CASCADE"), nullable=True
    )

    sale: Mapped[Sale] = relationship(back_populates="targets")
    product: Mapped["Product | None"] = relationship()
    category: Mapped["Category | None"] = relationship()
    subcategory: Mapped["Subcategory | None"] = relationship()
    brand: Mapped["Brand | None"] = relationship()

    @property
    def specificity(self) -> int:
        from app.models.enums import SALE_TARGET_SPECIFICITY

        return SALE_TARGET_SPECIFICITY[self.target_type]

    def __repr__(self) -> str:
        return f"<SaleTarget {self.target_type}>"
