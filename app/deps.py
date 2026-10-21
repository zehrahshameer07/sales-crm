"""Shared request dependencies: who is logged in, and role checks."""
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .enums import UserRole
from .errors import AppError, forbidden
from .models import User
from .security import decode_access_token, password_version

DbSession = Annotated[Session, Depends(get_db)]


def current_user_any(request: Request, db: DbSession) -> User:
    """The logged-in user (even if they still must change their password)."""
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise AppError(401, "Please log in.")
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AppError(401, "Your session has expired. Please log in again.")
    user = db.get(User, user_id)
    # Re-check the database on every request: deactivated users and changed passwords are cut off immediately
    if user is None or not user.is_active or payload.get("pwv") != password_version(user.password_hash):
        raise AppError(401, "Your session has expired. Please log in again.")
    return user


def current_user(user: Annotated[User, Depends(current_user_any)]) -> User:
    if user.must_change_password:
        raise AppError(
            403, "You must change your password before continuing.", code="password_change_required"
        )
    return user


def require_roles(*roles: UserRole):
    def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise forbidden()
        return user

    return dependency


CurrentUser = Annotated[User, Depends(current_user)]
AnyUser = Annotated[User, Depends(current_user_any)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
ManagerOrAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))]
