"""Return and exchange requests.

Foundation only: this captures the customer's request and the staff decision.
Courier pickup, refund processing, and automatic restocking are Phase 4 — an
approved request does not move stock or money here.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import OrderStatus, ReturnRequestStatus
from app.models.order import Order
from app.models.returns import ReturnRequest
from app.models.user import User
from app.schemas.order import ReturnRequestCreate, ReturnRequestDecision
from app.services import notifications, orders as order_service
from app.services.exceptions import ConflictError, InvalidRequestError, NotFoundError

# A request only makes sense once the customer has the goods.
ELIGIBLE_ORDER_STATUSES = frozenset({OrderStatus.DELIVERED})

OPEN_STATUSES = frozenset({ReturnRequestStatus.REQUESTED, ReturnRequestStatus.APPROVED})


def create_request(
    db: Session, user: User, order_number: str, payload: ReturnRequestCreate
) -> ReturnRequest:
    order = order_service.get_order_for_user(db, user.id, order_number)

    if order.order_status not in ELIGIBLE_ORDER_STATUSES:
        raise InvalidRequestError(
            "A return or exchange can only be requested once the order has been delivered."
        )

    open_request = db.execute(
        select(ReturnRequest).where(
            ReturnRequest.order_id == order.id, ReturnRequest.status.in_(OPEN_STATUSES)
        )
    ).scalar_one_or_none()
    if open_request is not None:
        raise ConflictError("There is already an open request for this order")

    request = ReturnRequest(
        order_id=order.id,
        user_id=user.id,
        type=payload.type,
        reason=payload.reason,
        description=payload.description,
        status=ReturnRequestStatus.REQUESTED,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    notifications.notify_order_event(
        notifications.NotificationEvent.RETURN_REQUESTED,
        order,
        request_type=str(payload.type),
        reason=payload.reason,
    )
    return request


def list_for_user(db: Session, user_id: uuid.UUID) -> Sequence[ReturnRequest]:
    return (
        db.execute(
            select(ReturnRequest)
            .where(ReturnRequest.user_id == user_id)
            .order_by(ReturnRequest.created_at.desc())
            .options(joinedload(ReturnRequest.order))
        )
        .unique()
        .scalars()
        .all()
    )


def list_all(
    db: Session, *, status: ReturnRequestStatus | None = None, page: int = 1, page_size: int = 24
) -> tuple[list[ReturnRequest], int]:
    conditions = [] if status is None else [ReturnRequest.status == status]
    total = db.execute(
        select(func.count()).select_from(ReturnRequest).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(ReturnRequest)
            .where(*conditions)
            .order_by(ReturnRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(joinedload(ReturnRequest.order))
        )
        .unique()
        .scalars()
        .all()
    )
    return list(rows), total


def decide(
    db: Session, request_id: uuid.UUID, payload: ReturnRequestDecision, *, actor: User
) -> ReturnRequest:
    """Record a staff decision.

    The order status is only moved to RETURNED or EXCHANGE when the request is
    COMPLETED, so an approval alone does not rewrite the order.
    """
    request = db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.id == request_id)
        .options(joinedload(ReturnRequest.order))
    ).unique().scalar_one_or_none()
    if request is None:
        raise NotFoundError("Return request not found")

    if request.status in (ReturnRequestStatus.REJECTED, ReturnRequestStatus.COMPLETED):
        raise InvalidRequestError(f"This request is already {request.status}")

    request.status = payload.status
    request.resolution_note = payload.resolution_note

    if payload.status is ReturnRequestStatus.COMPLETED:
        target = (
            OrderStatus.RETURNED
            if request.type.value == "RETURN"
            else OrderStatus.EXCHANGE
        )
        order: Order = request.order
        if order.order_status is not target:
            order.order_status = target
            from app.models.order import OrderStatusEvent

            db.add(
                OrderStatusEvent(
                    order_id=order.id,
                    status=target,
                    note=f"{request.type} completed",
                    changed_by_user_id=actor.id,
                )
            )

    db.commit()
    db.refresh(request)

    notifications.notify_order_event(
        notifications.NotificationEvent.RETURN_DECIDED,
        request.order,
        request_status=str(payload.status),
    )
    return request
