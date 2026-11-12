"""
Router de Cubas para consulta del Frontend (Dashboard, CubaDetail).
Controlador REST para monitoreo en tiempo real y curvas de fermentación.
"""
from typing import List, Optional
from datetime import datetime, timedelta
import random
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import (
    Cuba,
    ProcesoFermentacion,
    LecturaTelemetria,
    EventoAlerta,
    Dispositivo,
    AsignacionDispositivo,
    EmpresaCliente,
    ModeloDispositivo
)
from app.schemas import CubaOut, LecturaOut, HistoricoCubaOut, MLPredictionOut, SimulacionAnomaliaOut
from app.services.ml_service import evaluar_riesgo_parada_cuba
from app.services.rules_engine import rules_engine

router = APIRouter(prefix="/api/cubas", tags=["Cubas y Monitoreo"])


def _resolver_dispositivo_cuba(db: Session, cuba_id: int) -> int:
    """
    Obtiene o asigna un dispositivo activo para la cuba.
    Garantiza el cumplimiento del trigger fn_validar_lectura de PostgreSQL.
    """
    asig = (
        db.query(AsignacionDispositivo)
        .filter(
            AsignacionDispositivo.cuba_id == cuba_id,
            AsignacionDispositivo.activo == True
        )
        .first()
    )
    if asig:
        return asig.dispositivo_id

    disp = db.query(Dispositivo).first()
    if not disp:
        empresa = db.query(EmpresaCliente).first()
        modelo = db.query(ModeloDispositivo).first()
        disp = Dispositivo(
            mac_address="AA:BB:CC:DD:EE:01",
            tipo_dispositivo="ESP32_NODO_CUBA",
            empresa_id=empresa.id if empresa else 1,
            modelo_id=modelo.id if modelo else 1,
            estado="activo"
        )
        db.add(disp)
        db.commit()
        db.refresh(disp)

    nueva_asig = AsignacionDispositivo(
        dispositivo_id=disp.id,
        cuba_id=cuba_id,
        activo=True,
        desasignado_en=None
    )
    db.add(nueva_asig)
    db.commit()
    return disp.id


def _calcular_prediccion_ml(db: Session, proceso_id: Optional[int]) -> Optional[MLPredictionOut]:
    """Calcula la predicción de Machine Learning a partir de las últimas 12 lecturas del proceso."""
    if not proceso_id:
        return None

    lecturas = (
        db.query(LecturaTelemetria)
        .filter(
            LecturaTelemetria.fermentacion_id == proceso_id,
            LecturaTelemetria.brix.isnot(None),
            LecturaTelemetria.temp_mosto.isnot(None)
        )
        .order_by(desc(LecturaTelemetria.timestamp), desc(LecturaTelemetria.id))
        .limit(12)
        .all()
    )

    if not lecturas:
        return MLPredictionOut(
            riesgo_pct=0.0,
            estado_ia="RECOLECTANDO_DATOS",
            alerta_ia=False,
            mensaje="Sin lecturas históricas para calcular predicción",
            brix_suavizado=None,
            temp_suavizada=None,
            pendiente_brix_ventana=None,
            pendiente_temp_ventana=None,
            turbulencia_brix_std=None
        )

    lecturas_cron = list(reversed(lecturas))
    lecturas_brix = [float(l.brix) for l in lecturas_cron]
    lecturas_temp = [float(l.temp_mosto) for l in lecturas_cron]

    pred = evaluar_riesgo_parada_cuba(lecturas_brix, lecturas_temp)
    return MLPredictionOut(
        riesgo_pct=pred["riesgo_pct"],
        estado_ia=pred["estado_ia"],
        alerta_ia=pred["alerta_ia"],
        mensaje=pred["mensaje"],
        brix_suavizado=pred.get("brix_suavizado"),
        temp_suavizada=pred.get("temp_suavizada"),
        pendiente_brix_ventana=pred.get("pendiente_brix_ventana"),
        pendiente_temp_ventana=pred.get("pendiente_temp_ventana"),
        turbulencia_brix_std=pred.get("turbulencia_brix_std")
    )


def _mapear_cuba_out(
    c: Cuba,
    proceso_activo: Optional[ProcesoFermentacion],
    ultima_lectura: Optional[LecturaTelemetria],
    prediccion_ml: Optional[MLPredictionOut] = None
) -> CubaOut:
    """Helper para transformar la entidad Cuba y sus relaciones al DTO CubaOut."""
    variedad = None
    temp_min = None
    temp_max = None
    dia_ferm = None

    if proceso_activo:
        if proceso_activo.perfil:
            temp_min = float(proceso_activo.perfil.temp_min) if proceso_activo.perfil.temp_min is not None else 16.0
            temp_max = float(proceso_activo.perfil.temp_max) if proceso_activo.perfil.temp_max is not None else 26.0
            if proceso_activo.perfil.cepa:
                variedad = proceso_activo.perfil.cepa.nombre_variedad
        
        if not variedad:
            variedad = "Cabernet Sauvignon"

        if proceso_activo.fecha_inicio:
            delta_dias = (datetime.utcnow().date() - proceso_activo.fecha_inicio.date()).days
            dia_ferm = max(1, delta_dias + 1)
        else:
            dia_ferm = 1

    return CubaOut(
        id=c.id,
        codigo_cuba=c.codigo,
        nombre=f"Cuba {c.codigo}",
        capacidad_lts=float(c.cap_litros) if c.cap_litros else 10000.0,
        ubicacion_en_bodega=c.sector_cuba or "Sector Principal",
        estado_operativo=c.estado_operativo or "disponible",
        
        # Datos del proceso
        proceso_activo_id=proceso_activo.id if proceso_activo else None,
        variedad=variedad,
        lote=f"Lote {proceso_activo.id}-2026" if proceso_activo else None,
        volumen_actual_lts=float(proceso_activo.volumen_litros) if proceso_activo and proceso_activo.volumen_litros else None,
        dia_fermentacion=dia_ferm,
        dias_estimados=14,
        temp_min_perfil=temp_min,
        temp_max_perfil=temp_max,
        
        # Datos de telemetría reciente
        ultima_temperatura=float(ultima_lectura.temp_mosto) if ultima_lectura and ultima_lectura.temp_mosto is not None else None,
        ultimos_brix=float(ultima_lectura.brix) if ultima_lectura and ultima_lectura.brix is not None else None,
        ultimo_ph=float(ultima_lectura.ph) if ultima_lectura and ultima_lectura.ph is not None else None,
        ultima_lectura_timestamp=ultima_lectura.timestamp if ultima_lectura else None,

        # Predicción IA / ML
        prediccion_ml=prediccion_ml
    )


@router.get("", response_model=List[CubaOut], summary="Listar todas las cubas con telemetría en tiempo real")
def listar_cubas(response: Response, db: Session = Depends(get_db)):
    """Lista todas las cubas de la bodega con su última lectura de sensores registrada e inferencia IA."""
    # Cabeceras explícitas para evitar que los navegadores almacenen en caché el polling
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    cubas = db.query(Cuba).order_by(Cuba.id.asc()).all()
    resultado = []
    
    for c in cubas:
        # Buscar proceso de fermentación activo en la cuba (estado: 'en_proceso')
        proceso_activo = (
            db.query(ProcesoFermentacion)
            .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
            .order_by(desc(ProcesoFermentacion.id))
            .first()
        )

        ultima_lectura = None
        pred_ml = None
        if proceso_activo:
            ultima_lectura = (
                db.query(LecturaTelemetria)
                .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
                .order_by(desc(LecturaTelemetria.id))
                .first()
            )
            pred_ml = _calcular_prediccion_ml(db, proceso_activo.id)

        resultado.append(_mapear_cuba_out(c, proceso_activo, ultima_lectura, pred_ml))
        
    return resultado


@router.get("/{cuba_id}", response_model=CubaOut, summary="Obtener detalle de una cuba por ID")
def obtener_cuba(cuba_id: int, response: Response, db: Session = Depends(get_db)):
    """Obtiene el estado detallado de una cuba, sus sensores y predicción de IA."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )

    ultima_lectura = None
    pred_ml = None
    if proceso_activo:
        ultima_lectura = (
            db.query(LecturaTelemetria)
            .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
            .order_by(desc(LecturaTelemetria.id))
            .first()
        )
        pred_ml = _calcular_prediccion_ml(db, proceso_activo.id)

    return _mapear_cuba_out(c, proceso_activo, ultima_lectura, pred_ml)


@router.get("/{cuba_id}/historico", response_model=HistoricoCubaOut, summary="Curvas históricas de telemetría (para Chart.js)")
def obtener_historico_cuba(
    cuba_id: int,
    rango_horas: int = Query(24, description="Ventana de tiempo en horas (24, 48, 168)"),
    db: Session = Depends(get_db)
):
    """
    Entrega series temporales de temperatura de vino, grados Brix y pH
    listas para renderizar en los gráficos de Chart.js en CubaDetailView.vue.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    # Buscar el proceso activo de fermentación para esta cuba
    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )

    # Si la cuba no tiene un proceso activo, retornar datasets vacíos de forma segura
    if not proceso_activo:
        return HistoricoCubaOut(
            cuba_id=c.id,
            nombre_cuba=f"Cuba {c.codigo}",
            proceso_id=None,
            rango_horas=rango_horas,
            total_muestras=0,
            timestamps=[],
            temperaturas_vino=[],
            grados_brix=[],
            valores_ph=[],
            labels=[],
            temp=[],
            brix=[]
        )

    desde_tiempo = datetime.utcnow() - timedelta(hours=rango_horas)

    # Filtrar por proceso activo y ventana temporal solicitada
    lecturas = (
        db.query(LecturaTelemetria)
        .filter(
            LecturaTelemetria.fermentacion_id == proceso_activo.id,
            LecturaTelemetria.timestamp >= desde_tiempo
        )
        .order_by(desc(LecturaTelemetria.timestamp))
        .limit(200)
        .all()
    )

    # Si no hay lecturas dentro de la ventana exacta (entorno local o pruebas),
    # obtener las más recientes del proceso para visualización continua
    if not lecturas:
        lecturas = (
            db.query(LecturaTelemetria)
            .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
            .order_by(desc(LecturaTelemetria.timestamp))
            .limit(50)
            .all()
        )

    # Ordenar cronológicamente (de izquierda a derecha para Chart.js)
    lecturas = list(reversed(lecturas))

    # Formateo de marcas temporales: horario si es <= 24h, fecha/hora si es mayor
    formato_fecha = "%H:%M:%S" if rango_horas <= 24 else "%d/%m %H:%M"
    timestamps_list = [l.timestamp.strftime(formato_fecha) if l.timestamp else "" for l in lecturas]
    temp_list = [float(l.temp_mosto) if l.temp_mosto is not None else None for l in lecturas]
    brix_list = [float(l.brix) if l.brix is not None else None for l in lecturas]
    ph_list = [float(l.ph) if l.ph is not None else None for l in lecturas]

    return HistoricoCubaOut(
        cuba_id=c.id,
        nombre_cuba=f"Cuba {c.codigo}",
        proceso_id=proceso_activo.id,
        rango_horas=rango_horas,
        total_muestras=len(lecturas),
        timestamps=timestamps_list,
        temperaturas_vino=temp_list,
        grados_brix=brix_list,
        valores_ph=ph_list,
        labels=timestamps_list,
        temp=temp_list,
        brix=brix_list
    )


@router.get("/{cuba_id}/ml-prediction", response_model=MLPredictionOut, summary="Predicción de Machine Learning para parada de fermentación")
def obtener_prediccion_ml(cuba_id: int, response: Response, db: Session = Depends(get_db)):
    """
    Retorna la inferencia en tiempo real del modelo GradientBoostingClassifier para la cuba especificada,
    incluyendo porcentaje de riesgo, clasificación de severidad y métricas de cinética de fermentación.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )
    if not proceso_activo:
        return MLPredictionOut(
            riesgo_pct=0.0,
            estado_ia="RECOLECTANDO_DATOS",
            alerta_ia=False,
            mensaje="Cuba sin proceso de fermentación activo"
        )

    pred = _calcular_prediccion_ml(db, proceso_activo.id)
    return pred or MLPredictionOut(
        riesgo_pct=0.0,
        estado_ia="RECOLECTANDO_DATOS",
        alerta_ia=False,
        mensaje="Datos insuficientes para predicción"
    )


@router.post("/{cuba_id}/simular-anomalia", response_model=SimulacionAnomaliaOut, summary="Inyectar escenario de parada de fermentación para demo en vivo")
def simular_anomalia_parada(cuba_id: int, db: Session = Depends(get_db)):
    """
    Inyecta una secuencia de telemetría con consumo de azúcar estancado (~14.5 °Bx) y alta temperatura (~31.5 °C - 32.5 °C)
    para provocar que el modelo de Machine Learning clasifique estado CRITICO (riesgo >= 70%) y
    despache automáticamente la alerta correspondiente.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )
    if not proceso_activo:
        ahora = datetime.utcnow()
        proceso_activo = ProcesoFermentacion(
            cuba_id=c.id,
            volumen_litros=8500.0,
            brix_inicial=24.0,
            brix_objetivo=2.0,
            densidad_inicial_sg=1.0960,
            estado="en_proceso",
            fecha_inicio=ahora,
            fecha_estimada_fin=ahora + timedelta(days=14),
            creado_en=ahora
        )
        db.add(proceso_activo)
        db.commit()
        db.refresh(proceso_activo)

    ahora = datetime.utcnow()
    dispositivo_id = _resolver_dispositivo_cuba(db, c.id)
    lecturas_creadas = []
    
    # 8 lecturas estancadas: Brix ~ 14.5 °Bx y Temp subiendo a ~32.5 °C
    temp_escalones = [28.5, 29.5, 30.2, 30.9, 31.5, 31.8, 32.2, 32.6]
    for i, t_val in enumerate(temp_escalones):
        ts = ahora - timedelta(minutes=(len(temp_escalones) - 1 - i) * 2)
        brix_val = round(14.50 + random.gauss(0.0, 0.02), 2)
        temp_val = round(t_val + random.gauss(0.0, 0.08), 2)
        
        lectura = LecturaTelemetria(
            dispositivo_id=dispositivo_id,
            fermentacion_id=proceso_activo.id,
            timestamp=ts,
            temp_mosto=temp_val,
            temp_ambiente=22.5,
            densidad_sg=round(1.0000 + (brix_val * 0.0039), 4),
            brix=brix_val,
            ph=3.42,
            origen_dato="simulacion_anomalia_ia",
            lectura_valida=True
        )
        db.add(lectura)
        lecturas_creadas.append(lectura)

    db.commit()

    # Procesar alertas en el motor de reglas con la última lectura
    ultima = lecturas_creadas[-1]
    db.refresh(ultima)
    rules_engine.procesar_alertas_lectura(
        db=db,
        lectura=ultima,
        cuba_id=c.id,
        dispositivo_id=dispositivo_id
    )

    prediccion = _calcular_prediccion_ml(db, proceso_activo.id)

    return SimulacionAnomaliaOut(
        status="ok",
        mensaje="Escenario de parada de fermentación inyectado exitosamente.",
        cuba_id=c.id,
        proceso_id=proceso_activo.id,
        lecturas_inyectadas=len(lecturas_creadas),
        prediccion_ml=prediccion
    )


@router.post("/{cuba_id}/restaurar-normalidad", summary="Restaurar cinética normal de fermentación para resetear la demo")
def restaurar_normalidad_cuba(cuba_id: int, db: Session = Depends(get_db)):
    """
    Inyecta lecturas con cinética saludable (caída sostenida de Brix a ~22 °C)
    y resuelve las alertas pendientes de parada de fermentación para restaurar la cuba.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id, ProcesoFermentacion.estado == "en_proceso")
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )
    if not proceso_activo:
        raise HTTPException(status_code=400, detail="La cuba no tiene un proceso activo")

    ahora = datetime.utcnow()
    dispositivo_id = _resolver_dispositivo_cuba(db, c.id)
    # Inyectar 8 lecturas con caída saludable de Brix (ej: 18.0 -> 14.5) y temperatura óptima (22.0 °C)
    brix_escalones = [18.0, 17.5, 17.0, 16.5, 16.0, 15.5, 15.0, 14.5]
    for i, b_val in enumerate(brix_escalones):
        ts = ahora - timedelta(minutes=(len(brix_escalones) - 1 - i) * 2)
        lectura = LecturaTelemetria(
            dispositivo_id=dispositivo_id,
            fermentacion_id=proceso_activo.id,
            timestamp=ts,
            temp_mosto=round(22.0 + random.gauss(0.0, 0.15), 2),
            temp_ambiente=20.5,
            densidad_sg=round(1.0000 + (b_val * 0.0039), 4),
            brix=round(b_val + random.gauss(0.0, 0.03), 2),
            ph=3.40,
            origen_dato="restauracion_normalidad",
            lectura_valida=True
        )
        db.add(lectura)

    # Resolver alertas pendientes de parada
    alertas_parada = (
        db.query(EventoAlerta)
        .filter(
            EventoAlerta.fermentacion_id == proceso_activo.id,
            EventoAlerta.tipo_alerta == "parada_fermentacion",
            EventoAlerta.estado == "pendiente"
        )
        .all()
    )
    for a in alertas_parada:
        a.estado = "resuelta"
        a.fecha_resolucion = ahora
        a.nota_resolucion = "Cinética normalizada tras intervención enológica correctiva."

    db.commit()

    prediccion = _calcular_prediccion_ml(db, proceso_activo.id)
    return {
        "status": "ok",
        "mensaje": "Cinética saludable restaurada con éxito",
        "cuba_id": c.id,
        "prediccion_ml": prediccion
    }
