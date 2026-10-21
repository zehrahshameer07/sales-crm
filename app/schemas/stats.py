import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from ..enums import UserRole


class CountItem(BaseModel):
    key: str
    count: int


class DayCount(BaseModel):
    date: date
    count: int


class FollowUps(BaseModel):
    overdue: int
    due_today: int
    next_7_days: int


class Durations(BaseModel):
    avg_days_to_complete: Optional[float] = None
    fastest_days: Optional[int] = None
    slowest_days: Optional[int] = None
    timed_count: int = 0


class Overview(BaseModel):
    scope_label: str
    scope_people: int
    total: int
    pending: int
    in_progress: int
    completed: int
    completion_rate: int
    durations: Durations
    follow_ups: FollowUps
    by_type: list[CountItem]
    by_product: list[CountItem]
    last_7_days: list[DayCount]


class TeamRow(BaseModel):
    user_id: uuid.UUID
    full_name: str
    role: UserRole
    manager_id: Optional[uuid.UUID] = None
    manager_name: Optional[str] = None
    region: Optional[str] = None
    is_active: bool
    is_self: bool
    total: int
    pending: int
    in_progress: int
    completed: int
    completion_rate: int
    avg_days_to_complete: Optional[float] = None
    follow_ups_overdue: int
    last_activity_date: Optional[date] = None


class Report(BaseModel):
    generated_at: datetime
    scope_label: str
    filters: dict
    overview: Overview
    by_status: list[CountItem]
    by_employee: list[TeamRow]
