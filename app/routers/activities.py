import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .. import schemas
from ..crud import activities as crud
from ..crud.activities import ActivityFilters
from ..deps import CurrentUser, DbSession
from ..errors import too_many
from ..security import write_limiter
from .filters import activity_filters

router = APIRouter(prefix="/api/activities", tags=["Activities"])

Filters = Annotated[ActivityFilters, Depends(activity_filters)]


def _throttle(user) -> None:
    wait = write_limiter.hit(f"write:{user.id}")
    if wait:
        raise too_many("You're doing that too quickly. Please wait a moment.", wait)


@router.post("", response_model=schemas.ActivityOut, status_code=201)
def create_activity(data: schemas.ActivityCreate, user: CurrentUser, db: DbSession):
    _throttle(user)
    return crud.serialize(user, crud.create_activity(db, user, data))


@router.get("", response_model=schemas.ActivityPage)
def list_activities(
    user: CurrentUser,
    db: DbSession,
    filters: Filters,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    rows, total = crud.list_activities(db, user, filters, page, page_size)
    return schemas.ActivityPage(
        items=[crud.serialize(user, a) for a in rows],
        total=total, page=page, page_size=page_size, pages=crud.pages(total, page_size),
    )


@router.get("/{activity_id}", response_model=schemas.ActivityOut)
def get_activity(activity_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return crud.serialize(user, crud.get_visible_activity(db, user, activity_id))


@router.patch("/{activity_id}", response_model=schemas.ActivityOut)
def update_activity(activity_id: uuid.UUID, data: schemas.ActivityUpdate, user: CurrentUser, db: DbSession):
    _throttle(user)
    activity = crud.get_visible_activity(db, user, activity_id)
    return crud.serialize(user, crud.update_activity(db, user, activity, data))


@router.post("/{activity_id}/status", response_model=schemas.ActivityOut)
def change_status(activity_id: uuid.UUID, data: schemas.StatusChangeIn, user: CurrentUser, db: DbSession):
    """Admins (any activity) and managers (their team's) can move an activity forward."""
    _throttle(user)
    activity = crud.get_visible_activity(db, user, activity_id)
    return crud.serialize(user, crud.change_status(db, user, activity, data))


@router.get("/{activity_id}/history", response_model=list[schemas.StatusHistoryOut])
def activity_history(activity_id: uuid.UUID, user: CurrentUser, db: DbSession):
    activity = crud.get_visible_activity(db, user, activity_id)
    return crud.history(db, activity)
