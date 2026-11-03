"""
Configuración de la Base de Datos.
Carga automáticamente la URL de Supabase (PostgreSQL) desde el archivo .env.
Si no existe .env o falla, utiliza SQLite local como respaldo.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Lee DATABASE_URL desde .env (Supabase) o usa SQLite por defecto
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mosto.db")

# Compatibilidad SQLAlchemy: asegurar driver psycopg2 para PostgreSQL
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# SQLite requiere check_same_thread=False; PostgreSQL no lo acepta
connect_args = {}
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Generador de dependencias para inyectar la sesión de base de datos en los endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
