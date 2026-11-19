"""Local-only migration environment; never reads .env or DATABASE_URL."""
import os

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.config import validate_isolated_database
from app.db_base import Base
from app import models  # noqa: F401

config = context.config
purpose = config.attributes.get("purpose") or os.getenv("MOSTO_ENV")
if purpose not in {"test", "demo"}:
    raise RuntimeError("Migrations currently require MOSTO_ENV=test or demo")
connection = config.attributes.get("connection")
url = str(connection.engine.url) if connection is not None else (
    config.attributes.get("database_url") or os.getenv("MOSTO_MIGRATION_DATABASE_URL", ""))
validate_isolated_database(url, purpose)


def run(connection=None):
    kwargs = dict(target_metadata=Base.metadata, compare_type=True,
                  compare_server_default=True, render_as_batch=False)
    if connection is None:
        context.configure(url=url, literal_binds=True, **kwargs)
    else:
        context.configure(connection=connection, **kwargs)
    with context.begin_transaction():
        if connection is not None and connection.dialect.name == "postgresql":
            # Migrations are serialized; lock expires on commit/rollback.
            connection.execute(text("SELECT pg_advisory_xact_lock(746521903)"))
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
        context.run_migrations()


if context.is_offline_mode():
    run()
elif connection is not None:
    run(connection)
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            run(connection)
    finally:
        engine.dispose()
