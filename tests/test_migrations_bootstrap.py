import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app import bootstrap
from app.config import settings
from app.database import SessionLocal
from app.enums import UserRole
from app.models import Activity, StatusHistory, User

BASE = Path(__file__).resolve().parent.parent


def alembic_config(connection):
    config = Config(str(BASE / "alembic.ini"))
    config.set_main_option("script_location", str(BASE / "alembic"))
    config.attributes["connection"] = connection
    return config


def test_migration_creates_the_expected_tables_and_can_be_undone():
    engine = create_engine(f"sqlite:///{Path(tempfile.mkdtemp()) / 'm.db'}")
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
    tables = set(inspect(engine).get_table_names())
    assert {"users", "activities", "status_history", "alembic_version"} <= tables
    columns = {c["name"] for c in inspect(engine).get_columns("activities")}
    assert {"id", "owner_id", "customer_key", "created_at", "updated_at", "follow_up_date"} <= columns
    with engine.begin() as connection:
        command.downgrade(alembic_config(connection), "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}


def test_models_and_migration_agree():
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.database import Base

    engine = create_engine(f"sqlite:///{Path(tempfile.mkdtemp()) / 'd.db'}")
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], diff


def test_old_schema_is_detected_with_a_helpful_message(monkeypatch):
    from app import database
    engine = create_engine(f"sqlite:///{Path(tempfile.mkdtemp()) / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE activities (id INTEGER PRIMARY KEY, customer_name VARCHAR(120))"))
    monkeypatch.setattr(bootstrap, "engine", engine)
    with pytest.raises(RuntimeError, match="OLD version"):
        bootstrap.run_migrations()
    monkeypatch.setattr(settings, "reset_legacy_schema", True)
    bootstrap.run_migrations()                                  # drops the old table, then migrates
    assert {c["name"] for c in inspect(engine).get_columns("activities")} >= {"owner_id"}


def test_first_admin_bootstrap(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "boss@example.com")
    monkeypatch.setattr(settings, "admin_password", "weak")
    with pytest.raises(RuntimeError, match="too weak"):
        bootstrap.bootstrap_admin(db)
    monkeypatch.setattr(settings, "admin_password", "Str0ng-Initial-Pass")
    bootstrap.bootstrap_admin(db)
    bootstrap.bootstrap_admin(db)                               # idempotent
    admins = db.query(User).all()
    assert len(admins) == 1 and admins[0].role == UserRole.ADMIN and admins[0].must_change_password is False


def test_demo_seed_is_consistent_and_idempotent(db):
    assert bootstrap.seed_demo(db) is True
    assert bootstrap.seed_demo(db) is False
    assert db.query(User).count() == 9
    activities = db.query(Activity).all()
    assert len(activities) > 40
    for a in activities:
        if a.end_date:
            assert a.status.value == "completed" and a.end_date >= a.start_date
        history = db.query(StatusHistory).filter_by(activity_id=a.id).order_by(StatusHistory.changed_at).all()
        assert history and history[-1].to_status == a.status
    from app.models import utcnow  # noqa: F401
    assert max(a.updated_at for a in activities).timestamp() <= __import__("time").time() + 180
