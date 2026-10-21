"""Query-string filters shared by the activity list, stats and report endpoints."""
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import Query

from ..crud.activities import ActivityFilters
from ..enums import ActivityStatus, ActivityType


def activity_filters(
    period: Literal["today", "week", "month", "all"] = "all",
    date_from: Optional[date] = Query(None, alias="from", description="Start date from (inclusive)"),
    date_to: Optional[date] = Query(None, alias="to", description="Start date to (inclusive)"),
    status: Optional[ActivityStatus] = None,
    activity_type: Optional[ActivityType] = None,
    owner_id: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None, max_length=100),
    follow_up: Optional[Literal["overdue", "due_today", "upcoming"]] = None,
) -> ActivityFilters:
    return ActivityFilters(
        period=period, start_from=date_from, start_to=date_to, status=status,
        activity_type=activity_type, owner_id=owner_id, search=search, follow_up=follow_up,
    )
