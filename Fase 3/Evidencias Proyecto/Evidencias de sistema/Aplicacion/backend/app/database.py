"""Database configuration with explicit URL; no remote failure fallback or startup DDL."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .db_base import Base
from .config import load_settings

settings = load_settings()

# La URL es explícita y se valida antes de construir el motor.
SQLALCHEMY_DATABASE_URL = settings.database_url

# Compatibilidad SQLAlchemy: asegurar driver psycopg2 para PostgreSQL
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# SQLite requiere check_same_thread=False; PostgreSQL no lo acepta
connect_args = {}
if settings.environment == "production":
    connect_args = {"sslmode": "verify-full", "connect_timeout": 8}
elif settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Generador de dependencias para inyectar la sesión de base de datos en los endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
