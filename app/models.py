"""Database tables: users, activities and the status history (audit trail).

All primary keys are UUIDs, so IDs can't be guessed or used to count records.
All timestamps are stored in UTC.
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator

from .database import Base
from .enums import ActivityStatus, ActivityType, Product, UserRole
from .timeutil import utcnow


class UTCDateTime(TypeDecorator):
    """A timestamp that is always timezone-aware UTC in Python, on SQLite and PostgreSQL."""

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value if dialect.name == "postgresql" else value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def _enum(enum_cls, name: str) -> SAEnum:
    """A real database enum (PostgreSQL ENUM; VARCHAR + CHECK on SQLite). Stores the value, e.g. 'in_progress'."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        native_enum=True,
        create_constraint=True,
        validate_strings=True,
    )


user_role_enum = _enum(UserRole, "user_role")
activity_type_enum = _enum(ActivityType, "activity_type")
activity_status_enum = _enum(ActivityStatus, "activity_status")
product_enum = _enum(Product, "product")


def make_customer_key(name: str) -> str:
    """Lowercase, trimmed, single-spaced copy of a name. Used only to detect duplicates."""
    return " ".join(name.split()).casefold()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(user_role_enum, default=UserRole.SALESPERSON, index=True)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    designation: Mapped[Optional[str]] = mapped_column(String(80))
    region: Mapped[Optional[str]] = mapped_column(String(80))
    employee_code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    manager: Mapped[Optional["User"]] = relationship(
        "User", remote_side="User.id", back_populates="reports", foreign_keys="User.manager_id"
    )
    reports: Mapped[list["User"]] = relationship(
        "User", back_populates="manager", foreign_keys="User.manager_id"
    )

    @validates("email")
    def _normalize_email(self, _key, value: str) -> str:
        return value.strip().lower()

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > utcnow()


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_key: Mapped[str] = mapped_column(String(120))
    activity_type: Mapped[ActivityType] = mapped_column(activity_type_enum)
    status: Mapped[ActivityStatus] = mapped_column(
        activity_status_enum, default=ActivityStatus.PENDING, index=True
    )
    product_interested: Mapped[Optional[Product]] = mapped_column(product_enum)
    contact: Mapped[Optional[str]] = mapped_column(String(20))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    follow_up_notes: Mapped[Optional[str]] = mapped_column(String(500))
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    owner: Mapped[User] = relationship("User", foreign_keys=[owner_id])
    creator: Mapped[Optional[User]] = relationship("User", foreign_keys=[created_by_id])
    updater: Mapped[Optional[User]] = relationship("User", foreign_keys=[updated_by_id])
    history: Mapped[list["StatusHistory"]] = relationship(
        "StatusHistory",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="StatusHistory.changed_at",
    )

    __table_args__ = (
        # The duplicate rule: the same salesperson can't log the same customer + type on the same day twice
        UniqueConstraint(
            "owner_id", "customer_key", "activity_type", "start_date", name="uq_activities_no_duplicates"
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="end_after_start"),
        CheckConstraint("end_date IS NULL OR status = 'completed'", name="end_only_when_completed"),
        CheckConstraint("follow_up_date IS NULL OR follow_up_date >= start_date", name="follow_up_after_start"),
        Index("ix_activities_owner_id_start_date", "owner_id", "start_date"),
    )

    @validates("customer_name")
    def _sync_customer_key(self, _key, value: str) -> str:
        self.customer_key = make_customer_key(value)
        return value

    @property
    def days_to_complete(self) -> Optional[int]:
        if self.end_date is None:
            return None
        return max(0, (self.end_date - self.start_date).days)


class StatusHistory(Base):
    """Audit trail: who moved an activity to which status, and when."""

    __tablename__ = "status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    from_status: Mapped[Optional[ActivityStatus]] = mapped_column(activity_status_enum)
    to_status: Mapped[ActivityStatus] = mapped_column(activity_status_enum)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, server_default=func.now())

    activity: Mapped[Activity] = relationship("Activity", back_populates="history")
    changed_by: Mapped[Optional[User]] = relationship("User", foreign_keys=[changed_by_id])
