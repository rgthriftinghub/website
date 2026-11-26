"""Public policy pages and admin-managed storefront content."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.models.store_content import StoreContent
from app.models.user import User

router = APIRouter()
admin_router = APIRouter()
PAGE_KEYS = {"shipping", "returns", "refund", "privacy", "faq", "about", "contact", "announcement", "free_delivery_threshold"}

class ContentUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(max_length=20000)
    enabled: bool = True

@router.get("")
def public_content(db: Session = Depends(get_db)):
    return {row.key: {"title": row.title, "body": row.body, "enabled": row.enabled} for row in db.execute(select(StoreContent).where(StoreContent.key.in_(PAGE_KEYS))).scalars()}

@router.get("/{key}")
def public_page(key: str, db: Session = Depends(get_db)):
    if key not in PAGE_KEYS or key in {"announcement", "free_delivery_threshold"}:
        raise HTTPException(status_code=404, detail="Page not found")
    row = db.scalar(select(StoreContent).where(StoreContent.key == key, StoreContent.enabled.is_(True)))
    if row is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"key": row.key, "title": row.title, "body": row.body}

@admin_router.get("")
def admin_content(_actor: User = Depends(require_permission(Permission.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return {row.key: {"title": row.title, "body": row.body, "enabled": row.enabled} for row in db.execute(select(StoreContent)).scalars()}

@admin_router.put("/{key}")
def update_content(key: str, payload: ContentUpdate, _actor: User = Depends(require_permission(Permission.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    if key not in PAGE_KEYS:
        raise HTTPException(status_code=404, detail="Content key not found")
    row = db.scalar(select(StoreContent).where(StoreContent.key == key))
    if row is None:
        row = StoreContent(key=key, title=payload.title, body=payload.body, enabled=payload.enabled)
        db.add(row)
    else:
        row.title, row.body, row.enabled = payload.title, payload.body, payload.enabled
    db.commit()
    return {"key": row.key, "title": row.title, "body": row.body, "enabled": row.enabled}
