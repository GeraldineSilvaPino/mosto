from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.database import SessionLocal
from app.services.access import AccessContext, install_scope
from test_access import tenants, as_user
from test_migrations import postgres, _parallel


def payload(**changes):
    return dict(request_id=str(uuid4()), fermentacion_id=1, variable='brix_aparente', valor=18.3,
        unidad='°Bx', metodo='refractometro', instrumento='REF-001', evidencia='Muestra manual de contraste',
        observado_en=datetime.now(timezone.utc).isoformat(), **changes)


def create(client, **changes):
    response = client.post('/api/mediciones-manuales', json=payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def test_intervention_selector_scope_pagination_and_persisted_link(client, tenants):
    aid = tenants['own_alert']
    with SessionLocal() as db:
        other = m.EventoAlerta(fermentacion_id=1, dispositivo_id=1, tipo_alerta='temp_alta')
        db.add(other); db.commit(); other_id = other.id
    def proposal(alert=None, process=1):
        response = client.post('/api/intervenciones', json=dict(request_id=str(uuid4()),
            fermentacion_id=process, alerta_id=alert, tipo='contraste_manual',
            accion='Contrastar muestra manual', motivo='Verificar señal de Brix'))
        assert response.status_code == 201, response.text
        return response.json()['id']
    general, matching, incompatible = proposal(), proposal(aid), proposal(other_id)
    proposal(process=tenants['second']['process'])
    url = '/api/mediciones-manuales/intervenciones/1'
    page = client.get(url, params=dict(alerta_id=aid, limit=1)).json()
    assert page['total'] == 2 and page['items'][0]['id'] == matching
    assert client.get(url, params=dict(alerta_id=aid, limit=1, offset=1)).json()['items'][0]['id'] == general
    assert client.get(url).json()['total'] == 3
    assert client.get(url, params=dict(alerta_id=tenants['second']['alert'])).status_code == 409
    assert client.get(url, params=dict(limit=101)).status_code == 422
    row = create(client, alerta_id=aid, intervencion_id=matching)
    assert client.get('/api/mediciones-manuales', params=dict(fermentacion_id=1)).json()['items'][0]['intervencion_id'] == matching
    assert client.post('/api/mediciones-manuales', json=payload(alerta_id=aid, intervencion_id=incompatible)).status_code == 409
    as_user(client, tenants['stranger'])
    assert client.get(url).status_code == 404
    as_user(client, tenants['member'])
    assert client.get(url).json()['total'] == 3


def test_measurement_links_author_dates_and_no_automatic_effect(client, tenants):
    aid = tenants['own_alert']
    alert = client.get(f'/api/alertas/{aid}').json()
    with SessionLocal() as db:
        counts = [db.query(model).count() for model in (m.LecturaTelemetria, m.MensajeTelemetria, m.EstadoRegla)]
    proposal = client.post('/api/intervenciones', json=dict(request_id=str(uuid4()), fermentacion_id=1,
        alerta_id=aid, tipo='contraste_manual', accion='Medir con refractómetro', motivo='Comparar señal actual')).json()
    row = create(client, alerta_id=aid, intervencion_id=proposal['id'])
    assert row['usuario_id'] == 1 and row['origen'] == 'manual' and row['autor']
    assert row['anulacion'] is None and row['observado_en'].endswith(('+00:00', 'Z'))
    assert datetime.fromisoformat(row['registrado_en'].replace('Z', '+00:00')) >= datetime.fromisoformat(row['observado_en'].replace('Z', '+00:00'))
    assert client.get(f'/api/alertas/{aid}').json() == alert
    assert client.get('/api/intervenciones').json()['items'][0]['estado'] == 'propuesta'
    with SessionLocal() as db:
        assert [db.query(model).count() for model in (m.LecturaTelemetria, m.MensajeTelemetria, m.EstadoRegla)] == counts
        note = db.get(m.BitacoraIntervencion, row['bitacora_id'])
        assert note.alerta_id == aid and note.usuario_id == 1 and '18.3' in note.descripcion


@pytest.mark.parametrize('change', [
    {'unidad': 'g/L'}, {'metodo': 'phmetro'}, {'variable': 'azucar_residual'},
    {'valor': 'NaN'}, {'valor': True}, {'valor': 91}, {'instrumento': '  '}, {'evidencia': ' '},
    {'observado_en': '2026-01-01T12:00:00'}, {'usuario_id': 100}, {'source': 'fisico'}])
def test_invalid_contract_never_writes(client, change):
    assert client.post('/api/mediciones-manuales', json={**payload(), **change}).status_code == 422
    with SessionLocal() as db:
        assert db.query(m.MedicionManual).count() == db.query(m.BitacoraIntervencion).count() == 0


def test_idempotent_create_and_annulment_keep_original_and_actor(client, tenants):
    body = payload()
    row = client.post('/api/mediciones-manuales', json=body).json()
    assert client.post('/api/mediciones-manuales', json=body).json() == row
    assert client.post('/api/mediciones-manuales', json={**body, 'valor': 19}).status_code == 409
    cancel = dict(request_id=str(uuid4()), motivo='Error al transcribir el valor')
    url = f"/api/mediciones-manuales/{row['id']}/anular"
    result = client.post(url, json=cancel)
    assert result.status_code == 200 and result.json()['anulacion']['motivo'] == cancel['motivo']
    assert result.json()['valor'] == row['valor']
    assert client.post(url, json=cancel).json() == result.json()
    assert client.post(url, json={**cancel, 'request_id': str(uuid4())}).status_code == 409
    as_user(client, tenants['member'])
    assert client.post('/api/mediciones-manuales', json=body).status_code == 409
    assert client.post(url, json=cancel).status_code == 409
    with SessionLocal() as db:
        assert db.query(m.MedicionManual).count() == db.query(m.AnulacionMedicion).count() == 1
        assert db.query(m.BitacoraIntervencion).filter_by(tipo_intervencion='medicion_manual').count() == 2


def test_temporal_boundaries_and_late_entry_for_closed_process(client):
    with SessionLocal() as db:
        start = db.get(m.ProcesoFermentacion, 1).fecha_inicio.replace(tzinfo=timezone.utc)
    for when in (start - timedelta(seconds=1), datetime.now(timezone.utc) + timedelta(days=1)):
        assert client.post('/api/mediciones-manuales', json={**payload(), 'observado_en': when.isoformat()}).status_code == 409
    observed = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    assert client.post('/api/mediciones-manuales', json={**payload(), 'observado_en': observed.isoformat()}).status_code == 201
    assert client.post('/api/mediciones-manuales', json=payload()).status_code == 409
    assert client.get('/api/mediciones-manuales/contexto/1').json()['fin']


def test_tenant_roles_and_cross_process_links(client, tenants):
    second, foreign = tenants['second'], tenants['foreign']
    assert client.post('/api/mediciones-manuales', json={**payload(), 'fermentacion_id': foreign['process']}).status_code == 404
    assert client.get(f"/api/mediciones-manuales?fermentacion_id={foreign['process']}").status_code == 404
    assert client.post('/api/mediciones-manuales', json=payload(alerta_id=second['alert'])).status_code == 409
    proposal = client.post('/api/intervenciones', json=dict(request_id=str(uuid4()), fermentacion_id=second['process'],
        tipo='contraste_manual', accion='Medir Brix manual', motivo='Comprobar medición')).json()
    assert client.post('/api/mediciones-manuales', json=payload(intervencion_id=proposal['id'])).status_code == 409
    own = create(client)
    other = client.post('/api/mediciones-manuales', json={**payload(), 'fermentacion_id': second['process']}).json()
    as_user(client, tenants['member'])
    assert client.get(f"/api/mediciones-manuales/contexto/{second['process']}").json()['puede_operar'] is False
    assert client.get(f"/api/mediciones-manuales?fermentacion_id={second['process']}").json()['total'] == 1
    assert client.post('/api/mediciones-manuales', json={**payload(), 'fermentacion_id': second['process']}).status_code == 404
    cancel = dict(request_id=str(uuid4()), motivo='Lectura transcrita incorrectamente')
    assert client.post(f"/api/mediciones-manuales/{other['id']}/anular", json=cancel).status_code == 404
    as_user(client, tenants['stranger'])
    assert client.post(f"/api/mediciones-manuales/{own['id']}/anular", json=cancel).status_code == 404
    assert client.get('/api/mediciones-manuales/contexto/1').status_code == 404


def test_pagination_includes_annulled_and_session_immutability(client):
    row = create(client)
    create(client)
    page = client.get('/api/mediciones-manuales?fermentacion_id=1&limit=1&offset=1').json()
    assert page['total'] == 2 and page['items'][0]['id'] == row['id']
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), True, 'operations', True))
        db.get(m.MedicionManual, row['id']).valor = 20
        with pytest.raises(HTTPException) as error:
            db.flush()
        assert error.value.status_code == 409
        db.rollback()
    assert client.delete(f"/api/mediciones-manuales/{row['id']}").status_code == 404


def test_failed_measurement_rolls_back_note(client):
    def reject(*args):
        raise HTTPException(409, 'Simulated storage failure')
    event.listen(m.MedicionManual, 'before_insert', reject)
    try:
        assert client.post('/api/mediciones-manuales', json=payload()).status_code == 409
    finally:
        event.remove(m.MedicionManual, 'before_insert', reject)
    with SessionLocal() as db:
        assert db.query(m.MedicionManual).count() == db.query(m.BitacoraIntervencion).count() == 0


def test_failed_annulment_leaves_measurement_and_note_unchanged(client):
    row = create(client)
    def reject(*args):
        raise HTTPException(409, 'Simulated storage failure')
    event.listen(m.AnulacionMedicion, 'before_insert', reject)
    try:
        result = client.post(f"/api/mediciones-manuales/{row['id']}/anular", json=dict(request_id=str(uuid4()), motivo='Lectura incorrecta'))
        assert result.status_code == 409
    finally:
        event.remove(m.AnulacionMedicion, 'before_insert', reject)
    with SessionLocal() as db:
        assert db.query(m.AnulacionMedicion).count() == 0
        assert db.query(m.BitacoraIntervencion).count() == 1


@postgres
def test_postgres_concurrent_identical_creation_has_one_note(client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.auth_service import create_access_token
    body = payload()
    def action(_):
        with TestClient(app) as http:
            return http.post('/api/mediciones-manuales', json=body,
                headers={'Authorization': 'Bearer ' + create_access_token({'sub': 1})})
    results = _parallel(action)
    assert all(row.status_code == 201 for row in results)
    assert results[0].json()['id'] == results[1].json()['id']
    with SessionLocal() as db:
        assert db.query(m.MedicionManual).count() == db.query(m.BitacoraIntervencion).count() == 1


@postgres
def test_postgres_concurrent_annulments_keep_one_reason(client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.auth_service import create_access_token
    row = create(client)
    def action(index):
        with TestClient(app) as http:
            return http.post(f"/api/mediciones-manuales/{row['id']}/anular",
                json=dict(request_id=str(uuid4()), motivo=f'Corrección motivo {index}'),
                headers={'Authorization': 'Bearer ' + create_access_token({'sub': 1})}).status_code
    assert sorted(_parallel(action)) == [200, 409]
    with SessionLocal() as db:
        assert db.query(m.AnulacionMedicion).count() == 1
        assert db.query(m.BitacoraIntervencion).count() == 2


@postgres
def test_postgres_manual_evidence_is_immutable(client):
    row = create(client)
    client.post(f"/api/mediciones-manuales/{row['id']}/anular", json=dict(request_id=str(uuid4()), motivo='Error en el instrumento'))
    with SessionLocal() as db:
        for table in ('MEDICION_MANUAL', 'ANULACION_MEDICION'):
            for command in (f'DELETE FROM "{table}"', f'UPDATE "{table}" SET usuario_id=usuario_id'):
                with pytest.raises(IntegrityError):
                    db.execute(text(command)); db.commit()
                db.rollback()
