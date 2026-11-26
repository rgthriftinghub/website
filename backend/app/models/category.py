"""Category and subcategory models."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="Subcategory.sort_order",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class Subcategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subcategories"
    __table_args__ = (
        # Slugs are unique within their parent category, so "men/jackets" and
        # "women/jackets" can coexist.
        UniqueConstraint("category_id", "slug", name="uq_subcategory_category_slug"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    category: Mapped[Category] = relationship(back_populates="subcategories")
    products: Mapped[list["Product"]] = relationship(back_populates="subcategory")

    def __repr__(self) -> str:
        return f"<Subcategory {self.slug}>"
