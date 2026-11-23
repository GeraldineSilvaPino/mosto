"""Run from backend: python -m scripts.init_demo (requires explicit demo env)."""
import os
from app.config import validate_isolated_database
from app.database import Base, engine, SessionLocal, settings
from app.demo_seed import seed_demo, provision_demo_catalogs
from app.models import Bodega, Cuba, EmpresaCliente
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
        else:
            seed_demo(db, password, commit=False)
        warehouse = db.query(Bodega).filter_by(nombre="Bodega DEMO", empresa_id=(
            db.query(EmpresaCliente.id).filter_by(nomb_emp="MOSTO DEMO · Datos simulados").scalar()
        )).one()
        if not db.query(Cuba).filter_by(bodega_id=warehouse.id, codigo="REAL-06").first():
            db.add(Cuba(bodega_id=warehouse.id, codigo="REAL-06", estado_operativo="disponible",
                        cap_litros=10000, sector_cuba="Sensores físicos"))
        db.commit()
    print("Demo ready with an empty physical tank.")


if __name__ == "__main__":
    main()
