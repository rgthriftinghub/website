"""Staff category, subcategory and brand management."""
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.repositories import brand as brand_repo, category as category_repo
from app.schemas.catalog import (BrandCreate, BrandRead, BrandUpdate, CategoryCreate, CategoryDetail, CategoryRead, CategoryUpdate, SubcategoryCreate, SubcategoryRead, SubcategoryUpdate)
from app.schemas.common import MessageResponse
from app.services import catalog as catalog_service

categories_router = APIRouter()
subcategories_router = APIRouter()
brands_router = APIRouter()

@categories_router.get("", response_model=list[CategoryDetail], dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def list_categories(db: Session = Depends(get_db)):
    return category_repo.list_categories(db, include_inactive=True)

@categories_router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.PRODUCT_CREATE))])
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    return catalog_service.create_category(db, payload)

@categories_router.put("/{category_id}", response_model=CategoryRead, dependencies=[Depends(require_permission(Permission.PRODUCT_UPDATE))])
def update_category(category_id: uuid.UUID, payload: CategoryUpdate, db: Session = Depends(get_db)):
    return catalog_service.update_category(db, category_id, payload)

@categories_router.delete("/{category_id}", response_model=MessageResponse, dependencies=[Depends(require_permission(Permission.PRODUCT_DELETE))])
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    catalog_service.deactivate_category(db, category_id)
    return MessageResponse(detail="Category deactivated")

@subcategories_router.get("", response_model=list[SubcategoryRead], dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def list_subcategories(db: Session = Depends(get_db)):
    return [sub for category in category_repo.list_categories(db, include_inactive=True) for sub in category.subcategories]

@subcategories_router.post("", response_model=SubcategoryRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.PRODUCT_CREATE))])
def create_subcategory(payload: SubcategoryCreate, db: Session = Depends(get_db)):
    return catalog_service.create_subcategory(db, payload)

@subcategories_router.put("/{subcategory_id}", response_model=SubcategoryRead, dependencies=[Depends(require_permission(Permission.PRODUCT_UPDATE))])
def update_subcategory(subcategory_id: uuid.UUID, payload: SubcategoryUpdate, db: Session = Depends(get_db)):
    return catalog_service.update_subcategory(db, subcategory_id, payload)

@subcategories_router.delete("/{subcategory_id}", response_model=MessageResponse, dependencies=[Depends(require_permission(Permission.PRODUCT_DELETE))])
def delete_subcategory(subcategory_id: uuid.UUID, db: Session = Depends(get_db)):
    catalog_service.deactivate_subcategory(db, subcategory_id)
    return MessageResponse(detail="Subcategory deactivated")

@brands_router.get("", response_model=list[BrandRead], dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def list_brands(db: Session = Depends(get_db)):
    rows, _ = brand_repo.list_brands(db, include_inactive=True)
    return rows

@brands_router.get("/{brand_id}", response_model=BrandRead, dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def get_brand(brand_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.repositories import brand as brand_repo
    from app.services.exceptions import NotFoundError
    brand = brand_repo.get_by_id(db, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found")
    return brand

@brands_router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.PRODUCT_CREATE))])
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    return catalog_service.create_brand(db, payload)

@brands_router.put("/{brand_id}", response_model=BrandRead, dependencies=[Depends(require_permission(Permission.PRODUCT_UPDATE))])
def update_brand(brand_id: uuid.UUID, payload: BrandUpdate, db: Session = Depends(get_db)):
    return catalog_service.update_brand(db, brand_id, payload)

@brands_router.delete("/{brand_id}", response_model=BrandRead, dependencies=[Depends(require_permission(Permission.PRODUCT_DELETE))])
def delete_brand(brand_id: uuid.UUID, db: Session = Depends(get_db)):
    return catalog_service.deactivate_brand(db, brand_id)
