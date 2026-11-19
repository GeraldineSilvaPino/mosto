"""Schema metadata without runtime configuration or database connections."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
