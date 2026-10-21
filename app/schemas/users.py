import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..enums import UserRole
from .common import blank_to_none, check_phone, clean_name


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    manager_id: Optional[uuid.UUID] = None
    manager_name: Optional[str] = None
    designation: Optional[str] = None
    region: Optional[str] = None
    employee_code: Optional[str] = None
    is_active: bool
    must_change_password: bool
    is_locked: bool = False
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}

    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    role: UserRole = UserRole.SALESPERSON
    manager_id: Optional[uuid.UUID] = None
    designation: Optional[str] = Field(None, max_length=80)
    region: Optional[str] = Field(None, max_length=80)
    employee_code: Optional[str] = Field(None, max_length=30)
    password: Optional[str] = Field(None, max_length=128, description="Leave empty to generate a temporary password")

    @field_validator("phone", "designation", "region", "employee_code", "password", "manager_id", mode="before")
    @classmethod
    def _blank(cls, value):
        return blank_to_none(value)

    @field_validator("full_name")
    @classmethod
    def _name(cls, value):
        return clean_name(value)

    @field_validator("phone")
    @classmethod
    def _phone(cls, value):
        return check_phone(value)


class UserUpdate(BaseModel):
    model_config = {"str_strip_whitespace": True}

    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[UserRole] = None
    manager_id: Optional[uuid.UUID] = None
    designation: Optional[str] = Field(None, max_length=80)
    region: Optional[str] = Field(None, max_length=80)
    employee_code: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None

    @field_validator("full_name", "email", "role", "is_active", mode="before")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("phone", "designation", "region", "employee_code", "manager_id", mode="before")
    @classmethod
    def _blank(cls, value):
        return blank_to_none(value)

    @field_validator("full_name")
    @classmethod
    def _name(cls, value):
        return clean_name(value) if value else value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value):
        return check_phone(value)


class UserWithPassword(UserOut):
    """Returned once when an account is created or reset, so the admin can pass on the temporary password."""

    temporary_password: Optional[str] = None


class UserOption(BaseModel):
    """Minimal user info for dropdowns and filters."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: UserRole
    manager_id: Optional[uuid.UUID] = None


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int
    pages: int
