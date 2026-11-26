"""Per-variant inventory, auditable adjustments, and history."""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import InventoryTransactionType, Permission
from app.models.inventory import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.variant import ProductVariant
from app.schemas.common import Page
from app.services import bulk
from app.services.inventory import set_quantity
from app.models.user import User

router = APIRouter()


def _stock_row(p, v, inv):
    q = inv.quantity if inv else 0
    threshold = inv.low_stock_threshold if inv else 3
    return {"product_id": str(p.id), "product_name": p.name, "variant_id": str(v.id), "sku": v.sku,
            "variant_label": v.variant_name or v.size or (f"Waist {v.waist}" if v.waist else "One size"),
            "size": v.size, "waist": v.waist, "quantity": q, "low_stock_threshold": threshold,
            "status": "out" if q == 0 else ("low" if q <= threshold else "in_stock"), "is_active": p.is_active and v.is_active}


@router.get("")
def list_stock(search: str | None = None, status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), actor: User = Depends(require_permission(Permission.INVENTORY_VIEW)), db: Session = Depends(get_db)):
    stmt = select(Product, ProductVariant, InventoryItem).join(ProductVariant, ProductVariant.product_id == Product.id).outerjoin(InventoryItem, InventoryItem.product_variant_id == ProductVariant.id)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(term), ProductVariant.sku.ilike(term)))
    if status == "out": stmt = stmt.where(or_(InventoryItem.quantity == 0, InventoryItem.id.is_(None)))
    if status == "low": stmt = stmt.where(InventoryItem.quantity > 0, InventoryItem.quantity <= InventoryItem.low_stock_threshold)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(Product.name, ProductVariant.sku).offset((page-1)*page_size).limit(page_size)).all()
    return Page.build(items=[_stock_row(*row) for row in rows], page=page, page_size=page_size, total=total)


@router.post("/variants/{variant_id}/adjust")
def adjust_stock(variant_id: uuid.UUID, payload: dict, actor: User = Depends(require_permission(Permission.INVENTORY_UPDATE)), db: Session = Depends(get_db)):
    inv = db.scalar(select(InventoryItem).where(InventoryItem.product_variant_id == variant_id).with_for_update())
    if inv is None: raise ValueError("Inventory record not found")
    quantity = int(payload["quantity"])
    mode = payload["mode"]
    target = inv.quantity + quantity if mode == "add" else inv.quantity - quantity if mode == "remove" else quantity
    set_quantity(db, variant_id, target, note=payload.get("reason"))
    if payload.get("low_stock_threshold") is not None:
        inv.low_stock_threshold = int(payload["low_stock_threshold"])
    db.commit()
    p, v = db.execute(select(Product, ProductVariant).join(ProductVariant).where(ProductVariant.id == variant_id)).one()
    return _stock_row(p, v, inv)


@router.get("/history")
def list_history(search: str | None = None, type: InventoryTransactionType | None = None, variant_id: uuid.UUID | None = None, date_from: str | None = None, date_to: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), actor: User = Depends(require_permission(Permission.INVENTORY_VIEW)), db: Session = Depends(get_db)):
    stmt = select(InventoryTransaction, Product, ProductVariant).join(ProductVariant, InventoryTransaction.product_variant_id == ProductVariant.id).join(Product, ProductVariant.product_id == Product.id)
    if search: stmt = stmt.where(or_(Product.name.ilike(f"%{search}%"), ProductVariant.sku.ilike(f"%{search}%")))
    if type: stmt = stmt.where(InventoryTransaction.type == type)
    if variant_id: stmt = stmt.where(InventoryTransaction.product_variant_id == variant_id)
    if date_from: stmt = stmt.where(InventoryTransaction.created_at >= date_from)
    if date_to: stmt = stmt.where(InventoryTransaction.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(InventoryTransaction.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    items = [{"id": str(t.id), "created_at": t.created_at, "product_name": p.name, "sku": v.sku,
              "variant_label": v.variant_name or v.size or (f"Waist {v.waist}" if v.waist else "One size"),
              "type": t.type, "quantity_change": t.quantity_change, "quantity_before": t.quantity_before,
              "quantity_after": t.quantity_after, "reference_type": t.reference_type, "reference_id": t.reference_id, "note": t.note} for t,p,v in rows]
    return Page.build(items=items, page=page, page_size=page_size, total=total)
