"""Admin operational models: activity log, notifications, permissions, notes, imports."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AdminNotificationSeverity,
    AdminNotificationType,
    ImportStatus,
    Permission,
)
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.order import SNAPSHOT_JSON
from app.models.user import User


class AdminActivityLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only record of consequential admin actions.

    `metadata_json` holds a small before/after diff. It is passed through the same
    redaction helper the payment layer uses, so a password or key can never land
    here even if a caller is careless.

    Nothing updates or deletes these rows.
    """

    __tablename__ = "admin_activity_logs"
    __table_args__ = (
        Index("ix_activity_entity", "entity_type", "entity_id"),
        Index("ix_activity_user_created", "user_id", "created_at"),
        Index("ix_activity_action_created", "action", "created_at"),
    )

    # SET NULL, not CASCADE: removing a staff account must not erase the audit trail.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Denormalised so the log stays readable after an account is deleted.
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(SNAPSHOT_JSON, nullable=True)

    user: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<AdminActivityLog {self.action} {self.entity_type}>"


class AdminNotification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Operational alert for staff.

    `dedupe_key` prevents the same condition raising a new row every time it is
    re-detected — one open "low stock" alert per variant, not one per page load.
    """

    __tablename__ = "admin_notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_admin_notification_dedupe"),
        Index("ix_notification_unread", "is_read", "created_at"),
    )

    type: Mapped[AdminNotificationType] = mapped_column(
        Enum(AdminNotificationType, name="admin_notification_type"), nullable=False, index=True
    )
    severity: Mapped[AdminNotificationSeverity] = mapped_column(
        Enum(AdminNotificationSeverity, name="admin_notification_severity"),
        nullable=False,
        default=AdminNotificationSeverity.INFO,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deep link into the admin UI, e.g. /admin/orders/<id>.
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AdminNotification {self.type} read={self.is_read}>"


class StaffPermissionGrant(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One permission granted to one staff account.

    A row-per-grant rather than a bitmask or JSON array, so a grant is auditable:
    who was given what, and when.

    ADMIN accounts are not represented here — they implicitly hold everything.
    """

    __tablename__ = "staff_permission_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "permission", name="uq_staff_permission"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[Permission] = mapped_column(
        Enum(Permission, name="staff_permission"), nullable=False
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<StaffPermissionGrant {self.permission}>"


class CustomerNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Private staff note about a customer.

    Never serialised onto any customer-facing response model. The only routes that
    read it require CUSTOMER_VIEW.
    """

    __tablename__ = "customer_notes"
    __table_args__ = (Index("ix_customer_note_customer", "customer_id", "created_at"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<CustomerNote customer={self.customer_id}>"


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A parsed, validated upload awaiting confirmation.

    Uploaded rows are **never** written straight to the catalogue. They are parsed
    into `rows_json` and validated first; only an explicit confirm step applies
    them. That is what makes the preview meaningful rather than decorative.
    """

    __tablename__ = "import_batches"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status"),
        nullable=False,
        default=ImportStatus.PENDING,
        index=True,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Parsed rows with their per-row validation verdicts. Bounded by the row cap in
    # the import service, so this stays a reasonable size.
    rows_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        SNAPSHOT_JSON, nullable=True
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_committable(self) -> bool:
        return self.status is ImportStatus.VALIDATED and self.valid_rows > 0

    def __repr__(self) -> str:
        return f"<ImportBatch {self.filename} {self.status}>"
