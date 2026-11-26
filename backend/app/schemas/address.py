"""Customer address schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class AddressBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=6, max_length=32)
    address_line_1: str = Field(min_length=1, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=80)
    province: str = Field(min_length=1, max_length=80)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="Pakistan", min_length=1, max_length=80)
    is_default: bool = False

    @field_validator("full_name", "phone", "address_line_1", "city", "province", "country")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return _strip(value)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, min_length=6, max_length=32)
    address_line_1: str | None = Field(default=None, min_length=1, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    province: str | None = Field(default=None, min_length=1, max_length=80)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, min_length=1, max_length=80)
    is_default: bool | None = None


class AddressRead(AddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AddressSnapshot(BaseModel):
    """Address as frozen onto an order. Deliberately has no id or timestamps."""

    full_name: str
    phone: str
    address_line_1: str
    address_line_2: str | None = None
    city: str
    province: str
    postal_code: str | None = None
    country: str
