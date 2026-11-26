"""Cart endpoints.

All are authenticated, and every operation is scoped to the requesting user's own
cart. No request body carries a price — only a variant id and a quantity.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartRead
from app.services import cart as cart_service

router = APIRouter()


@router.get("", response_model=CartRead, summary="Retrieve the signed-in customer's bag")
def read_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartRead:
    return cart_service.serialise_cart(cart_service.get_cart(db, user.id), db)


@router.post(
    "/items",
    response_model=CartRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to the bag",
)
def add_item(
    payload: CartItemAdd,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartRead:
    """Adding a variant already in the bag increases its quantity."""
    cart = cart_service.add_item(db, user.id, payload.product_variant_id, payload.quantity)
    return cart_service.serialise_cart(cart, db)


@router.put("/items/{item_id}", response_model=CartRead, summary="Change a line quantity")
def update_item(
    item_id: uuid.UUID,
    payload: CartItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartRead:
    cart = cart_service.update_item_quantity(db, user.id, item_id, payload.quantity)
    return cart_service.serialise_cart(cart, db)


@router.delete("/items/{item_id}", response_model=CartRead, summary="Remove a line")
def remove_item(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartRead:
    cart = cart_service.remove_item(db, user.id, item_id)
    return cart_service.serialise_cart(cart, db)


@router.delete("", response_model=CartRead, summary="Empty the bag")
def clear_cart(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CartRead:
    return cart_service.serialise_cart(cart_service.clear_cart(db, user.id), db)
