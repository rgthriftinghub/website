"""Public product endpoints."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import product as product_repo
from app.schemas.catalog import ProductDetail, ProductListItem
from app.schemas.common import Page
from app.schemas.query import ProductQuery

router = APIRouter()


class ProductFilterOptions(BaseModel):
    """Filter values actually present in the catalogue, for building the UI sidebar."""

    colors: list[str]
    fabrics: list[str]
    sizes: list[str]
    waists: list[int]
    min_price: float | None
    max_price: float | None


@router.get("", response_model=Page[ProductListItem], summary="List active products")
def list_products(
    query: Annotated[ProductQuery, Query()], db: Session = Depends(get_db)
) -> Page[ProductListItem]:
    items, total = product_repo.list_products(db, query)
    return Page.build(
        items=[ProductListItem.model_validate(item) for item in items],
        page=query.page,
        page_size=query.page_size,
        total=total,
    )


@router.get(
    "/filter-options",
    response_model=ProductFilterOptions,
    summary="Distinct filter values available in the catalogue",
)
def filter_options(db: Session = Depends(get_db)) -> ProductFilterOptions:
    values = product_repo.distinct_filter_values(db)
    return ProductFilterOptions(
        colors=values["colors"],
        fabrics=values["fabrics"],
        sizes=values["sizes"],
        waists=values["waists"],
        min_price=float(values["min_price"]) if values["min_price"] is not None else None,
        max_price=float(values["max_price"]) if values["max_price"] is not None else None,
    )


@router.get("/by-ids", response_model=list[ProductListItem], summary="Resolve products for guest wishlist")
def products_by_ids(
    ids: Annotated[list[uuid.UUID], Query(min_length=1, max_length=50)],
    db: Session = Depends(get_db),
) -> list[ProductListItem]:
    return [ProductListItem.model_validate(item) for item in product_repo.get_active_by_ids(db, ids)]


@router.get("/{slug}", response_model=ProductDetail, summary="Retrieve one product by slug")
def get_product(slug: str, db: Session = Depends(get_db)) -> ProductDetail:
    product = product_repo.get_by_slug(db, slug)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductDetail.model_validate(product)
