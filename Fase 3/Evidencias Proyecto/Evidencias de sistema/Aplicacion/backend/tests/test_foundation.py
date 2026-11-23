import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.config import Settings, validate_isolated_database
from app.database import SessionLocal
from app.main import app
from app.models import BitacoraIntervencion, Cepa, TipoMaterialCuba, EmpresaCliente
from app.routers.binnacle import listar_entradas_bitacora
from app.routers.master import listar_cepas, listar_materiales
from app.routers.company import obtener_configuracion_empresa
from ml.legacy_generator import generate_windows


@pytest.mark.parametrize("url", [
    "postgresql://user:secret@remote.example/mosto_test",
    "postgresql://user:secret@localhost/postgres",
    "sqlite:///mosto.db",
])
def test_test_database_rejects_real_targets(url):
    with pytest.raises(ValueError):
        validate_isolated_database(url, "test")


@pytest.mark.parametrize("secret", ["", "short"])
def test_no_implicit_jwt_secret(secret):
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings.from_env({"MOSTO_ENV": "test", "DATABASE_URL": "sqlite:///:memory:", "JWT_SECRET_KEY": secret})


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "postgresql://postgres.tenant@host/postgres"])
def test_production_requires_postgres_application_role(url):
    with pytest.raises(ValueError, match="dedicated application role"):
        Settings.from_env({"MOSTO_ENV": "production", "DATABASE_URL": url, "JWT_SECRET_KEY": "x"*32})


def test_demo_catalog_upgrade_is_idempotent_and_preserves_credentials():
    from app.demo_seed import provision_demo_catalogs
    from app.models import Usuario, Rol, ModeloDispositivo
    with SessionLocal() as db:
        before = db.get(Usuario, 1).password_hash
        for _ in range(2):
            provision_demo_catalogs(db)
            db.commit()
        assert db.query(Rol).count() == 4
        assert db.query(ModeloDispositivo).filter_by(modelo="ESP32-WROOM-32D").count() == 1
        assert db.get(Usuario, 1).password_hash == before


def test_import_does_not_connect_or_seed():
    code = 'from sqlalchemy.engine import Engine\ndef fail(*a, **k): raise AssertionError("database connection during import")\nEngine.connect = fail\nfrom app.main import app\nprint("imported")'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


@pytest.mark.parametrize("path", ["/api/cubas", "/api/usuarios", "/api/dispositivos", "/api/alertas", "/api/bitacora", "/api/perfiles", "/api/empresa", "/api/procesos"])
def test_business_routes_reject_anonymous(path):
    with TestClient(app) as client:
        assert client.get(path).status_code == 401


def test_simulation_cannot_write_in_development(client, monkeypatch):
    from app.services import demo_access
    monkeypatch.setattr(demo_access, "settings", SimpleNamespace(environment="development", simulator_key=""))
    assert client.post("/api/cubas/1/simular-anomalia").status_code == 403
    assert client.post("/api/cubas/1/restaurar-normalidad").status_code == 403
    assert client.post("/api/telemetria/nodo-cuba", json={"mac_address":"00:00:00:00:00:01", "temperatura_vino":22}).status_code == 403


def test_legacy_ingestion_requires_separate_key(client):
    assert client.post("/api/telemetria/nodo-cuba", json={"mac_address":"00:00:00:00:00:01", "temperatura_vino":22}).status_code == 401


def test_authorized_legacy_reading_is_explicitly_simulated(client):
    from app.database import settings
    from app.models import LecturaTelemetria
    response = client.post("/api/telemetria/nodo-cuba",
        headers={"X-Mosto-Simulator-Key": settings.simulator_key},
        json={"mac_address": "02:00:00:00:00:01", "cuba_id": 1, "temperatura_vino": 22})
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        assert db.query(LecturaTelemetria).one().origen_dato == "simulado_legacy"


@pytest.mark.empty_db
def test_gets_never_invent_audit_catalog_or_company():
    from fastapi import HTTPException
    with SessionLocal() as db:
        assert listar_entradas_bitacora(db=db, tipo=None, cuba=None, search=None) == []
        assert listar_cepas(db=db) == []
        assert listar_materiales(db=db) == []
        with pytest.raises(HTTPException) as exc:
            obtener_configuracion_empresa(db=db)
        assert exc.value.status_code == 404
        for model in (BitacoraIntervencion, Cepa, TipoMaterialCuba, EmpresaCliente):
            assert db.query(model).count() == 0


def test_readiness_reports_database_failure(monkeypatch):
    import app.main as main
    def unavailable():
        raise RuntimeError("sensitive connection detail")
    monkeypatch.setattr(main.engine, "connect", unavailable)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert "sensitive" not in response.text


def test_baseline_reproduces_all_supplied_csv_rows():
    source = Path(__file__).resolve().parents[1] / "app/ml/dataset_fermentacion_kontogiannis.csv"
    pd.testing.assert_frame_equal(generate_windows(seed=42), pd.read_csv(source), check_exact=True)


@pytest.mark.parametrize("mutation", [
    {"observed_at": "2026-11-14T12:00:00"},
    {"source": "physical"},
    {"received_at": "2026-11-14T12:00:00Z"},
    {"sequence": -1},
    {"temperature_c": {"value": 22, "quality": "missing"}},
    {"brix_apparent": {"value": 18, "quality": "good"}},
    {"temperature_c": {"value": float("nan"), "quality": "good"}},
])
def test_v2_rejects_ambiguous_or_fabricated_measurements(mutation):
    from app.telemetry_contract import TelemetryV2
    payload = {"schema_version": 2, "device_id": 1,
               "boot_id": "d5c5579f-529e-483f-a2b2-617506b2630f", "sequence": 1,
               "observed_at": "2026-11-14T12:00:00-03:00",
               "temperature_c": {"value": 22, "quality": "good"},
               "brix_apparent": {"value": None, "quality": "missing"}}
    with pytest.raises(ValueError):
        TelemetryV2.model_validate({**payload, **mutation})


def test_v2_preserves_missing_channel_and_normalizes_time():
    from app.telemetry_contract import TelemetryV2
    reading = TelemetryV2.model_validate({"schema_version": 2, "device_id": 1,
        "boot_id": "d5c5579f-529e-483f-a2b2-617506b2630f", "sequence": 1,
        "observed_at": "2026-11-14T12:00:00-03:00",
        "temperature_c": {"value": 22, "quality": "good"},
        "brix_apparent": {"value": None, "quality": "missing"}})
    assert reading.observed_at.hour == 15
    assert reading.brix_apparent.value is None

