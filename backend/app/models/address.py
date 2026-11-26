"""Customer delivery addresses."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class CustomerAddress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An address book entry.

    Orders never point at this row. They keep a snapshot instead, so editing or
    deleting an address cannot rewrite where a past order was sent.
    """

    __tablename__ = "customer_addresses"
    __table_args__ = (
        # Only one default per customer, enforced by a partial unique index.
        Index(
            "uq_address_single_default",
            "user_id",
            unique=True,
            postgresql_where="is_default",
            sqlite_where="is_default",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    province: Mapped[str] = mapped_column(String(80), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(80), nullable=False, default="Pakistan")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship()

    def as_snapshot(self) -> dict[str, str | None]:
        """Flatten into the JSON structure stored on an order."""
        return {
            "full_name": self.full_name,
            "phone": self.phone,
            "address_line_1": self.address_line_1,
            "address_line_2": self.address_line_2,
            "city": self.city,
            "province": self.province,
            "postal_code": self.postal_code,
            "country": self.country,
        }

    def __repr__(self) -> str:
        return f"<CustomerAddress {self.city} user={self.user_id}>"
