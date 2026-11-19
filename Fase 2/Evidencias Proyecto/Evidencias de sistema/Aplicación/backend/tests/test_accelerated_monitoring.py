from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from app.services import monitoring, simulation_time, profile_overrides
from app.simulation.clock import SimulationClock
from test_kinetic_episodes import kinetic_stream, slopes, activate


def test_monitoring_separates_future_simulated_age_and_real_silence(monkeypatch):
    real = datetime(2026, 11, 18, tzinfo=timezone.utc)
    simulated = real + timedelta(days=10)
    clock = SimulationClock(real_anchor=real, simulated_anchor=simulated, factor=60)
    message = NS(recibido_en=real, observado_en=simulated)
    class Query:
        def filter(self, *args): return self
        def filter_by(self, **kwargs): return self
        def order_by(self, *args): return self
        def first(self): return message
        def __iter__(self): return iter([])
    db = NS(query=lambda *args: Query(), get=lambda *args: None)
    monkeypatch.setattr(simulation_time, 'message_clock', lambda *args: clock)
    monkeypatch.setattr(profile_overrides, 'applied_profile', lambda *args: {})
    process = NS(id=1, fecha_real_fin=None, perfil_id=None)
    status = monitoring.monitoring_status(db, process, real + timedelta(seconds=30))
    assert status['status'] == 'datos_recientes'
    assert status['observation_age_seconds'] == 1800
    assert status['expected_delivery_age_seconds'] == 30
    assert status['receipt_age_seconds'] == 30
    assert monitoring.monitoring_status(db, process, real + timedelta(seconds=901))['status'] == 'sin_recepcion_reciente'


def test_historical_clock_is_scoped_and_revocation_does_not_rewrite_time():
    real = datetime(2026,11,18,tzinfo=timezone.utc)
    clock = SimulationClock(real_anchor=real,simulated_anchor=real,factor=60)
    calibration = NS(dispositivo_id=1, revocada_en=real, parametros={
        'simulation':{'process_id':2}, 'simulation_clock':clock.model_dump(mode='json')})
    db=NS(get=lambda *args:calibration)
    message=NS(origen='simulado',calibracion_id=1,dispositivo_id=1,fermentacion_id=2)
    assert simulation_time.message_clock(db,message)==clock
    message.fermentacion_id=3
    with pytest.raises(ValueError,match='scope'):
        simulation_time.message_clock(db,message)
    message.origen='fisico'
    assert simulation_time.message_clock(db,message) is None


def test_kinetic_rule_passes_separate_cuts(client, kinetic_stream, slopes, monkeypatch):
    from app.services import kinetic_episodes
    base = kinetic_stream[2]
    clock = SimulationClock(real_anchor=base, simulated_anchor=base, factor=60)
    monkeypatch.setattr(simulation_time, 'message_clock', lambda *args: clock)
    previous = kinetic_episodes.process_kinetics
    calls = []
    def capture(db, process, as_of, **kwargs):
        calls.append((as_of, kwargs))
        return previous(db, process, as_of)
    monkeypatch.setattr(kinetic_episodes, 'process_kinetics', capture)
    activate(client)
    assert kinetic_stream[0](1).status_code == 201
    assert calls[-1] == (base + timedelta(hours=1), {'received_as_of':base + timedelta(minutes=1)})
