from datetime import datetime, timedelta, timezone
import json
import socket
import sqlite3
from threading import Thread
import time
from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic import ValidationError

from app import models as m
from app.database import SessionLocal
from app.demo_seed import seed_demo
from app.main import app
from app.simulation.faults import FaultPlan, emission
from app.simulation.model import SimulationSpec, Trajectory
from app.simulation.provision_demo import demo_process_starts, provision_fleet
from app.simulation.worker import Worker, LocalHTTP, run_id, canonical_json
from app.telemetry_contract import CalibrationCreate
from app.services import telemetry_v2
from test_simulation import APISender, one_device, spec

pytestmark = pytest.mark.empty_db


def fault(kind, start=1, end=4, **parameters):
    return dict(kind=kind, start_sequence=start, end_sequence=end, **parameters)


def prepare(events, hot_profile=False, clock_factor=1):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    plan = FaultPlan(events=events)
    with SessionLocal() as db:
        seed_demo(db, 'test-only-password-2026', process_starts=demo_process_starts(now))
        if hot_profile:
            profile = db.get(m.PerfilFermentacion, 1)
            profile.temp_min, profile.temp_max = 5, 10
            db.flush()
        config, keys = provision_fleet(db, now=now, fault_plans={1: plan}, clock_factor=clock_factor)
        db.commit()
    return config, keys


@pytest.mark.parametrize('events', [
    [fault('brix_missing', 4, 4)], [fault('brix_frozen_unflagged', 0, 3)],
    [fault('brix_missing'), fault('brix_drift_unflagged', 2, 5, drift_brix_per_hour=.1)],
    [fault('communication_outage'), fault('message_loss', 2, 6)],
    [fault('delivery_delay')], [fault('brix_drift_unflagged')],
    [fault('brix_missing', delay_seconds=10)]])
def test_fault_plan_rejects_ambiguous_invalid_recipes(events):
    with pytest.raises(ValidationError):
        FaultPlan(events=events)


def test_sensor_faults_are_deterministic_independent_and_do_not_change_biology():
    model = Trajectory(spec())
    baseline = model.sample(4)
    plan = FaultPlan(events=[fault('brix_frozen_unflagged', 2, 6), fault('temperature_missing', 3, 5)])
    temp, brix, available, lost, truth = emission(model, 4, plan)
    assert temp == {'quality': 'missing', 'value': None}
    assert brix == {'quality': 'good', 'value': model.sample(1)['brix_apparent']}
    assert truth['latent_brix'] == baseline['latent_brix'] and not lost
    assert emission(Trajectory(spec()), 4, plan) == emission(model, 4, plan)
    assert emission(model, 6, plan)[1]['value'] == model.sample(6)['brix_apparent']
    drift = FaultPlan(events=[fault('brix_drift_unflagged', 1, 20, drift_brix_per_hour=.12)])
    assert emission(model, 13, drift)[1]['value'] == pytest.approx(model.sample(13)['brix_apparent'] + .12)


def test_physical_calibrations_and_horizon_reject_fault_plan():
    plan = FaultPlan(events=[fault('brix_missing')])
    with pytest.raises(ValidationError):
        CalibrationCreate(version='physical', method='tilt_polynomial', valid_from=spec().process_start,
                          coefficients=[0, 1], tilt_min=0, tilt_max=90, emitter_faults=plan)
    with pytest.raises(ValueError, match='horizon'):
        FaultPlan(events=[fault('brix_missing', 1, 300)]).validate_horizon(spec(duration_hours=24))


def test_missing_channels_have_valid_receipts_and_fault_metadata(client, tmp_path):
    config, keys = one_device(prepare([fault('brix_missing', 1, 3), fault('temperature_missing', 2, 4)]))
    sender = APISender(client)
    worker = Worker(config, tmp_path / 'channels.db', sender, keys)
    try:
        assert worker.tick(max_per_device=5) == 5
        assert worker.statuses()[0]['status'] == 'running'
        assert worker.statuses()[0]['pending'] == 0
    finally:
        worker.close()
    assert sender.sent[1]['brix_apparent']['value'] is None
    with SessionLocal() as db:
        rows = db.query(m.MensajeTelemetria).order_by(m.MensajeTelemetria.secuencia).all()
        assert len(rows) == 5
        assert rows[1].calidad_brix == 'missing' and rows[1].brix is None
        assert rows[1].calidad_temperatura == 'good'
        assert rows[2].calidad_temperatura == rows[2].calidad_brix == 'missing'
        assert rows[4].calidad_brix == rows[4].calidad_temperatura == 'good'
    assert client.get('/api/simulaciones/procesos/1').json()['emitter_faults']['version'] == 'emitter-faults-v1'
    assert client.get('/api/cubas/1/ml-prediction').json()['riesgo_pct'] is None


def test_outage_queues_without_post_restart_preserves_exact_envelopes(client, tmp_path, monkeypatch):
    config, keys = one_device(prepare([fault('communication_outage', 1, 5)]))
    start = config.devices[0].simulation.process_start
    clock = {'now': start}
    monkeypatch.setattr(telemetry_v2, 'utc_now', lambda: clock['now'])
    sender, path = APISender(client), tmp_path / 'outage.db'
    worker = Worker(config, path, sender, keys)
    assert worker.tick(start, max_per_device=10) == 1
    clock['now'] = start + timedelta(minutes=20)
    assert worker.tick(clock['now'], max_per_device=10) == 0
    assert len(sender.sent) == 1
    assert worker.statuses()[0]['pending'] == 4 and worker.statuses()[0]['generated_sequence'] == 5
    before = [tuple(r) for r in worker.db.execute('SELECT sequence,payload FROM outbox WHERE receipt_id IS NULL ORDER BY sequence')]
    worker.close()
    resumed = Worker(config, path, sender, keys)
    try:
        clock['now'] = start + timedelta(minutes=25)
        assert resumed.tick(clock['now'], max_per_device=10) == 5
        after = [tuple(r) for r in resumed.db.execute('SELECT sequence,payload FROM outbox WHERE sequence BETWEEN 1 AND 4 ORDER BY sequence')]
        assert after == before and resumed.statuses()[0]['pending'] == 0
    finally:
        resumed.close()
    with SessionLocal() as db:
        rows = db.query(m.MensajeTelemetria).order_by(m.MensajeTelemetria.secuencia).all()
        assert len(rows) == 6
        assert telemetry_v2.aware(rows[1].recibido_en) == clock['now']
        assert telemetry_v2.aware(rows[1].observado_en) == start + timedelta(minutes=5)
        assert rows[1].retrasado
    assert [r['sequence'] for r in sender.sent] == list(range(6))


def test_delay_is_fifo_and_loss_has_no_receipt(client, tmp_path, monkeypatch):
    config, keys = one_device(prepare([fault('delivery_delay', 1, 3, delay_seconds=1200), fault('message_loss', 3, 5)]))
    start = config.devices[0].simulation.process_start
    clock = {'now': start + timedelta(minutes=20)}
    monkeypatch.setattr(telemetry_v2, 'utc_now', lambda: clock['now'])
    sender = APISender(client)
    worker = Worker(config, tmp_path / 'delay.db', sender, keys)
    try:
        assert worker.tick(clock['now'], max_per_device=10) == 1
        assert worker.statuses()[0]['pending'] == 2 and worker.statuses()[0]['lost'] == 2
        clock['now'] = start + timedelta(minutes=30)
        assert worker.tick(clock['now'], max_per_device=10) == 4  # seq 1,2,5,6
        lost = worker.db.execute("SELECT receipt_id FROM outbox WHERE disposition='lost'").fetchall()
        assert len(lost) == 2 and all(r[0] is None for r in lost)
        assert worker.statuses()[0]['next_sequence'] == 7
    finally:
        worker.close()
    assert [r['sequence'] for r in sender.sent] == [0, 1, 2, 5, 6]


def test_changed_faults_rejected_by_state_and_preflight(client, tmp_path):
    config, keys = one_device(prepare([fault('brix_missing')]))
    path = tmp_path / 'immutable.db'
    worker = Worker(config, path, APISender(client), keys)
    worker.close()
    changed = config.devices[0].model_copy(update={'emitter_faults': FaultPlan(events=[fault('temperature_missing')])})
    altered = config.model_copy(update={'devices': [changed]})
    with pytest.raises(ValueError, match='recipe changed'):
        Worker(altered, path, APISender(client), keys)
    worker = Worker(altered, tmp_path / 'other.db', APISender(client), keys)
    try:
        assert worker.tick() == 0
        assert worker.statuses()[0]['last_error'] == 'preflight_recipe_mismatch'
        assert worker.statuses()[0]['generated_sequence'] == 0
    finally:
        worker.close()


def test_planned_outage_does_not_stop_other_devices(client, tmp_path):
    config, keys = prepare([fault('communication_outage', 96, 108)])
    sender = APISender(client)
    worker = Worker(config, tmp_path / 'fleet-fault.db', sender, keys)
    now = config.devices[0].simulation.process_start + timedelta(hours=8)
    try:
        assert worker.tick(now, max_per_device=2) == 8
        states = {row['device_id']: row for row in worker.statuses()}
        assert states[1]['pending'] == 2 and states[1]['next_sequence'] == 0
        assert all(states[index]['next_sequence'] == 2 for index in range(2, 6))
        assert {body['device_id'] for body in sender.sent} == {2, 3, 4, 5}
    finally:
        worker.close()


@pytest.mark.parametrize('alteration', ['timestamp', 'quality', 'message_id'])
def test_misleading_success_never_acknowledges_pending_channel(client, tmp_path, alteration):
    config, keys = one_device(prepare([fault('brix_missing', 0, 4)]))

    class CorruptReceipt(APISender):
        def __call__(self, body, token):
            code, receipt = super().__call__(body, token)
            if alteration == 'timestamp':
                receipt['observed_at'] = datetime.now(timezone.utc).isoformat()
            elif alteration == 'quality':
                receipt['brix_apparent'] = {'value': 20, 'quality': 'good'}
            else:
                receipt['message_id'] = True
            return code, receipt

    worker = Worker(config, tmp_path / 'invalid-ack.db', CorruptReceipt(client), keys)
    try:
        assert worker.tick(max_per_device=1) == 0
        status = worker.statuses()[0]
        assert status['last_error'] == 'invalid_receipt' and status['next_sequence'] == 0
        assert status['pending'] == 1
        assert worker.db.execute('SELECT receipt_id FROM outbox').fetchone()[0] is None
    finally:
        worker.close()


@pytest.mark.parametrize('kind, expected_code', [('delivery_delay', 2), ('message_loss', 0)])
def test_drain_cli_reports_pending_and_drains_deliberate_losses(client, tmp_path, monkeypatch, capsys, kind, expected_code):
    from scripts import simulate_v2
    parameters = {'delay_seconds': 86400} if kind == 'delivery_delay' else {}
    config, keys = one_device(prepare([fault(kind, 0, 110, **parameters)]))
    manifest, state = tmp_path / 'fleet.json', tmp_path / 'drain.db'
    manifest.write_text(config.model_dump_json(), encoding='utf-8')
    sender = APISender(client)
    monkeypatch.setattr(simulate_v2, 'Worker', lambda fleet, path, **kwargs: Worker(fleet, path, sender, keys, **kwargs))
    monkeypatch.setattr(simulate_v2.signal, 'signal', lambda *_: None)
    monkeypatch.setattr('sys.argv', ['simulate_v2', '--manifest', str(manifest), '--state', str(state), '--drain', '--batch', '100'])
    assert simulate_v2.main() == expected_code
    last = json.loads(capsys.readouterr().out.splitlines()[-1])['devices'][0]
    assert last['generated_sequence'] >= 97
    assert last['pending'] > 0 if expected_code == 2 else last['pending'] == 0 and last['lost'] >= 97
    assert not sender.sent


def test_transient_failure_keeps_sampling_and_response_loss_retries_exact_missing_channel(client, tmp_path):
    config, keys = one_device(prepare([fault('brix_missing', 0, 8)]))
    sender = APISender(client)
    sender.drop_next_response = True
    path = tmp_path / 'retry.db'
    worker = Worker(config, path, sender, keys)
    now = datetime.now(timezone.utc)
    assert worker.tick(now, max_per_device=2) == 0
    assert worker.statuses()[0]['pending'] == 2
    assert worker.tick(now + timedelta(seconds=1), max_per_device=2) == 0
    assert worker.statuses()[0]['pending'] == 4  # Backoff does not stop sampling.
    worker.close()
    resumed = Worker(config, path, sender, keys)
    try:
        assert resumed.tick(now + timedelta(seconds=3), max_per_device=4) == 4
        assert sender.sent[0] == sender.sent[1]
    finally:
        resumed.close()
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 4


def test_legacy_emitter_state_upgrade_retains_identity_pending_payload(client, tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with SessionLocal() as db:
        seed_demo(db, 'test-only-password-2026', process_starts=demo_process_starts(now))
        original = provision_fleet(db, now=now); db.commit()
    config, keys = one_device(original)
    emitter = config.devices[0]
    # Freeze the fields present in the original persisted identity.
    legacy = emitter.model_dump(mode='json', include={'device_id', 'calibration_id', 'simulation'})
    ident = str(uuid5(NAMESPACE_URL, 'mosto/simulation/' + canonical_json(legacy)))
    assert ident == run_id(emitter)
    sender, path = APISender(client), tmp_path / 'old.db'
    sample = Trajectory(emitter.simulation).sample(0)
    body = dict(schema_version=2, device_id=emitter.device_id, calibration_id=emitter.calibration_id,
                sequence=0, boot_id=ident, observed_at=emitter.simulation.process_start.isoformat(),
                temperature_c={'value': sample['temperature_c'], 'quality': 'good'},
                brix_apparent={'value': sample['brix_apparent'], 'quality': 'good'})
    with sqlite3.connect(path) as state:
        state.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE runs(run_id TEXT PRIMARY KEY,device_id INTEGER UNIQUE NOT NULL,manifest TEXT NOT NULL,
          next_sequence INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'running',failures INTEGER NOT NULL DEFAULT 0,retry_after TEXT,last_error TEXT);
        CREATE TABLE outbox(run_id TEXT NOT NULL,sequence INTEGER NOT NULL,payload TEXT NOT NULL,truth TEXT NOT NULL,receipt_id INTEGER,PRIMARY KEY(run_id,sequence));''')
        state.execute('INSERT INTO metadata VALUES (?,?)', ('api_origin', config.base_url))
        state.execute('INSERT INTO runs(run_id,device_id,manifest) VALUES (?,?,?)', (ident, emitter.device_id, '{}'))
        state.execute('INSERT INTO outbox VALUES (?,?,?,?,NULL)', (ident, 0, canonical_json(body), canonical_json(sample)))
    worker = Worker(config, path, sender, keys)
    try:
        assert worker.tick(max_per_device=1) == 1
        assert sender.sent[0] == body
        assert worker.statuses()[0]['generated_sequence'] == 2
    finally:
        worker.close()


@pytest.mark.parametrize("factor", [1, 60])
def test_real_local_http_recovers_after_outage_without_fabricated_recovery(client, tmp_path, monkeypatch, factor):
    import uvicorn
    end = 8 if factor == 1 else 320
    config, keys = one_device(prepare([fault('communication_outage', 3, end)], hot_profile=True, clock_factor=factor))
    emitter = config.devices[0]
    start = emitter.simulation_clock.real_anchor if emitter.simulation_clock else emitter.simulation.process_start
    clock = {'now': start + timedelta(seconds=600 / factor)}
    monkeypatch.setattr(telemetry_v2, 'utc_now', lambda: clock['now'])
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error', lifespan='off'))
    thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    worker = None
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        config = config.model_copy(update={'base_url': f'http://127.0.0.1:{port}'})
        worker = Worker(config, tmp_path / 'tcp.db', keys=keys)  # Actual LocalHTTP, no mocked POST.
        assert isinstance(worker.sender, LocalHTTP)
        assert worker.tick(clock['now'], max_per_device=10) == 3
        with SessionLocal() as db:
            episode = db.query(m.EventoAlerta).filter_by(fermentacion_id=1).one()
            assert episode.version_regla and episode.estado_condicion == 'activa'
            eid = episode.id
        clock['now'] = start + timedelta(seconds=(end - 1) * 300 / factor)
        assert worker.tick(clock['now'], max_per_device=10) == 0
        assert worker.statuses()[0]['pending'] == min(end - 3, 10)
        with SessionLocal() as db:
            from app.services.monitoring import sweep_silence
            assert sweep_silence(db, clock['now']) == 1
            db.commit()
            assert db.get(m.EventoAlerta, eid).estado_condicion == 'desconocida'
        worker.close()
        worker = Worker(config, tmp_path / 'tcp.db', keys=keys)
        clock['now'] = start + timedelta(seconds=end * 300 / factor)
        assert worker.tick(clock['now'], max_per_device=2) == 2  # Only delayed observations are replayed.
        with SessionLocal() as db:
            from app.services.monitoring import monitoring_status
            assert db.query(m.MensajeTelemetria).count() == 5
            assert monitoring_status(db, db.get(m.ProcesoFermentacion, 1), clock['now'])['status'] == 'mediciones_atrasadas'
            assert db.get(m.EventoAlerta, eid).estado_condicion != 'recuperada'
            assert db.get(m.EventoAlerta, eid).fin_condicion is None
            assert db.get(m.EventoAlerta, eid).fecha_resolucion is None
            assert db.query(m.LecturaTelemetria).filter_by(dispositivo_id=6).count() == 0
    finally:
        if worker:
            worker.close()
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
    assert not thread.is_alive()
