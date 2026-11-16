"""Explicit migration entry points shared by the demo initializer and tests."""
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import validate_isolated_database


def migration_config(url, purpose):
    validate_isolated_database(url, purpose)
    if purpose not in {"demo", "test"}:
        raise ValueError("Only local demo/test migrations are enabled")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes.update(database_url=url, purpose=purpose)
    return config


def upgrade_local(url, purpose):
    command.upgrade(migration_config(url, purpose), "head")
