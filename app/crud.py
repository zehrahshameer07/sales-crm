"""Database queries, kept separate from the API routes."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas


def period_start(period: str) -> Optional[date]:
    """First day of today / this week (Monday) / this month, or None for all time."""
    today = date.today()
    if period == "today":
        return today
    if period == "week":
        return today - timedelta(days=today.weekday())
    if period == "month":
        return today.replace(day=1)
    return None


# ---------- Business rules ----------
# Status can only move forward: Pending -> In Progress -> Completed. Completed is final.
ALLOWED_STATUS_CHANGES = {
    "Pending": {"In Progress", "Completed"},
    "In Progress": {"Completed"},
    "Completed": set(),
}


class InvalidActivity(Exception):
    """The request breaks a business rule (shown to the user as a 400 error)."""


class InvalidStatusChange(InvalidActivity):
    """Someone tried to move an activity's status backwards."""


def check_dates(start: date, end: Optional[date], status: str) -> None:
    today = date.today()
    if start > today:
        raise InvalidActivity("Start date can't be in the future.")
    if end is not None:
        if status != "Completed":
            raise InvalidActivity("End date can only be set on a completed activity.")
        if end < start:
            raise InvalidActivity("End date can't be before the start date.")
        if end > today:
            raise InvalidActivity("End date can't be in the future.")


def create_activity(db: Session, data: schemas.ActivityCreate) -> models.Activity:
    values = data.model_dump()
    if values["status"] == "Completed" and values["end_date"] is None:
        values["end_date"] = date.today()          # completed today unless told otherwise
    check_dates(values["start_date"], values["end_date"], values["status"])

    activity = models.Activity(**values)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def update_activity(db: Session, activity_id: int, data: schemas.ActivityUpdate):
    """Edit an activity. Returns None if it doesn't exist."""
    activity = db.get(models.Activity, activity_id)
    if activity is None:
        return None

    changes = data.model_dump(exclude_unset=True)

    new_status = changes.get("status")
    moving_to_completed = False
    if new_status and new_status != activity.status:
        if new_status not in ALLOWED_STATUS_CHANGES.get(activity.status, set()):
            raise InvalidStatusChange(
                f"Status can't be changed from {activity.status} to {new_status}."
            )
        moving_to_completed = new_status == "Completed"

    final_start = changes.get("start_date", activity.start_date)
    final_end = changes["end_date"] if "end_date" in changes else activity.end_date
    final_status = new_status or activity.status

    if moving_to_completed and final_end is None:
        final_end = date.today()                    # completed today unless told otherwise
        changes["end_date"] = final_end

    check_dates(final_start, final_end, final_status)

    for field, value in changes.items():
        setattr(activity, field, value)
    db.commit()
    db.refresh(activity)
    return activity


def list_activities(db: Session, period: str, status: Optional[str], search: Optional[str]):
    query = db.query(models.Activity)
    start = period_start(period)
    if start:
        query = query.filter(models.Activity.start_date >= start)
    if status:
        query = query.filter(models.Activity.status == status)
    if search:
        query = query.filter(models.Activity.customer_name.ilike(f"%{search.strip()}%"))
    return query.order_by(
        models.Activity.start_date.desc(), models.Activity.created_at.desc(), models.Activity.id.desc()
    ).all()


TYPES = ["Call", "Visit", "Demo", "Follow-up"]
PRODUCTS = ["FreeBees-Menu", "FreeBees-Play", "Both"]


def _count_by(db: Session, column, start: Optional[date]) -> dict:
    query = db.query(column, func.count(models.Activity.id))
    if start:
        query = query.filter(models.Activity.start_date >= start)
    return dict(query.group_by(column).all())


def _last_7_days(db: Session) -> list:
    today = date.today()
    first = today - timedelta(days=6)
    rows = (
        db.query(models.Activity.start_date, func.count(models.Activity.id))
        .filter(models.Activity.start_date >= first)
        .group_by(models.Activity.start_date)
        .all()
    )
    per_day = {str(day): count for day, count in rows}
    days = []
    for i in range(7):
        day = first + timedelta(days=i)
        days.append({"date": day.isoformat(), "label": day.strftime("%a"), "count": per_day.get(day.isoformat(), 0)})
    return days


def _time_to_complete(db: Session, start: Optional[date]) -> dict:
    """How long completed activities took (end date minus start date), in days."""
    query = db.query(models.Activity.start_date, models.Activity.end_date).filter(
        models.Activity.status == "Completed", models.Activity.end_date.isnot(None)
    )
    if start:
        query = query.filter(models.Activity.start_date >= start)
    durations = [max(0, (end - begin).days) for begin, end in query.all()]
    if not durations:
        return {"avg_days_to_complete": None, "fastest_days": None, "slowest_days": None, "timed_count": 0}
    return {
        "avg_days_to_complete": round(sum(durations) / len(durations), 1),
        "fastest_days": min(durations),
        "slowest_days": max(durations),
        "timed_count": len(durations),
    }


def get_stats(db: Session, period: str) -> dict:
    start = period_start(period)
    by_status = _count_by(db, models.Activity.status, start)
    by_type = _count_by(db, models.Activity.activity_type, start)
    by_product = _count_by(db, models.Activity.product_interested, start)

    total = sum(by_status.values())
    completed = by_status.get("Completed", 0)
    products = [{"label": p, "count": by_product.get(p, 0)} for p in PRODUCTS]
    products.append({"label": "Not specified", "count": by_product.get(None, 0)})

    return {
        "total": total,
        "pending": by_status.get("Pending", 0),
        "in_progress": by_status.get("In Progress", 0),
        "completed": completed,
        "completion_rate": round(completed * 100 / total) if total else 0,
        **_time_to_complete(db, start),
        "by_type": [{"label": t, "count": by_type.get(t, 0)} for t in TYPES],
        "by_product": products,
        "last_7_days": _last_7_days(db),
    }