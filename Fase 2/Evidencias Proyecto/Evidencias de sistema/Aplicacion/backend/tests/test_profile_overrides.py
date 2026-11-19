from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.database import SessionLocal
from app.routers import profile_overrides
from app.services.profile_versions import snapshot
from app.services.access import AccessContext, install_scope
from test_episodes import stream, open_episode
from test_access import tenants, as_user
from test_migrations import postgres, _parallel


@pytest.fixture
def frozen():
    with SessionLocal() as db:
        process = db.get(m.ProcesoFermentacion, 1)
        process.perfil_snapshot = snapshot(db.get(m.PerfilFermentacion, 1))
        db.commit()


def body(**updates):
    return {**dict(request_id=str(uuid4()), expected_revision=0, accion='ajustar', temp_min=18, temp_max=35,
        motivo='Revisión técnica del perfil de este proceso'), **updates}


def approve(client, monkeypatch, at, **updates):
    with monkeypatch.context() as patch:
        patch.setattr(profile_overrides, 'utc_now', lambda: at)
        result = client.post('/api/procesos/1/ajustes-perfil', json=body(**updates))
    assert result.status_code == 201, result.text
    return result.json()


def test_open_episode_retains_thresholds_and_needs_observed_recovery(client, stream, frozen, monkeypatch):
    alert = open_episode(client, stream)
    send, start = stream
    before = client.get(f"/api/alertas/{alert['id']}/eventos").json()
    adjustment = approve(client, monkeypatch, start + timedelta(minutes=15))
    assert adjustment['revision'] == 1
    assert client.get(f"/api/alertas/{alert['id']}/eventos").json() == before
    for minute in (20, 25, 30):
        assert send(minute, 30).status_code == 201
    current = client.get(f"/api/alertas/{alert['id']}").json()
    assert current['estado_condicion'] == 'activa' and current['fin_condicion'] is None
    assert current['evidencia']['configuration']['temp_max'] == 26
    for minute in (35, 40, 45):
        assert send(minute, 25).status_code == 201
    recovered = client.get(f"/api/alertas/{alert['id']}").json()
    assert recovered['estado_condicion'] == 'recuperada' and recovered['fecha_resolucion'] is None
    for minute in (50, 55, 60):
        assert send(minute, 30).status_code == 201
    assert len(client.get('/api/alertas').json()) == 1
    for minute in (65, 70, 75):
        assert send(minute, 40).status_code == 201
    new = client.get('/api/alertas').json()[0]
    assert new['evidencia']['configuration']['temp_max'] == 35
    assert new['evidencia']['configuration']['override_revision'] == 1
    with SessionLocal() as db:
        assert db.get(m.ProcesoFermentacion, 1).perfil_snapshot['temp_max'] == 26
        state = db.query(m.EstadoRegla).filter_by(fermentacion_id=1, codigo='temperatura_alta').one()
        assert state.configuracion['temp_max'] == 26 and state.perfil_ajuste_revision == 1


def test_candidate_cannot_accumulate_across_configuration_boundary(client, stream, frozen, monkeypatch):
    send, start = stream
    send(0); send(5)
    approve(client, monkeypatch, start + timedelta(minutes=7), temp_max=28)
    send(10); send(15)
    assert client.get('/api/alertas').json() == []
    send(20)
    alert = client.get('/api/alertas').json()[0]
    assert alert['evidencia']['configuration']['temp_max'] == 28
    assert datetime.fromisoformat(alert['inicio_condicion'].replace('Z', '+00:00')) == start + timedelta(minutes=10)


def test_backlog_uses_observation_time_and_restore_is_another_revision(client, stream, frozen, monkeypatch):
    send, start = stream
    approve(client, monkeypatch, start + timedelta(minutes=15))
    for minute in (0, 5, 10):
        send(minute, 30)
    assert client.get('/api/alertas').json()[0]['evidencia']['configuration']['temp_max'] == 26
    restored = approve(client, monkeypatch, start + timedelta(minutes=16), accion='restaurar',
        temp_min=None, temp_max=None, expected_revision=1)
    assert restored['revision'] == 2 and restored['configuracion']['temp_max'] == 26
    result = client.get('/api/procesos/1/ajustes-perfil').json()
    assert [row['revision'] for row in result['items']] == [2, 1]
    assert len(result['open_episodes']) == 1
    assert client.get('/api/cubas/1').json()['temp_max_perfil'] == 26


def test_idempotent_approval_conflicts_and_current_display(client, frozen):
    payload = body()
    first = client.post('/api/procesos/1/ajustes-perfil', json=payload)
    assert first.status_code == 201, first.text
    assert client.post('/api/procesos/1/ajustes-perfil', json=payload).json() == first.json()
    assert client.post('/api/procesos/1/ajustes-perfil', json={**payload, 'temp_max': 36}).status_code == 409
    assert client.post('/api/procesos/1/ajustes-perfil', json=body(temp_max=36)).status_code == 409
    assert client.post('/api/procesos/1/ajustes-perfil', json=body(expected_revision=1)).status_code == 409
    assert client.get('/api/cubas/1').json()['temp_max_perfil'] == 35
    assert client.get('/api/procesos/1/cinetica').json()['current_monitoring']['current_profile_override_revision'] == 1
    with SessionLocal() as db:
        assert db.query(m.AjustePerfilProceso).count() == db.query(m.BitacoraIntervencion).count() == 1


@pytest.mark.parametrize('updates', [{'temp_min': 40}, {'temp_max': None}, {'temp_max': 'NaN'},
    {'temp_max': True}, {'motivo': '  '}, {'vigente_desde': '2026-01-01T00:00:00Z'},
    {'usuario_id': 2}, {'accion': 'restaurar'}, {'expected_revision': -1}])
def test_invalid_contract(client, frozen, updates):
    assert client.post('/api/procesos/1/ajustes-perfil', json=body(**updates)).status_code == 422


def test_unknown_initial_profile_closed_process_and_future_observation_reject(client, stream, monkeypatch):
    assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 409
    with SessionLocal() as db:
        db.get(m.ProcesoFermentacion, 1).perfil_snapshot = snapshot(db.get(m.PerfilFermentacion, 1)); db.commit()
    send, start = stream
    send(10)
    with monkeypatch.context() as patch:
        patch.setattr(profile_overrides, 'utc_now', lambda: start + timedelta(minutes=5))
        assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 409
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 409


def test_roles_scope_and_immutable_history(client, tenants, frozen):
    assert client.post(f"/api/procesos/{tenants['foreign']['process']}/ajustes-perfil", json=body()).status_code == 404
    row = client.post('/api/procesos/1/ajustes-perfil', json=body()).json()
    as_user(client, tenants['member'])
    assert client.get('/api/procesos/1/ajustes-perfil').json()['can_approve'] is False
    assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 403
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), True, 'profile_overrides', True))
        db.get(m.AjustePerfilProceso, row['id']).motivo = 'Alterado'
        with pytest.raises(HTTPException) as error:
            db.flush()
        assert error.value.status_code == 409
        db.rollback()


def test_approval_failure_rolls_back_note(client, frozen):
    def reject(*args): raise HTTPException(409, 'Storage failure')
    event.listen(m.AjustePerfilProceso, 'before_insert', reject)
    try:
        assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 409
    finally:
        event.remove(m.AjustePerfilProceso, 'before_insert', reject)
    with SessionLocal() as db:
        assert db.query(m.BitacoraIntervencion).count() == db.query(m.AjustePerfilProceso).count() == 0


@postgres
def test_postgres_override_history_immutable(client, frozen):
    assert client.post('/api/procesos/1/ajustes-perfil', json=body()).status_code == 201
    with SessionLocal() as db:
        for sql in ('UPDATE "AJUSTE_PERFIL_PROCESO" SET motivo=motivo', 'DELETE FROM "AJUSTE_PERFIL_PROCESO"'):
            with pytest.raises(IntegrityError): db.execute(text(sql)); db.commit()
            db.rollback()


@postgres
def test_postgres_concurrent_approvals_use_revision(client, frozen):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.auth_service import create_access_token
    def action(index):
        with TestClient(app) as http:
            return http.post('/api/procesos/1/ajustes-perfil', json=body(temp_max=35 + index),
                headers={'Authorization': 'Bearer ' + create_access_token({'sub': 1})}).status_code
    assert sorted(_parallel(action)) == [201, 409]
    with SessionLocal() as db:
        assert db.query(m.AjustePerfilProceso).count() == db.query(m.BitacoraIntervencion).count() == 1
