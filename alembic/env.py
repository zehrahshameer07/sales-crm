"""Alembic environment. Uses the same database as the app (DATABASE_URL)."""
from alembic import context

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, engine

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")   # supplied when the app migrates itself at startup
    if connection is not None:
        _run(connection)
    else:
        with engine.begin() as connection:
            _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode is not supported. Run migrations against a database.")
run_migrations_online()
