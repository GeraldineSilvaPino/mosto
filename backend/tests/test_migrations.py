"""Migration lifecycle, portable constraints and real PostgreSQL concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import io
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.config import validate_isolated_database
from app.database import Base, engine, SessionLocal, settings
from app.main import app
from app.migrations import migration_config, upgrade_local
from app.services.auth_service import create_access_token

postgres = pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires PostgreSQL triggers/locking")


@pytest.mark.parametrize("query", ["host=remote.example", "hostaddr=203.0.113.1", "dbname=postgres", "service=production"])
def test_migration_url_cannot_override_local_destination(query):
    with pytest.raises(ValueError):
        validate_isolated_database("postgresql://localhost/mosto_test?" + query, "test")


def test_migration_head_matches_orm_and_is_idempotent():
    upgrade_local(settings.database_url, "test")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert context.get_current_revision() == "0004_alert_episodes"
        assert len(inspect(connection).get_table_names()) == 24
        assert compare_metadata(context, Base.metadata) == []


@pytest.mark.empty_db
def test_upgrade_downgrade_upgrade_and_readiness(client):
    config = migration_config(settings.database_url, "test")
    try:
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
        assert client.get("/api/ready").status_code == 503
    finally:
        command.upgrade(config, "head")
    assert client.get("/api/ready").status_code == 200


def test_offline_sql_contains_postgres_guards_without_connection(monkeypatch):
    from sqlalchemy.engine import Engine
    monkeypatch.setattr(Engine, "connect", lambda *_: pytest.fail("Offline migration connected"))
    config = migration_config("postgresql+psycopg2://localhost/mosto_test", "test")
    output = io.StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE" in sql and '"UMBRAL_FERMENTACION"' in sql
    assert "CREATE FUNCTION public.mosto_validate_reading" in sql
    assert "idx_cuba_proceso_activo_unico" in sql
    assert "detenida" in sql


def test_unversioned_existing_schema_is_not_stamped(tmp_path):
    from sqlalchemy import create_engine
    url = "sqlite:///" + (tmp_path / "mosto_test_existing.db").as_posix()
    existing = create_engine(url)
    try:
        with existing.begin() as connection:
            connection.execute(text("CREATE TABLE preserve_me (value TEXT)"))
            connection.execute(text("INSERT INTO preserve_me VALUES ('original')"))
        with pytest.raises(RuntimeError, match="empty database"):
            upgrade_local(url, "test")
        with existing.connect() as connection:
            assert connection.execute(text("SELECT value FROM preserve_me")).scalar() == "original"
    finally:
        existing.dispose()


def test_unique_codes_are_per_warehouse_and_casefolded_email_is_unique():
    with SessionLocal() as db:
        warehouse = m.Bodega(nombre="Second warehouse", empresa_id=1)
        db.add(warehouse); db.flush()
        db.add(m.Cuba(codigo="DEMO-01", bodega_id=warehouse.id))
        db.commit()
        db.add(m.Cuba(codigo="DEMO-01", bodega_id=1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(m.Usuario(nomb_compl="Duplicate", correo_elec="DEMO@EXAMPLE.INVALID", empresa_id=1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_stopped_process_still_reserves_tank(client):
    with SessionLocal() as db:
        db.get(m.ProcesoFermentacion, 1).estado = "detenida"
        db.commit()
        db.add(m.ProcesoFermentacion(cuba_id=1, perfil_id=1, estado="en_proceso"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    response = client.post("/api/procesos/iniciar", json={"cuba_id": 1, "perfil_id": 1, "volumen_litros": 500})
    assert response.status_code in (400, 409)
    assert client.patch("/api/procesos/1/finalizar").status_code == 200


@postgres
def test_database_guards_reject_cross_company_links_and_ownership_changes():
    with SessionLocal() as db:
        company = m.EmpresaCliente(nomb_emp="Foreign")
        db.add(company); db.flush()
        warehouse = m.Bodega(nombre="Foreign", empresa_id=company.id)
        db.add(warehouse); db.flush()
        tank = m.Cuba(codigo="Foreign", bodega_id=warehouse.id)
        db.add(tank); db.flush()
        ids = warehouse.id, tank.id
        db.commit()
        for obj in (
            m.UsuarioBodega(usuario_id=1, bodega_id=ids[0], rol_id=1),
            m.AsignacionDispositivo(dispositivo_id=1, cuba_id=ids[1], activo=True),
            m.ProcesoFermentacion(cuba_id=ids[1], perfil_id=1),
            m.BitacoraIntervencion(usuario_id=1, cuba_id=ids[1], tipo_intervencion="nota", descripcion="Forbidden"),
        ):
            db.add(obj)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        db.get(m.Cuba, 1).bodega_id = ids[0]
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@postgres
def test_readings_follow_assignment_time_not_current_assignment(client):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        assignment = db.query(m.AsignacionDispositivo).filter_by(dispositivo_id=1, activo=True).one()
        start = assignment.asignado_en
        db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1, timestamp=start - timedelta(seconds=1), brix=10))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert client.post("/api/dispositivos/vincular", json={"dispositivo_id": 1, "cuba_id": 2}).status_code == 200
    with SessionLocal() as db:
        # A delayed reading from the previous interval is legitimate.
        db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1, timestamp=now - timedelta(minutes=1), brix=-0.5))
        db.commit()
        # Current telemetry must no longer attach to the former tank.
        db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1, timestamp=datetime.now(timezone.utc), brix=10))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def _parallel(action):
    barrier = Barrier(2)
    def worker(index):
        barrier.wait(timeout=10)
        return action(index)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, i) for i in (0, 1)]
        return [future.result(timeout=30) for future in futures]


@postgres
def test_concurrent_start_requests_create_exactly_one_process():
    with SessionLocal() as db:
        tank = m.Cuba(codigo="CONCURRENT", bodega_id=1, cap_litros=1000, estado_operativo="disponible")
        db.add(tank); db.commit(); ident = tank.id
    def start(_):
        with TestClient(app) as client:
            return client.post("/api/procesos/iniciar", headers={"Authorization": "Bearer " + create_access_token({"sub": 1})},
                               json={"cuba_id": ident, "perfil_id": 1, "volumen_litros": 500}).status_code
    results = _parallel(start)
    assert results.count(201) == 1 and any(code in (400, 409) for code in results)
    with SessionLocal() as db:
        assert db.query(m.ProcesoFermentacion).filter_by(cuba_id=ident).count() == 1


@postgres
def test_concurrent_sensor_reassignment_leaves_one_active_interval():
    def assign(index):
        with TestClient(app) as client:
            return client.post("/api/dispositivos/vincular", headers={"Authorization": "Bearer " + create_access_token({"sub": 1})},
                               json={"dispositivo_id": 1, "cuba_id": index + 2}).status_code
    assert _parallel(assign) == [200, 200]
    with SessionLocal() as db:
        rows = db.query(m.AsignacionDispositivo).filter_by(dispositivo_id=1).order_by(m.AsignacionDispositivo.asignado_en).all()
        assert sum(row.activo for row in rows) == 1
        assert len(rows) == 3
        assert all(a.desasignado_en <= b.asignado_en for a, b in zip(rows, rows[1:]))


@postgres
def test_concurrent_admin_demotions_preserve_one_active_admin():
    with SessionLocal() as db:
        user = m.Usuario(nomb_compl="Second admin", correo_elec="second@example.invalid", empresa_id=1, rol="admin")
        db.add(user); db.flush()
        db.add(m.UsuarioBodega(usuario_id=user.id, bodega_id=1, rol_id=1))
        db.commit(); ident = user.id
    def demote(index):
        actor = (1, ident)[index]
        with TestClient(app) as client:
            return client.patch(f"/api/usuarios/{actor}/rol", headers={"Authorization": "Bearer " + create_access_token({"sub": actor})},
                                json={"role": "enologo", "bodega_id": 1}).status_code
    assert sorted(_parallel(demote)) == [200, 409]
    with SessionLocal() as db:
        assert db.query(m.UsuarioBodega).filter_by(bodega_id=1, rol_id=1).count() == 1
        row = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
        assert row == (False, False)
