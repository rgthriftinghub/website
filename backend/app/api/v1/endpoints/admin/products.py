"""Staff catalogue management."""
import uuid
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from app.api.v1.dependencies import get_current_user, require_permission
from app.db.session import get_db
from app.models.enums import Permission, UserRole
from app.models.user import User
from app.repositories import product as product_repo
from app.schemas.catalog import ProductAdminRead, ProductCreate, ProductUpdate
from app.schemas.common import Page, MessageResponse
from app.schemas.query import AdminProductQuery
from app.services import catalog as catalog_service
from app.services import permissions as permission_service

router = APIRouter()
PRODUCT_MEDIA_DIR = Path(__file__).resolve().parents[5] / "uploads" / "products"
MAX_PRODUCT_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}


def require_product_image_access(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    """Allow product creators and editors to upload photos for a product."""
    if user.role is UserRole.ADMIN:
        return user
    held = permission_service.permissions_for(db, user)
    if Permission.PRODUCT_CREATE in held or Permission.PRODUCT_UPDATE in held:
        return user
    raise HTTPException(status_code=403, detail="Product create or update permission required")


@router.post("/images", dependencies=[Depends(require_product_image_access)])
async def upload_product_image(file: UploadFile = File(...)):
    """Store a validated product photo and return its public API URL."""
    spec = IMAGE_TYPES.get(file.content_type or "")
    if spec is None:
        from app.services.exceptions import InvalidRequestError
        raise InvalidRequestError("Use a JPG, PNG, or WebP image.")

    content = await file.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        from app.services.exceptions import InvalidRequestError
        raise InvalidRequestError("Product images are limited to 8 MB.")
    if not any(content.startswith(signature) for signature in spec[1]):
        from app.services.exceptions import InvalidRequestError
        raise InvalidRequestError("The uploaded file does not match its image type.")
    if file.content_type == "image/webp" and content[8:12] != b"WEBP":
        from app.services.exceptions import InvalidRequestError
        raise InvalidRequestError("The uploaded file is not a valid WebP image.")

    PRODUCT_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{spec[0]}"
    (PRODUCT_MEDIA_DIR / filename).write_bytes(content)
    return {"image_url": f"/api/v1/media/products/{filename}"}

@router.get("", response_model=Page[ProductAdminRead], dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def list_products(query: Annotated[AdminProductQuery, Query()], db: Session = Depends(get_db)):
    rows, total = product_repo.list_products(db, query, include_inactive=query.include_inactive)
    return Page.build(items=[ProductAdminRead.model_validate(row) for row in rows], page=query.page, page_size=query.page_size, total=total)

@router.get("/{product_id}", response_model=ProductAdminRead, dependencies=[Depends(require_permission(Permission.PRODUCT_VIEW))])
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.services.exceptions import NotFoundError
    product = product_repo.get_by_id(db, product_id)
    if product is None: raise NotFoundError("Product not found")
    return ProductAdminRead.model_validate(product)

@router.post("", response_model=ProductAdminRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Permission.PRODUCT_CREATE))])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    return ProductAdminRead.model_validate(catalog_service.create_product(db, payload))

@router.put("/{product_id}", response_model=ProductAdminRead, dependencies=[Depends(require_permission(Permission.PRODUCT_UPDATE))])
def update_product(product_id: uuid.UUID, payload: ProductUpdate, db: Session = Depends(get_db)):
    return ProductAdminRead.model_validate(catalog_service.update_product(db, product_id, payload))

@router.delete("/{product_id}", response_model=ProductAdminRead)
def deactivate_product(product_id: uuid.UUID, actor: User = Depends(require_permission(Permission.PRODUCT_DELETE)), db: Session = Depends(get_db)):
    if actor.role is not UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can remove products")
    return ProductAdminRead.model_validate(catalog_service.deactivate_product(db, product_id))
