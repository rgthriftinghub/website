"""Wishlist.

Saved against the product rather than a variant: a shopper saves "these jeans",
then picks a size when they are ready to buy.
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.product import Product


class WishlistItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )

    product: Mapped[Product] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"<WishlistItem user={self.user_id} product={self.product_id}>"
