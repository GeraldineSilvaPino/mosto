from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm.exc import StaleDataError

from app import models as m
from app.database import SessionLocal
from app.services.access import AccessContext, install_scope
from test_access import tenants, as_user
from test_migrations import postgres, _parallel


def proposal(**changes):
    return dict(request_id=str(uuid4()), fermentacion_id=1, tipo="contraste_manual",
                accion="Contrastar Brix con lectura manual", motivo="Verificar evolución de la señal", **changes)


def create(client, **changes):
    response = client.post('/api/intervenciones', json=proposal(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def advance(client, row, state, **changes):
    payload = dict(request_id=str(uuid4()), expected_revision=row['revision'],
                   estado=state, descripcion="Registro del seguimiento manual")
    payload.update(changes)
    return client.post(f"/api/intervenciones/{row['id']}/eventos", json=payload)


def test_workflow_does_not_resolve_or_recover_alert(client, tenants):
    alert_id = tenants['own_alert']
    before = client.get(f'/api/alertas/{alert_id}').json()
    row = create(client, alerta_id=alert_id)
    assert row['estado'] == 'propuesta' and row['responsable_id'] == row['usuario_id'] == 1
    assert row['registrado_en'].endswith(('+00:00', 'Z'))
    for revision, state in enumerate(('ejecutada', 'en_seguimiento', 'en_seguimiento', 'cerrada'), 1):
        row['revision'] = revision
        result = advance(client, row, state, **({} if state == 'ejecutada' else {'respuesta': 'mejora_declarada'}))
        assert result.status_code == 201, result.text
        assert result.json()['revision'] == revision + 1
    history = client.get(f"/api/intervenciones/{row['id']}/eventos").json()
    assert history['total'] == 5
    assert [e['revision'] for e in history['items']] == [5, 4, 3, 2, 1]
    notes = client.get(f'/api/bitacora?alerta_id={alert_id}').json()
    assert len(notes) == 5
    assert {n['id'] for n in notes} == {e['bitacora_id'] for e in history['items']}
    after = client.get(f'/api/alertas/{alert_id}').json()
    assert after == before


def test_idempotent_retry_checks_payload_actor_and_revision(client, tenants):
    payload = proposal()
    first = client.post('/api/intervenciones', json=payload).json()
    assert client.post('/api/intervenciones', json=payload).json() == first
    assert client.post('/api/intervenciones', json={**payload, 'motivo': 'Otro motivo distinto'}).status_code == 409
    event = dict(request_id=str(uuid4()), expected_revision=1, estado='ejecutada', descripcion='Realizada comprobación manual')
    url = f"/api/intervenciones/{first['id']}/eventos"
    result = client.post(url, json=event)
    assert result.status_code == 201, result.text
    assert client.post(url, json=event).json() == result.json()
    assert client.post(url, json={**event, 'descripcion': 'Cambio de descripción'}).status_code == 409
    assert client.post(url, json={**event, 'request_id': str(uuid4())}).status_code == 409
    as_user(client, tenants['member'])
    assert client.post(url, json=event).status_code == 409
    assert client.get(url).json()['total'] == 2


@pytest.mark.parametrize('state,response,status', [
    ('cerrada', 'no_evaluable', 409), ('en_seguimiento', 'sin_cambio', 409),
    ('cerrada', None, 422), ('ejecutada', 'mejora_declarada', 422)])
def test_invalid_transitions_are_atomic(client, state, response, status):
    row = create(client)
    result = advance(client, row, state, respuesta=response)
    assert result.status_code == status, result.text
    assert client.get('/api/intervenciones').json()['items'][0]['revision'] == 1
    assert client.get(f"/api/intervenciones/{row['id']}/eventos").json()['total'] == 1
    with SessionLocal() as db:
        assert db.query(m.BitacoraIntervencion).count() == 1


def test_cancel_terminal_and_closed_process_followup(client):
    cancelled = create(client)
    assert advance(client, cancelled, 'cancelada').status_code == 201
    cancelled['revision'] = 2
    assert advance(client, cancelled, 'ejecutada').status_code == 409
    executed, pending = create(client), create(client)
    assert advance(client, executed, 'ejecutada').status_code == 201
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    assert client.post('/api/intervenciones', json=proposal()).status_code == 409
    assert advance(client, pending, 'ejecutada').status_code == 409
    assert advance(client, pending, 'cancelada').status_code == 201
    executed['revision'] = 2
    assert advance(client, executed, 'cerrada', respuesta='no_evaluable').status_code == 201


def test_tenant_roles_responsible_and_alert_consistency(client, tenants):
    foreign, second = tenants['foreign'], tenants['second']
    assert client.post('/api/intervenciones', json={**proposal(), 'fermentacion_id': foreign['process']}).status_code == 404
    assert client.post('/api/intervenciones', json=proposal(alerta_id=second['alert'])).status_code == 409
    assert client.post('/api/intervenciones', json=proposal(responsable_id=tenants['stranger'])).status_code == 404
    assert client.post('/api/intervenciones', json={**proposal(responsable_id=tenants['member']), 'fermentacion_id': second['process']}).status_code == 409
    row = create(client, responsable_id=tenants['member'])
    second_row = client.post('/api/intervenciones', json={**proposal(), 'fermentacion_id': second['process']}).json()
    as_user(client, tenants['member'])
    context = client.get('/api/intervenciones/contexto/1').json()
    assert context['puede_operar'] and context['proceso_activo']
    assert {user['id'] for user in context['responsables']} == {1, tenants['member']}
    assert client.get(f"/api/intervenciones/contexto/{second['process']}").json()['puede_operar'] is False
    assert client.get(f"/api/intervenciones/contexto/{foreign['process']}").status_code == 404
    assert client.get(f"/api/intervenciones?fermentacion_id={second['process']}").status_code == 200
    assert advance(client, second_row, 'ejecutada').status_code == 404
    assert advance(client, row, 'ejecutada').status_code == 201
    as_user(client, tenants['stranger'])
    assert client.get('/api/intervenciones').json()['items'] == []
    assert client.get(f"/api/intervenciones/{row['id']}/eventos").status_code == 404
    assert advance(client, row, 'ejecutada').status_code == 404


def test_inactive_responsible_whitespace_and_unknown_fields(client):
    with SessionLocal() as db:
        user = m.Usuario(nomb_compl='Inactive', correo_elec='inactive@example.invalid', empresa_id=1, activo=False)
        db.add(user); db.flush()
        uid = user.id
        role = db.query(m.Rol).filter_by(codigo='operador').one()
        db.add(m.UsuarioBodega(usuario_id=uid, bodega_id=1, rol_id=role.id)); db.commit()
    assert client.post('/api/intervenciones', json=proposal(responsable_id=uid)).status_code == 409
    assert client.post('/api/intervenciones', json={**proposal(), 'accion': '     '}).status_code == 422
    assert client.post('/api/intervenciones', json=proposal(author='Inventado')).status_code == 422


def test_pagination_and_immutable_audit(client):
    row = create(client)
    create(client)
    page = client.get('/api/intervenciones?limit=1&offset=1').json()
    assert page['total'] == 2 and page['items'][0]['id'] == row['id']
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), True, 'operations', True))
        event = db.query(m.EventoIntervencion).first()
        event.descripcion = 'Reescrito'
        with pytest.raises(HTTPException) as error:
            db.flush()
        assert error.value.status_code == 409
        db.rollback()


def test_failed_event_rolls_back_workflow_and_note(client, monkeypatch):
    from sqlalchemy import event
    row = create(client)
    def reject(*args):
        raise HTTPException(409, 'Simulated audit failure')
    event.listen(m.EventoIntervencion, 'before_insert', reject)
    try:
        assert advance(client, row, 'ejecutada').status_code == 409
    finally:
        event.remove(m.EventoIntervencion, 'before_insert', reject)
    assert client.get('/api/intervenciones').json()['items'][0]['estado'] == 'propuesta'
    assert client.get(f"/api/intervenciones/{row['id']}/eventos").json()['total'] == 1
    with SessionLocal() as db:
        assert db.query(m.BitacoraIntervencion).count() == 1


def test_optimistic_version_prevents_lost_update(client):
    row = create(client)
    with SessionLocal() as first, SessionLocal() as second:
        a = first.get(m.IntervencionOperativa, row['id'])
        b = second.get(m.IntervencionOperativa, row['id'])
        a.estado = 'ejecutada'; first.commit()
        b.estado = 'cancelada'
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()


@postgres
def test_postgres_event_audit_cannot_be_changed_or_deleted(client):
    from sqlalchemy.exc import IntegrityError
    create(client)
    with SessionLocal() as db:
        row = db.query(m.EventoIntervencion).one()
        row.descripcion = 'Reescritura directa'
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.delete(db.query(m.EventoIntervencion).one())
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@postgres
def test_concurrent_retries_create_one_intervention(client):
    from fastapi.testclient import TestClient
    from app.main import app
    payload = proposal()
    def send(_):
        with TestClient(app) as instance:
            return instance.post('/api/intervenciones', headers=dict(client.headers), json=payload)
    results = _parallel(send)
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json()['id'] == results[1].json()['id']
    with SessionLocal() as db:
        assert db.query(m.EventoIntervencion).count() == db.query(m.BitacoraIntervencion).count() == 1


@postgres
def test_concurrent_execution_and_cancellation_have_one_winner(client):
    from fastapi.testclient import TestClient
    from app.main import app
    row = create(client)
    def send(index):
        with TestClient(app) as instance:
            instance.headers.update(dict(client.headers))
            return advance(instance, row, ('ejecutada', 'cancelada')[index]).status_code
    assert sorted(_parallel(send)) == [201, 409]
    with SessionLocal() as db:
        assert db.get(m.IntervencionOperativa, row['id']).revision == 2
        assert db.query(m.EventoIntervencion).count() == db.query(m.BitacoraIntervencion).count() == 2
