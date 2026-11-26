"""Public brand endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import brand as brand_repo
from app.schemas.catalog import BrandRead

router = APIRouter()


@router.get("", response_model=list[BrandRead], summary="List active brands")
def list_brands(db: Session = Depends(get_db)) -> list[BrandRead]:
    brands, _ = brand_repo.list_brands(db)
    return [BrandRead.model_validate(row) for row in brands]


@router.get("/{slug}", response_model=BrandRead, summary="Retrieve one brand by slug")
def get_brand(slug: str, db: Session = Depends(get_db)) -> BrandRead:
    brand = brand_repo.get_by_slug(db, slug)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return BrandRead.model_validate(brand)
