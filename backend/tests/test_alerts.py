"""
Pruebas unitarias y de integración para TASK-BE-04A:
API de Consulta y Reconocimiento de Alertas (AlertsView.vue)
- Listado paginado y con filtros (?estado, ?severidad, ?cuba_id).
- Reconocimiento de alertas (PATCH /api/alertas/{id}/atender).
- Verificación estricta de la restricción ck_alerta_atencion (atendida_por exige fecha_atencion).
"""
import sys
import os
from datetime import datetime

# Agregar carpeta backend al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import (
    EmpresaCliente, Bodega, Cuba, Cepa, PerfilFermentacion,
    ProcesoFermentacion, Dispositivo, ModeloDispositivo,
    EventoAlerta, Usuario, Rol
)
from app.schemas import AlertaAtenderIn
from app.routers.alerts import listar_alertas, atender_alerta, obtener_alerta

# Base de datos SQLite en memoria para tests aislados
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def seed_test_data(db):
    """Siembra datos maestros mínimos para pruebas relacionales."""
    # 1. Empresa y Bodega
    empresa = EmpresaCliente(id=1, nomb_emp="Viña Test")
    bodega = Bodega(id=1, nombre="Bodega Principal", empresa_id=1)
    db.add_all([empresa, bodega])
    
    # 2. Cubas
    cuba1 = Cuba(id=1, codigo="CB-01", bodega_id=1, cap_litros=10000.0, sector_cuba="Nave 1")
    cuba2 = Cuba(id=2, codigo="CB-02", bodega_id=1, cap_litros=15000.0, sector_cuba="Nave 2")
    db.add_all([cuba1, cuba2])
    
    # 3. Cepa y Perfil
    cepa = Cepa(id=1, nombre_variedad="Carménère", tipo_uva="Tinto")
    perfil = PerfilFermentacion(id=1, nomb_perfil="Perfil Carménère", cepa_id=1, bodega_id=1, temp_min=18.0, temp_max=26.0)
    db.add_all([cepa, perfil])
    
    # 4. Procesos de Fermentación
    proceso1 = ProcesoFermentacion(id=1, cuba_id=1, perfil_id=1, estado="en_proceso")
    proceso2 = ProcesoFermentacion(id=2, cuba_id=2, perfil_id=1, estado="en_proceso")
    db.add_all([proceso1, proceso2])
    
    # 5. Usuario
    rol = Rol(id=1, nomb_rol="Enólogo")
    usuario = Usuario(id=1, nombre="Carlos Cartes", email="ccartes@mosto.cl", password_hash="hash123", rol_id=1)
    db.add_all([rol, usuario])
    
    # 6. Alertas de prueba
    alerta1 = EventoAlerta(
        id=1,
        fermentacion_id=1,
        tipo_alerta="temp_alta",
        severidad="critica",
        estado="pendiente",
        met_dispar="sensor_iot",
        timestamp=datetime.utcnow()
    )
    alerta2 = EventoAlerta(
        id=2,
        fermentacion_id=1,
        tipo_alerta="ph_bajo",
        severidad="media",
        estado="pendiente",
        met_dispar="sensor_iot",
        timestamp=datetime.utcnow()
    )
    alerta3 = EventoAlerta(
        id=3,
        fermentacion_id=2,
        tipo_alerta="temp_baja",
        severidad="critica",
        estado="atendida",
        atendida_por=1,
        fecha_atencion=datetime.utcnow(),
        met_dispar="sensor_iot",
        timestamp=datetime.utcnow()
    )
    alerta4 = EventoAlerta(
        id=4,
        fermentacion_id=2,
        tipo_alerta="wifi_debil",
        severidad="baja",
        estado="resuelta",
        atendida_por=1,
        fecha_atencion=datetime.utcnow(),
        fecha_resolucion=datetime.utcnow(),
        met_dispar="nodo_salud",
        timestamp=datetime.utcnow()
    )
    db.add_all([alerta1, alerta2, alerta3, alerta4])
    db.commit()


def test_suite():
    db = TestingSessionLocal()
    seed_test_data(db)

    print("--- 1. Probando listar todas las alertas ---")
    alertas = listar_alertas(db=db)
    assert len(alertas) == 4, f"Esperado 4, obtenido {len(alertas)}"
    assert alertas[0].cuba_codigo in ["CB-01", "CB-02"]
    assert alertas[0].titulo is not None
    assert alertas[0].descripcion is not None
    print(f"OK: Obtenidas {len(alertas)} alertas enriquecidas.")

    print("--- 2. Probando filtro ?estado=pendiente ---")
    alertas_pend = listar_alertas(estado="pendiente", db=db)
    assert len(alertas_pend) == 2, f"Esperado 2, obtenido {len(alertas_pend)}"
    for a in alertas_pend:
        assert a.estado == "pendiente"
    print(f"OK: Filtro de estado pendiente correcto.")

    print("--- 3. Probando filtro ?severidad=critica ---")
    alertas_crit = listar_alertas(severidad="critica", db=db)
    assert len(alertas_crit) == 2, f"Esperado 2, obtenido {len(alertas_crit)}"
    for a in alertas_crit:
        assert a.severidad == "critica"
    print(f"OK: Filtro de severidad crítica correcto.")

    print("--- 4. Probando filtro ?cuba_id=1 ---")
    alertas_cuba1 = listar_alertas(cuba_id=1, db=db)
    assert len(alertas_cuba1) == 2, f"Esperado 2, obtenido {len(alertas_cuba1)}"
    for a in alertas_cuba1:
        assert a.cuba_id == 1
    print(f"OK: Filtro por cuba_id correcto.")

    print("--- 5. Probando paginación limit y offset ---")
    p1 = listar_alertas(limit=2, offset=0, db=db)
    p2 = listar_alertas(limit=2, offset=2, db=db)
    assert len(p1) == 2 and len(p2) == 2
    ids_p1 = {a.id for a in p1}
    ids_p2 = {a.id for a in p2}
    assert len(ids_p1.intersection(ids_p2)) == 0
    print(f"OK: Paginación correcta (p1: {ids_p1}, p2: {ids_p2}).")

    print("--- 6. Probando PATCH /api/alertas/{id}/atender (ck_alerta_atencion) ---")
    payload = AlertaAtenderIn(usuario_id=1, nota="Inspeccionada en terreno por Carlos Cartes")
    res = atender_alerta(id=1, payload=payload, db=db)
    assert res.id == 1
    assert res.estado == "atendida"
    assert res.atendida_por == 1
    assert res.operador_nombre == "Carlos Cartes"
    assert res.fecha_atencion is not None
    assert res.nota_atencion == "Inspeccionada en terreno por Carlos Cartes"
    
    # Verificar persistencia directa en DB y restricción ck_alerta_atencion
    alerta_db = db.query(EventoAlerta).filter(EventoAlerta.id == 1).first()
    assert alerta_db.estado == "atendida"
    assert alerta_db.atendida_por == 1
    assert alerta_db.fecha_atencion is not None
    # Restricción CHECK: si atendida_por existe, fecha_atencion no puede ser None
    assert not (alerta_db.atendida_por is not None and alerta_db.fecha_atencion is None)
    print(f"OK: Alerta #{res.id} atendida exitosamente cumpliendo ck_alerta_atencion en timestamp {res.fecha_atencion}.")

    print("--- 7. Probando 404 en alerta inexistente ---")
    try:
        atender_alerta(id=999, payload=payload, db=db)
        assert False, "Debería haber lanzado HTTPException 404"
    except HTTPException as e:
        assert e.status_code == 404
        print(f"OK: Error 404 controlado correctamente: {e.detail}")

    print("--- 8. Probando 400 en alerta ya resuelta ---")
    try:
        atender_alerta(id=4, payload=payload, db=db)
        assert False, "Debería haber lanzado HTTPException 400"
    except HTTPException as e:
        assert e.status_code == 400
        print(f"OK: Error 400 controlado correctamente: {e.detail}")

    db.close()
    print("\n=======================================================")
    print("¡TODAS LAS PRUEBAS DE LA TAREA PASARON CON ÉXITO (100%)!")
    print("=======================================================")


if __name__ == "__main__":
    test_suite()
