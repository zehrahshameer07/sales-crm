"""FastAPI application: API routes + the web frontend."""
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .bootstrap import startup
from .config import settings
from .errors import install_error_handlers
from .routers import activities, auth, health, reports, stats, users

# Some Windows setups map .js to text/plain, which browsers refuse to run as a script
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent.parent

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup()          # migrations, first admin, optional demo data
    yield


app = FastAPI(
    title="FreeBees Sales CRM API",
    version="2.0.0",
    description="Sales activity tracking with login, roles (admin / manager / salesperson), "
                "dashboards and exports. Log in via POST /api/auth/login (a session cookie is set).",
    lifespan=lifespan,
)
install_error_handlers(app)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"      # never cache anyone's data
    if request.url.path not in DOCS_PATHS:                   # the Swagger page loads its own scripts
        response.headers["Content-Security-Policy"] = CSP
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(activities.router)
app.include_router(stats.router)
app.include_router(reports.router)
app.include_router(health.router)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html", headers={"Cache-Control": "no-cache"})
