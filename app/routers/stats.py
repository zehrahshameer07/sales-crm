from typing import Annotated

from fastapi import APIRouter, Depends

from .. import schemas
from ..crud import stats as crud
from ..crud.activities import ActivityFilters
from ..deps import CurrentUser, DbSession, ManagerOrAdmin
from .filters import activity_filters

router = APIRouter(prefix="/api/stats", tags=["Dashboard"])

Filters = Annotated[ActivityFilters, Depends(activity_filters)]


@router.get("/overview", response_model=schemas.Overview)
def overview(user: CurrentUser, db: DbSession, filters: Filters):
    """Numbers for the dashboard, limited to what you may see (yours, your team's, or everyone's)."""
    return crud.overview(db, user, filters)


@router.get("/team", response_model=list[schemas.TeamRow])
def team(user: ManagerOrAdmin, db: DbSession, filters: Filters):
    """Per-employee progress for managers (their team) and admins (everyone)."""
    return crud.team(db, user, filters)
