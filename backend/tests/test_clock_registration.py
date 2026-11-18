from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4

from app.database import SessionLocal
from app import models as m
from app.services import demo_access


def test_registered_clock_is_scoped_frozen_and_not_yet_ingestible(client, monkeypatch):
    credential = client.post('/api/dispositivos/1/credenciales', json={
        'source':'simulado', 'label':'Clock test'}).json()
    with SessionLocal() as db:
        start = db.get(m.ProcesoFermentacion, 1).fecha_inicio.replace(tzinfo=timezone.utc).isoformat()
    clock = dict(real_anchor=datetime.now(timezone.utc).isoformat(), simulated_anchor=start, factor=60)
    body = dict(version='clock-test', method='synthetic_identity', valid_from=start,
        simulation=dict(process_id=1, process_start=start, seed=42, scenario='healthy'), simulation_clock=clock)
    url='/api/dispositivos/1/calibraciones'
    response=client.post(url,json=body)
    assert response.status_code == 201, response.text
    ident=response.json()['calibration_id']
    headers={'X-Mosto-Device-Key':credential['token']}
    config=client.get(f'/api/v2/telemetria/configuracion/1/{ident}',headers=headers).json()
    assert config['simulation_clock']['factor']==60
    assert client.post(url,json={**body,'simulation_clock':{**clock,'factor':180}}).status_code==409
    assert client.post(url,json={**body,'simulation_clock':None}).status_code==409
    assert client.post(url,json={**body,'simulation':None}).status_code==422
    packet=dict(schema_version=2,device_id=1,boot_id=str(uuid4()),sequence=0,
        observed_at=start,calibration_id=ident,temperature_c=dict(value=22,quality='good'),
        brix_apparent=dict(value=24,quality='good'))
    assert client.post('/api/v2/telemetria',headers=headers,json=packet).status_code==409
    monkeypatch.setattr(demo_access,'settings',replace(demo_access.settings,environment='development'))
    assert client.post(url,json=body).status_code==403
