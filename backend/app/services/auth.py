"""Registration and login logic."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password, needs_rehash, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import user as user_repo
from app.schemas.user import UserLoginRequest, UserRegisterRequest
from app.services.exceptions import AuthenticationError, ConflictError

# Deliberately identical for "no such email" and "wrong password" so the endpoint
# cannot be used to discover which addresses are registered.
INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password"


def register_user(
    db: Session, payload: UserRegisterRequest, *, role: UserRole = UserRole.CUSTOMER
) -> User:
    email = user_repo.normalize_email(payload.email)
    if user_repo.email_exists(db, email):
        raise ConflictError("An account with this email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone.strip() if payload.phone else None,
        role=role,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, payload: UserLoginRequest) -> User:
    user = user_repo.get_by_email(db, payload.email)
    if user is None:
        # Hash anyway so a missing account and a wrong password take a similar
        # amount of time, avoiding a timing oracle for valid addresses.
        hash_password(payload.password)
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

    if not verify_password(payload.password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

    if not user.is_active:
        raise AuthenticationError("This account has been deactivated")

    # Transparently upgrade the stored hash if the cost parameters have changed.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user
