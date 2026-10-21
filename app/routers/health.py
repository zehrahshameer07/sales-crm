from fastapi import APIRouter, Response
from sqlalchemy import text

from ..database import engine

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health(response: Response):
    """Used by hosting platforms to check the app is alive and can reach its database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}
