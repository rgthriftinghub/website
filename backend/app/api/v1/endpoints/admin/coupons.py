"""Admin coupon management."""
import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import require_permission
from app.db.session import get_db
from app.models.coupon import Coupon
from app.models.enums import Permission
from app.models.user import User
from app.services.exceptions import ConflictError, NotFoundError

router=APIRouter()

class CouponInput(BaseModel):
    code:str=Field(min_length=3,max_length=40)
    discount_type:str
    discount_value:Decimal=Field(gt=0,max_digits=10,decimal_places=2)
    minimum_order:Decimal=Field(default=Decimal("0"),ge=0,max_digits=10,decimal_places=2)
    max_redemptions:int|None=Field(default=None,ge=1)
    starts_at:datetime|None=None
    ends_at:datetime|None=None
    is_active:bool=True
    @model_validator(mode="after")
    def valid_discount(self):
        if self.discount_type not in {"PERCENTAGE","FIXED_AMOUNT"}: raise ValueError("Use PERCENTAGE or FIXED_AMOUNT")
        if self.discount_type=="PERCENTAGE" and self.discount_value>100: raise ValueError("Percentage cannot exceed 100")
        if self.ends_at and self.starts_at and self.ends_at<=self.starts_at: raise ValueError("End must be after start")
        return self

@router.get("", dependencies=[Depends(require_permission(Permission.SALES_VIEW))])
def list_coupons(db:Session=Depends(get_db)):
    return db.execute(select(Coupon).order_by(Coupon.created_at.desc())).scalars().all()

@router.post("")
def create_coupon(payload:CouponInput,actor:User=Depends(require_permission(Permission.SALES_MANAGE)),db:Session=Depends(get_db)):
    values=payload.model_dump();values["code"]=values["code"].strip().upper()
    if db.scalar(select(Coupon).where(Coupon.code==values["code"])): raise ConflictError("Coupon code already exists")
    row=Coupon(**values);db.add(row);db.commit();db.refresh(row);return row

@router.put("/{coupon_id}")
def update_coupon(coupon_id:uuid.UUID,payload:CouponInput,actor:User=Depends(require_permission(Permission.SALES_MANAGE)),db:Session=Depends(get_db)):
    row=db.get(Coupon,coupon_id)
    if row is None: raise NotFoundError("Coupon not found")
    values=payload.model_dump();values["code"]=values["code"].strip().upper()
    duplicate=db.scalar(select(Coupon).where(Coupon.code==values["code"],Coupon.id!=coupon_id))
    if duplicate: raise ConflictError("Coupon code already exists")
    for key,value in values.items(): setattr(row,key,value)
    db.commit();db.refresh(row);return row

@router.delete("/{coupon_id}")
def delete_coupon(coupon_id:uuid.UUID,actor:User=Depends(require_permission(Permission.SALES_MANAGE)),db:Session=Depends(get_db)):
    row=db.get(Coupon,coupon_id)
    if row is None: raise NotFoundError("Coupon not found")
    db.delete(row);db.commit();return {"detail":"Coupon deleted"}
