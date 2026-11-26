"""Public category endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import category as category_repo
from app.schemas.catalog import CategoryDetail

router = APIRouter()


@router.get(
    "",
    response_model=list[CategoryDetail],
    summary="List active categories with their subcategories",
)
def list_categories(db: Session = Depends(get_db)) -> list[CategoryDetail]:
    """Subcategories are included so navigation and filter menus need one call."""
    return [CategoryDetail.model_validate(row) for row in category_repo.list_categories(db)]


@router.get(
    "/{slug}",
    response_model=CategoryDetail,
    summary="Retrieve one category with its subcategories",
)
def get_category(slug: str, db: Session = Depends(get_db)) -> CategoryDetail:
    category = category_repo.get_by_slug(db, slug)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryDetail.model_validate(category)
