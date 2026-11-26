"""Bulk operations, audit, notifications, staff, and customer tools."""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_admin, require_permission, require_staff
from app.db.session import get_db
from app.models.admin import CustomerNote
from app.models.enums import Permission, UserRole
from app.models.order import Order
from app.models.user import User
from app.schemas.admin_ops import (ActivityQuery, BulkAttributeUpdate, BulkPriceRequest, BulkStockRequest, CustomerListQuery, CustomerNoteCreate, CustomerNoteRead, NotificationQuery, NotificationRead, NotificationListRead, StaffPermissionsUpdate, StaffMemberRead)
from app.schemas.common import Page, MessageResponse
from app.services import activity, bulk, permissions, sale_admin
from app.services.bulk import StockAdjustment

router = APIRouter(); notifications_router = APIRouter(); staff_router = APIRouter(); customers_router = APIRouter()

@router.get("/me/access")
def read_admin_access(actor: User = Depends(require_staff), db: Session = Depends(get_db)):
    return {
        "role": actor.role,
        "permissions": sorted(permissions.permissions_for(db, actor), key=str),
    }

@router.get("/activity")
def list_activity(query: Annotated[ActivityQuery, Query()], actor: User = Depends(require_permission(Permission.REPORTS_VIEW)), db: Session = Depends(get_db)):
    rows,total=activity.list_activity(db, action=query.action, entity_type=query.entity_type, user_id=query.user_id, page=query.page, page_size=query.page_size)
    return Page.build(items=rows,page=query.page,page_size=query.page_size,total=total)

@notifications_router.get("")
def list_notifications(query: Annotated[NotificationQuery, Query()], actor: User=Depends(require_permission(Permission.INVENTORY_VIEW)), db: Session=Depends(get_db)):
    rows,total,unread=activity.list_notifications(db, unread_only=query.unread_only,page=query.page,page_size=query.page_size)
    return {"items": rows, "total": total, "unread": unread}

@notifications_router.post("/scan")
def scan_notifications(actor: User=Depends(require_permission(Permission.INVENTORY_UPDATE)),db: Session=Depends(get_db)):
    return activity.scan_stock_alerts(db)

@notifications_router.post("/{notification_id}/read")
def read_notification(notification_id: uuid.UUID,actor: User=Depends(require_permission(Permission.INVENTORY_VIEW)),db: Session=Depends(get_db)):
    if not activity.mark_read(db,notification_id,actor=actor): return MessageResponse(detail="Already read")
    return MessageResponse(detail="Notification marked read")

@notifications_router.post("/read-all")
def read_all(actor: User=Depends(require_permission(Permission.INVENTORY_VIEW)),db: Session=Depends(get_db)):
    return {"detail": f"Marked {activity.mark_all_read(db,actor=actor)} notifications read"}

@staff_router.get("")
def list_staff(actor: User=Depends(require_admin),db: Session=Depends(get_db)):
    return [_staff_read(db,u) for u in permissions.list_staff(db)]

def _staff_read(db: Session,user: User):
    held=permissions.permissions_for(db,user)
    return {"id":user.id,"email":user.email,"first_name":user.first_name,"last_name":user.last_name,"role":user.role,"permissions":sorted(held,key=str),"holds_all":user.role is UserRole.ADMIN}

@staff_router.put("/{user_id}/permissions")
def update_staff(user_id: uuid.UUID,payload: StaffPermissionsUpdate,actor: User=Depends(require_admin),db: Session=Depends(get_db)):
    permissions.grant(db,user_id,payload.permissions,granted_by=actor)
    return _staff_read(db,db.get(User,user_id))

@customers_router.get("")
def list_customers(query: Annotated[CustomerListQuery,Query()],actor:User=Depends(require_permission(Permission.CUSTOMER_VIEW)),db: Session=Depends(get_db)):
    from app.models.enums import CustomerSegment
    stmt=select(User).where(User.role==UserRole.CUSTOMER)
    if query.search:
        term=f"%{query.search.strip()}%"; stmt=stmt.where(or_(User.email.ilike(term),User.first_name.ilike(term),User.last_name.ilike(term),User.phone.ilike(term)))
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users=db.execute(stmt.order_by(User.created_at.desc()).offset((query.page-1)*query.page_size).limit(query.page_size)).scalars().all()
    items=[]
    for u in users:
        orders=db.execute(select(Order).where(Order.user_id==u.id).order_by(Order.created_at.desc())).scalars().all()
        spent=sum((o.total_amount for o in orders if str(o.order_status) not in {"CANCELLED"}), start=0)
        items.append({"id":u.id,"email":u.email,"first_name":u.first_name,"last_name":u.last_name,"phone":u.phone,"order_count":len(orders),"total_spent":float(spent),"last_order_at":orders[0].created_at if orders else None,"segment":"LOYAL" if len(orders)>=5 else "REPEAT" if len(orders)>=2 else "NEW","created_at":u.created_at})
    return Page.build(items=items,page=query.page,page_size=query.page_size,total=total)

@customers_router.get("/{customer_id}")
def get_customer(customer_id:uuid.UUID,actor:User=Depends(require_permission(Permission.CUSTOMER_VIEW)),db:Session=Depends(get_db)):
    from app.models.address import CustomerAddress
    from app.models.wishlist import WishlistItem
    from app.services.addresses import list_addresses
    user=db.get(User,customer_id)
    if user is None or user.role is not UserRole.CUSTOMER: from app.services.exceptions import NotFoundError; raise NotFoundError("Customer not found")
    orders=db.execute(select(Order).where(Order.user_id==user.id).order_by(Order.created_at.desc())).scalars().all()
    notes=db.execute(select(CustomerNote).where(CustomerNote.customer_id==user.id).order_by(CustomerNote.created_at.desc())).scalars().all()
    spent=sum((o.total_amount for o in orders if str(o.order_status)!="CANCELLED"),start=0)
    return {"id":user.id,"email":user.email,"first_name":user.first_name,"last_name":user.last_name,"phone":user.phone,"order_count":len(orders),"total_spent":float(spent),"last_order_at":orders[0].created_at if orders else None,"segment":"LOYAL" if len(orders)>=5 else "REPEAT" if len(orders)>=2 else "NEW","created_at":user.created_at,"is_active":user.is_active,"is_verified":user.is_verified,"last_login_at":user.last_login_at,"addresses":list_addresses(db,user.id),"orders":[{"id":o.id,"order_number":o.order_number,"order_status":o.order_status,"payment_status":o.payment_status,"total_amount":o.total_amount,"item_count":o.item_count,"created_at":o.created_at} for o in orders],"wishlist":[str(row.product_id) for row in db.execute(select(WishlistItem).where(WishlistItem.user_id==user.id)).scalars().all()],"notes":notes}

@customers_router.get("/{customer_id}/notes")
def list_notes(customer_id:uuid.UUID,actor:User=Depends(require_permission(Permission.CUSTOMER_VIEW)),db:Session=Depends(get_db)):
    return db.execute(select(CustomerNote).where(CustomerNote.customer_id==customer_id).order_by(CustomerNote.created_at.desc())).scalars().all()

@customers_router.post("/{customer_id}/notes")
def add_note(customer_id:uuid.UUID,payload:CustomerNoteCreate,actor:User=Depends(require_permission(Permission.CUSTOMER_UPDATE)),db:Session=Depends(get_db)):
    if db.get(User,customer_id) is None: from app.services.exceptions import NotFoundError; raise NotFoundError("Customer not found")
    note=CustomerNote(customer_id=customer_id,author_user_id=actor.id,author_email=actor.email,body=payload.body); db.add(note); db.commit(); db.refresh(note); return note

@router.post("/bulk/products")
def update_products(payload:BulkAttributeUpdate,actor:User=Depends(require_permission(Permission.PRODUCT_UPDATE)),db:Session=Depends(get_db)):
    result=bulk.bulk_update_attributes(db,payload.product_ids,actor=actor,is_active=payload.is_active,is_featured=payload.is_featured,is_new_arrival=payload.is_new_arrival,category_id=payload.category_id,subcategory_id=payload.subcategory_id,brand_id=payload.brand_id)
    return {"affected":result.affected,"detail":result.detail}

@router.post("/bulk/prices/preview")
def preview_prices(payload:BulkPriceRequest,actor:User=Depends(require_permission(Permission.PRODUCT_UPDATE)),db:Session=Depends(get_db)):
    products=bulk.resolve_selection(db,product_ids=payload.product_ids,category_id=payload.category_id,subcategory_id=payload.subcategory_id,brand_id=payload.brand_id)
    rows,summary=bulk.preview_price_update(db,products,mode=payload.mode,value=payload.value,field=payload.field)
    return {"rows":rows,"affected":summary["affected"],"total_before":summary["total_before"],"total_after":summary["total_after"],"total_change":summary["total_change"]}

@router.post("/bulk/prices/apply")
def apply_prices(payload:BulkPriceRequest,actor:User=Depends(require_permission(Permission.PRODUCT_UPDATE)),db:Session=Depends(get_db)):
    products=bulk.resolve_selection(db,product_ids=payload.product_ids,category_id=payload.category_id,subcategory_id=payload.subcategory_id,brand_id=payload.brand_id)
    result=bulk.apply_price_update(db,products,mode=payload.mode,value=payload.value,field=payload.field,actor=actor)
    return {"affected":result.affected,"detail":result.detail}

@router.post("/bulk/stock")
def update_stock(payload:BulkStockRequest,actor:User=Depends(require_permission(Permission.INVENTORY_UPDATE)),db:Session=Depends(get_db)):
    adjustments=[StockAdjustment(**item.model_dump()) for item in payload.adjustments]
    result=bulk.apply_stock_update(db,adjustments,reason=payload.reason,actor=actor);return {"affected":result.affected,"detail":result.detail}

@router.get("/bulk/variants")
def selection_variants(product_ids:list[uuid.UUID]=Query(...),actor:User=Depends(require_permission(Permission.PRODUCT_VIEW)),db:Session=Depends(get_db)):
    return bulk.variant_rows_for_products(db,product_ids)
