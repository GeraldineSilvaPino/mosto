"""Run from backend: python -m scripts.init_demo (requires explicit demo env)."""
import os
from app.config import validate_isolated_database
from app.database import Base, engine, SessionLocal, settings
from app.demo_seed import seed_demo, provision_demo_catalogs
from app.models import EmpresaCliente
from app.migrations import upgrade_local


def main():
    if settings.environment != "demo":
        raise SystemExit("Initialization is only allowed with MOSTO_ENV=demo")
    validate_isolated_database(settings.database_url, "demo")
    password = os.environ.get("MOSTO_DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set MOSTO_DEMO_PASSWORD (at least 12 characters)")
    upgrade_local(settings.database_url, "demo")
    with SessionLocal() as db:
        existing = db.query(EmpresaCliente).first()
        if existing and existing.nomb_emp == "MOSTO DEMO · Datos simulados":
            provision_demo_catalogs(db)
            db.commit()
            print("Demo already initialized; existing records and password preserved.")
            return
        seed_demo(db, password)
    print("Isolated demo initialized; login: demo@example.invalid. No real measurements were created.")


if __name__ == "__main__":
    main()
