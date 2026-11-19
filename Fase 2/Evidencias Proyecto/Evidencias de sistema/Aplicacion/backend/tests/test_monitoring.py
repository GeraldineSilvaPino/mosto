from datetime import timedelta

import pytest

from app import models as m
from app.database import SessionLocal
from app.services.monitoring import monitoring_status, sweep_silence
from test_episodes import stream, open_episode


def test_status_distinguishes_no_telemetry_missing_profile_and_closed(client):
    status = client.get('/api/procesos/1/cinetica').json()['current_monitoring']
    assert status['status'] == 'sin_telemetria_v2'
    assert status['thermal_rules']['temperatura_alta'] == 'pendiente_primera_evaluacion'
    with SessionLocal() as db:
        db.get(m.PerfilFermentacion, 1).temp_max = None
        db.commit()
    assert client.get('/api/procesos/1/cinetica').json()['current_monitoring']['thermal_rules']['temperatura_alta'] == 'sin_limites_de_perfil'
    assert client.patch('/api/procesos/1/finalizar').status_code == 200
    assert client.get('/api/procesos/1/cinetica').json()['current_monitoring']['status'] == 'proceso_cerrado'


def test_receiving_backlog_does_not_mean_fresh_measurements(client, stream):
    stream[0](0)
    status = client.get('/api/procesos/1/cinetica').json()['current_monitoring']
    assert status['status'] == 'mediciones_atrasadas'
    assert status['receipt_age_seconds'] < 15
    assert status['observation_age_seconds'] > 900


def test_watchdog_marks_unknown_once_without_recovery_or_fake_observations(client, stream):
    alert = open_episode(client, stream)
    with SessionLocal() as db:
        before = db.query(m.AuditoriaAlerta).count()
    # Reading diagnostics cannot mutate the episode.
    client.get('/api/procesos/1/cinetica')
    assert client.get(f"/api/alertas/{alert['id']}").json()['estado_condicion'] == 'activa'
    from app.services.telemetry_v2 import utc_now
    now = utc_now() + timedelta(minutes=16)
    with SessionLocal() as db:
        assert sweep_silence(db, now) == 1
        db.commit()
        assert sweep_silence(db, now + timedelta(minutes=5)) == 0
        db.commit()
        assert db.query(m.AuditoriaAlerta).count() == before + 1
    result = client.get(f"/api/alertas/{alert['id']}").json()
    assert result['estado_condicion'] == 'desconocida' and result['fin_condicion'] is None
    assert result['ultima_observacion'] == alert['ultima_observacion']
    assert result['estado'] == 'pendiente'
    event = client.get(f"/api/alertas/{alert['id']}/eventos").json()[-1]
    assert event['accion'] == 'silencio_detectado' and event['observado_en'] is None


def test_sweep_skips_closed_process(client, stream):
    alert = open_episode(client, stream)
    client.patch('/api/procesos/1/finalizar')
    from app.services.telemetry_v2 import utc_now
    with SessionLocal() as db:
        assert sweep_silence(db, utc_now() + timedelta(hours=1)) == 0
    assert client.get(f"/api/alertas/{alert['id']}").json()['estado_condicion'] == 'cerrada_proceso'


def test_audit_failure_rolls_back_sweep(client, stream, monkeypatch):
    alert = open_episode(client, stream)
    from app.services import monitoring
    from app.services.telemetry_v2 import utc_now
    def fail(*args, **kwargs):
        raise RuntimeError('audit failure')
    monkeypatch.setattr(monitoring, 'record_action', fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError):
            sweep_silence(db, utc_now() + timedelta(hours=1))
        db.rollback()
    assert client.get(f"/api/alertas/{alert['id']}").json()['estado_condicion'] == 'activa'


def test_exact_threshold_and_fresh_samples_do_not_trigger_watchdog(client, stream, monkeypatch):
    from app.services import telemetry_v2
    send, start = stream
    for minute in (0, 5, 10):
        monkeypatch.setattr(telemetry_v2, 'utc_now', lambda minute=minute: start + timedelta(minutes=minute))
        assert send(minute).status_code == 201
    with SessionLocal() as db:
        assert sweep_silence(db, start + timedelta(minutes=25)) == 0
        assert sweep_silence(db, start + timedelta(minutes=25, seconds=1)) == 1
        db.commit()
    # Returning measurements begin a new recovery window; silence did not count.
    for minute in (30, 35):
        monkeypatch.setattr(telemetry_v2, 'utc_now', lambda minute=minute: start + timedelta(minutes=minute))
        assert send(minute, 24).status_code == 201
    assert client.get('/api/alertas').json()[0]['fin_condicion'] is None
    monkeypatch.setattr(telemetry_v2, 'utc_now', lambda: start + timedelta(minutes=40))
    assert send(40, 24).status_code == 201
    assert client.get('/api/alertas').json()[0]['estado_condicion'] == 'recuperada'


def test_watchdog_clears_unconfirmed_candidate(client, stream):
    send, _ = stream
    send(0)
    from app.services.telemetry_v2 import utc_now
    with SessionLocal() as db:
        state = db.query(m.EstadoRegla).filter_by(codigo='temperatura_alta').one()
        assert state.inicio_candidato is not None
        assert sweep_silence(db, utc_now() + timedelta(minutes=20)) == 0
        db.commit()
        assert state.inicio_candidato is None and state.episodio_id is None


def test_worker_rejects_development_before_opening_database(monkeypatch):
    from app import config
    from scripts.watchdog import main
    monkeypatch.setattr(config, 'load_settings', lambda: config.Settings(
        environment='development', database_url='sqlite:///not-a-demo.db', jwt_secret='x'*32))
    with pytest.raises(ValueError, match='Only demo/test'):
        main(['--once'])
