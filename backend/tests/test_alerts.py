"""
Pruebas unitarias y de integración para:
TASK-BE-04A: API de Consulta y Reconocimiento de Alertas (AlertsView.vue)
TASK-BE-04B: Resolución de Incidencias, Métricas MTTR y Exportación CSV (AlertsAuditView.vue)

Criterios de Aceptación Verificados:
- [x] Listado paginado y con filtros (?estado, ?severidad, ?cuba_id).
- [x] Reconocimiento de alertas (PATCH /api/alertas/{id}/atender) con ck_alerta_atencion.
- [x] Resolución de alertas (PATCH /api/alertas/{id}/resolver) con nota_resolucion.
- [x] Cálculo estricto de fórmula MTTR = sum(fecha_resolucion - timestamp) / Total Resueltas.
- [x] Exportación bitácora CSV con cabeceras Content-Type: text/csv y descarga directa.
"""
import sys
import os
from datetime import datetime, timedelta

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
from app.schemas import AlertaAtenderIn, AlertaResolverIn
from app.routers.alerts import (
    listar_alertas, atender_alerta, obtener_alerta,
    resolver_alerta, obtener_metricas_alertas, exportar_bitacora_alertas_csv
)

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
    
    # 6. Alertas de prueba con tiempos controlados para validar MTTR
    ahora = datetime.utcnow()
    t_gen_4 = ahora - timedelta(minutes=60)
    t_res_4 = t_gen_4 + timedelta(minutes=30)  # delta = 30 minutos

    alerta1 = EventoAlerta(
        id=1,
        fermentacion_id=1,
        tipo_alerta="temp_alta",
        severidad="critica",
        estado="pendiente",
        met_dispar="sensor_iot",
        timestamp=ahora - timedelta(minutes=50)
    )
    alerta2 = EventoAlerta(
        id=2,
        fermentacion_id=1,
        tipo_alerta="ph_bajo",
        severidad="media",
        estado="pendiente",
        met_dispar="sensor_iot",
        timestamp=ahora - timedelta(minutes=40)
    )
    alerta3 = EventoAlerta(
        id=3,
        fermentacion_id=2,
        tipo_alerta="temp_baja",
        severidad="critica",
        estado="atendida",
        atendida_por=1,
        fecha_atencion=ahora - timedelta(minutes=15),
        met_dispar="sensor_iot",
        timestamp=ahora - timedelta(minutes=20)
    )
    alerta4 = EventoAlerta(
        id=4,
        fermentacion_id=2,
        tipo_alerta="wifi_debil",
        severidad="baja",
        estado="resuelta",
        atendida_por=1,
        fecha_atencion=t_gen_4 + timedelta(minutes=10),
        fecha_resolucion=t_res_4,  # Duró 30 minutos
        nota_resolucion="Reemplazo de módulo por técnico de bodega",
        met_dispar="nodo_salud",
        timestamp=t_gen_4
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
    payload_atender = AlertaAtenderIn(usuario_id=1, nota="Inspeccionada en terreno por Carlos Cartes")
    res_atender = atender_alerta(id=1, payload=payload_atender, db=db)
    assert res_atender.id == 1
    assert res_atender.estado == "atendida"
    assert res_atender.atendida_por == 1
    assert res_atender.operador_nombre == "Carlos Cartes"
    assert res_atender.fecha_atencion is not None
    assert res_atender.nota_atencion == "Inspeccionada en terreno por Carlos Cartes"
    
    # Verificar persistencia directa en DB y restricción ck_alerta_atencion
    alerta_db = db.query(EventoAlerta).filter(EventoAlerta.id == 1).first()
    assert alerta_db.estado == "atendida"
    assert alerta_db.atendida_por == 1
    assert alerta_db.fecha_atencion is not None
    assert not (alerta_db.atendida_por is not None and alerta_db.fecha_atencion is None)
    print(f"OK: Alerta #{res_atender.id} atendida exitosamente cumpliendo ck_alerta_atencion.")

    print("--- 7. Probando 404 en alerta inexistente al atender ---")
    try:
        atender_alerta(id=999, payload=payload_atender, db=db)
        assert False, "Debería haber lanzado HTTPException 404"
    except HTTPException as e:
        assert e.status_code == 404
        print(f"OK: Error 404 controlado correctamente: {e.detail}")

    print("--- 8. Probando 400 en alerta ya resuelta al atender ---")
    try:
        atender_alerta(id=4, payload=payload_atender, db=db)
        assert False, "Debería haber lanzado HTTPException 400"
    except HTTPException as e:
        assert e.status_code == 400
        print(f"OK: Error 400 controlado correctamente: {e.detail}")

    # ==========================================
    # TESTS ESPECÍFICOS DE TASK-BE-04B
    # ==========================================

    print("\n--- 9. Probando PATCH /api/alertas/{id}/resolver ---")
    # Fijar tiempo de alerta 1 a exactamente 50 minutos de duración para la prueba matemática de MTTR
    alerta_1 = db.query(EventoAlerta).filter(EventoAlerta.id == 1).first()
    alerta_1.timestamp = datetime.utcnow() - timedelta(minutes=50)
    db.commit()

    payload_resolver = AlertaResolverIn(
        usuario_id=1,
        nota_resolucion="Ajuste de electroválvula de camisa térmica y adición de nutrientes."
    )
    res_resolver = resolver_alerta(id=1, payload=payload_resolver, db=db)
    assert res_resolver.id == 1
    assert res_resolver.estado == "resuelta"
    assert res_resolver.fecha_resolucion is not None
    assert res_resolver.nota_resolucion == "Ajuste de electroválvula de camisa térmica y adición de nutrientes."
    print(f"OK: Alerta #1 resuelta con éxito en timestamp {res_resolver.fecha_resolucion}.")

    print("--- 10. Probando GET /api/alertas/metricas y Criterio MTTR ---")
    # Ahora tenemos 2 alertas resueltas:
    # Alerta 4: duró 30 minutos.
    # Alerta 1: duró ~50 minutos.
    # Promedio MTTR esperado: (30 + 50) / 2 = ~40 minutos (tolerancia ±1 minuto).
    metricas = obtener_metricas_alertas(db=db)
    assert metricas.total_alertas == 4
    assert metricas.total_resueltas == 2
    assert metricas.alertas_activas == 2  # alertas 2 y 3
    assert metricas.tasa_resolucion_pct == 50.0  # 2 de 4 = 50%
    assert 39.0 <= metricas.mttr_promedio_minutos <= 41.0, f"MTTR obtenido: {metricas.mttr_promedio_minutos}"
    print(f"OK: Métricas calculadas con éxito:")
    print(f"    - Total alertas: {metricas.total_alertas}")
    print(f"    - Alertas activas: {metricas.alertas_activas}")
    print(f"    - Alertas críticas activas: {metricas.alertas_criticas}")
    print(f"    - Total resueltas: {metricas.total_resueltas}")
    print(f"    - MTTR promedio: {metricas.mttr_promedio_minutos} minutos (Fórmula MTTR validada)")
    print(f"    - Tasa de resolución: {metricas.tasa_resolucion_pct}%")

    print("--- 11. Probando GET /api/alertas/exportar (CSV) y Criterio de Cabeceras ---")
    resp_csv = exportar_bitacora_alertas_csv(db=db)
    assert resp_csv.media_type == "text/csv"
    assert "Content-Disposition" in resp_csv.headers
    assert "attachment; filename=\"bitacora_alertas_" in resp_csv.headers["Content-Disposition"]
    assert resp_csv.headers["Content-Disposition"].endswith(".csv\"")
    assert "text/csv" in resp_csv.headers["Content-Type"]

    contenido = resp_csv.body.decode("utf-8")
    assert "ID Incidencia,Cuba,Variedad" in contenido
    assert "Accion Correctiva / Nota Resolucion" in contenido
    assert "CB-01" in contenido
    assert "Ajuste de electroválvula de camisa térmica" in contenido
    print("OK: Exportación CSV generada con cabecera Content-Type: text/csv y descarga directa.")

    db.close()
    print("\n==================================================================")
    print("¡TODAS LAS PRUEBAS DE TASK-BE-04A Y TASK-BE-04B PASARON AL 100%!")
    print("==================================================================")


if __name__ == "__main__":
    test_suite()
