"""Password hashing and JWT handling.

Passwords are hashed with Argon2id (the current password-hashing competition
winner) and never stored or logged in plaintext. Access tokens are signed JWTs
delivered in an HTTP-only cookie so browser JavaScript cannot read them.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.models.enums import UserRole

JWT_ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used weaker parameters than the current policy."""
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or not an access token."""


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": str(role),
        "type": TOKEN_TYPE_ACCESS,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise TokenError("Not an access token")
    return payload


def user_id_from_token(token: str) -> uuid.UUID:
    payload = decode_access_token(token)
    try:
        return uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise TokenError("Token subject is not a valid user id") from exc
