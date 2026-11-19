"""HTTP integration of device identity, quality, temporal routing and idempotency."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, get_ident
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy import event

from app import models as m
from app.database import SessionLocal, engine
from app.main import app
from app.services.auth_service import create_access_token
from app.services.telemetry_v2 import token_hash


def provision(client, device=1, source="fisico"):
    response = client.post(f"/api/dispositivos/{device}/credenciales", json={
        "source": source, "label": "Test fixture"})
    assert response.status_code == 201, response.text
    credential = response.json()
    assert response.headers["cache-control"] == "no-store"
    calibration = {"version": "test-v1", "method": "tilt_polynomial" if source == "fisico" else "synthetic_identity",
                   "valid_from": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
    if source == "fisico":
        calibration.update(coefficients=[-10, 0.5], tilt_min=20, tilt_max=80)
    response = client.post(f"/api/dispositivos/{device}/calibraciones", json=calibration)
    assert response.status_code == 201, response.text
    return credential, response.json()["calibration_id"]


@pytest.fixture
def packet(client):
    credential, calibration = provision(client)
    body = {"schema_version": 2, "device_id": 1, "boot_id": str(uuid4()), "sequence": 1,
            "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "temperature_c": {"value": 22, "quality": "good"},
            "brix_apparent": {"value": 20, "quality": "good"},
            "tilt_degrees": 60, "calibration_id": calibration}
    return body, credential


def send(client, packet, body=None):
    payload, credential = packet
    return client.post("/api/v2/telemetria", json=body or payload,
                       headers={"X-Mosto-Device-Key": credential["token"]})


def test_physical_ingestion_is_visible_in_history_and_has_no_fake_channels(client, packet):
    response = send(client, packet)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["source"] == "fisico" and result["process_id"] == 1
    assert result["temperature_c"] == {"value": 22, "quality": "good"}
    assert result["brix_apparent"] == {"value": 20, "quality": "good"}
    with SessionLocal() as db:
        message = db.get(m.MensajeTelemetria, result["message_id"])
        reading = db.get(m.LecturaTelemetria, message.lectura_id)
        assert reading.origen_dato == "v2_fisico"
        assert reading.ph is None and reading.temp_ambiente is None and reading.densidad_sg is None
        assert message.payload["tilt_degrees"] == 60
        assert packet[1]["token"] not in str(message.payload)
        assert db.get(m.CredencialDispositivo, packet[1]["credential_id"]).token_hash == token_hash(packet[1]["token"])
    history = client.get("/api/cubas/1/historico").json()
    assert history["grados_brix"][-1] == 20
    device = client.get("/api/dispositivos/1").json()
    assert device["source"] == "fisico" and device["status"] == "online"
    assert device["batteryLevel"] is None and device["signalRssi"] is None
    prediction = client.get("/api/cubas/1/ml-prediction").json()
    assert prediction["estado_ia"] == "NO_VALIDADO" and prediction["riesgo_pct"] is None
    assert client.get(f"/api/v2/telemetria/{result['message_id']}").status_code == 200


def test_identical_retry_is_idempotent_but_conflicting_sequence_is_rejected(client, packet):
    first = send(client, packet)
    assert first.status_code == 201
    retry = send(client, packet)
    assert retry.status_code == 200 and retry.json()["duplicate"]
    assert retry.json()["message_id"] == first.json()["message_id"]
    assert retry.json()["received_at"] == first.json()["received_at"]
    changed = deepcopy(packet[0]); changed["temperature_c"]["value"] = 23
    assert send(client, packet, changed).status_code == 409
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 1
        assert db.query(m.LecturaTelemetria).count() == 1


@pytest.mark.parametrize("quality,value", [("missing", None), ("invalid", -127), ("uncalibrated", 20)])
def test_one_failed_channel_does_not_discard_other_measurement(client, packet, quality, value):
    body = deepcopy(packet[0]); body["brix_apparent"] = {"value": value, "quality": quality}
    body["calibration_id"] = None
    response = send(client, packet, body)
    assert response.status_code == 201, response.text
    assert response.json()["temperature_c"] == {"quality": "good", "value": 22}
    assert response.json()["brix_apparent"] == {"quality": quality, "value": None}


def test_mismatched_calibration_preserves_raw_value_but_excludes_it_from_curves(client, packet):
    body = deepcopy(packet[0]); body["brix_apparent"]["value"] = 25
    response = send(client, packet, body)
    assert response.status_code == 201
    assert response.json()["brix_apparent"] == {"quality": "invalid", "value": None}
    assert "reported_brix_disagrees_with_calibration" in response.json()["diagnostics"]
    with SessionLocal() as db:
        assert db.get(m.MensajeTelemetria, response.json()["message_id"]).payload["brix_apparent"]["value"] == 25
    assert client.get("/api/cubas/1/historico").json()["grados_brix"][-1] is None


@pytest.mark.parametrize("mutation,diagnostic,quality", [
    ({"tilt_degrees": None}, "tilt_missing_or_outside_calibration", "uncalibrated"),
    ({"tilt_degrees": 90}, "tilt_missing_or_outside_calibration", "uncalibrated"),
])
def test_tilt_calibration_domain_is_enforced(client, packet, mutation, diagnostic, quality):
    body = {**packet[0], **mutation}
    response = send(client, packet, body)
    assert response.status_code == 201
    assert response.json()["brix_apparent"]["quality"] == quality
    assert diagnostic in response.json()["diagnostics"]


def test_bad_temperature_does_not_invalidate_uncompensated_brix(client, packet):
    body = deepcopy(packet[0]); body["temperature_c"]["value"] = -127
    response = send(client, packet, body)
    assert response.status_code == 201
    assert response.json()["temperature_c"] == {"quality": "invalid", "value": None}
    assert response.json()["brix_apparent"]["quality"] == "good"


def test_revoked_calibration_downgrades_new_messages_but_not_prior_receipts(client, packet):
    first = send(client, packet)
    assert first.status_code == 201
    assert client.delete(f"/api/dispositivos/1/calibraciones/{packet[0]['calibration_id']}").status_code == 200
    assert send(client, packet).json()["brix_apparent"]["quality"] == "good"
    body = deepcopy(packet[0]); body["sequence"] = 2
    body["observed_at"] = datetime.now(timezone.utc).isoformat()
    response = send(client, packet, body)
    assert response.status_code == 201
    assert response.json()["brix_apparent"]["quality"] == "uncalibrated"


def test_keys_are_bound_to_device_revocable_and_not_retrievable(client, packet):
    listing = client.get("/api/dispositivos/1/credenciales")
    assert listing.status_code == 200
    assert "token" not in listing.text and "hash" not in listing.text
    assert client.post("/api/v2/telemetria", json=packet[0]).status_code == 401
    body = deepcopy(packet[0]); body["device_id"] = 2
    assert send(client, packet, body).status_code == 403
    assert client.delete(f"/api/dispositivos/1/credenciales/{packet[1]['credential_id']}").status_code == 200
    assert send(client, packet).status_code == 401


def test_expired_key_and_suspended_device_are_rejected(client, packet, monkeypatch):
    from app.services import telemetry_v2
    future = datetime.now(timezone.utc) + timedelta(days=100)
    with monkeypatch.context() as patch:
        patch.setattr(telemetry_v2, "utc_now", lambda: future)
        assert send(client, packet).status_code == 401
    with SessionLocal() as db:
        db.get(m.Dispositivo, 1).estado = "inactivo"
        db.commit()
    assert send(client, packet).status_code == 403


@pytest.mark.parametrize("field,value", [("source", "fisico"), ("empresa_id", 2), ("received_at", "2026-01-01T00:00:00Z")])
def test_client_cannot_supply_server_owned_fields(client, packet, field, value):
    body = {**packet[0], field: value}
    assert send(client, packet, body).status_code == 422


def test_future_unassigned_and_wrong_calibration_messages_do_not_create_rows(client, packet):
    with SessionLocal() as db:
        initial_process_count = db.query(m.ProcesoFermentacion).count()
    body = deepcopy(packet[0]); body["observed_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert send(client, packet, body).status_code == 422
    body["observed_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assert send(client, packet, body).status_code == 409
    _, other_calibration = provision(client, 2)
    body = {**packet[0], "calibration_id": other_calibration}
    assert send(client, packet, body).status_code == 409
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == db.query(m.LecturaTelemetria).count() == 0
        assert db.query(m.ProcesoFermentacion).count() == initial_process_count


def test_late_out_of_order_reading_and_boot_restart(client, packet):
    assert send(client, packet).status_code == 201
    body = deepcopy(packet[0]); body["sequence"] = 2
    body["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    response = send(client, packet, body)
    assert response.status_code == 201
    assert response.json()["out_of_order"] and response.json()["delayed"]
    body["sequence"] = 1; body["boot_id"] = str(uuid4())
    body["observed_at"] = datetime.now(timezone.utc).isoformat()
    assert send(client, packet, body).status_code == 201
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 3


def test_measurement_is_attributed_to_old_assignment_after_reassignment(client, packet):
    assert client.post("/api/dispositivos/vincular", json={"dispositivo_id": 1, "cuba_id": 2}).status_code == 200
    response = send(client, packet)
    assert response.status_code == 201 and response.json()["process_id"] == 1
    body = deepcopy(packet[0]); body["sequence"] = 2; body["observed_at"] = datetime.now(timezone.utc).isoformat()
    response = send(client, packet, body)
    assert response.status_code == 201 and response.json()["process_id"] == 2


def test_process_cannot_mix_physical_and_simulated_sources(client, packet):
    assert send(client, packet).status_code == 201
    credential, calibration = provision(client, device=2, source="simulado")
    assert client.post("/api/dispositivos/vincular", json={"dispositivo_id": 2, "cuba_id": 1}).status_code == 200
    body = {**packet[0], "device_id": 2, "calibration_id": calibration,
            "observed_at": datetime.now(timezone.utc).isoformat(), "tilt_degrees": None}
    response = send(client, (body, credential))
    assert response.status_code == 409 and "mezclar" in response.json()["detail"]
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 1


def test_simulated_source_is_explicit_and_cannot_be_promoted_to_physical(client):
    key, calibration = provision(client, source="simulado")
    body = {"schema_version": 2, "device_id": 1, "boot_id": str(uuid4()), "sequence": 0,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": {"value": 22, "quality": "good"},
            "brix_apparent": {"value": 18, "quality": "good"}, "calibration_id": calibration}
    response = send(client, (body, key))
    assert response.status_code == 201 and response.json()["source"] == "simulado"
    assert client.post("/api/dispositivos/1/credenciales", json={"source": "fisico", "label": "Forbidden"}).status_code == 409


def test_non_admin_cannot_issue_keys_or_calibrations(client, packet):
    with SessionLocal() as db:
        membership = db.query(m.UsuarioBodega).filter_by(usuario_id=1).one()
        membership.rol_id = db.query(m.Rol).filter_by(codigo="operador").one().id
        db.commit()
    assert client.post("/api/dispositivos/1/credenciales", json={"source": "fisico", "label": "Forbidden"}).status_code == 403
    assert client.delete(f"/api/dispositivos/1/calibraciones/{packet[0]['calibration_id']}").status_code == 403
    # Browser roles do not substitute for the hardware credential.
    assert client.post("/api/v2/telemetria", json=packet[0]).status_code == 401


def test_tenant_cannot_provision_or_read_another_company_receipt(client, packet):
    receipt = send(client, packet).json()
    with SessionLocal() as db:
        company = m.EmpresaCliente(nomb_emp="Another company")
        db.add(company); db.flush()
        warehouse = m.Bodega(nombre="Another warehouse", empresa_id=company.id)
        actor = m.Usuario(nomb_compl="Another admin", correo_elec="other@example.invalid", empresa_id=company.id)
        db.add_all([warehouse, actor]); db.flush()
        db.add(m.UsuarioBodega(usuario_id=actor.id, bodega_id=warehouse.id, rol_id=1))
        db.commit(); ident = actor.id
    client.headers["Authorization"] = "Bearer " + create_access_token({"sub": ident})
    assert client.get(f"/api/v2/telemetria/{receipt['message_id']}").status_code == 404
    assert client.get("/api/dispositivos/1/calibraciones").status_code == 404
    assert client.post("/api/dispositivos/1/credenciales", json={"source": "fisico", "label": "Forbidden"}).status_code == 404


def test_temperature_compensation_requires_a_valid_temperature(client, packet):
    response = client.post("/api/dispositivos/1/calibraciones", json={
        "version": "compensated", "method": "tilt_polynomial", "coefficients": [-10, 0.5],
        "tilt_min": 20, "tilt_max": 80, "temperature_coefficient": 0.1, "reference_temperature": 20,
        "valid_from": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()})
    assert response.status_code == 201
    body = deepcopy(packet[0]); body["calibration_id"] = response.json()["calibration_id"]
    body["temperature_c"] = {"quality": "missing", "value": None}
    result = send(client, packet, body)
    assert result.status_code == 201 and result.json()["brix_apparent"]["quality"] == "uncalibrated"
    assert "temperature_required_for_calibration" in result.json()["diagnostics"]


def test_same_timestamp_with_new_sequence_conflicts_without_partial_message(client, packet):
    first = send(client, packet)
    assert first.status_code == 201
    body = {**packet[0], "sequence": 2}
    assert send(client, packet, body).status_code == 409
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == db.query(m.LecturaTelemetria).count() == 1
    assert send(client, packet).status_code == 200


@pytest.mark.parametrize("source", ["fisico", "simulado"])
def test_provisioned_device_and_tank_reject_legacy_demo_injection(client, source):
    with SessionLocal() as db:
        initial_process_count = db.query(m.ProcesoFermentacion).count()
        initial_assignment_count = db.query(m.AsignacionDispositivo).count()
    from app.database import settings
    provision(client, source=source)
    # Isolation starts at provisioning, before the first canonical measurement.
    for action in ("simular-anomalia", "restaurar-normalidad"):
        assert client.post(f"/api/cubas/1/{action}").status_code == 409
    for device, target in ((1, 1), (2, 1)):
        response = client.post("/api/telemetria/nodo-cuba", json={
            "mac_address": f"02:00:00:00:00:{device:02X}", "cuba_id": target, "temperatura_vino": 22},
            headers={"X-Mosto-Simulator-Key": settings.simulator_key})
        assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.query(m.LecturaTelemetria).count() == 0
        assert db.query(m.ProcesoFermentacion).count() == initial_process_count
        assert db.query(m.AsignacionDispositivo).count() == initial_assignment_count


def test_process_with_canonical_history_rejects_demo_after_device_reassignment(client, packet):
    assert send(client, packet).status_code == 201
    assert client.post("/api/dispositivos/vincular", json={"dispositivo_id": 1, "cuba_id": 2}).status_code == 200
    assert client.post("/api/cubas/1/simular-anomalia").status_code == 409
    assert client.post("/api/cubas/1/restaurar-normalidad").status_code == 409
    with SessionLocal() as db:
        assert db.query(m.LecturaTelemetria).count() == 1


def test_retry_after_process_close_and_equivalent_utc_offset_is_identical(client, packet):
    response = send(client, packet)
    assert response.status_code == 201
    assert client.patch("/api/procesos/1/finalizar").status_code == 200
    body = deepcopy(packet[0])
    observed = datetime.fromisoformat(body["observed_at"])
    body["observed_at"] = observed.astimezone(timezone(timedelta(hours=-3))).isoformat()
    retry = send(client, packet, body)
    assert retry.status_code == 200 and retry.json()["message_id"] == response.json()["message_id"]


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL row locking")
def test_revocation_wins_when_ingestion_is_waiting_for_device_lock(client, packet):
    waiting = Event()
    owner_thread = get_ident()
    def query_started(conn, cursor, statement, parameters, context, executemany):
        if get_ident() != owner_thread and '"DISPOSITIVO"' in statement and "FOR UPDATE" in statement:
            waiting.set()
    event.listen(engine, "before_cursor_execute", query_started)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with SessionLocal() as db:
                db.query(m.Dispositivo).filter_by(id=1).with_for_update().one()
                def transmit():
                    with TestClient(app) as sender:
                        return send(sender, packet).status_code
                future = pool.submit(transmit)
                try:
                    assert waiting.wait(timeout=10), "Ingestion did not reach the device lock"
                    credential = db.get(m.CredencialDispositivo, packet[1]["credential_id"])
                    credential.revocada_en = datetime.now(timezone.utc)
                    db.commit()
                finally:
                    db.rollback()
            assert future.result(timeout=15) == 401
    finally:
        event.remove(engine, "before_cursor_execute", query_started)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL concurrency and immutability")
def test_concurrent_retries_and_database_immutability(client, packet):
    barrier = Barrier(2)
    def transmit(_):
        with TestClient(app) as sender:
            barrier.wait(timeout=10)
            response = send(sender, packet)
            return response.status_code, response.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transmit, (0, 1)))
    assert sorted(code for code, _ in results) == [200, 201]
    assert results[0][1]["message_id"] == results[1][1]["message_id"]
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == db.query(m.LecturaTelemetria).count() == 1
        row = db.query(m.MensajeTelemetria).one()
        row.origen = "simulado"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
