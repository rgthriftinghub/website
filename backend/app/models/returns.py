"""Return and exchange request foundation.

This records the customer's request and the staff decision. Courier pickup and
refund processing are deliberately out of scope for this phase; when they arrive
they attach to this row rather than replacing it.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReturnRequestStatus, ReturnRequestType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User

if TYPE_CHECKING:
    from app.models.order import Order


class ReturnRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "return_requests"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[ReturnRequestType] = mapped_column(
        Enum(ReturnRequestType, name="return_request_type"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReturnRequestStatus] = mapped_column(
        Enum(ReturnRequestStatus, name="return_request_status"),
        nullable=False,
        default=ReturnRequestStatus.REQUESTED,
        index=True,
    )
    # Staff-only decision note; not exposed on customer responses.
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="return_requests")
    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<ReturnRequest {self.type} {self.status}>"
