"""User management and authentication."""
import math
import secrets
import string
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..enums import UserRole
from ..errors import AppError, conflict, invalid, not_found, too_many
from ..models import Activity, User
from ..security import (
    burn_password_check,
    hash_password,
    login_ip_limiter,
    login_unknown_email_limiter,
    password_needs_rehash,
    password_problems,
    verify_password,
)
from ..timeutil import utcnow

GENERIC_LOGIN_ERROR = "Incorrect email or password."


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    return user


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not password_problems(candidate):
            return candidate


def _check_password_or_422(password: str, email: str, name: str) -> None:
    problems = password_problems(password, email=email, name=name)
    if problems:
        raise invalid(" ".join(problems))


# ------------------------------------------------------------ authentication
def authenticate(db: Session, email: str, password: str, ip: str) -> User:
    """Check a login. Every failure looks the same to the caller (401) except throttling (429)."""
    wait = login_ip_limiter.hit(f"ip:{ip}")
    if wait:
        raise too_many("Too many login attempts from this network. Please wait and try again.", wait)

    email = normalize_email(email)
    user = get_by_email(db, email)

    if user is None:
        # Unknown email: still do the slow hash check and apply the same attempt limit as real accounts
        burn_password_check(password)
        wait = login_unknown_email_limiter.retry_after(email)
        if wait:
            raise too_many(f"Too many failed attempts. Try again in {math.ceil(wait / 60)} minute(s).", wait)
        login_unknown_email_limiter.record(email)
        raise AppError(401, GENERIC_LOGIN_ERROR)

    if user.is_locked:
        wait = int((user.locked_until - utcnow()).total_seconds()) + 1
        raise too_many(f"Too many failed attempts. Try again in {math.ceil(wait / 60)} minute(s).", wait)

    if not verify_password(user.password_hash, password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = utcnow() + timedelta(minutes=settings.login_lock_minutes)
            user.failed_login_attempts = 0
            db.commit()
            raise too_many(
                f"Too many failed attempts. Try again in {settings.login_lock_minutes} minute(s).",
                settings.login_lock_minutes * 60,
            )
        db.commit()
        raise AppError(401, GENERIC_LOGIN_ERROR)

    # Correct password from here on
    if not user.is_active:
        raise AppError(403, "This account has been deactivated. Please contact an administrator.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    db.commit()
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    if not verify_password(user.password_hash, current_password):
        raise AppError(403, "Your current password is incorrect.")
    if current_password == new_password:
        raise invalid("Choose a new password that is different from the current one.")
    _check_password_or_422(new_password, user.email, user.full_name)
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    return user


# ---------------------------------------------------------------- admin CRUD
def _validate_manager(db: Session, manager_id: Optional[uuid.UUID], user_id: Optional[uuid.UUID] = None) -> None:
    if manager_id is None:
        return
    if user_id is not None and manager_id == user_id:
        raise invalid("A person can't be their own manager.")
    manager = db.get(User, manager_id)
    if manager is None:
        raise invalid("The selected manager does not exist.")
    if manager.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise invalid("The manager must have the manager or admin role.")


def _ensure_unique(db: Session, *, email: Optional[str], employee_code: Optional[str], exclude_id=None) -> None:
    if email:
        query = select(User.id).where(User.email == normalize_email(email))
        if exclude_id:
            query = query.where(User.id != exclude_id)
        if db.scalar(query):
            raise conflict("A user with this email already exists.")
    if employee_code:
        query = select(User.id).where(User.employee_code == employee_code)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        if db.scalar(query):
            raise conflict("This employee code is already used.")


def create_user(db: Session, data: schemas.UserCreate) -> tuple[User, Optional[str]]:
    _ensure_unique(db, email=data.email, employee_code=data.employee_code)
    _validate_manager(db, data.manager_id)
    if data.role == UserRole.ADMIN and data.manager_id:
        raise invalid("Admins don't have a manager.")

    temporary = None
    password = data.password
    if password:
        _check_password_or_422(password, data.email, data.full_name)
    else:
        password = temporary = generate_password()

    user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        role=data.role,
        manager_id=data.manager_id,
        designation=data.designation,
        region=data.region,
        employee_code=data.employee_code,
        password_hash=hash_password(password),
        must_change_password=True,  # they choose their own password at first login
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("A user with this email or employee code already exists.")
    return user, temporary


def _admin_count(db: Session, exclude_id: Optional[uuid.UUID] = None) -> int:
    query = select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    if exclude_id:
        query = query.where(User.id != exclude_id)
    return db.scalar(query) or 0


def update_user(db: Session, user: User, data: schemas.UserUpdate, actor: User) -> User:
    changes = data.model_dump(exclude_unset=True)

    _ensure_unique(
        db,
        email=changes.get("email") if changes.get("email") != user.email else None,
        employee_code=changes.get("employee_code") if changes.get("employee_code") != user.employee_code else None,
        exclude_id=user.id,
    )

    new_role = changes.get("role", user.role)
    new_active = changes.get("is_active", user.is_active)
    new_manager = changes["manager_id"] if "manager_id" in changes else user.manager_id

    if user.id == actor.id:
        if new_active is False:
            raise conflict("You can't deactivate your own account.")
        if new_role != UserRole.ADMIN:
            raise conflict("You can't remove your own admin role.")

    losing_admin = user.role == UserRole.ADMIN and (new_role != UserRole.ADMIN or new_active is False)
    if losing_admin and _admin_count(db, exclude_id=user.id) == 0:
        raise conflict("There must be at least one active admin.")

    if user.role == UserRole.MANAGER and new_role != UserRole.MANAGER:
        has_reports = db.scalar(select(func.count(User.id)).where(User.manager_id == user.id)) or 0
        if has_reports:
            raise conflict("This manager still has team members. Reassign them first.")

    if new_role == UserRole.ADMIN:
        new_manager = None
        changes["manager_id"] = None
    _validate_manager(db, new_manager, user.id)

    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("A user with this email or employee code already exists.")
    return user


def reset_password(db: Session, user: User) -> str:
    temporary = generate_password()
    user.password_hash = hash_password(temporary)
    user.must_change_password = True
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return temporary


def unlock_user(db: Session, user: User) -> User:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return user


def list_users(
    db: Session, *, search: Optional[str], role: Optional[UserRole], is_active: Optional[bool],
    manager_id: Optional[uuid.UUID], page: int, page_size: int,
) -> tuple[list[User], int]:
    conditions = []
    if search:
        like = f"%{_escape_like(search.strip().lower())}%"
        conditions.append(
            or_(func.lower(User.full_name).like(like, escape="\\"), func.lower(User.email).like(like, escape="\\"))
        )
    if role:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if manager_id:
        conditions.append(User.manager_id == manager_id)

    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(User).where(*conditions).order_by(User.full_name, User.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(rows), total


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def users_in_scope(db: Session, viewer: User, *, include_inactive: bool = False) -> list[User]:
    """People this user may see: everyone (admin), themself + team (manager), themself (salesperson)."""
    query = select(User)
    if viewer.role == UserRole.MANAGER:
        query = query.where(or_(User.id == viewer.id, User.manager_id == viewer.id))
    elif viewer.role == UserRole.SALESPERSON:
        query = query.where(User.id == viewer.id)
    if not include_inactive:
        query = query.where(User.is_active.is_(True))
    return list(db.scalars(query.order_by(User.full_name)).all())


def user_out(user: User) -> schemas.UserOut:
    out = schemas.UserOut.model_validate(user)
    out.manager_name = user.manager.full_name if user.manager else None
    out.is_locked = user.is_locked
    return out


def count_activities(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count(Activity.id)).where(Activity.owner_id == user_id)) or 0
