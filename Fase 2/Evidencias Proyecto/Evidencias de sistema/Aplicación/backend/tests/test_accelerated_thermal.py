from datetime import timedelta

from app import models as m
from app.database import SessionLocal
from app.services import simulation_time
from app.services.telemetry_v2 import aware
from app.simulation.clock import SimulationClock
from test_episodes import stream, open_episode
from test_profile_overrides import frozen, approve


def test_override_uses_expected_real_time_not_simulated_or_receipt(client, stream, frozen, monkeypatch):
    send, start = stream
    clock = SimulationClock(real_anchor=start-timedelta(hours=1),simulated_anchor=start,factor=60)
    monkeypatch.setattr(simulation_time,'message_clock',lambda *args:clock)
    approve(client,monkeypatch,clock.real_anchor+timedelta(seconds=20))
    # Ten simulated minutes correspond to ten real seconds: the later override
    # must not affect these observations, even though reception is much later.
    alert = open_episode(client,stream)
    assert alert['evidencia']['configuration']['temp_max']==26
    for minute in (15,20,25):
        assert send(minute,25).status_code==201
    for minute in (30,35,40):
        assert send(minute,30).status_code==201
    assert len(client.get('/api/alertas').json())==1


def test_closure_keeps_server_time_and_simulated_condition_time(client, stream, monkeypatch):
    alert = open_episode(client,stream)
    start=stream[1]
    clock=SimulationClock(real_anchor=start,simulated_anchor=start,factor=60)
    monkeypatch.setattr(simulation_time,'message_clock',lambda *args:clock)
    assert client.patch('/api/procesos/1/finalizar').status_code==200
    with SessionLocal() as db:
        process=db.get(m.ProcesoFermentacion,1)
        episode=db.get(m.EventoAlerta,alert['id'])
        assert aware(episode.fin_condicion)==clock.simulated_at(aware(process.fecha_real_fin))
        assert episode.estado_condicion=='cerrada_proceso'
        assert episode.fecha_resolucion is None
        event=db.query(m.AuditoriaAlerta).filter_by(alerta_id=episode.id,accion='cerrada_proceso').one()
        assert aware(event.registrado_en)==aware(process.fecha_real_fin)
        assert event.detalle['observation_clock']=='simulated'
