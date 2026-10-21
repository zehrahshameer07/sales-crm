"""Initial schema: users, activities, status_history.

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = {
    "user_role": ("admin", "manager", "salesperson"),
    "activity_type": ("call", "visit", "demo", "follow_up"),
    "activity_status": ("pending", "in_progress", "completed"),
    "product": ("freebees_menu", "freebees_play", "both"),
}


def _enum(name: str):
    """Real ENUM type on PostgreSQL; VARCHAR + CHECK on SQLite."""
    values = ENUMS[name]
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name, values in ENUMS.items():
            postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", _enum("user_role"), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("designation", sa.String(80), nullable=True),
        sa.Column("region", sa.String(80), nullable=True),
        sa.Column("employee_code", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], name="fk_users_manager_id_users", ondelete="SET NULL"),
        sa.UniqueConstraint("employee_code", name="uq_users_employee_code"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_manager_id", "users", ["manager_id"])

    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_key", sa.String(120), nullable=False),
        sa.Column("activity_type", _enum("activity_type"), nullable=False),
        sa.Column("status", _enum("activity_status"), nullable=False),
        sa.Column("product_interested", _enum("product"), nullable=True),
        sa.Column("contact", sa.String(20), nullable=True),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("follow_up_notes", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_activities"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_activities_owner_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_activities_created_by_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_activities_updated_by_id_users", ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "customer_key", "activity_type", "start_date", name="uq_activities_no_duplicates"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_activities_end_after_start"),
        sa.CheckConstraint("end_date IS NULL OR status = 'completed'", name="ck_activities_end_only_when_completed"),
        sa.CheckConstraint("follow_up_date IS NULL OR follow_up_date >= start_date", name="ck_activities_follow_up_after_start"),
    )
    op.create_index("ix_activities_owner_id", "activities", ["owner_id"])
    op.create_index("ix_activities_status", "activities", ["status"])
    op.create_index("ix_activities_start_date", "activities", ["start_date"])
    op.create_index("ix_activities_follow_up_date", "activities", ["follow_up_date"])
    op.create_index("ix_activities_owner_id_start_date", "activities", ["owner_id", "start_date"])

    op.create_table(
        "status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", _enum("activity_status"), nullable=True),
        sa.Column("to_status", _enum("activity_status"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_status_history"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], name="fk_status_history_activity_id_activities", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], name="fk_status_history_changed_by_id_users", ondelete="SET NULL"),
    )
    op.create_index("ix_status_history_activity_id", "status_history", ["activity_id"])


def downgrade() -> None:
    op.drop_index("ix_status_history_activity_id", table_name="status_history")
    op.drop_table("status_history")
    for name in ("ix_activities_owner_id_start_date", "ix_activities_follow_up_date", "ix_activities_start_date",
                 "ix_activities_status", "ix_activities_owner_id"):
        op.drop_index(name, table_name="activities")
    op.drop_table("activities")
    for name in ("ix_users_manager_id", "ix_users_role", "ix_users_email"):
        op.drop_index(name, table_name="users")
    op.drop_table("users")
    if op.get_bind().dialect.name == "postgresql":
        for name in ENUMS:
            postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
