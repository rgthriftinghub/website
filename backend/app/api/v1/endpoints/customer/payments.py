"""Customer payment status and bank-transfer reference submission."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.payments import service as payment_service
from app.schemas.payment import PaymentRead, BankTransferSubmission
from app.services import orders as order_service

router = APIRouter()

@router.get("/{order_number}/payment", response_model=PaymentRead)
def get_payment(order_number: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = order_service.get_order_for_user(db, user.id, order_number)
    if order.active_payment is None:
        from app.services.exceptions import NotFoundError
        raise NotFoundError("Payment not found")
    return order.active_payment

@router.post("/{order_number}/payment/bank-transfer", response_model=PaymentRead)
def submit_bank_transfer(order_number: str, payload: BankTransferSubmission, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return payment_service.submit_bank_transfer_proof(db, user.id, order_number, reference=payload.reference, note=payload.note, proof_url=payload.proof_url)
