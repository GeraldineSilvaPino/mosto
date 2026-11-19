from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from app import models as m
from app.database import SessionLocal
from app.services import telemetry_v2
from test_access import tenants, as_user
from test_telemetry_v2 import provision


def test_create_edit_noop_conflict_and_history(client):
    payload = dict(nomb_perfil="Version test", temp_min=18, temp_max=26, cepa_id=1, bodega_id=1)
    created = client.post('/api/perfiles', json=payload)
    assert created.status_code == 201, created.text
    ident = created.json()['id']
    assert created.json()['revision'] == 1
    path = f'/api/perfiles/{ident}'
    assert client.put(path, json={'temp_max': 26, 'expected_revision': 1}).json()['revision'] == 1
    assert client.put(path, json={'temp_max': 28, 'expected_revision': 1}).json()['revision'] == 2
    assert client.put(path, json={'temp_max': 29, 'expected_revision': 1}).status_code == 409
    history = client.get(path + '/versiones').json()
    assert [v['revision'] for v in history] == [1, 2]
    assert [v['configuration']['temp_max'] for v in history] == [26, 28]
    assert all(v['actor_id'] == 1 for v in history)
    assert client.delete(path).status_code == 200
    assert client.delete(path).status_code == 200
    assert len(client.get(path + '/versiones').json()) == 3


def test_old_profile_capture_is_explicit_and_nulls_are_not_defaults(client):
    assert client.get('/api/perfiles/1/versiones').json() == []
    response = client.put('/api/perfiles/1', json={'temp_min': None, 'temp_max': None, 'ph_min': None})
    assert response.status_code == 200, response.text
    assert response.json()['temp_min'] is None and response.json()['crit_min'] is None
    assert response.json()['ph_min'] is None
    history = client.get('/api/perfiles/1/versiones').json()
    assert history[0]['origin'] == 'captura_existente' and history[0]['actor_id'] is None
    assert history[1]['origin'] == 'edicion'
    assert client.get('/api/procesos/1').json()['perfil_snapshot'] is None


def test_new_process_snapshot_survives_edit_before_first_telemetry(client, monkeypatch):
    credential, calibration = provision(client, source='simulado')
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    started = client.post('/api/procesos/iniciar', json={'cuba_id': 1, 'perfil_id': 1, 'volumen_litros': 500})
    assert started.status_code == 201, started.text
    process = started.json()
    assert process['perfil_snapshot']['temp_max'] == 26
    assert client.put('/api/perfiles/1', json={'temp_max': 40, 'nomb_perfil': 'New title'}).status_code == 200
    assert client.get(f"/api/procesos/{process['id']}").json()['perfil_nombre'] == process['perfil_snapshot']['nomb_perfil']
    assert client.get('/api/cubas/1').json()['temp_max_perfil'] == 26
    base = datetime.now(timezone.utc) + timedelta(seconds=1)
    boot = str(uuid4())
    for minute in (0, 5, 10):
        now = base + timedelta(minutes=minute)
        monkeypatch.setattr(telemetry_v2, 'utc_now', lambda now=now: now)
        sent = client.post('/api/v2/telemetria', headers={'X-Mosto-Device-Key': credential['token']}, json={
            'schema_version': 2, 'device_id': 1, 'boot_id': boot, 'sequence': minute,
            'observed_at': now.isoformat(), 'calibration_id': calibration,
            'temperature_c': {'value': 30, 'quality': 'good'}, 'brix_apparent': {'value': 20, 'quality': 'good'}})
        assert sent.status_code == 201, sent.text
    alert = client.get('/api/alertas').json()[0]
    assert alert['evidencia']['configuration']['temp_max'] == 26
    assert alert['evidencia']['configuration']['profile_revision'] == 1


def test_history_access_and_operator_cannot_edit(client, tenants):
    foreign = tenants['foreign']['profile']
    assert client.get(f'/api/perfiles/{foreign}/versiones').status_code == 404
    as_user(client, tenants['member'])
    assert client.get('/api/perfiles/1/versiones').status_code == 200
    assert client.put('/api/perfiles/1', json={'temp_max': 28}).status_code == 403


def test_invalid_edit_rolls_back_without_new_revision(client):
    assert client.put('/api/perfiles/1', json={'temp_min': 35}).status_code == 400
    assert client.get('/api/perfiles/1/versiones').json() == []
    assert client.get('/api/perfiles/1').json()['revision'] == 1


def test_no_silent_reconciliation_after_out_of_band_mutation(client):
    client.put('/api/perfiles/1', json={'temp_max': 28})
    with SessionLocal() as db:
        db.get(m.PerfilFermentacion, 1).temp_max = 35
        db.commit()
    assert client.put('/api/perfiles/1', json={'temp_max': 29}).status_code == 409


def test_scoped_history_cannot_be_rewritten(client):
    from app.services.access import AccessContext, install_scope
    from fastapi import HTTPException
    client.put('/api/perfiles/1', json={'temp_max': 28})
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), True, 'profiles', True))
        row = db.query(m.VersionPerfil).first()
        row.configuracion = {'temp_max': 99}
        with pytest.raises(HTTPException) as error:
            db.flush()
        assert error.value.status_code == 409
        db.rollback()


def test_upgrade_existing_local_profiles_preserves_values_without_inventing_history(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from alembic import command
    from app.migrations import migration_config
    from app.demo_seed import seed_demo
    url = 'sqlite:///' + (tmp_path / 'mosto_test_profiles.db').as_posix()
    config = migration_config(url, 'test')
    command.upgrade(config, 'head')
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            seed_demo(db, 'test-only-version-migration')
        command.downgrade(config, '0004_alert_episodes')
        command.upgrade(config, 'head')
        with Session(engine) as db:
            assert float(db.get(m.PerfilFermentacion, 1).temp_max) == 26
            assert db.get(m.ProcesoFermentacion, 1).perfil_snapshot is None
            assert db.query(m.VersionPerfil).count() == 0
    finally:
        engine.dispose()
