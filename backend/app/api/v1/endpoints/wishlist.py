"""Wishlist endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.catalog import ProductListItem
from app.schemas.common import MessageResponse
from app.schemas.wishlist import WishlistItemRead, WishlistRead
from app.services import wishlist as wishlist_service

router = APIRouter()


@router.get("", response_model=WishlistRead, summary="List saved products")
def read_wishlist(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WishlistRead:
    items = wishlist_service.list_items(db, user.id)
    return WishlistRead(
        items=[
            WishlistItemRead(
                id=item.id,
                created_at=item.created_at,
                product=ProductListItem.model_validate(item.product),
            )
            for item in items
        ],
        total=len(items),
    )


@router.get(
    "/ids",
    response_model=list[uuid.UUID],
    summary="Saved product ids, for rendering wishlist state in bulk",
)
def read_wishlist_ids(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[uuid.UUID]:
    return sorted(wishlist_service.product_ids(db, user.id), key=str)


@router.post(
    "/{product_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a product",
)
def add_to_wishlist(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Idempotent: saving an already-saved product succeeds without duplicating."""
    wishlist_service.add(db, user.id, product_id)
    return MessageResponse(detail="Saved to your wishlist")


@router.delete("/{product_id}", response_model=MessageResponse, summary="Remove a saved product")
def remove_from_wishlist(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    wishlist_service.remove(db, user.id, product_id)
    return MessageResponse(detail="Removed from your wishlist")
