"""Checkout endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.rate_limit import limit_guest_checkout
from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import DeliveryMethod
from app.payments.service import selectable_methods
from app.models.user import User
from app.schemas.cart import CartRead, GuestCartPreviewRequest
from app.schemas.order import CheckoutConfig, CheckoutRequest, GuestCheckoutRequest, OrderRead
from app.services import cart as cart_service, orders as order_service

router = APIRouter()


@router.get(
    "/config",
    response_model=CheckoutConfig,
    summary="Delivery pricing and available payment methods",
)
def read_checkout_config(db: Session = Depends(get_db)) -> CheckoutConfig:
    """Public so the cart can preview delivery before the customer signs in.

    The storefront reads charges from here rather than hardcoding them.
    """
    settings = get_settings()
    from app.shipping_ops.service import method_for
    method = method_for(db, DeliveryMethod.STANDARD)
    return CheckoutConfig(
        currency=settings.currency_code,
        standard_delivery_charge=method.price if method else settings.standard_delivery_charge,
        free_delivery_threshold=(
            method.free_threshold if method else settings.free_delivery_threshold if settings.free_delivery_threshold > 0 else None
        ),
        payment_methods=sorted(selectable_methods(), key=lambda method: method.value),
        delivery_methods=[DeliveryMethod.STANDARD],
        max_quantity_per_item=settings.max_quantity_per_item,
        jazzcash_number=settings.jazzcash_number,
        easypaisa_number=settings.easypaisa_number,
        payment_whatsapp_number=settings.payment_whatsapp_number,
    )


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from the bag",
)
def place_order(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderRead:
    """Creates the order atomically.

    Prices and totals are recomputed from the catalogue, stock is decremented
    under row locks, and the bag is emptied — all in one transaction that rolls
    back completely on any failure. The request body carries no monetary value.
    """
    order = order_service.place_order(db, user, payload)
    return OrderRead.model_validate(order)


@router.post("/cart-preview", response_model=CartRead, summary="Preview a guest bag")
def preview_guest_cart(
    payload: GuestCartPreviewRequest, db: Session = Depends(get_db)
) -> CartRead:
    return cart_service.preview_guest_cart(db, payload)


@router.post(
    "/guest",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Place a Cash on Delivery order without an account",
)
def place_guest_order(
    payload: GuestCheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OrderRead:
    limit_guest_checkout(request)
    order = order_service.place_guest_order(db, payload)
    return OrderRead.model_validate(order)
