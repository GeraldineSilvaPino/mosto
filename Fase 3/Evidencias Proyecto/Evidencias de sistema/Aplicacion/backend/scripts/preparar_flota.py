"""Prepare the five emitters and the physical reserve in an empty winery."""
import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as m
from app.simulation.winery import create_winery_fleet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bodega", type=int, required=True)
    parser.add_argument("--perfil", type=int, required=True)
    parser.add_argument("--material", type=int, required=True)
    parser.add_argument("--modelo-simulado", type=int, required=True)
    parser.add_argument("--admin", required=True)
    parser.add_argument("--salida", type=Path, required=True, help="Nuevo directorio privado")
    args = parser.parse_args()
    url = os.environ.get("MOSTO_PROVISION_DATABASE_URL")
    if not url:
        parser.error("Configurar MOSTO_PROVISION_DATABASE_URL con la cuenta de aprovisionamiento")
    if args.salida.exists():
        parser.error("La carpeta de salida debe ser nueva")
    engine = create_engine(url, hide_parameters=True, connect_args={"sslmode": "verify-full"})
    try:
        with Session(engine) as db, db.begin():
            warehouse = db.query(m.Bodega).filter_by(id=args.bodega).with_for_update().one()
            admin = (db.query(m.Usuario).join(m.UsuarioBodega).join(m.Rol)
                     .filter(m.Usuario.correo_elec == args.admin, m.Usuario.activo.is_(True),
                             m.UsuarioBodega.bodega_id == args.bodega, m.Rol.codigo == "admin").one())
            fleet, keys = create_winery_fleet(
                db, warehouse, db.query(m.PerfilFermentacion).filter_by(id=args.perfil).one(),
                db.query(m.TipoMaterialCuba).filter_by(id=args.material).one(),
                db.query(m.ModeloDispositivo).filter_by(id=args.modelo_simulado).one(), admin)
            args.salida.mkdir(mode=0o700, parents=True)
            (args.salida / "fleet.json").write_text(fleet.model_dump_json(indent=2), encoding="utf-8")
            with (args.salida / "device-keys.env").open("x", encoding="utf-8") as output:
                os.chmod(output.name, 0o600)
                output.writelines(f"{name}={value}\n" for name, value in keys.items())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
