"""Admin-managed, scheduled discount campaigns."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.models.user import User
from app.schemas.admin_ops import SaleCreate, SaleListQuery, SaleRead, SaleUpdate
from app.schemas.common import MessageResponse, Page
from app.services import sale_admin

router = APIRouter()


@router.get("", response_model=Page[SaleRead])
def list_sales(query: Annotated[SaleListQuery, Query()], actor: User = Depends(require_permission(Permission.SALES_VIEW)), db: Session = Depends(get_db)):
    rows, total = sale_admin.list_sales(db, status=query.status, search=query.search, page=query.page, page_size=query.page_size)
    return Page.build(items=[SaleRead.model_validate(row) for row in rows], page=query.page, page_size=query.page_size, total=total)


@router.post("", response_model=SaleRead)
def create_sale(payload: SaleCreate, actor: User = Depends(require_permission(Permission.SALES_MANAGE)), db: Session = Depends(get_db)):
    return SaleRead.model_validate(sale_admin.create_sale(db, payload.model_dump(), actor=actor))


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: uuid.UUID, actor: User = Depends(require_permission(Permission.SALES_VIEW)), db: Session = Depends(get_db)):
    return SaleRead.model_validate(sale_admin.get_sale(db, sale_id))


@router.put("/{sale_id}", response_model=SaleRead)
def update_sale(sale_id: uuid.UUID, payload: SaleUpdate, actor: User = Depends(require_permission(Permission.SALES_MANAGE)), db: Session = Depends(get_db)):
    return SaleRead.model_validate(sale_admin.update_sale(db, sale_id, payload.model_dump(exclude_unset=True), actor=actor))


@router.post("/{sale_id}/activate", response_model=SaleRead)
def activate(sale_id: uuid.UUID, actor: User = Depends(require_permission(Permission.SALES_MANAGE)), db: Session = Depends(get_db)):
    return SaleRead.model_validate(sale_admin.set_active(db, sale_id, True, actor=actor))


@router.post("/{sale_id}/deactivate", response_model=SaleRead)
def deactivate(sale_id: uuid.UUID, actor: User = Depends(require_permission(Permission.SALES_MANAGE)), db: Session = Depends(get_db)):
    return SaleRead.model_validate(sale_admin.set_active(db, sale_id, False, actor=actor))


@router.delete("/{sale_id}", response_model=MessageResponse)
def delete_sale(sale_id: uuid.UUID, actor: User = Depends(require_permission(Permission.SALES_MANAGE)), db: Session = Depends(get_db)):
    sale_admin.delete_sale(db, sale_id, actor=actor)
    return MessageResponse(detail="Sale deleted")
