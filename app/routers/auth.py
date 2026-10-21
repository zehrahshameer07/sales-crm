from fastapi import APIRouter, Request, Response

from .. import schemas
from ..config import settings
from ..crud import users as user_crud
from ..deps import AnyUser, DbSession
from ..errors import AppError
from ..security import client_ip, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

APP_VERSION = "2.0.0"


def _set_session_cookie(response: Response, user) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id, user.password_hash),
        max_age=settings.access_token_minutes * 60,
        httponly=True,                       # JavaScript can't read it, so XSS can't steal it
        secure=settings.cookie_secure,       # HTTPS only in production
        samesite="strict",                   # not sent on cross-site requests (CSRF protection)
        path="/",
    )


@router.post("/login", response_model=schemas.UserOut)
def login(data: schemas.LoginIn, request: Request, response: Response, db: DbSession):
    user = user_crud.authenticate(db, data.email, data.password, client_ip(request))
    _set_session_cookie(response, user)
    return user_crud.user_out(user)


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie(settings.cookie_name, path="/")
    return response


@router.get("/me", response_model=schemas.UserOut)
def me(user: AnyUser):
    return user_crud.user_out(user)


@router.post("/change-password", response_model=schemas.UserOut)
def change_password(data: schemas.ChangePasswordIn, response: Response, user: AnyUser, db: DbSession):
    user = user_crud.change_password(db, user, data.current_password, data.new_password)
    _set_session_cookie(response, user)       # old tokens stop working, so issue a fresh one
    return user_crud.user_out(user)


@router.get("/config", response_model=schemas.AuthConfig)
def config():
    """Public, non-sensitive settings for the login screen. Demo accounts only appear on demo deployments."""
    from ..bootstrap import DEMO_PASSWORD, DEMO_USERS  # local import: avoids a circular import

    demo = []
    if settings.show_demo_logins:
        shown = {"admin": None, "manager": None, "salesperson": None}
        for person in DEMO_USERS:
            if shown.get(person["role"]) is None:
                shown[person["role"]] = person
        demo = [
            schemas.DemoAccount(role=role, email=person["email"], password=DEMO_PASSWORD)
            for role, person in shown.items() if person
        ]
    return schemas.AuthConfig(
        demo_accounts=demo,
        password_min_length=settings.min_password_length,
        app_timezone=settings.timezone,
        version=APP_VERSION,
        demo_note="Demo accounts for reviewers. Do not use these on a real deployment." if demo else None,
    )
