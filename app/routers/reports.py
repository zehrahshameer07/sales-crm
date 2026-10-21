from typing import Annotated

from fastapi import APIRouter, Depends, Response

from .. import schemas
from ..crud import activities as activity_crud
from ..crud import stats as stats_crud
from ..crud.activities import ActivityFilters
from ..deps import CurrentUser, DbSession
from ..errors import too_many
from ..models import User
from ..security import export_limiter
from ..services import exports
from ..timeutil import today
from .filters import activity_filters

router = APIRouter(prefix="/api/reports", tags=["Reports"])

Filters = Annotated[ActivityFilters, Depends(activity_filters)]
EXPORT_LIMIT = 5000
PDF_ROW_LIMIT = 500


def _describe(db, user, f: ActivityFilters) -> dict:
    description = {}
    start = f.start_from or activity_crud.period_start(f.period)
    if start or f.start_to:
        description["Start date"] = f"{start.isoformat() if start else 'any'} to {f.start_to.isoformat() if f.start_to else 'today'}"
    else:
        description["Start date"] = "All time"
    if f.status:
        description["Status"] = f.status.value.replace("_", " ").title()
    if f.activity_type:
        description["Type"] = f.activity_type.value.replace("_", " ").title()
    if f.owner_id:
        person = db.get(User, f.owner_id)
        description["Salesperson"] = person.full_name if person else "Selected"
    if f.search:
        description["Customer contains"] = f.search
    return description


def _throttle(user) -> None:
    wait = export_limiter.hit(f"export:{user.id}")
    if wait:
        raise too_many("Too many exports. Please wait a moment and try again.", wait)


@router.get("/summary", response_model=schemas.Report)
def summary(user: CurrentUser, db: DbSession, filters: Filters):
    return stats_crud.report(db, user, filters, _describe(db, user, filters))


@router.get("/activities.csv")
def export_csv(user: CurrentUser, db: DbSession, filters: Filters):
    _throttle(user)
    rows = activity_crud.all_for_export(db, user, filters, limit=EXPORT_LIMIT)
    return Response(
        content=exports.activities_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="sales-activities-{today().isoformat()}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/activities.pdf")
def export_pdf(user: CurrentUser, db: DbSession, filters: Filters):
    _throttle(user)
    description = _describe(db, user, filters)
    report = stats_crud.report(db, user, filters, description)
    rows = activity_crud.all_for_export(db, user, filters, limit=PDF_ROW_LIMIT + 1)
    truncated = len(rows) > PDF_ROW_LIMIT
    pdf = exports.activities_pdf(
        rows[:PDF_ROW_LIMIT], report, user.full_name,
        "; ".join(f"{k}: {v}" for k, v in description.items()), truncated,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sales-report-{today().isoformat()}.pdf"',
            "Cache-Control": "no-store",
        },
    )
