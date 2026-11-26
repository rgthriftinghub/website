"""User persistence."""

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models.user import User


def normalize_email(email: str) -> str:
    """Emails are compared and stored case-insensitively."""
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == normalize_email(email))
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def email_exists(db: Session, email: str) -> bool:
    stmt = select(exists().where(func.lower(User.email) == normalize_email(email)))
    return bool(db.execute(stmt).scalar())
