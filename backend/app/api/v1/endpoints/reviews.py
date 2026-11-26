"""Public product reviews; submissions require a delivered purchase."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import OrderStatus
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.review import ProductReview
from app.models.user import User

router = APIRouter()
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, max_length=3000)
class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rating: int
    title: str | None
    body: str | None
    created_at: datetime

@router.get("/{slug}/reviews", response_model=list[ReviewRead])
def list_reviews(slug: str, db: Session = Depends(get_db)):
    product = db.execute(select(Product).where(Product.slug == slug, Product.is_active.is_(True))).scalar_one_or_none()
    if not product: raise HTTPException(404, "Product not found")
    return db.execute(select(ProductReview).where(ProductReview.product_id == product.id).order_by(ProductReview.created_at.desc())).scalars().all()

@router.post("/{slug}/reviews", response_model=ReviewRead, status_code=201)
def create_review(slug: str, payload: ReviewCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.execute(select(Product).where(Product.slug == slug, Product.is_active.is_(True))).scalar_one_or_none()
    if not product: raise HTTPException(404, "Product not found")
    purchased = db.execute(select(OrderItem.id).join(Order).where(Order.user_id == user.id, Order.order_status == OrderStatus.DELIVERED, OrderItem.product_id == product.id)).first()
    if not purchased: raise HTTPException(403, "A delivered purchase is required to review this product")
    review = db.execute(select(ProductReview).where(ProductReview.product_id == product.id, ProductReview.user_id == user.id)).scalar_one_or_none()
    if review:
        review.rating, review.title, review.body = payload.rating, payload.title, payload.body
    else:
        review = ProductReview(product_id=product.id, user_id=user.id, **payload.model_dump())
        db.add(review)
    db.commit(); db.refresh(review)
    return review
