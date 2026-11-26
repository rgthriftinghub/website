"""Staff order review and status operations."""
import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.dependencies import require_permission
from app.models.enums import OrderStatus, PaymentStatus, Permission, ReturnRequestStatus, UserRole
from app.models.order import Order
from app.models.returns import ReturnRequest
from app.models.user import User
from app.repositories import order as order_repo
from app.schemas.common import MessageResponse, Page
from app.schemas.order import (OrderAdminRead, OrderAdminSummary, OrderStatusUpdate, PaymentStatusUpdate, InternalNoteUpdate, ReturnRequestAdminRead, ReturnRequestDecision)
from app.services import orders as order_service

router = APIRouter()

def _return_read(row):
    return {"id":row.id,"order_id":row.order_id,"order_number":row.order.order_number,"type":row.type,"reason":row.reason,"description":row.description,"status":row.status,"resolution_note":row.resolution_note,"created_at":row.created_at,"updated_at":row.updated_at}

@router.get("/stats", dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def order_stats(db: Session = Depends(get_db)):
    total=db.scalar(select(func.count()).select_from(Order)) or 0
    statuses=db.execute(select(Order.order_status,func.count()).group_by(Order.order_status)).all()
    revenue=db.scalar(select(func.coalesce(func.sum(Order.total_amount),0)).where(Order.order_status != OrderStatus.CANCELLED)) or 0
    return {"total_orders":total,"status_counts":{str(status):count for status,count in statuses},"revenue_total":float(revenue)}

@router.get("/returns", dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def list_return_requests(status: ReturnRequestStatus | None = None, page: int = Query(1,ge=1), page_size: int = Query(24,ge=1,le=100), db: Session = Depends(get_db)):
    from app.services import returns as return_service
    rows,total=return_service.list_all(db,status=status,page=page,page_size=page_size)
    return Page.build(items=[_return_read(row) for row in rows],page=page,page_size=page_size,total=total)

@router.put("/returns/{request_id}",response_model=ReturnRequestAdminRead)
def decide_return(request_id: uuid.UUID,payload:ReturnRequestDecision,actor:User=Depends(require_permission(Permission.ORDER_UPDATE)),db:Session=Depends(get_db)):
    from app.services import returns as return_service
    return _return_read(return_service.decide(db,request_id,payload,actor=actor))

@router.get("", response_model=Page[OrderAdminSummary], dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def list_orders(status: OrderStatus | None = None, payment_status: PaymentStatus | None = None, date_from: date | None = None, date_to: date | None = None, customer: str | None = None, order_number: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100), db: Session = Depends(get_db)):
    rows, total = order_repo.list_orders(db, status=status, payment_status=payment_status, date_from=date_from, date_to=date_to, customer=customer, order_number=order_number, page=page, page_size=page_size)
    return Page.build(items=[OrderAdminSummary.model_validate(row) for row in rows], page=page, page_size=page_size, total=total)

@router.get("/{order_id}", response_model=OrderAdminRead, dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.services.exceptions import NotFoundError
    order = order_service.get_order_by_id(db, order_id)
    if order is None: raise NotFoundError("Order not found")
    return OrderAdminRead.model_validate(order)

@router.delete("/{order_id}", response_model=MessageResponse)
def delete_order(order_id: uuid.UUID, actor: User = Depends(require_permission(Permission.ORDER_UPDATE)), db: Session = Depends(get_db)):
    if actor.role is not UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can delete orders")
    order_service.delete_unpaid_order(db, order_id)
    return {"detail": "Order deleted"}

@router.delete("", response_model=MessageResponse)
def delete_all_test_orders(actor: User = Depends(require_permission(Permission.ORDER_UPDATE)), db: Session = Depends(get_db)):
    if actor.role is not UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can reset all test orders")
    deleted_count, restored_variants = order_service.delete_all_test_orders(db)
    return {
        "detail": f"Deleted {deleted_count} test orders; restored stock for {restored_variants} product variants."
    }

@router.get("/{order_id}/invoice", dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def get_invoice(order_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.services.invoices import invoice_filename, render_invoice_pdf
    order=order_service.get_order_by_id(db,order_id)
    if order is None:
        from app.services.exceptions import NotFoundError
        raise NotFoundError("Order not found")
    return Response(content=render_invoice_pdf(order),media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="{invoice_filename(order)}"'})

@router.put("/{order_id}/status", response_model=OrderAdminRead)
def set_order_status(order_id: uuid.UUID, payload: OrderStatusUpdate, actor: User = Depends(require_permission(Permission.ORDER_UPDATE)), db: Session = Depends(get_db)):
    return OrderAdminRead.model_validate(order_service.update_order_status(db, order_id, payload.status, actor=actor, note=payload.note))

@router.put("/{order_id}/payment-status", response_model=OrderAdminRead)
def set_payment_status(order_id: uuid.UUID, payload: PaymentStatusUpdate, actor: User = Depends(require_permission(Permission.PAYMENT_MANAGE)), db: Session = Depends(get_db)):
    return OrderAdminRead.model_validate(order_service.update_payment_status(db, order_id, payload.payment_status, actor=actor, note=payload.note))

@router.put("/{order_id}/note", response_model=OrderAdminRead)
def set_internal_note(order_id: uuid.UUID, payload: InternalNoteUpdate, actor: User = Depends(require_permission(Permission.ORDER_UPDATE)), db: Session = Depends(get_db)):
    return OrderAdminRead.model_validate(order_service.set_internal_note(db, order_id, payload.internal_note))

@router.get("/{order_id}/inventory", dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def order_inventory(order_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.services.inventory import history_for_order
    return history_for_order(db, order_id)
