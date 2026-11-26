"""Staff permissions.

Deliberately small: a flat list of permissions, a row per grant, and one dependency
factory. No roles-within-roles, no scopes, no inheritance tree.

ADMIN implicitly holds every permission — there is no way to create a
half-privileged admin, because that is a support burden with no business value.
STAFF holds only what has been explicitly granted, so a newly created staff
account can look but not touch.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.admin import StaffPermissionGrant
from app.models.enums import DEFAULT_STAFF_PERMISSIONS, Permission, UserRole
from app.models.user import User
from app.services.exceptions import InvalidRequestError, NotFoundError

ALL_PERMISSIONS: frozenset[Permission] = frozenset(Permission)


def permissions_for(db: Session, user: User) -> frozenset[Permission]:
    """Every permission this user effectively holds."""
    if user.role is UserRole.ADMIN:
        return ALL_PERMISSIONS
    if user.role is not UserRole.STAFF:
        # Customers hold no admin permissions at all.
        return frozenset()

    granted = (
        db.execute(
            select(StaffPermissionGrant.permission).where(
                StaffPermissionGrant.user_id == user.id
            )
        )
        .scalars()
        .all()
    )
    return frozenset(granted)


def has_permission(db: Session, user: User, permission: Permission) -> bool:
    return permission in permissions_for(db, user)


def grant(
    db: Session,
    user_id: uuid.UUID,
    permissions: Iterable[Permission],
    *,
    granted_by: User | None = None,
) -> frozenset[Permission]:
    """Replace a staff member's grants with exactly `permissions`.

    Replacement rather than accumulation, so the admin screen is a checklist whose
    state matches reality — a permission unticked is a permission removed.
    """
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found")
    if target.role is UserRole.ADMIN:
        raise InvalidRequestError(
            "Admin accounts already hold every permission; grants do not apply."
        )
    if target.role is not UserRole.STAFF:
        raise InvalidRequestError("Only staff accounts can be granted permissions")

    wanted = set(permissions)
    db.execute(delete(StaffPermissionGrant).where(StaffPermissionGrant.user_id == user_id))
    for permission in sorted(wanted, key=str):
        db.add(
            StaffPermissionGrant(
                user_id=user_id,
                permission=permission,
                granted_by_user_id=granted_by.id if granted_by else None,
            )
        )
    db.commit()
    return frozenset(wanted)


def apply_default_grants(db: Session, user: User) -> None:
    """Give a brand-new staff account the read-only baseline."""
    if user.role is not UserRole.STAFF:
        return
    existing = permissions_for(db, user)
    if existing:
        return
    for permission in sorted(DEFAULT_STAFF_PERMISSIONS, key=str):
        db.add(StaffPermissionGrant(user_id=user.id, permission=permission))
    db.commit()


def list_staff(db: Session) -> Sequence[User]:
    return (
        db.execute(
            select(User)
            .where(User.role.in_([UserRole.STAFF, UserRole.ADMIN]))
            .order_by(User.role, User.email)
        )
        .scalars()
        .all()
    )
