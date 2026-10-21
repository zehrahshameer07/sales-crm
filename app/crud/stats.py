"""Dashboard numbers. Everything is limited to what the logged-in user is allowed to see."""
import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..enums import ActivityStatus, ActivityType, Product, UserRole
from ..models import Activity, User
from ..timeutil import today as business_today, utcnow
from . import users as user_crud
from .activities import ActivityFilters, build_conditions


def _status_counts(db: Session, conditions: list) -> dict:
    rows = db.execute(
        select(Activity.status, func.count(Activity.id)).where(*conditions).group_by(Activity.status)
    ).all()
    return {status: count for status, count in rows}


def _durations(db: Session, conditions: list) -> schemas.Durations:
    rows = db.execute(
        select(Activity.start_date, Activity.end_date).where(
            *conditions, Activity.status == ActivityStatus.COMPLETED, Activity.end_date.is_not(None)
        )
    ).all()
    days = [max(0, (end - start).days) for start, end in rows]
    if not days:
        return schemas.Durations()
    return schemas.Durations(
        avg_days_to_complete=round(sum(days) / len(days), 1),
        fastest_days=min(days),
        slowest_days=max(days),
        timed_count=len(days),
    )


def _scope_label(db: Session, user: User, f: ActivityFilters) -> tuple[str, int]:
    if f.owner_id:
        person = db.get(User, f.owner_id)
        return (person.full_name if person else "Selected salesperson"), 1
    if user.role == UserRole.ADMIN:
        people = db.scalar(
            select(func.count(User.id)).where(User.is_active.is_(True), User.role != UserRole.ADMIN)
        ) or 0
        return "Whole company", people
    if user.role == UserRole.MANAGER:
        people = len(user_crud.users_in_scope(db, user))
        return "Your team", people
    return "Your activities", 1


def overview(db: Session, user: User, f: ActivityFilters) -> schemas.Overview:
    conditions = build_conditions(db, user, f)
    counts = _status_counts(db, conditions)
    total = sum(counts.values())
    completed = counts.get(ActivityStatus.COMPLETED, 0)

    # Follow-ups are action items: they ignore the period and status filters but respect who you can see
    base = build_conditions(db, user, f.without_period())
    day = business_today()
    open_ = Activity.status != ActivityStatus.COMPLETED

    def follow_ups(*extra) -> int:
        return db.scalar(select(func.count(Activity.id)).where(*base, open_, *extra)) or 0

    follow = schemas.FollowUps(
        overdue=follow_ups(Activity.follow_up_date < day),
        due_today=follow_ups(Activity.follow_up_date == day),
        next_7_days=follow_ups(Activity.follow_up_date > day, Activity.follow_up_date <= day + timedelta(days=7)),
    )

    by_type_rows = dict(db.execute(
        select(Activity.activity_type, func.count(Activity.id)).where(*conditions).group_by(Activity.activity_type)
    ).all())
    by_product_rows = dict(db.execute(
        select(Activity.product_interested, func.count(Activity.id)).where(*conditions)
        .group_by(Activity.product_interested)
    ).all())

    first = day - timedelta(days=6)
    per_day = dict(db.execute(
        select(Activity.start_date, func.count(Activity.id))
        .where(*base, Activity.start_date >= first, Activity.start_date <= day)
        .group_by(Activity.start_date)
    ).all())

    label, people = _scope_label(db, user, f)
    return schemas.Overview(
        scope_label=label,
        scope_people=people,
        total=total,
        pending=counts.get(ActivityStatus.PENDING, 0),
        in_progress=counts.get(ActivityStatus.IN_PROGRESS, 0),
        completed=completed,
        completion_rate=round(completed * 100 / total) if total else 0,
        durations=_durations(db, conditions),
        follow_ups=follow,
        by_type=[schemas.CountItem(key=t.value, count=by_type_rows.get(t, 0)) for t in ActivityType],
        by_product=[schemas.CountItem(key=p.value, count=by_product_rows.get(p, 0)) for p in Product]
        + [schemas.CountItem(key="none", count=by_product_rows.get(None, 0))],
        last_7_days=[
            schemas.DayCount(date=first + timedelta(days=i), count=per_day.get(first + timedelta(days=i), 0))
            for i in range(7)
        ],
    )


def by_status(db: Session, user: User, f: ActivityFilters) -> list[schemas.CountItem]:
    counts = _status_counts(db, build_conditions(db, user, f))
    return [schemas.CountItem(key=s.value, count=counts.get(s, 0)) for s in ActivityStatus]


def team(db: Session, user: User, f: ActivityFilters) -> list[schemas.TeamRow]:
    """One row per salesperson/manager the viewer can see, with their numbers."""
    conditions = build_conditions(db, user, f)
    people = [p for p in user_crud.users_in_scope(db, user, include_inactive=True) if p.role != UserRole.ADMIN]
    if f.owner_id:
        people = [p for p in people if p.id == f.owner_id]

    counts: dict = defaultdict(lambda: defaultdict(int))
    for owner_id, status, n in db.execute(
        select(Activity.owner_id, Activity.status, func.count(Activity.id))
        .where(*conditions).group_by(Activity.owner_id, Activity.status)
    ).all():
        counts[owner_id][status] = n

    durations: dict = defaultdict(list)
    for owner_id, start, end in db.execute(
        select(Activity.owner_id, Activity.start_date, Activity.end_date).where(
            *conditions, Activity.status == ActivityStatus.COMPLETED, Activity.end_date.is_not(None)
        )
    ).all():
        durations[owner_id].append(max(0, (end - start).days))

    day = business_today()
    base = build_conditions(db, user, f.without_period())
    overdue = dict(db.execute(
        select(Activity.owner_id, func.count(Activity.id)).where(
            *base, Activity.status != ActivityStatus.COMPLETED, Activity.follow_up_date < day
        ).group_by(Activity.owner_id)
    ).all())

    last_dates = dict(db.execute(
        select(Activity.owner_id, func.max(Activity.start_date)).where(*conditions).group_by(Activity.owner_id)
    ).all())

    names = {p.id: p.full_name for p in db.scalars(select(User)).all()}
    rows = []
    for person in people:
        c = counts.get(person.id, {})
        total = sum(c.values())
        if not person.is_active and total == 0:
            continue
        completed = c.get(ActivityStatus.COMPLETED, 0)
        days = durations.get(person.id, [])
        rows.append(schemas.TeamRow(
            user_id=person.id,
            full_name=person.full_name,
            role=person.role,
            manager_id=person.manager_id,
            manager_name=names.get(person.manager_id),
            region=person.region,
            is_active=person.is_active,
            is_self=person.id == user.id,
            total=total,
            pending=c.get(ActivityStatus.PENDING, 0),
            in_progress=c.get(ActivityStatus.IN_PROGRESS, 0),
            completed=completed,
            completion_rate=round(completed * 100 / total) if total else 0,
            avg_days_to_complete=round(sum(days) / len(days), 1) if days else None,
            follow_ups_overdue=overdue.get(person.id, 0),
            last_activity_date=last_dates.get(person.id),
        ))
    rows.sort(key=lambda r: (-r.completed, -r.total, r.full_name))
    return rows


def report(db: Session, user: User, f: ActivityFilters, filters_description: dict) -> schemas.Report:
    ov = overview(db, user, f)
    return schemas.Report(
        generated_at=utcnow(),
        scope_label=ov.scope_label,
        filters=filters_description,
        overview=ov,
        by_status=by_status(db, user, f),
        by_employee=team(db, user, f) if user.role != UserRole.SALESPERSON else [],
    )
