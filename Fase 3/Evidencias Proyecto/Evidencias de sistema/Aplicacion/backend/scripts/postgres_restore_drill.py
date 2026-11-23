"""Internal worker for scripts.test_postgres --restore-drill."""
import os
import secrets
import subprocess

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import validate_isolated_database
from app.database import SessionLocal, engine, settings
from app.demo_seed import seed_demo
from app.migrations import upgrade_local
from app.models import AsignacionDispositivo, LecturaTelemetria, ProcesoFermentacion


def inventory(db):
    with db.connect() as conn:
        names = inspect(conn).get_table_names(schema="public")
        quote = db.dialect.identifier_preparer.quote_identifier
        counts = {name: conn.scalar(text(f"SELECT count(*) FROM public.{quote(name)}"))
                  for name in names}
        revisions = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY 1")).all()
        companies = conn.execute(text('SELECT id, nomb_emp FROM "EMPRESA_CLIENTE" ORDER BY id')).all()
        readings = conn.execute(text('''SELECT l.id, l.timestamp, l.brix, l.temp_mosto, r.fermentacion_id, r.clave
            FROM "LECTURA_TELEMETRIA" AS l JOIN "RELOJ_PROCESO" AS r
              ON l.fermentacion_id = r.fermentacion_id ORDER BY l.id''')).all()
        constraints = conn.execute(text("""
            SELECT conrelid::regclass::text, conname, contype, convalidated
              FROM pg_constraint WHERE connamespace = 'public'::regnamespace
             ORDER BY 1, 2
        """)).all()
    return counts, revisions, companies, constraints, readings


def run_restore_drill(binaries, archive):
    validate_isolated_database(settings.database_url, "test")
    source = engine.url
    if (settings.environment != "test" or source.host != "127.0.0.1"
            or source.username != "mosto_test" or not source.port or archive.exists()):
        raise ValueError("Expected a fresh local test cluster and archive")
    upgrade_local(settings.database_url, "test")
    with SessionLocal() as db:
        seed_demo(db, secrets.token_hex(24))
        process = db.query(ProcesoFermentacion).order_by(ProcesoFermentacion.id).first()
        assignment = db.query(AsignacionDispositivo).filter_by(cuba_id=process.cuba_id, activo=True).one()
        db.add(LecturaTelemetria(dispositivo_id=assignment.dispositivo_id, fermentacion_id=process.id,
                                timestamp=process.fecha_inicio, temp_mosto=21, brix=20))
        db.commit()
    before = inventory(engine)
    counts, revisions, companies, constraints, readings = before
    if not (companies and revisions and constraints and counts["USUARIO"] and readings):
        raise RuntimeError("Expected a migrated schema with demo data")
    target = source.set(database="mosto_test_restore")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env["PGPASSWORD"] = source.password
    connection = ["-h", source.host, "-p", str(source.port), "-U", source.username, "-w"]
    subprocess.run([binaries / "pg_dump", *connection, "-Fc", "-f", archive,
                    "-d", source.database], check=True, env=env)
    with engine.begin() as conn:
        conn.execute(text('UPDATE "EMPRESA_CLIENTE" SET nomb_emp=:name WHERE id=:id'),
                     {"name": secrets.token_hex(16), "id": companies[0].id})
    subprocess.run([binaries / "pg_restore", *connection, "--single-transaction",
                    "-d", target.database, archive], check=True, env=env)
    restored = create_engine(target)
    try:
        after = inventory(restored)
        for label, expected, actual in zip(("counts", "revisions", "companies", "constraints", "readings"),
                                           before, after, strict=True):
            if actual != expected:
                if label == "constraints":
                    print("Missing constraints:", list(set(expected) - set(actual))[:3])
                    print("Additional constraints:", list(set(actual) - set(expected))[:3])
                raise RuntimeError(f"Restored {label} differs from snapshot")
        for statement, expected_code in (
            ('UPDATE "DISPOSITIVO" SET estado=\'invalid\'', "23514"),
            ('UPDATE "BODEGA" SET empresa_id=-1', "23514"),
            ("""INSERT INTO "BODEGA" (nombre, empresa_id) VALUES ('drill', -1)""", "23503"),
        ):
            try:
                with restored.begin() as conn:
                    conn.execute(text(statement))
                    raise RuntimeError(f"Restored database accepted invalid write ({expected_code})")
            except IntegrityError as error:
                if error.orig.pgcode != expected_code:
                    raise
        print(f"Restore verified: {len(counts)} tables, {sum(counts.values())} rows, "
              f"{len(constraints)} constraints, revision {revisions[0][0]}", flush=True)
    finally:
        restored.dispose()
        engine.dispose()
