"""API routes + serves the frontend."""
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, schemas
from .database import Base, engine, get_db

BASE_DIR = Path(__file__).resolve().parent.parent

# Create tables on startup if they don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sales CRM API", version="1.0.0")

Period = Literal["today", "week", "month", "all"]


@app.post("/api/activities", response_model=schemas.ActivityOut, status_code=201)
def create_activity(data: schemas.ActivityCreate, db: Session = Depends(get_db)):
    """Create a new sales activity."""
    try:
        return crud.create_activity(db, data)
    except crud.InvalidActivity as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/api/activities", response_model=List[schemas.ActivityOut])
def list_activities(
    period: Period = "all",
    status: Optional[schemas.Status] = None,
    search: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """List activities (newest first). Optional filters: period, status, search."""
    return crud.list_activities(db, period, status, search)


@app.patch("/api/activities/{activity_id}", response_model=schemas.ActivityOut)
def update_activity(activity_id: int, data: schemas.ActivityUpdate, db: Session = Depends(get_db)):
    """Edit an activity or change its status (status can only move forward)."""
    try:
        activity = crud.update_activity(db, activity_id, data)
    except crud.InvalidActivity as error:
        raise HTTPException(status_code=400, detail=str(error))
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@app.get("/api/stats", response_model=schemas.StatsOut)
def get_stats(period: Period = "all", db: Session = Depends(get_db)):
    """Dashboard counts for the chosen period."""
    return crud.get_stats(db, period)


# ---- Frontend ----
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")