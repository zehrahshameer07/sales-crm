"""Validation rules (request) and response shapes."""
import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActivityType = Literal["Call", "Visit", "Demo", "Follow-up"]
Status = Literal["Pending", "In Progress", "Completed"]
Product = Literal["FreeBees-Menu", "FreeBees-Play", "Both"]

PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{7,20}$")


class ActivityCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_name: str = Field(..., min_length=2, max_length=120)
    activity_type: ActivityType
    status: Status
    contact: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=120)
    product_interested: Optional[Product] = None
    notes: Optional[str] = Field(None, max_length=500)
    start_date: date = Field(default_factory=date.today)   # defaults to today, can be backdated
    end_date: Optional[date] = None                         # filled in when the activity is completed

    @field_validator("contact", "location", "notes", "product_interested", "end_date", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        """Treat blank form fields as 'not provided'."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("contact")
    @classmethod
    def check_phone(cls, value):
        if value is not None and not PHONE_PATTERN.match(value):
            raise ValueError("Contact must be a valid phone number (digits, +, -, spaces)")
        return value


class ActivityUpdate(BaseModel):
    """Used for editing. Every field is optional, so you can send only what changed."""
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_name: Optional[str] = Field(None, min_length=2, max_length=120)
    activity_type: Optional[ActivityType] = None
    status: Optional[Status] = None
    contact: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=120)
    product_interested: Optional[Product] = None
    notes: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("customer_name", "activity_type", "status", "start_date", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be empty")
        return value

    @field_validator("contact", "location", "notes", "product_interested", "end_date", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("contact")
    @classmethod
    def check_phone(cls, value):
        if value is not None and not PHONE_PATTERN.match(value):
            raise ValueError("Contact must be a valid phone number (digits, +, -, spaces)")
        return value


class ActivityOut(ActivityCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CountItem(BaseModel):
    label: str
    count: int


class DayCount(BaseModel):
    date: str
    label: str
    count: int


class StatsOut(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    completion_rate: int          # percentage of activities that are Completed
    avg_days_to_complete: Optional[float] = None   # average of (end date - start date)
    fastest_days: Optional[int] = None
    slowest_days: Optional[int] = None
    timed_count: int = 0          # completed activities that have an end date
    by_type: list[CountItem]
    by_product: list[CountItem]
    last_7_days: list[DayCount]   # always the last 7 days, regardless of period