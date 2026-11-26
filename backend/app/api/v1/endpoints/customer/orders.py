"""Customer order history and lifecycle endpoints."""
import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.order import OrderRead, OrderSummary, OrderCancelRequest, ReturnRequestCreate, ReturnRequestRead
from app.services import orders as order_service, returns as return_service, invoices

router = APIRouter()

@router.get("", response_model=Page[OrderSummary])
def list_orders(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows, total = order_service.list_orders_for_user(db, user.id, page=page, page_size=page_size)
    return Page.build(items=[OrderSummary.model_validate(row) for row in rows], page=page, page_size=page_size, total=total)

@router.get("/{order_number}", response_model=OrderRead)
def get_order(order_number: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.get_order_for_user(db, user.id, order_number)

@router.post("/{order_number}/cancel", response_model=OrderRead)
def cancel_order(order_number: str, payload: OrderCancelRequest | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.cancel_order_as_customer(db, user.id, order_number, reason=payload.reason if payload else None)

@router.post("/{order_number}/returns", response_model=ReturnRequestRead, status_code=201)
def request_return(order_number: str, payload: ReturnRequestCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return return_service.create_request(db, user, order_number, payload)

@router.get("/{order_number}/invoice")
def get_invoice(order_number: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = order_service.get_order_for_user(db, user.id, order_number)
    return Response(content=invoices.render_invoice_pdf(order), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{order.order_number}.pdf"'})
