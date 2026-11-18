"""Persistence policy via HTTP; mocked features isolate lifecycle, one real 25 h replay."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import models as m
from app.database import SessionLocal
from app.main import app
from app.services import kinetic_episodes, telemetry_v2, episodes
from test_telemetry_v2 import provision
from test_access import tenants, as_user


@pytest.fixture
def kinetic_stream(client, monkeypatch):
    credential, calibration = provision(client, source="simulado")
    # Advance a controlled clock from the existing assignment instead of
    # rewriting immutable historical ownership (enforced by PostgreSQL).
    base = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.get(m.ProcesoFermentacion, 1).fecha_inicio = base - timedelta(days=1)
        db.commit()
    clock = {"now": base}
    monkeypatch.setattr(telemetry_v2, "utc_now", lambda: clock["now"])
    boot = str(uuid4())
    def send(minute, *, brix=10, quality="good", temperature=22, sender=None, delay=0):
        observed = base + timedelta(minutes=minute)
        clock["now"] = observed + timedelta(minutes=delay)
        return (sender or client).post("/api/v2/telemetria", headers={"X-Mosto-Device-Key": credential["token"]}, json={
            "schema_version": 2, "device_id": 1, "boot_id": boot, "sequence": minute,
            "observed_at": observed.isoformat(), "calibration_id": calibration,
            "temperature_c": {"value": temperature, "quality": "good" if temperature is not None else "missing"},
            "brix_apparent": {"value": brix if quality == "good" else None, "quality": quality}})
    return send, clock, base


@pytest.fixture
def slopes(monkeypatch):
    snapshot = {"version": "kinetics-v1", "window_start": "2026-01-01T00:00:00+00:00",
        "as_of": "2026-01-02T00:00:00+00:00", "channels": {"brix": {"coverage": 1}},
        "features": {"age_hours": 48, "brix_mean_1h": 10,
                     "brix_slope_6h": 0, "brix_slope_24h": -.1}}
    monkeypatch.setattr(kinetic_episodes, "process_kinetics", lambda *args: deepcopy(snapshot))
    return snapshot["features"]


def activate(client, **config):
    result = client.post("/api/procesos/1/regla-cinetica", json=config)
    assert result.status_code == 201, result.text
    return result.json()


def alerts(client):
    return client.get("/api/alertas", params={"tipo_alerta": "brix_ralentizacion"}).json()


def open_episode(client, stream):
    activate(client)
    for minute in range(5, 66, 10):
        result = stream[0](minute)
        assert result.status_code == 201, result.text
    result = alerts(client)
    assert len(result) == 1
    return result[0]


def test_opt_in_frozen_configuration_and_separate_probability(client, kinetic_stream, slopes):
    send, _, _ = kinetic_stream
    assert send(1).status_code == 201
    assert alerts(client) == []
    first = activate(client)
    repeat = client.post("/api/procesos/1/regla-cinetica", json={})
    assert repeat.status_code == 200 and repeat.json() == first
    assert client.post("/api/procesos/1/regla-cinetica", json={"hold_minutes": 120}).status_code == 409
    assert first["configuration"]["configured_by"] == 1
    assert client.get("/api/procesos/1/cinetica").json()["riesgo_pct"] is None


def test_persistent_episode_audit_and_resolution_do_not_repeat(client, kinetic_stream, slopes):
    alert = open_episode(client, kinetic_stream)
    assert alert["version_regla"] == "kinetic-episodes-v1"
    assert "Brix" in alert["titulo"] and "Temperatura" not in alert["titulo"]
    assert alert["evidencia"]["features"]["brix_slope_6h"] == 0
    assert alert["evidencia"]["configuration"]["hold_minutes"] == 60
    result = client.patch(f"/api/alertas/{alert['id']}/resolver", json={"nota_resolucion": "Revisada la simulación y registrada para seguimiento."})
    assert result.status_code == 200 and result.json()["estado_condicion"] == "activa"
    assert kinetic_stream[0](75).status_code == 201
    assert len(alerts(client)) == 1
    history = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    assert [e["accion"] for e in history] == ["creada", "resuelta"]
    assert len(client.get(f"/api/bitacora?alerta_id={alert['id']}").json()) == 1


def test_hysteresis_recovery_and_new_episode(client, kinetic_stream, slopes):
    alert = open_episode(client, kinetic_stream)
    send = kinetic_stream[0]
    slopes["brix_slope_6h"] = -.02
    for minute in range(75, 136, 10):
        assert send(minute).status_code == 201
    assert alerts(client)[0]["fin_condicion"] is None
    slopes["brix_slope_6h"] = -.05
    for minute in range(145, 206, 10):
        assert send(minute).status_code == 201
    recovered = client.get(f"/api/alertas/{alert['id']}").json()
    assert recovered["estado_condicion"] == "recuperada" and recovered["estado"] == "pendiente"
    history = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    assert history[-1]["accion"] == "evidencia_recuperacion"
    slopes["brix_slope_6h"] = 0
    for minute in range(215, 276, 10):
        assert send(minute).status_code == 201
    assert len(alerts(client)) == 2


def test_bad_brix_gap_and_late_delivery_reset_persistence(client, kinetic_stream, slopes):
    activate(client)
    send = kinetic_stream[0]
    for minute in (5, 15, 25):
        assert send(minute).status_code == 201
    assert send(35, quality="missing").status_code == 201
    for minute in (45, 55, 65):
        assert send(minute).status_code == 201
    assert alerts(client) == []
    assert send(90).status_code == 201  # gap resets again
    for minute in range(100, 151, 10):
        assert send(minute, temperature=None).status_code == 201  # thermal failure independent
    assert len(alerts(client)) == 1
    assert send(160, delay=20).status_code == 201
    assert alerts(client)[0]["estado_condicion"] == "desconocida"


def test_lag_low_brix_and_no_prior_decline_do_not_create_episodes(client, kinetic_stream, slopes):
    activate(client)
    for field, value in (("age_hours", 12), ("brix_mean_1h", 2), ("brix_slope_24h", 0)):
        old = slopes[field]
        slopes[field] = value
        start = {"age_hours": 5, "brix_mean_1h": 105, "brix_slope_24h": 205}[field]
        for minute in range(start, start+71, 10):
            assert kinetic_stream[0](minute).status_code == 201
        slopes[field] = old
        assert alerts(client) == []


def test_duplicate_and_out_of_order_do_not_rewrite_history(client, kinetic_stream, slopes):
    alert = open_episode(client, kinetic_stream)
    before = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    assert kinetic_stream[0](65).status_code == 200
    assert kinetic_stream[0](7).status_code == 201
    assert client.get(f"/api/alertas/{alert['id']}/eventos").json() == before


def test_audit_failure_rolls_back_message_and_retry(client, kinetic_stream, slopes, monkeypatch):
    activate(client)
    for minute in range(5, 65, 10):
        kinetic_stream[0](minute)
    original = episodes.record_action
    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")
    monkeypatch.setattr(episodes, "record_action", fail)
    with TestClient(app, raise_server_exceptions=False) as sender:
        assert kinetic_stream[0](65, sender=sender).status_code == 500
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).filter_by(secuencia=65).first() is None
    monkeypatch.setattr(episodes, "record_action", original)
    assert kinetic_stream[0](65).status_code == 201
    assert len(alerts(client)) == 1


def test_process_closure_and_physical_guard(client, kinetic_stream, slopes):
    alert = open_episode(client, kinetic_stream)
    assert client.patch("/api/procesos/1/finalizar").status_code == 200
    assert client.get(f"/api/alertas/{alert['id']}").json()["estado_condicion"] == "cerrada_proceso"
    assert client.post("/api/procesos/1/regla-cinetica", json={}).status_code == 409


def test_physical_and_unprovisioned_devices_cannot_enable_experiment(client):
    assert client.post("/api/procesos/1/regla-cinetica", json={}).status_code == 409
    provision(client, source="fisico")
    assert client.post("/api/procesos/1/regla-cinetica", json={}).status_code == 409


def test_operator_cannot_configure_but_can_read_kinetics(client, tenants):
    as_user(client, tenants["member"])
    assert client.post("/api/procesos/1/regla-cinetica", json={}).status_code == 403
    assert client.get("/api/procesos/1/cinetica").status_code == 200


def test_invalid_parameters_and_environment_guard(client, kinetic_stream, monkeypatch):
    assert client.post("/api/procesos/1/regla-cinetica", json={"scope": "fisico"}).status_code == 422
    assert client.post("/api/procesos/1/regla-cinetica", json={"recovery_slope_threshold": -.005}).status_code == 422
    from app.services import demo_access
    from dataclasses import replace
    monkeypatch.setattr(demo_access, "settings", replace(demo_access.settings, environment="development"))
    assert client.post("/api/procesos/1/regla-cinetica", json={}).status_code == 403


def test_real_extractor_replay_creates_a_causal_episode(client, kinetic_stream):
    activate(client)
    for minute in range(10, 1501, 10):
        # 16 h of activity followed by a plateau: 6 h slope near zero after hour 22.
        brix = 24 - .1 * min(minute/60, 16)
        result = kinetic_stream[0](minute, brix=brix)
        assert result.status_code == 201, result.text
    result = alerts(client)
    assert len(result) == 1
    evidence = result[0]["evidencia"]
    assert evidence["features"]["brix_slope_6h"] > -.015
    assert evidence["features"]["brix_slope_24h"] < -.04
    assert evidence["channels"]["brix"]["coverage"] >= .8
    current = client.get("/api/procesos/1/cinetica").json()
    assert current["current_kinetic_rule"]["episode_id"] == result[0]["id"]
    assert current["riesgo_pct"] is None
