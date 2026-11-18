from datetime import datetime, timedelta, timezone
from dataclasses import replace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine, settings
from app.main import app
from app import models as m
from app.services import demo_access


def test_registered_clock_is_scoped_frozen_and_not_yet_ingestible(client, monkeypatch):
    credential = client.post('/api/dispositivos/1/credenciales', json={
        'source':'simulado', 'label':'Clock test'}).json()
    with SessionLocal() as db:
        start = db.get(m.ProcesoFermentacion, 1).fecha_inicio.replace(tzinfo=timezone.utc).isoformat()
    clock = dict(real_anchor=datetime.now(timezone.utc).isoformat(), simulated_anchor=start, factor=60)
    body = dict(version='clock-test', method='synthetic_identity', valid_from=start,
        simulation=dict(process_id=1, process_start=start, seed=42, scenario='healthy'), simulation_clock=clock)
    url='/api/dispositivos/1/calibraciones'
    response=client.post(url,json=body)
    assert response.status_code == 201, response.text
    ident=response.json()['calibration_id']
    headers={'X-Mosto-Device-Key':credential['token']}
    config=client.get(f'/api/v2/telemetria/configuracion/1/{ident}',headers=headers).json()
    assert config['simulation_clock']['factor']==60
    assert client.post(url,json={**body,'simulation_clock':{**clock,'factor':180}}).status_code==409
    assert client.post(url,json={**body,'simulation_clock':None}).status_code==409
    assert client.post(url,json={**body,'simulation':None}).status_code==422
    packet=dict(schema_version=2,device_id=1,boot_id=str(uuid4()),sequence=0,
        observed_at=start,calibration_id=ident,temperature_c=dict(value=22,quality='good'),
        brix_apparent=dict(value=24,quality='good'))
    assert client.post('/api/v2/telemetria',headers=headers,json=packet).status_code==409
    assert client.post('/api/v2/telemetria',headers=headers,
                       json={**packet, 'calibration_id': None,
                             'brix_apparent': {'value': None, 'quality': 'missing'}}).status_code == 409
    with SessionLocal() as db:
        assert not db.query(m.LecturaTelemetria).filter_by(fermentacion_id=1).count()
    monkeypatch.setattr(demo_access,'settings',replace(demo_access.settings,environment='development'))
    assert client.post(url,json=body).status_code==403


def two_device_recipes(client, late_assignment=False):
    anchor = datetime.now(timezone.utc)
    with SessionLocal() as db:
        process = db.get(m.ProcesoFermentacion, 1)
        start = process.fecha_inicio.replace(tzinfo=timezone.utc)
        device = m.Dispositivo(mac_address="02:00:00:00:FF:01", empresa_id=1,
                               modelo_id=1, tipo_dispositivo="DUAL", estado="activo")
        db.add(device)
        db.flush()
        other = device.id
        db.add(m.AsignacionDispositivo(dispositivo_id=other, cuba_id=process.cuba_id,
                                       activo=True, asignado_en=anchor - timedelta(seconds=2) if late_assignment else start))
        db.commit()
    for ident in (1, other):
        assert client.post(f"/api/dispositivos/{ident}/credenciales", json={
            "source": "simulado", "label": "reloj"}).status_code == 201
    stamp = start.isoformat()
    recipe = dict(method="synthetic_identity", version="primera", valid_from=stamp,
                  simulation=dict(process_id=1, process_start=stamp, seed=42, scenario="healthy"))
    clock = dict(real_anchor=anchor.isoformat(), simulated_anchor=stamp, factor=60)
    return other, recipe, clock


@pytest.mark.parametrize("first_uses_clock", [True, False])
def test_historical_recipe_binds_clock_across_devices_and_migration(client, first_uses_clock):
    from alembic import command
    from app.migrations import migration_config
    other, recipe, clock = two_device_recipes(client)
    first = clock if first_uses_clock else None
    second = None if first_uses_clock else clock
    original = client.post("/api/dispositivos/1/calibraciones", json={**recipe, "simulation_clock": first})
    assert original.status_code == 201
    assert client.delete(f"/api/dispositivos/1/calibraciones/{original.json()['calibration_id']}").status_code == 200
    config = migration_config(settings.database_url, "test")
    command.downgrade(config, "0008_process_profile_overrides")
    command.upgrade(config, "head")
    url = f"/api/dispositivos/{other}/calibraciones"
    assert client.post(url, json={**recipe, "simulation_clock": second}).status_code == 409
    assert client.post(url, json={**recipe, "simulation_clock": first}).status_code == 201


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="PostgreSQL concurrency")
def test_parallel_different_device_clocks_choose_only_one(client):
    other, recipe, clock = two_device_recipes(client)
    barrier = Barrier(2)

    def register(ident):
        with TestClient(app) as caller:
            barrier.wait(timeout=10)
            return caller.post(f"/api/dispositivos/{ident}/calibraciones",
                               headers={"Authorization": client.headers["Authorization"]},
                               json={**recipe, "simulation_clock": clock if ident == 1 else None}).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(register, (1, other))) == [201, 409]


def test_conflicting_legacy_history_keeps_old_revision(client):
    from alembic import command
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import IntegrityError
    from app.migrations import migration_config

    other, recipe, clock = two_device_recipes(client)
    config = migration_config(settings.database_url, "test")
    command.downgrade(config, "0008_process_profile_overrides")
    try:
        for ident, setting in ((1, clock), (other, None)):
            result = client.post(f"/api/dispositivos/{ident}/calibraciones",
                                 json={**recipe, "simulation_clock": setting})
            assert result.status_code == 201
        with pytest.raises(IntegrityError):
            command.upgrade(config, "head")
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0008_process_profile_overrides"
            assert not inspect(conn).has_table("RELOJ_PROCESO")
            assert conn.scalar(text('SELECT count(*) FROM "CALIBRACION_DISPOSITIVO"')) == 2
    finally:
        # Only the isolated test fixture is reset. The migration never repairs data.
        with engine.begin() as conn:
            conn.execute(text('DELETE FROM "CALIBRACION_DISPOSITIVO"'))
        command.upgrade(config, "head")


def test_existing_unclocked_reading_prevents_retiming(client):
    other, recipe, clock = two_device_recipes(client)
    with SessionLocal() as db:
        db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1,
                                  timestamp=db.get(m.ProcesoFermentacion, 1).fecha_inicio, brix=22))
        db.commit()
    url = f"/api/dispositivos/{other}/calibraciones"
    assert client.post(url, json={**recipe, "simulation_clock": clock}).status_code == 409
    assert client.post(url, json=recipe).status_code == 201


def test_clock_registration_checks_real_calibration_and_lifecycle(client):
    other, recipe, clock = two_device_recipes(client, late_assignment=True)
    url = f"/api/dispositivos/{other}/calibraciones"
    start = datetime.fromisoformat(recipe["valid_from"])
    anchor = datetime.fromisoformat(clock["real_anchor"])
    body = {**recipe, "simulation_clock": clock}
    assert client.post(url, json={**body, "valid_until": anchor.isoformat()}).status_code == 422
    early = {**clock, "real_anchor": (start - timedelta(seconds=1)).isoformat()}
    assert client.post(url, json={**body, "simulation_clock": early}).status_code == 409
    # The second instrument was assigned after the biological start but before
    # the first real due time. Its calibration can begin at that due time.
    too_early = {**clock, "real_anchor": (anchor - timedelta(seconds=3)).isoformat()}
    assert client.post(url, json={**body, "simulation_clock": too_early}).status_code == 409
    assert client.post(url, json={**body, "valid_from": anchor.isoformat()}).status_code == 201
    assert client.patch("/api/procesos/1/finalizar").status_code == 200
    assert client.post(url, json={**body, "version": "cerrado"}).status_code == 409
