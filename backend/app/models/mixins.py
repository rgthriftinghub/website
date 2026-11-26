"""Reusable column groups shared by the catalogue and account models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    """UUID primary key.

    UUIDs keep identifiers non-sequential, so public URLs and admin ids do not
    leak row counts or allow trivial enumeration of the catalogue.
    """

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Creation and modification timestamps.

    The Python-side `default` is what ORM inserts use, and it is deliberately
    per-row: PostgreSQL's `now()` is fixed for the whole transaction, so relying
    on `server_default` alone would give every row inserted together an
    identical `created_at` and make "newest first" ordering arbitrary. The
    server defaults remain as a safety net for inserts made outside the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
    )


class CreatedAtMixin:
    """Creation timestamp only, for append-style rows such as product images."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=func.now()
    )
