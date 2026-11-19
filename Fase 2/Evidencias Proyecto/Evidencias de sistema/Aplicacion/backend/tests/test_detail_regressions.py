from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from app import models as m
from app.database import SessionLocal
from app.services import ml_service
from app.services.telemetry_v2 import aware
from test_telemetry_v2 import packet
from test_curve_comparison import emit


def legacy_readings(end, hours=24):
    with SessionLocal() as db:
        process = db.get(m.ProcesoFermentacion, 1)
        process.fecha_inicio = end - timedelta(hours=hours + 1)
        for step in range(int(hours * 12) + 1):
            stamp = end - timedelta(hours=hours) + timedelta(minutes=step * 5)
            db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1, timestamp=stamp,
                brix=24 - step / 120, temp_mosto=22 + step / 1000, ph=3.4,
                origen_dato='simulado_legacy', lectura_valida=True))
        db.commit()


def test_detail_metrics_include_legacy_without_claiming_v2_eligibility(client):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    legacy_readings(end)
    result = client.get('/api/procesos/1/cinetica', params={'as_of': end.isoformat()})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['eligible'] is False  # display statistics are separate from prediction
    metrics = data['display']['metrics']
    assert metrics['brix_mean_1h'] == pytest.approx(21.65, abs=.02)
    assert metrics['temperature_mean_1h'] > 22
    assert metrics['brix_slope_6h'] == pytest.approx(-.1, abs=.001)
    assert metrics['brix_slope_24h'] == pytest.approx(-.1, abs=.001)
    assert data['display']['sources'] == ['simulado_legacy']


def test_history_legacy_cutoff_and_ph_are_available(client):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    legacy_readings(end, hours=2)
    cutoff = end - timedelta(hours=1)
    response = client.get('/api/procesos/1/comparacion', params={'as_of': cutoff.isoformat(), 'variable': 'ph'})
    assert response.status_code == 200, response.text
    process = response.json()['processes'][0]
    points = [p for s in process['segments'] for p in s['points']]
    assert len(points) == 13
    assert all(datetime.fromisoformat(p['observed_at']) <= cutoff for p in points)
    assert all(p['value'] == 3.4 and p['available_at'] is None for p in points)
    assert 'recepcion_legacy_no_registrada' in process['warnings']
    assert process['telemetry']['total'] == 13


def test_one_hour_v2_mean_does_not_require_24h_and_does_not_duplicate_projection(client, packet, monkeypatch):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    for index in range(13):
        emit(client, packet, monkeypatch, end - timedelta(minutes=(12 - index) * 5), index + 1)
    data = client.get('/api/procesos/1/cinetica', params={'as_of': end.isoformat()}).json()
    assert data['eligible'] is False
    assert data['display']['metrics']['brix_mean_1h'] == 20
    assert 'brix_slope_6h' not in data['display']['metrics']
    history = client.get('/api/procesos/1/comparacion').json()['processes'][0]
    assert history['telemetry']['total'] == 13
    assert len(history['segments']) == 1
    assert len(history['segments'][0]['points']) == 13


def test_invalid_v2_window_does_not_fall_back_to_legacy(client, packet, monkeypatch):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    legacy_readings(end, hours=2)
    emit(client, packet, monkeypatch, end + timedelta(seconds=1), 1, brix_apparent={'value': None, 'quality': 'missing'})
    data = client.get('/api/procesos/1/cinetica').json()['display']
    assert data['legacy'] is False
    assert 'brix_latest' not in data['metrics']
    assert 'brix_mean_1h' not in data['metrics']


def test_future_demo_reading_does_not_override_current_detail_or_ml(client):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    legacy_readings(end, hours=1)
    with SessionLocal() as db:
        db.add(m.LecturaTelemetria(dispositivo_id=1, fermentacion_id=1,
            timestamp=end + timedelta(days=1), temp_mosto=35, brix=14.5, origen_dato='simulado_legacy'))
        db.commit()
    detail = client.get('/api/cubas/1').json()
    assert detail['ultima_temperatura'] < 23
    assert detail['prediccion_ml']['temp_suavizada'] < 23


def test_demo_buttons_do_not_write_future_measurements(client):
    for action in ('simular-anomalia', 'restaurar-normalidad'):
        response = client.post(f'/api/cubas/1/{action}')
        assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert all(aware(r.timestamp) <= datetime.now(timezone.utc) for r in db.query(m.LecturaTelemetria))


def test_legacy_model_has_no_artificial_brix_or_slope_threshold(monkeypatch):
    model = SimpleNamespace(predict_proba=lambda _: np.array([[.02, .98]]))
    monkeypatch.setattr(ml_service, 'get_model', lambda: model)
    for brix in (19.99, 20.01):
        for slope in (-.009, -.011):
            result = ml_service.evaluar_riesgo_parada_cuba([brix + slope * i for i in range(12)], [22] * 12)
            assert result['riesgo_pct'] == 98


def test_incomplete_v2_ml_does_not_invent_three_percent(client, packet, monkeypatch):
    end = datetime.now(timezone.utc) - timedelta(minutes=1)
    emit(client, packet, monkeypatch, end, 1)
    prediction = client.get('/api/cubas/1/ml-prediction').json()
    assert prediction['riesgo_pct'] is None


def test_profile_create_and_save_use_catalog_warehouse(client):
    warehouse = client.get('/api/bodegas').json()[0]
    grape = client.get('/api/cepas').json()[0]
    created = client.post('/api/perfiles', json=dict(nomb_perfil='Perfil revisión', bodega_id=warehouse['id'],
        cepa_id=grape['id'], temp_min=18, temp_max=26, activo=True))
    assert created.status_code == 201, created.text
    profile = created.json()
    updated = client.put(f"/api/perfiles/{profile['id']}", json=dict(expected_revision=profile['revision'], temp_max=25))
    assert updated.status_code == 200, updated.text
    assert updated.json()['bodega_id'] == warehouse['id']
    assert updated.json()['temp_max'] == 25


def test_simulator_temperature_and_brix_are_continuous_and_stable_per_tick():
    from scripts.simulate_esp import SimuladorFermentacion
    args = SimpleNamespace(cuba='1', duracion_dias=14, horas_por_ciclo=.05, brix_inicial=24,
        brix_final=2, temp_base=18.5, temp_amplitud=.6, stuck_fermentation=True, stuck_after=10)
    simulator = SimuladorFermentacion(args)
    previous_t, previous_b = simulator.temperatura_vino, simulator.brix
    assert previous_t == 18.5  # no forced clamp to 21 degrees
    for _ in range(100):
        simulator.avanzar()
        temperature, brix = simulator.temperatura_vino, simulator.brix
        assert temperature == simulator.temperatura_vino and brix == simulator.brix
        assert abs(temperature - previous_t) <= .081
        assert abs(brix - previous_b) < .15
        previous_t, previous_b = temperature, brix


def test_dense_legacy_packets_do_not_imply_a_model_window(client):
    legacy_readings(datetime.now(timezone.utc) - timedelta(minutes=1), hours=0.5)
    assert client.get('/api/cubas/1/ml-prediction').json()['riesgo_pct'] is None


def test_float_payload_never_reverses_healthy_brix():
    from scripts.simulate_esp import parsear_args, SimuladorFermentacion
    from app.services.telemetry_service import TelemetryService
    sim = SimuladorFermentacion(parsear_args(['--horas-por-ciclo', '1']))
    previous = sim.brix
    for _ in range(350):
        sim.avanzar()
        payload = sim.paquete_esp8266('02:00:00:00:00:01')
        _, measured, _ = TelemetryService.calcular_brix_y_densidad(payload['angulo_tilt'])
        assert sim.brix_final <= measured <= previous
        previous = measured
    assert previous == sim.brix_final
