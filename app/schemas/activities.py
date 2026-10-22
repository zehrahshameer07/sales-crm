import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..enums import ActivityStatus, ActivityType, Product
from .common import blank_to_none, check_phone, clean_name
from .users import UserBrief


class _ActivityFields(BaseModel):
    model_config = {"str_strip_whitespace": True}

    @field_validator("customer_name", check_fields=False)
    @classmethod
    def _customer(cls, value):
        return clean_name(value) if value else value

    @field_validator("contact", check_fields=False)
    @classmethod
    def _phone(cls, value):
        return check_phone(value)


class ActivityCreate(_ActivityFields):
    customer_name: str = Field(..., min_length=2, max_length=120)
    activity_type: ActivityType
    status: ActivityStatus = ActivityStatus.PENDING
    product_interested: Optional[Product] = None
    contact: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = Field(None, description="Defaults to today; can be backdated")
    follow_up_date: Optional[date] = None
    follow_up_notes: Optional[str] = Field(None, max_length=500)
    owner_id: Optional[uuid.UUID] = Field(None, description="Admins only: log the activity for another user")

    @field_validator(
        "product_interested", "contact", "location", "notes", "start_date",
        "follow_up_date", "follow_up_notes", "owner_id", mode="before",
    )
    @classmethod
    def _blank(cls, value):
        return blank_to_none(value)


class ActivityUpdate(_ActivityFields):
    """Edit details. Status has its own endpoint, so it is not accepted here."""

    customer_name: Optional[str] = Field(None, min_length=2, max_length=120)
    activity_type: Optional[ActivityType] = None
    product_interested: Optional[Product] = None
    contact: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    follow_up_date: Optional[date] = None
    follow_up_notes: Optional[str] = Field(None, max_length=500)
    owner_id: Optional[uuid.UUID] = None

    @field_validator("customer_name", "activity_type", "start_date", mode="before")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator(
        "product_interested", "contact", "location", "notes", "end_date",
        "follow_up_date", "follow_up_notes", "owner_id", mode="before",
    )
    @classmethod
    def _blank(cls, value):
        return blank_to_none(value)


class StatusChangeIn(BaseModel):
    status: ActivityStatus
    end_date: Optional[date] = Field(None, description="When completing: the day it was completed (default today)")

    @field_validator("end_date", mode="before")
    @classmethod
    def _blank(cls, value):
        return blank_to_none(value)


class ActivityPermissions(BaseModel):
    can_edit: bool
    can_change_status: bool
    can_set_end_date: bool


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner: UserBrief
    customer_name: str
    activity_type: ActivityType
    status: ActivityStatus
    product_interested: Optional[Product] = None
    contact: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    days_to_complete: Optional[int] = None
    follow_up_date: Optional[date] = None
    follow_up_notes: Optional[str] = None
    created_by_name: Optional[str] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    permissions: ActivityPermissions


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    page_size: int
    pages: int


class StatusHistoryOut(BaseModel):
    id: uuid.UUID
    from_status: Optional[ActivityStatus] = None
    to_status: ActivityStatus
    changed_by_name: Optional[str] = None
    changed_at: datetime
