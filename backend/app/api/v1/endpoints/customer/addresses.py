"""Customer address-book endpoints."""
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.address import AddressCreate, AddressRead, AddressUpdate
from app.services import addresses as address_service

router = APIRouter()

@router.get("", response_model=list[AddressRead])
def list_addresses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.list_addresses(db, user.id)

@router.get("/{address_id}", response_model=AddressRead)
def get_address(address_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.get_address(db, user.id, address_id)

@router.post("", response_model=AddressRead, status_code=status.HTTP_201_CREATED)
def create_address(payload: AddressCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.create_address(db, user.id, payload)

@router.put("/{address_id}", response_model=AddressRead)
def update_address(address_id: uuid.UUID, payload: AddressUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return address_service.update_address(db, user.id, address_id, payload)

@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address_service.delete_address(db, user.id, address_id)
