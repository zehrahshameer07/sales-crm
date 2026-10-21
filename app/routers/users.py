import uuid
from typing import Optional

from fastapi import APIRouter, Query

from .. import schemas
from ..crud import activities as activity_crud
from ..crud import users as user_crud
from ..deps import AdminUser, CurrentUser, DbSession
from ..enums import UserRole

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/options", response_model=list[schemas.UserOption])
def options(user: CurrentUser, db: DbSession):
    """People the current user may filter by: everyone (admin), their team (manager) or just themself."""
    return user_crud.users_in_scope(db, user)


@router.get("", response_model=schemas.UserPage)
def list_users(
    _admin: AdminUser,
    db: DbSession,
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    manager_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = user_crud.list_users(
        db, search=search, role=role, is_active=is_active, manager_id=manager_id, page=page, page_size=page_size
    )
    return schemas.UserPage(
        items=[user_crud.user_out(u) for u in items],
        total=total, page=page, page_size=page_size, pages=activity_crud.pages(total, page_size),
    )


@router.post("", response_model=schemas.UserWithPassword, status_code=201)
def create_user(data: schemas.UserCreate, _admin: AdminUser, db: DbSession):
    user, temporary = user_crud.create_user(db, data)
    out = schemas.UserWithPassword(**user_crud.user_out(user).model_dump())
    out.temporary_password = temporary
    return out


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: uuid.UUID, _admin: AdminUser, db: DbSession):
    return user_crud.user_out(user_crud.get_user(db, user_id))


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: uuid.UUID, data: schemas.UserUpdate, admin: AdminUser, db: DbSession):
    user = user_crud.get_user(db, user_id)
    return user_crud.user_out(user_crud.update_user(db, user, data, admin))


@router.post("/{user_id}/reset-password", response_model=schemas.UserWithPassword)
def reset_password(user_id: uuid.UUID, _admin: AdminUser, db: DbSession):
    user = user_crud.get_user(db, user_id)
    temporary = user_crud.reset_password(db, user)
    out = schemas.UserWithPassword(**user_crud.user_out(user).model_dump())
    out.temporary_password = temporary
    return out


@router.post("/{user_id}/unlock", response_model=schemas.UserOut)
def unlock(user_id: uuid.UUID, _admin: AdminUser, db: DbSession):
    user = user_crud.get_user(db, user_id)
    return user_crud.user_out(user_crud.unlock_user(db, user))
