"""Account and authentication schemas.

`password_hash` is never declared on any response model, so it cannot be
serialised out of the API by accident.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("password")
    @classmethod
    def reject_whitespace_only_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None
