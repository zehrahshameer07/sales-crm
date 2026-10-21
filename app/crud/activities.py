"""Activities: who can see what, create/edit rules, duplicate prevention, status changes."""
import math
import uuid
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import schemas
from ..enums import ALLOWED_STATUS_CHANGES, ActivityStatus, UserRole
from ..errors import AppError, conflict, forbidden, invalid, not_found
from ..models import Activity, StatusHistory, User, make_customer_key
from ..timeutil import today as business_today


# --------------------------------------------------------------- filters
@dataclass
class ActivityFilters:
    period: str = "all"                      # today | week | month | all
    start_from: Optional[date] = None        # explicit date range (start date), used by reports
    start_to: Optional[date] = None
    status: Optional[ActivityStatus] = None
    activity_type: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    search: Optional[str] = None
    follow_up: Optional[str] = None          # overdue | due_today | upcoming

    def without_period(self) -> "ActivityFilters":
        return replace(self, period="all", start_from=None, start_to=None, status=None,
                       activity_type=None, search=None, follow_up=None)


def period_start(period: str) -> Optional[date]:
    day = business_today()
    if period == "today":
        return day
    if period == "week":
        return day - timedelta(days=day.weekday())   # Monday
    if period == "month":
        return day.replace(day=1)
    return None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ----------------------------------------------------------------- scope
def visible_owner_ids(db: Session, user: User) -> Optional[list[uuid.UUID]]:
    """Whose activities this user may see. None means everyone (admin)."""
    if user.role == UserRole.ADMIN:
        return None
    ids = [user.id]
    if user.role == UserRole.MANAGER:
        ids += list(db.scalars(select(User.id).where(User.manager_id == user.id)).all())
    return ids


def build_conditions(db: Session, user: User, f: ActivityFilters) -> list:
    conditions = []
    visible = visible_owner_ids(db, user)
    if visible is not None:
        conditions.append(Activity.owner_id.in_(visible))

    if f.owner_id:
        if visible is not None and f.owner_id not in visible:
            raise not_found("Salesperson not found")
        conditions.append(Activity.owner_id == f.owner_id)

    start = f.start_from or period_start(f.period)
    if start:
        conditions.append(Activity.start_date >= start)
    if f.start_to:
        conditions.append(Activity.start_date <= f.start_to)
    if f.status:
        conditions.append(Activity.status == f.status)
    if f.activity_type:
        conditions.append(Activity.activity_type == f.activity_type)
    if f.search and f.search.strip():
        like = f"%{_escape_like(f.search.strip().lower())}%"
        conditions.append(func.lower(Activity.customer_name).like(like, escape="\\"))

    day = business_today()
    if f.follow_up == "overdue":
        conditions += [Activity.follow_up_date < day, Activity.status != ActivityStatus.COMPLETED]
    elif f.follow_up == "due_today":
        conditions += [Activity.follow_up_date == day, Activity.status != ActivityStatus.COMPLETED]
    elif f.follow_up == "upcoming":
        conditions += [Activity.follow_up_date > day, Activity.status != ActivityStatus.COMPLETED]
    return conditions


_LOAD = (joinedload(Activity.owner), joinedload(Activity.creator), joinedload(Activity.updater))


def list_activities(
    db: Session, user: User, f: ActivityFilters, page: int, page_size: int
) -> tuple[list[Activity], int]:
    conditions = build_conditions(db, user, f)
    total = db.scalar(select(func.count(Activity.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(Activity)
        .options(*_LOAD)
        .where(*conditions)
        .order_by(Activity.start_date.desc(), Activity.created_at.desc(), Activity.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return list(rows), total


def all_for_export(db: Session, user: User, f: ActivityFilters, limit: int = 5000) -> list[Activity]:
    conditions = build_conditions(db, user, f)
    rows = db.scalars(
        select(Activity)
        .options(*_LOAD)
        .where(*conditions)
        .order_by(Activity.start_date.desc(), Activity.created_at.desc(), Activity.id)
        .limit(limit)
    ).unique().all()
    return list(rows)


def get_visible_activity(db: Session, user: User, activity_id: uuid.UUID) -> Activity:
    """404 for activities that don't exist AND for ones the user may not see (so IDs can't be probed)."""
    # populate_existing: after an edit, reload related people too (otherwise "updated by" could be stale)
    activity = db.scalar(
        select(Activity).options(*_LOAD).where(Activity.id == activity_id).execution_options(populate_existing=True)
    )
    if activity is None:
        raise not_found("Activity not found")
    visible = visible_owner_ids(db, user)
    if visible is not None and activity.owner_id not in visible:
        raise not_found("Activity not found")
    return activity


# ----------------------------------------------------------- permissions
def can_edit(user: User, activity: Activity) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    return activity.owner_id == user.id and activity.status != ActivityStatus.COMPLETED


def can_change_status(user: User, activity: Activity) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.MANAGER:
        # A manager approves their team's work, not their own
        return activity.owner_id != user.id and activity.owner.manager_id == user.id
    return False


def permissions_for(user: User, activity: Activity) -> schemas.ActivityPermissions:
    return schemas.ActivityPermissions(
        can_edit=can_edit(user, activity),
        can_change_status=can_change_status(user, activity) and activity.status != ActivityStatus.COMPLETED,
        can_set_end_date=user.role == UserRole.ADMIN and activity.status == ActivityStatus.COMPLETED,
    )


def serialize(user: User, activity: Activity) -> schemas.ActivityOut:
    return schemas.ActivityOut(
        id=activity.id,
        owner=schemas.UserBrief.model_validate(activity.owner),
        customer_name=activity.customer_name,
        activity_type=activity.activity_type,
        status=activity.status,
        product_interested=activity.product_interested,
        contact=activity.contact,
        location=activity.location,
        notes=activity.notes,
        start_date=activity.start_date,
        end_date=activity.end_date,
        days_to_complete=activity.days_to_complete,
        follow_up_date=activity.follow_up_date,
        follow_up_notes=activity.follow_up_notes,
        created_by_name=activity.creator.full_name if activity.creator else None,
        updated_by_name=activity.updater.full_name if activity.updater else None,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
        permissions=permissions_for(user, activity),
    )


# ----------------------------------------------------------------- rules
def _check_dates(start: date, end: Optional[date], follow_up: Optional[date], status: ActivityStatus) -> None:
    day = business_today()
    if start > day:
        raise invalid("Start date can't be in the future.")
    if follow_up is not None and follow_up < start:
        raise invalid("Follow-up date can't be before the start date.")
    if end is not None:
        if status != ActivityStatus.COMPLETED:
            raise invalid("An end date can only be set on a completed activity.")
        if end < start:
            raise invalid("End date can't be before the start date.")
        if end > day:
            raise invalid("End date can't be in the future.")


def _duplicate_message(name: str, activity_type, start: date) -> str:
    label = activity_type.value.replace("_", " ")
    return (
        f"You already logged a {label} for {name} on {start.strftime('%d %b %Y')}. "
        "Edit that activity instead of adding a new one."
    )


def _find_duplicate(db: Session, owner_id, name: str, activity_type, start: date, exclude_id=None) -> bool:
    query = select(Activity.id).where(
        Activity.owner_id == owner_id,
        Activity.customer_key == make_customer_key(name),
        Activity.activity_type == activity_type,
        Activity.start_date == start,
    )
    if exclude_id:
        query = query.where(Activity.id != exclude_id)
    return db.scalar(query) is not None


def _log(db: Session, activity: Activity, by: User, old: Optional[ActivityStatus], new: ActivityStatus) -> None:
    db.add(StatusHistory(activity=activity, changed_by_id=by.id, from_status=old, to_status=new))


# ------------------------------------------------------------------ CRUD
def create_activity(db: Session, user: User, data: schemas.ActivityCreate) -> Activity:
    owner = user
    if data.owner_id and data.owner_id != user.id:
        if user.role != UserRole.ADMIN:
            raise forbidden("Only admins can log activities for someone else.")
        owner = db.get(User, data.owner_id)
        if owner is None or not owner.is_active:
            raise invalid("The selected salesperson does not exist or is deactivated.")

    start = data.start_date or business_today()
    _check_dates(start, None, data.follow_up_date, ActivityStatus.PENDING)

    if _find_duplicate(db, owner.id, data.customer_name, data.activity_type, start):
        raise conflict(_duplicate_message(data.customer_name, data.activity_type, start))

    activity = Activity(
        owner_id=owner.id,
        customer_name=data.customer_name,
        activity_type=data.activity_type,
        status=ActivityStatus.PENDING,        # always starts as pending
        product_interested=data.product_interested,
        contact=data.contact,
        location=data.location,
        notes=data.notes,
        start_date=start,
        follow_up_date=data.follow_up_date,
        follow_up_notes=data.follow_up_notes,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(activity)
    _log(db, activity, user, None, ActivityStatus.PENDING)
    try:
        db.commit()
    except IntegrityError:        # two identical requests at the same moment: the database rule wins
        db.rollback()
        raise conflict(_duplicate_message(data.customer_name, data.activity_type, start))
    return get_visible_activity(db, user, activity.id)


def update_activity(db: Session, user: User, activity: Activity, data: schemas.ActivityUpdate) -> Activity:
    if not can_edit(user, activity):
        if activity.owner_id == user.id and activity.status == ActivityStatus.COMPLETED:
            raise forbidden("Completed activities can only be edited by an admin.")
        raise forbidden("You can only edit your own activities.")

    changes = data.model_dump(exclude_unset=True)

    if "owner_id" in changes:
        if user.role != UserRole.ADMIN:
            raise forbidden("Only admins can reassign an activity.")
        new_owner = db.get(User, changes["owner_id"]) if changes["owner_id"] else None
        if new_owner is None or not new_owner.is_active:
            raise invalid("The selected salesperson does not exist or is deactivated.")
    if "end_date" in changes and user.role != UserRole.ADMIN:
        raise forbidden("Only admins can change the end date.")

    owner_id = changes.get("owner_id", activity.owner_id)
    name = changes.get("customer_name", activity.customer_name)
    activity_type = changes.get("activity_type", activity.activity_type)
    start = changes.get("start_date", activity.start_date)
    end = changes["end_date"] if "end_date" in changes else activity.end_date
    follow_up = changes["follow_up_date"] if "follow_up_date" in changes else activity.follow_up_date

    _check_dates(start, end, follow_up, activity.status)
    if _find_duplicate(db, owner_id, name, activity_type, start, exclude_id=activity.id):
        raise conflict(_duplicate_message(name, activity_type, start))

    for field, value in changes.items():
        setattr(activity, field, value)
    activity.updated_by_id = user.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict(_duplicate_message(name, activity_type, start))
    return get_visible_activity(db, user, activity.id)


def change_status(db: Session, user: User, activity: Activity, data: schemas.StatusChangeIn) -> Activity:
    if not can_change_status(user, activity):
        raise forbidden("Only an admin, or the salesperson's manager, can change the status.")

    new = data.status
    if new == activity.status:
        raise conflict(f"This activity is already {new.value.replace('_', ' ')}.")
    if new not in ALLOWED_STATUS_CHANGES[activity.status]:
        raise conflict(
            f"Status can't move from {activity.status.value.replace('_', ' ')} to {new.value.replace('_', ' ')}. "
            "It can only move forward."
        )

    end = None
    if new == ActivityStatus.COMPLETED:
        end = data.end_date or business_today()
    elif data.end_date is not None:
        raise invalid("An end date can only be set when completing an activity.")
    _check_dates(activity.start_date, end, activity.follow_up_date, new)

    old = activity.status
    activity.status = new
    activity.end_date = end
    activity.updated_by_id = user.id
    _log(db, activity, user, old, new)
    db.commit()
    return get_visible_activity(db, user, activity.id)


def history(db: Session, activity: Activity) -> list[schemas.StatusHistoryOut]:
    rows = db.scalars(
        select(StatusHistory)
        .options(joinedload(StatusHistory.changed_by))
        .where(StatusHistory.activity_id == activity.id)
        .order_by(StatusHistory.changed_at, StatusHistory.id)
    ).unique().all()
    return [
        schemas.StatusHistoryOut(
            id=row.id,
            from_status=row.from_status,
            to_status=row.to_status,
            changed_by_name=row.changed_by.full_name if row.changed_by else None,
            changed_at=row.changed_at,
        )
        for row in rows
    ]


def pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))
