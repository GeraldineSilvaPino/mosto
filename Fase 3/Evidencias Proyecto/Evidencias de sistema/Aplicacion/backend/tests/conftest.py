"""Choose an isolated database BEFORE any test imports the application."""
import os
from pathlib import Path
import secrets
import tempfile

_temporary = tempfile.TemporaryDirectory(prefix="mosto_tests_")
os.environ["MOSTO_ENV"] = "test"
os.environ["DATABASE_URL"] = os.getenv("MOSTO_TEST_DATABASE_URL") or (
    "sqlite:///" + (Path(_temporary.name) / "mosto_test.db").as_posix())
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["MOSTO_SIMULATOR_KEY"] = secrets.token_hex(32)

import pytest
from app.database import Base, engine, SessionLocal, settings
from app.config import validate_isolated_database
from app.main import app
from app.demo_seed import seed_demo
from app.services.auth_service import create_access_token
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.migrations import upgrade_local

validate_isolated_database(settings.database_url, "test")


@pytest.fixture(scope="session", autouse=True)
def migrated_schema():
    upgrade_local(settings.database_url, "test")


@pytest.fixture(autouse=True)
def isolated_schema(request, migrated_schema):
    # This URL was validated before opening a connection. Never use DATABASE_URL
    # from the shell or developer .env as a destructive test database.
    tables = list(reversed(Base.metadata.sorted_tables))
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            names = ", ".join('public."' + table.name + '"' for table in tables)
            connection.execute(text("TRUNCATE " + names + " RESTART IDENTITY CASCADE"))
        else:
            for table in tables:
                connection.execute(table.delete())
    if not request.node.get_closest_marker("empty_db"):
        with SessionLocal() as db:
            seed_demo(db, "test-only-password-2026")
    yield


@pytest.fixture
def client():
    with TestClient(app) as instance:
        instance.headers["Authorization"] = "Bearer " + create_access_token({"sub": 1})
        yield instance


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _temporary.cleanup()
