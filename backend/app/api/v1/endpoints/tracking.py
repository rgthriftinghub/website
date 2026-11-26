"""Public order tracking.

Unauthenticated, but not unguarded: the caller must supply both the order number
and a contact detail recorded on that order. The response is deliberately narrow —
status, items, and courier tracking only. No address, no prices, no customer name.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rate_limit import limit_public_tracking
from app.schemas.payment import (
    ShipmentEventRead,
    TrackingItemRead,
    TrackingRead,
    TrackingRequest,
)
from app.shipping_ops import service as shipping_service

router = APIRouter()


@router.post(
    "",
    response_model=TrackingRead,
    summary="Track an order using its number and a matching contact detail",
)
def track_order(payload: TrackingRequest, request: Request, db: Session = Depends(get_db)) -> TrackingRead:
    """Verified lookup.

    A wrong contact detail and a non-existent order produce the identical error,
    so this endpoint cannot be used to discover which order numbers exist.
    """
    limit_public_tracking(request)
    order = shipping_service.track_by_order_number(
        db, payload.order_number, contact=payload.contact
    )
    shipment = order.shipment

    return TrackingRead(
        order_number=order.order_number,
        order_status=order.order_status,
        payment_status=order.payment_status,
        placed_at=order.created_at,
        item_count=order.item_count,
        items=[
            TrackingItemRead(
                name=item.product_name_snapshot,
                variant_label=item.variant_label,
                quantity=item.quantity,
            )
            for item in order.items
        ],
        shipping_status=shipment.shipping_status if shipment else None,
        courier=shipment.provider if shipment else None,
        tracking_number=shipment.tracking_number if shipment else None,
        tracking_url=shipment.tracking_url if shipment else None,
        shipped_at=shipment.shipped_at if shipment else None,
        delivered_at=shipment.delivered_at if shipment else None,
        status_history=[ShipmentEventRead.model_validate(event) for event in shipment.events]
        if shipment
        else [],
    )
