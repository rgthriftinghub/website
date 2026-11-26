"""Editable public pages and small storefront settings."""
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class StoreContent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_content"
    __table_args__ = (UniqueConstraint("key", name="uq_store_content_key"),)

    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
