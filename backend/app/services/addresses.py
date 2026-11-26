"""Customer address book.

Every function takes the requesting user's id and scopes its query by it, so one
customer can never read or modify another's address by id.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.address import CustomerAddress
from app.schemas.address import AddressCreate, AddressUpdate
from app.services.exceptions import NotFoundError


def list_addresses(db: Session, user_id: uuid.UUID) -> Sequence[CustomerAddress]:
    return (
        db.execute(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user_id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_address(db: Session, user_id: uuid.UUID, address_id: uuid.UUID) -> CustomerAddress:
    address = db.execute(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id, CustomerAddress.user_id == user_id
        )
    ).scalar_one_or_none()
    if address is None:
        raise NotFoundError("Address not found")
    return address


def _clear_other_defaults(db: Session, user_id: uuid.UUID, keep_id: uuid.UUID | None) -> None:
    """Demote any other default, so the partial unique index cannot be violated."""
    stmt = (
        update(CustomerAddress)
        .where(CustomerAddress.user_id == user_id, CustomerAddress.is_default.is_(True))
        .values(is_default=False)
    )
    if keep_id is not None:
        stmt = stmt.where(CustomerAddress.id != keep_id)
    db.execute(stmt)


def create_address(db: Session, user_id: uuid.UUID, payload: AddressCreate) -> CustomerAddress:
    existing = list_addresses(db, user_id)
    address = CustomerAddress(user_id=user_id, **payload.model_dump())

    # The first address a customer saves becomes their default automatically.
    if not existing:
        address.is_default = True
    if address.is_default:
        _clear_other_defaults(db, user_id, keep_id=None)

    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def update_address(
    db: Session, user_id: uuid.UUID, address_id: uuid.UUID, payload: AddressUpdate
) -> CustomerAddress:
    address = get_address(db, user_id, address_id)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("is_default") is True:
        _clear_other_defaults(db, user_id, keep_id=address.id)

    for field, value in changes.items():
        setattr(address, field, value)
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
    """Hard delete is safe here: orders keep their own address snapshot."""
    address = get_address(db, user_id, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()

    # Promote another address so the customer always has a default to check out with.
    if was_default:
        remaining = list_addresses(db, user_id)
        if remaining:
            remaining[0].is_default = True
    db.commit()
