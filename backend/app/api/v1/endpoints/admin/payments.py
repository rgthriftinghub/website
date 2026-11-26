"""Manual payment review plus courier assignment and label generation."""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.enums import Permission, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.schemas.common import Page
from app.schemas.payment import PaymentAdminRead, PaymentVerifyRequest, PaymentRejectRequest, RefundCreateRequest, RefundRead, ShippingMethodRead, ShippingMethodUpdate, CourierStatusRead, ShipmentAdminRead, CourierAssignRequest, ShippingStatusUpdate
from app.payments import service as payment_service
from app.shipping_ops import service as shipping_service
from app.services.exceptions import NotFoundError
from app.services.invoices import render_invoice_pdf

router=APIRouter(); shipping_router=APIRouter()

def _admin_payment(p):
    # Convert nested audit rows to Pydantic before JSON encoding. The raw ORM
    # objects have back-references to Payment and can recurse during encoding.
    address = p.order.shipping_address_snapshot or {}
    return PaymentAdminRead.model_validate({"id":p.id,"provider":p.provider,"payment_method":p.payment_method,"status":p.status,"amount":p.amount,"currency":p.currency,"customer_reference":p.customer_reference,"proof_submitted_at":p.proof_submitted_at,"failure_reason":p.failure_reason,"paid_at":p.paid_at,"created_at":p.created_at,"order_id":p.order_id,"order_number":p.order.order_number,"customer_email":p.order.contact_email or "","customer_name":address.get("full_name") or (p.order.user.full_name if p.order.user else "Guest"),"provider_transaction_id":p.provider_transaction_id,"customer_note":p.customer_note,"proof_url":p.proof_url,"internal_note":p.internal_note,"verified_at":p.verified_at,"raw_response":p.raw_response,"transactions":p.transactions,"refunds":p.refunds,"updated_at":p.updated_at})

@router.get("", response_model=Page[PaymentAdminRead])
def list_payments(provider:str|None=None,payment_method:str|None=None,status:PaymentStatus|None=None,awaiting_verification:bool|None=None,date_from:str|None=None,date_to:str|None=None,search:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),actor:User=Depends(require_permission(Permission.PAYMENT_VIEW)),db:Session=Depends(get_db)):
    stmt=select(Payment).join(Order,Payment.order_id==Order.id).options(*payment_service.payment_loads())
    if provider: stmt=stmt.where(Payment.provider==provider)
    if payment_method: stmt=stmt.where(Payment.payment_method==payment_method)
    if status: stmt=stmt.where(Payment.status==status)
    if awaiting_verification: stmt=stmt.where(Payment.status==PaymentStatus.PENDING,Payment.proof_submitted_at.is_not(None))
    if date_from: stmt=stmt.where(Payment.created_at>=date_from)
    if date_to: stmt=stmt.where(Payment.created_at<=date_to)
    if search: stmt=stmt.where(or_(Order.order_number.ilike(f"%{search}%"),Order.contact_email.ilike(f"%{search}%"),Order.contact_phone.ilike(f"%{search}%")))
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows=db.execute(stmt.order_by(Payment.created_at.desc()).offset((page-1)*page_size).limit(page_size)).unique().scalars().all()
    return Page.build(items=[_admin_payment(p) for p in rows],page=page,page_size=page_size,total=total)

@router.get("/stats")
def payment_stats(actor:User=Depends(require_permission(Permission.PAYMENT_VIEW)),db:Session=Depends(get_db)):
    total=db.scalar(select(func.count()).select_from(Payment)) or 0
    states=db.execute(select(Payment.status,func.count()).group_by(Payment.status)).all(); methods=db.execute(select(Payment.payment_method,func.count()).group_by(Payment.payment_method)).all()
    collected=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.status==PaymentStatus.PAID)) or Decimal("0")
    awaiting=db.scalar(select(func.count()).select_from(Payment).where(Payment.status==PaymentStatus.PENDING,Payment.proof_submitted_at.is_not(None))) or 0
    return {"total_payments":total,"status_counts":{str(k):v for k,v in states},"method_counts":{str(k):v for k,v in methods},"awaiting_verification":awaiting,"collected_total":float(collected)}

@router.get("/{payment_id}")
def get_payment(payment_id:uuid.UUID,actor:User=Depends(require_permission(Permission.PAYMENT_VIEW)),db:Session=Depends(get_db)):
    payment=payment_service.get_payment(db,payment_id)
    if payment is None: raise NotFoundError("Payment not found")
    return _admin_payment(payment)

@router.post("/{payment_id}/verify-bank-transfer")
def verify_transfer(payment_id:uuid.UUID,payload:PaymentVerifyRequest,actor:User=Depends(require_permission(Permission.PAYMENT_MANAGE)),db:Session=Depends(get_db)):
    return _admin_payment(payment_service.verify_bank_transfer(db,payment_id,actor=actor,note=payload.note))

@router.post("/{payment_id}/reject-bank-transfer")
def reject_transfer(payment_id:uuid.UUID,payload:PaymentRejectRequest,actor:User=Depends(require_permission(Permission.PAYMENT_MANAGE)),db:Session=Depends(get_db)):
    return _admin_payment(payment_service.reject_bank_transfer(db,payment_id,actor=actor,reason=payload.reason))

@router.post("/{payment_id}/mark-cod-collected")
def mark_cod(payment_id:uuid.UUID,payload:PaymentVerifyRequest,actor:User=Depends(require_permission(Permission.PAYMENT_MANAGE)),db:Session=Depends(get_db)):
    return _admin_payment(payment_service.mark_cod_collected(db,payment_id,actor=actor,note=payload.note))

@router.post("/{payment_id}/refunds",response_model=RefundRead)
def request_refund(payment_id:uuid.UUID,payload:RefundCreateRequest,actor:User=Depends(require_permission(Permission.PAYMENT_MANAGE)),db:Session=Depends(get_db)):
    return payment_service.request_refund(db,payment_id,amount=payload.amount,reason=payload.reason,actor=actor)

@router.post("/refunds/{refund_id}/complete",response_model=RefundRead)
def complete_refund(refund_id:uuid.UUID,actor:User=Depends(require_permission(Permission.PAYMENT_MANAGE)),db:Session=Depends(get_db)):
    return payment_service.complete_refund(db,refund_id,actor=actor)

@shipping_router.get("/methods",response_model=list[ShippingMethodRead])
def list_methods(actor:User=Depends(require_permission(Permission.SETTINGS_MANAGE)),db:Session=Depends(get_db)):
    from app.models.shipping import ShippingMethod
    return db.execute(select(ShippingMethod).order_by(ShippingMethod.sort_order)).scalars().all()

@shipping_router.put("/methods/{method_id}",response_model=ShippingMethodRead)
def update_method(method_id:uuid.UUID,payload:ShippingMethodUpdate,actor:User=Depends(require_permission(Permission.SETTINGS_MANAGE)),db:Session=Depends(get_db)):
    return shipping_service.update_method(db,method_id,**payload.model_dump(exclude_unset=True))

@shipping_router.get("/couriers",response_model=list[CourierStatusRead],dependencies=[Depends(require_permission(Permission.ORDER_VIEW))])
def couriers():
    from app.models.enums import CourierProvider
    output=[]
    for code in CourierProvider:
        provider=shipping_service.get_courier(code)
        output.append({"code":str(code),"display_name":provider.display_name,"is_automated":provider.is_automated,"is_configured":provider.is_configured,"configuration_hint":provider.configuration_hint})
    return output

@shipping_router.get("/orders/{order_id}",response_model=ShipmentAdminRead)
def get_shipment(order_id:uuid.UUID,actor:User=Depends(require_permission(Permission.ORDER_VIEW)),db:Session=Depends(get_db)):
    from app.services.orders import get_order_by_id
    order=get_order_by_id(db,order_id)
    if order is None: raise NotFoundError("Order not found")
    return shipping_service.ensure_shipment(db,order)

@shipping_router.put("/orders/{order_id}/courier",response_model=ShipmentAdminRead)
def assign_courier(order_id:uuid.UUID,payload:CourierAssignRequest,actor:User=Depends(require_permission(Permission.ORDER_UPDATE)),db:Session=Depends(get_db)):
    return shipping_service.assign_courier(db,order_id,provider=payload.provider,tracking_number=payload.tracking_number,shipment_reference=payload.shipment_reference,tracking_url=payload.tracking_url,label_url=payload.label_url,notes=payload.notes,actor=actor)

@shipping_router.put("/orders/{order_id}/status",response_model=ShipmentAdminRead)
def update_shipping_status(order_id:uuid.UUID,payload:ShippingStatusUpdate,actor:User=Depends(require_permission(Permission.ORDER_UPDATE)),db:Session=Depends(get_db)):
    return shipping_service.update_shipping_status(db,order_id,payload.status,actor=actor,note=payload.note,location=payload.location)

@shipping_router.get("/orders/{order_id}/label.pdf")
def shipping_label(order_id:uuid.UUID,actor:User=Depends(require_permission(Permission.ORDER_VIEW)),db:Session=Depends(get_db)):
    from app.services.orders import get_order_by_id
    from reportlab.lib.pagesizes import A6
    from reportlab.pdfgen import canvas
    import io
    order=get_order_by_id(db,order_id)
    if order is None: raise NotFoundError("Order not found")
    stream=io.BytesIO(); c=canvas.Canvas(stream,pagesize=A6); width,height=A6
    c.setFont("Helvetica-Bold",14); c.drawString(28,height-35,"RG THRIFTING HUB")
    c.setFont("Helvetica-Bold",12); c.drawString(28,height-65,f"Order {order.order_number}")
    address=order.shipping_address_snapshot or {}; y=height-95
    c.setFont("Helvetica-Bold",10); c.drawString(28,y,str(address.get("full_name") or (f"{order.user.first_name} {order.user.last_name}" if order.user else "Guest"))); y-=16
    c.setFont("Helvetica",9)
    for value in (order.contact_phone,address.get("line1"),address.get("line2"),address.get("city"),address.get("province"),address.get("postal_code")):
        if value: c.drawString(28,y,str(value)[:64]); y-=13
    if order.shipment and order.shipment.tracking_number:
        y-=10;c.setFont("Helvetica-Bold",10);c.drawString(28,y,f"{order.shipment.provider}: {order.shipment.tracking_number}")
    c.setFont("Helvetica",9);c.drawString(28,28,f"COD / Payable: PKR {order.total_amount:,.2f}" if order.payment_method.value=="COD" else f"Payment: {order.payment_status}")
    c.showPage();c.save()
    return Response(stream.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="label-{order.order_number}.pdf"'})
