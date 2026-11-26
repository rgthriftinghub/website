"""Shared API dependencies: database session, current user, role enforcement."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import TokenError, user_id_from_token
from app.db.session import get_db
from app.models.enums import Permission, UserRole
from app.models.user import User
from app.repositories import user as user_repo

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
)


def _extract_token(request: Request) -> str | None:
    """Read the access token from the HTTP-only cookie.

    An `Authorization: Bearer` header is also accepted so non-browser API
    clients can authenticate without a cookie jar; browsers always use the
    cookie, which JavaScript cannot read.
    """
    settings = get_settings()
    cookie_token = request.cookies.get(settings.access_cookie_name)
    if cookie_token:
        return cookie_token

    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Resolve the signed-in user, or None when there is no valid session."""
    token = _extract_token(request)
    if token is None:
        return None
    try:
        user_id = user_id_from_token(token)
    except TokenError:
        return None

    user = user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Build a dependency that admits only the given roles.

    Authorisation foundation for the admin area. STAFF is admitted alongside
    ADMIN where the two currently share access; finer-grained staff permissions
    can later be layered on without changing call sites.
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return dependency


def require_permission(*required: "Permission") -> Callable[..., User]:
    """Build a dependency requiring specific staff permissions.

    ADMIN passes unconditionally. STAFF must hold **all** the listed permissions;
    partial credit would let a route run with half its preconditions met.

    The check is a database read rather than anything carried on the token, so
    revoking a permission takes effect on the next request instead of when a
    session happens to expire.
    """
    from app.models.enums import Permission as _Permission  # noqa: F401

    def dependency(
        user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        from app.services import permissions as permission_service

        if user.role is UserRole.ADMIN:
            return user
        if user.role is not UserRole.STAFF:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        held = permission_service.permissions_for(db, user)
        missing = [str(item) for item in required if item not in held]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {', '.join(missing)}",
            )
        return user

    return dependency


# Convenience aliases used by the admin routers.
require_admin = require_roles(UserRole.ADMIN)
require_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)
