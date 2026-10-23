from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    r=client.get('/api/health')
    assert r.status_code==200 and r.json()['mode']=='demo'

def test_seed_consistent():
    for resource in ('bodegas','cubas','fermentaciones','dispositivos','alertas','lecturas'):
        r=client.get(f'/api/{resource}')
        assert r.status_code==200 and len(r.json())>0

def test_active_alert_requires_attend_and_note():
    assert client.post('/api/alertas/1/resolver',json={'nota':'Corregido'}).status_code==409
    assert client.post('/api/alertas/1/atender').json()['estado']=='atendida'
    assert client.post('/api/alertas/1/resolver',json={'nota':'Se corrigió temperatura'}).json()['estado']=='resuelta'

def test_fermentation_cannot_exceed_cuba_capacity():
    from app.main import DEMO_DB
    payload={'data':{'cuba_id':3,'perfil_id':1,'volumen_litros':7000,'fecha_inicio':'2026-10-23T10:00:00','fecha_estimada_fin':'2026-11-02T10:00:00'}}
    assert client.post('/api/fermentaciones',json=payload).status_code==422

def test_readings_filter_and_export():
    r=client.get('/api/lecturas?fermentacion_id=2')
    assert r.status_code==200 and all(x['fermentacion_id']==2 for x in r.json())
    e=client.get('/api/exportaciones/lecturas.csv?fermentacion_id=2')
    assert e.status_code==200 and 'temp_mosto' in e.text

def test_company_uniqueness_and_role_replace():
    assert client.post('/api/empresas',json={'data':{'nomb_emp':'Viña Los Aromos','email_emp':'x@ejemplo.invalid','activo':True}}).status_code==409
    r=client.post('/api/usuarios_bodega',json={'data':{'usuario_id':3,'bodega_id':1,'rol_id':2}})
    assert r.status_code==201
    entries=[x for x in client.get('/api/usuarios_bodega').json() if x['usuario_id']==3 and x['bodega_id']==1]
    assert len(entries)==1 and entries[0]['rol_id']==2

def test_cuba_with_active_process_cannot_be_maintained():
    assert client.patch('/api/cubas/1/estado',json={'estado':'mantención'}).status_code==409

def test_iot_ingest_rejects_unknown_key_and_invalid_ph():
    body={'dispositivo_id':1,'timestamp':'2026-10-23T20:13:00Z','temp_mosto':23.1,'brix':14.4,'ph':3.4}
    assert client.post('/api/iot/lecturas',json=body,headers={'X-Device-Key':'mal'}).status_code==401
    assert client.post('/api/iot/lecturas',json={**body,'ph':15},headers={'X-Device-Key':'mosto-demo-dispositivo-1'}).status_code==422

def test_iot_creates_alert_on_out_of_range_and_deduplicates():
    body={'dispositivo_id':1,'timestamp':'2026-10-23T20:14:00Z','temp_mosto':31,'brix':14.4,'ph':3.4}
    r=client.post('/api/iot/lecturas',json=body,headers={'X-Device-Key':'mosto-demo-dispositivo-1'})
    assert r.status_code==201
    assert any(a['tipo_alerta']=='temp_mosto_alta' for a in r.json()['alertas_generadas'])
    dup=client.post('/api/iot/lecturas',json={**body,'timestamp':'2026-10-23T20:15:00Z'},headers={'X-Device-Key':'mosto-demo-dispositivo-1'})
    assert dup.status_code==201 and not dup.json()['alertas_generadas']
    same=client.post('/api/iot/lecturas',json=body,headers={'X-Device-Key':'mosto-demo-dispositivo-1'})
    assert same.status_code==409
