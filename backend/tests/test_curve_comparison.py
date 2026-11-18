from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import models as m
from app.database import SessionLocal
from app.services import telemetry_v2
from app.routers import manual_measurements
from test_telemetry_v2 import packet, send, provision
from test_manual_measurements import payload
from test_access import tenants, as_user


def query(client, **params):
    result = client.get('/api/procesos/1/comparacion', params=params)
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'no-store'
    return result.json()


def emit(client, packet, monkeypatch, observed, sequence=1, received=None, **changes):
    body = deepcopy(packet[0])
    body.update(observed_at=observed.isoformat(), sequence=sequence, **changes)
    with monkeypatch.context() as patch:
        patch.setattr(telemetry_v2, 'utc_now', lambda: received or observed)
        response = send(client, packet, body)
    assert response.status_code == 201, response.text
    return response.json()


def manual(client, monkeypatch, observed, registered, **changes):
    class Clock:
        @staticmethod
        def now(*_): return registered
    with monkeypatch.context() as patch:
        patch.setattr(manual_measurements, 'datetime', Clock)
        result = client.post('/api/mediciones-manuales', json={**payload(), 'observado_en': observed.isoformat(), **changes})
    assert result.status_code == 201, result.text
    return result.json()


def test_snapshot_ignores_future_observations_and_late_receipts(client, packet, monkeypatch):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    emit(client, packet, monkeypatch, cutoff - timedelta(minutes=5))
    before = query(client, as_of=cutoff.isoformat())
    emit(client, packet, monkeypatch, cutoff - timedelta(minutes=1), 2, received=cutoff + timedelta(minutes=1))
    emit(client, packet, monkeypatch, cutoff + timedelta(minutes=2), 3)
    manual(client, monkeypatch, cutoff - timedelta(minutes=4), cutoff + timedelta(minutes=3))
    assert query(client, as_of=cutoff.isoformat()) == before
    assert before['riesgo_pct'] is None and before['recommendations'] == []


def test_manual_registration_and_annulment_are_as_of_not_current(client, monkeypatch):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    row = manual(client, monkeypatch, cutoff - timedelta(minutes=5), cutoff - timedelta(minutes=1))
    before = query(client, as_of=cutoff.isoformat())
    assert before['processes'][0]['manual'][0]['annulment'] is None
    result = client.post(f"/api/mediciones-manuales/{row['id']}/anular", json=dict(request_id=str(uuid4()), motivo='Error de transcripción'))
    assert result.status_code == 200
    assert query(client, as_of=cutoff.isoformat()) == before
    now = query(client)['processes'][0]
    assert now['manual'][0]['annulment']['reason'] == 'Error de transcripción'
    assert 'mediciones_anuladas' in now['warnings']


def test_quality_barrier_and_long_gap_break_lines_without_carry_forward(client, packet, monkeypatch):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    for index, minutes in enumerate([0, 5, 10, 15, 40], 1):
        change = {'brix_apparent': {'value': None, 'quality': 'missing'}} if minutes == 10 else {}
        emit(client, packet, monkeypatch, base + timedelta(minutes=minutes), index, **change)
    brix = query(client)['processes'][0]
    assert [len(s['points']) for s in brix['segments']] == [2, 1, 1]
    assert brix['telemetry']['excluded'] == 1
    temp = query(client, variable='temperatura')['processes'][0]
    assert [len(s['points']) for s in temp['segments']] == [4, 1]


def test_duplicate_timestamps_are_ambiguous_not_averaged(client, packet, monkeypatch):
    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    emit(client, packet, monkeypatch, base, 1)
    # Canonical ingestion forbids duplicates for one device; two devices may
    # observe the same process at the same instant and must not be averaged.
    with SessionLocal() as db:
        device = m.Dispositivo(mac_address='comparison-second-device', empresa_id=1, modelo_id=1, tipo_dispositivo='DUAL', origen='fisico', estado='activo')
        db.add(device); db.flush()
        ident = device.id
        db.add(m.AsignacionDispositivo(dispositivo_id=ident, cuba_id=1, activo=True, asignado_en=base - timedelta(minutes=1)))
        db.commit()
    credential, calibration = provision(client, ident)
    other = {**packet[0], 'device_id': ident, 'calibration_id': calibration}
    emit(client, (other, credential), monkeypatch, base, 2)
    result = query(client)['processes'][0]
    assert result['segments'] == [] and result['telemetry']['excluded'] == 2


def test_calibration_changes_remain_separate(client, packet, monkeypatch):
    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    emit(client, packet, monkeypatch, base, 1)
    result = client.post('/api/dispositivos/1/calibraciones', json=dict(version='other-version', method='tilt_polynomial',
        valid_from=(base - timedelta(days=1)).isoformat(), coefficients=[-10, .5], tilt_min=20, tilt_max=80))
    assert result.status_code == 201, result.text
    emit(client, packet, monkeypatch, base + timedelta(minutes=5), 2, calibration_id=result.json()['calibration_id'])
    segments = query(client)['processes'][0]['segments']
    assert len(segments) == 2 and segments[0]['calibration_id'] != segments[1]['calibration_id']


def test_limits_explicit_and_no_guessed_boundary_value(client, packet, monkeypatch):
    from app.services import curve_comparison
    monkeypatch.setattr(curve_comparison, 'TELEMETRY_LIMIT', 2)
    monkeypatch.setattr(curve_comparison, 'MANUAL_LIMIT', 1)
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    for index in range(3):
        emit(client, packet, monkeypatch, base + timedelta(minutes=index), index + 1)
        manual(client, monkeypatch, base + timedelta(minutes=index), base + timedelta(minutes=index + 1))
    result = query(client)['processes'][0]
    assert result['telemetry'] == dict(total=3, returned=2, excluded=1, truncated=True)
    assert result['manual_counts'] == dict(total=3, returned=1, truncated=True)
    assert 'limite_de_registros' in result['warnings']


@pytest.mark.empty_db
def test_two_processes_align_by_age_not_calendar_and_respect_availability(client, monkeypatch):
    from app.demo_seed import seed_demo
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with SessionLocal() as db:
        seed_demo(db, 'test-only-password-2026', process_starts={1: now - timedelta(hours=10), 2: now - timedelta(hours=20)})
    for device, observed in ((1, now - timedelta(hours=1)), (2, now - timedelta(hours=11))):
        credential, calibration = provision(client, device)
        body = dict(schema_version=2, device_id=device, boot_id=str(uuid4()), sequence=1, observed_at=observed.isoformat(),
            calibration_id=calibration, tilt_degrees=60, temperature_c=dict(value=22, quality='good'), brix_apparent=dict(value=20, quality='good'))
        emit(client, (body, credential), monkeypatch, observed)
    data = query(client, reference_id=2, as_of=now.isoformat())
    points = [p['segments'][0]['points'][0] for p in data['processes']]
    assert points[0]['hour'] == points[1]['hour'] == 9
    assert points[0]['observed_at'] != points[1]['observed_at']
    assert data['age_start'] == 0 and data['age_end'] == 10


def test_empty_and_manual_only_variables_do_not_invent_telemetry(client, monkeypatch):
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    manual(client, monkeypatch, now, now, variable='ph', valor=3.4, unidad='pH', metodo='phmetro')
    data = query(client, variable='ph')['processes'][0]
    assert data['segments'] == [] and data['telemetry']['total'] == 0
    assert data['manual'][0]['method'] == 'phmetro'
    assert 'sin_canal_automatico' in data['warnings']
    assert query(client)['processes'][0]['segments'] == []


def test_closed_process_window_stops_at_closure_not_wall_clock(client):
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    data = query(client)
    with SessionLocal() as db:
        process = db.get(m.ProcesoFermentacion, 1)
        expected = (telemetry_v2.aware(process.fecha_real_fin) - telemetry_v2.aware(process.fecha_inicio)).total_seconds() / 3600
    assert data['age_end'] == pytest.approx(expected)
    assert data['processes'][0]['current_state'] == 'finalizada'


def test_scope_readonly_roles_and_no_mutations(client, tenants):
    with SessionLocal() as db:
        counts = [db.query(model).count() for model in (m.EstadoRegla, m.EventoAlerta, m.BitacoraIntervencion)]
    foreign = tenants['foreign']['process']
    assert client.get('/api/procesos/1/comparacion', params={'reference_id': foreign}).status_code == 404
    assert client.get(f'/api/procesos/{foreign}/comparacion').status_code == 404
    as_user(client, tenants['member'])
    assert len(query(client, reference_id=tenants['second']['process'])['processes']) == 2
    assert len(query(client, reference_id=1)['processes']) == 1
    with SessionLocal() as db:
        assert [db.query(model).count() for model in (m.EstadoRegla, m.EventoAlerta, m.BitacoraIntervencion)] == counts


@pytest.mark.parametrize('parameters', [{'hours': 0}, {'hours': 169}, {'variable': 'azucar'},
    {'as_of': '2026-01-01T12:00:00'}, {'as_of': '2000-01-01T12:00:00Z'}, {'as_of': '2099-01-01T12:00:00Z'}])
def test_invalid_cutoffs_and_bounds(client, parameters):
    assert client.get('/api/procesos/1/comparacion', params=parameters).status_code == 422
