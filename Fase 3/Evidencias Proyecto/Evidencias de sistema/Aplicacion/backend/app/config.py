"""Explicit configuration. Importing the application never opens a database."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def validate_isolated_database(url: str, purpose: str) -> None:
    """Only allow explicitly named local stores for demo/test writes."""
    if purpose not in {"test", "demo"}:
        raise ValueError("Only demo/test isolation policies are supported")
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        name = Path(parsed.database or "").name
        if name == ":memory:" or name.startswith(f"mosto_{purpose}"):
            return
    elif parsed.get_backend_name() == "postgresql":
        # libpq query parameters can override the visible host/database in a URL.
        if set(parsed.query) - {"connect_timeout", "sslmode", "application_name"}:
            raise ValueError("Database URL contains unsupported connection overrides")
        if (parsed.host in {"localhost", "127.0.0.1", "::1", f"mosto-{purpose}-db"}
                and parsed.database == f"mosto_{purpose}"):
            return
    raise ValueError(f"{purpose}: use a local database explicitly named mosto_{purpose}")


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str = field(repr=False)
    jwt_secret: str = field(repr=False)
    simulator_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str]):
        mode = env.get("MOSTO_ENV", "development")
        if mode not in {"development", "demo", "test", "production"}:
            raise ValueError("MOSTO_ENV must be development, demo, test or production")
        url = env.get("DATABASE_URL", "")
        if not url:
            raise ValueError("DATABASE_URL is required; no implicit database fallback")
        # Validate without echoing a URL containing credentials.
        try:
            parsed = make_url(url)
            if parsed.get_backend_name() not in {"sqlite", "postgresql"}:
                raise ValueError()
        except Exception:
            raise ValueError("Invalid DATABASE_URL (expected SQLite or PostgreSQL)") from None
        if mode in {"demo", "test"}:
            validate_isolated_database(url, mode)
        if mode == "production":
            role = (parsed.username or "").split(".", 1)[0]
            if (parsed.drivername not in {"postgresql", "postgresql+psycopg2"}
                    or not parsed.host or not role
                    or role in {"postgres", "supabase_admin", "service_role"}):
                raise ValueError("Production requires PostgreSQL and a dedicated application role")
        secret = env.get("JWT_SECRET_KEY", "")
        if len(secret.encode()) < 32 or secret.startswith("mosto_enologia_"):
            raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes and cannot use the former default")
        key = env.get("MOSTO_SIMULATOR_KEY", "")
        if mode == "demo" and len(key.encode()) < 32:
            raise ValueError("Demo requires MOSTO_SIMULATOR_KEY with at least 32 bytes")
        return cls(mode, url, secret, key)


def load_settings():
    # Tests and demo must never inherit the developer's remote .env database.
    values = {}
    if os.environ.get("MOSTO_ENV", "development") == "development":
        values.update(dotenv_values(Path(__file__).resolve().parents[1] / ".env"))
    values.update(os.environ)
    return Settings.from_env(values)
