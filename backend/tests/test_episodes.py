"""V2 episode lifecycle, time evidence, human actions and concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.database import SessionLocal, engine
from app.main import app
from app.services.auth_service import create_access_token
from app.services.telemetry_v2 import aware


@pytest.fixture
def stream(client):
    key = client.post("/api/dispositivos/1/credenciales", json={"source": "simulado", "label": "Episode tests"}).json()["token"]
    start = datetime.now(timezone.utc) - timedelta(hours=3)
    calibration = client.post("/api/dispositivos/1/calibraciones", json={"version": "episodes", "method": "synthetic_identity",
                               "valid_from": (start-timedelta(hours=1)).isoformat()}).json()["calibration_id"]
    boot = str(uuid4())
    def transmit(minutes, temperature=30, quality="good", seq=None, sender=None, brix_quality="good"):
        return (sender or client).post("/api/v2/telemetria", headers={"X-Mosto-Device-Key": key}, json={
            "schema_version": 2, "device_id": 1, "boot_id": boot, "sequence": seq if seq is not None else minutes,
            "observed_at": (start+timedelta(minutes=minutes)).isoformat(),
            "temperature_c": {"quality": quality, "value": temperature},
            "brix_apparent": {"quality": brix_quality, "value": 20 if brix_quality == "good" else None},
            "calibration_id": calibration})
    return transmit, start


def open_episode(client, stream):
    send, _ = stream
    for minute in (0, 5, 10):
        response = send(minute)
        assert response.status_code == 201, response.text
    alerts = client.get("/api/alertas?origen=simulado").json()
    assert len(alerts) == 1
    return alerts[0]


def test_sustained_condition_creates_one_episode_with_frozen_evidence(client, stream):
    send, start = stream
    assert send(0).status_code == 201
    assert send(5).status_code == 201
    assert client.get("/api/alertas").json() == []
    assert send(10, brix_quality="missing").status_code == 201
    for minute in (15, 30, 60, 90):
        assert send(minute).status_code == 201
    alerts = client.get("/api/alertas").json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["tipo_alerta"] == "temperatura_alta" and alert["version_regla"] == "thermal-v2-1"
    assert datetime.fromisoformat(alert["inicio_condicion"]) == start
    assert alert["evidencia"]["configuration"]["temp_max"] == 26
    assert datetime.fromisoformat(alert["timestamp"]) > start + timedelta(hours=2)
    assert alert["estado_condicion"] == "activa" and alert["estado"] == "pendiente"


def test_recovery_needs_hysteresis_and_hold_and_does_not_resolve_human_work(client, stream):
    alert = open_episode(client, stream)
    send, _ = stream
    for minute in (15, 20, 25):
        assert send(minute, 25.8).status_code == 201
    assert client.get(f"/api/alertas/{alert['id']}").json()["fin_condicion"] is None
    for minute in (30, 35, 40):
        assert send(minute, 25).status_code == 201
    recovered = client.get(f"/api/alertas/{alert['id']}").json()
    assert recovered["estado_condicion"] == "recuperada" and recovered["estado"] == "pendiente"
    assert recovered["fecha_resolucion"] is None
    for minute in (45, 50, 55):
        assert send(minute, 30).status_code == 201
    assert len(client.get("/api/alertas").json()) == 2


def test_missing_channel_and_gaps_cannot_fake_recovery_or_persistence(client, stream):
    send, _ = stream
    send(0); send(20); send(25)
    assert client.get("/api/alertas").json() == []
    send(30)
    alert = client.get("/api/alertas").json()[0]
    send(35, None, "missing")
    assert client.get(f"/api/alertas/{alert['id']}").json()["estado_condicion"] == "desconocida"
    send(40, 24); send(60, 24); send(65, 24)
    assert client.get(f"/api/alertas/{alert['id']}").json()["fin_condicion"] is None
    send(70, 24)
    assert client.get(f"/api/alertas/{alert['id']}").json()["estado_condicion"] == "recuperada"


def test_out_of_order_and_duplicate_messages_do_not_rewrite_episode_history(client, stream):
    alert = open_episode(client, stream)
    send, _ = stream
    before = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    assert send(10).status_code == 200
    assert send(2, 22).status_code == 201
    assert client.get(f"/api/alertas/{alert['id']}/eventos").json() == before


def test_profile_changes_do_not_reinterpret_existing_rule_snapshot(client, stream):
    alert = open_episode(client, stream)
    with SessionLocal() as db:
        db.get(m.PerfilFermentacion, 1).temp_max = 40
        db.commit()
    for minute in (15, 20, 25):
        stream[0](minute, 30)
    result = client.get(f"/api/alertas/{alert['id']}").json()
    assert result["estado_condicion"] == "activa" and result["evidencia"]["configuration"]["temp_max"] == 26


def test_episode_escalates_once_and_preserves_initial_evidence(client, stream):
    alert = open_episode(client, stream)
    stream[0](15, 36); stream[0](20, 38)
    result = client.get(f"/api/alertas/{alert['id']}").json()
    assert result["severidad"] == "critica" and result["evidencia"]["temperature_c"] == 30
    events = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    assert sum(e["accion"] == "escalada" for e in events) == 1


def test_no_profile_does_not_invent_thresholds(client, stream):
    with SessionLocal() as db:
        db.get(m.PerfilFermentacion, 1).temp_min = None
        db.get(m.PerfilFermentacion, 1).temp_max = None
        db.commit()
    for minute in (0, 5, 10):
        assert stream[0](minute).status_code == 201
    assert client.get("/api/alertas").json() == []


def test_resolution_is_idempotent_and_distinct_from_signal_recovery(client, stream):
    alert = open_episode(client, stream)
    ident = alert["id"]
    assert client.patch(f"/api/alertas/{ident}/resolver", json={"nota_resolucion": ""}).status_code == 422
    attended = client.patch(f"/api/alertas/{ident}/atender", json={"nota": "Inspección", "usuario_id": 999}).json()
    assert client.patch(f"/api/alertas/{ident}/atender", json={"nota": "Inspección"}).json()["fecha_atencion"] == attended["fecha_atencion"]
    note = {"nota_resolucion": "Revisada la condición; seguimiento pendiente."}
    resolved = client.patch(f"/api/alertas/{ident}/resolver", json=note).json()
    assert resolved["resuelta_por"] == 1 and resolved["estado_condicion"] == "activa"
    repeat = client.patch(f"/api/alertas/{ident}/resolver", json=note).json()
    assert repeat["fecha_resolucion"] == resolved["fecha_resolucion"]
    assert client.patch(f"/api/alertas/{ident}/resolver", json={"nota_resolucion": "Una nota diferente"}).status_code == 409
    assert len(client.get(f"/api/bitacora?alerta_id={ident}").json()) == 1
    for minute in (15, 20, 25):
        stream[0](minute)
    assert len(client.get("/api/alertas").json()) == 1
    events = client.get(f"/api/alertas/{ident}/eventos").json()
    assert [e["accion"] for e in events] == ["creada", "atendida", "resuelta"]
    assert client.get("/api/alertas/metricas").json()["condiciones_sin_recuperacion"] == 1


def test_process_closure_preserves_human_work_and_supports_linked_historical_intervention(client, stream):
    alert = open_episode(client, stream)
    assert client.patch("/api/procesos/1/finalizar").status_code == 200
    closed = client.get(f"/api/alertas/{alert['id']}").json()
    assert closed["estado_condicion"] == "cerrada_proceso" and closed["estado"] == "pendiente"
    body = {"type": "nota", "message": "Verificación posterior del lote cerrado", "alerta_id": alert["id"]}
    result = client.post("/api/bitacora", json=body)
    assert result.status_code == 201, result.text
    assert result.json()["fermentacion_id"] == 1
    assert client.post("/api/bitacora", json={**body, "fermentacion_id": 2}).status_code == 409


def test_episode_failure_rolls_back_the_telemetry_and_retry_remains_possible(client, stream, monkeypatch):
    from app.services import episodes
    stream[0](0); stream[0](5)
    original = episodes.record_action
    def failure(*args, **kwargs):
        raise RuntimeError("Injected audit failure")
    monkeypatch.setattr(episodes, "record_action", failure)
    with pytest.raises(RuntimeError, match="Injected audit failure"):
        stream[0](10)
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 2 and db.query(m.EventoAlerta).count() == 0
    monkeypatch.setattr(episodes, "record_action", original)
    assert stream[0](10).status_code == 201


def test_mttr_excludes_invalid_dates_and_filters_match_export_and_list(client, stream):
    open_episode(client, stream)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for stamp, resolved in ((now-timedelta(minutes=30), now), (now, None), (now, now-timedelta(minutes=1))):
            db.add(m.EventoAlerta(fermentacion_id=1, tipo_alerta="legacy", estado="resuelta",
                                 severidad="media", timestamp=stamp, fecha_resolucion=resolved))
        db.commit()
    metrics = client.get("/api/alertas/metricas").json()
    assert metrics["muestras_mttr"] == 1 and metrics["resueltas_sin_tiempos_validos"] == 2
    assert metrics["mttr_promedio_minutos"] == 30
    filters = "origen=simulado&tipo_alerta=temperatura_alta&estado=pendiente"
    assert client.get(f"/api/alertas/metricas?{filters}").json()["total_alertas"] == 1
    assert client.get(f"/api/alertas/metricas?{filters}").json()["mttr_promedio_minutos"] is None
    assert len(client.get(f"/api/alertas?{filters}").json()) == 1
    csv = client.get(f"/api/alertas/exportar?{filters}").text
    assert "thermal" not in csv and "legacy" not in csv and "simulado" in csv


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires PostgreSQL concurrency")
def test_concurrent_confirmation_and_resolution_create_one_episode_and_one_action(client, stream):
    send, _ = stream
    send(0); send(5)
    barrier = Barrier(2)
    def transmit(minute):
        with TestClient(app) as sender:
            barrier.wait(timeout=10)
            return send(minute, sender=sender).status_code
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(transmit, (10, 15))) == [201, 201]
    alerts = client.get("/api/alertas").json(); assert len(alerts) == 1
    ident = alerts[0]["id"]
    barrier = Barrier(2)
    def resolve(_):
        with TestClient(app) as sender:
            barrier.wait(timeout=10)
            return sender.patch(f"/api/alertas/{ident}/resolver", headers={"Authorization": "Bearer " + create_access_token({"sub":1})},
                                json={"nota_resolucion": "Revisión concurrente registrada"}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(resolve, (0, 1))) == [200, 200]
    with SessionLocal() as db:
        assert db.query(m.AuditoriaAlerta).filter_by(alerta_id=ident, accion="resuelta").count() == 1
        assert db.query(m.BitacoraIntervencion).filter_by(alerta_id=ident).count() == 1
        event = db.query(m.AuditoriaAlerta).filter_by(alerta_id=ident).first()
        event.accion = "changed"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
