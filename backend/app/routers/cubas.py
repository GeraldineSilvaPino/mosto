"""
Router de Cubas para consulta del Frontend (Dashboard, CubaDetail).
Controlador REST para monitoreo en tiempo real y curvas de fermentación.
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import random
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from pydantic import AwareDatetime

from app.services.demo_access import require_demo_mode, require_legacy_tank
from app.services.access import business_db
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
from app.models import MensajeTelemetria
from app.schemas import CubaOut, LecturaOut, HistoricoCubaOut, MLPredictionOut, SimulacionAnomaliaOut
from app.services.ml_service import evaluar_riesgo_parada_cuba, evaluar_proceso_cinetica
from app.services.rules_engine import rules_engine
from app.services.telemetry_v2 import aware, utc_now

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

    disp = db.query(Dispositivo).filter(Dispositivo.origen.is_(None)).first()
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
    """Calcula la predicción cinético-enológica sobre la telemetría del proceso."""
    if not proceso_id:
        return None
    if db.query(MensajeTelemetria.id).filter_by(fermentacion_id=proceso_id).first():
        pred_cinetica = evaluar_proceso_cinetica(db, proceso_id)
        if pred_cinetica:
            return MLPredictionOut(**pred_cinetica)

    lecturas = (
        db.query(LecturaTelemetria)
        .filter(
            LecturaTelemetria.fermentacion_id == proceso_id,
            LecturaTelemetria.timestamp <= utc_now(),
            LecturaTelemetria.lectura_valida.is_(True),
            LecturaTelemetria.brix.isnot(None),
            LecturaTelemetria.temp_mosto.isnot(None)
        )
        .order_by(desc(LecturaTelemetria.timestamp), desc(LecturaTelemetria.id))
        .limit(17)
        .all()
    )

    if not lecturas:
        return MLPredictionOut(
            riesgo_pct=None,
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
    # A deterministic trailing average of overlapping model windows, based on
    # samples rather than requests. Refreshing cannot advance the displayed risk.
    instant = pred['riesgo_pct']
    if len(lecturas_cron) >= 12 and instant is not None and pred['estado_ia'] != 'FINALIZADA':
        estimates = [evaluar_riesgo_parada_cuba(lecturas_brix[:end], lecturas_temp[:end])['riesgo_pct']
                     for end in range(max(12, len(lecturas_cron) - 5), len(lecturas_cron) + 1)]
        if all(value is not None for value in estimates):
            pred['riesgo_pct'] = round(sum(estimates) / len(estimates), 1)
            risk = pred['riesgo_pct']
            pred['estado_ia'] = 'CRITICO' if risk >= 70 else 'ADVERTENCIA' if risk >= 40 else 'NORMAL'
            pred['alerta_ia'] = risk >= 70
            pred['mensaje'] = 'Estimación experimental suavizada sobre ventanas de lecturas demo.'
    return MLPredictionOut(
        riesgo_instantaneo_pct=instant,
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
    prediccion_ml: Optional[MLPredictionOut] = None,
    db: Session = None
) -> CubaOut:
    """Helper para transformar la entidad Cuba y sus relaciones al DTO CubaOut."""
    variedad = None
    temp_min = None
    temp_max = None
    dia_ferm = None

    if proceso_activo:
        if proceso_activo.perfil:
            from app.services.profile_overrides import applied_profile
            from app.services.telemetry_v2 import utc_now
            applied = applied_profile(db, proceso_activo, proceso_activo.perfil, utc_now())
            temp_min = applied.get("temp_min")
            temp_max = applied.get("temp_max")
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
def listar_cubas(response: Response, db: Session = Depends(business_db("demo"))):
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
                .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id,
                        LecturaTelemetria.timestamp <= utc_now())
                .order_by(desc(LecturaTelemetria.timestamp), desc(LecturaTelemetria.id))
                .first()
            )
            pred_ml = _calcular_prediccion_ml(db, proceso_activo.id)

        resultado.append(_mapear_cuba_out(c, proceso_activo, ultima_lectura, pred_ml, db))
        
    return resultado


@router.get("/{cuba_id}", response_model=CubaOut, summary="Obtener detalle de una cuba por ID")
def obtener_cuba(cuba_id: int, response: Response, db: Session = Depends(business_db("demo"))):
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
            .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id,
                        LecturaTelemetria.timestamp <= utc_now())
            .order_by(desc(LecturaTelemetria.timestamp), desc(LecturaTelemetria.id))
            .first()
        )
        pred_ml = _calcular_prediccion_ml(db, proceso_activo.id)

    return _mapear_cuba_out(c, proceso_activo, ultima_lectura, pred_ml, db)


@router.get("/{cuba_id}/historico", response_model=HistoricoCubaOut, summary="Curvas históricas de telemetría (para Chart.js)")
def obtener_historico_cuba(
    cuba_id: int,
    rango_horas: int = Query(24, ge=1, le=168, description="Ventana de tiempo en horas, de 1 a 168"),
    as_of: AwareDatetime | None = None,
    db: Session = Depends(business_db("demo"))
):
    """
    Entrega series temporales de temperatura de vino, grados Brix y pH
    listas para renderizar en los gráficos de Chart.js en CubaDetailView.vue.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    now = utc_now()
    cutoff = aware(as_of) if as_of else now
    if cutoff > now:
        raise HTTPException(422, "El corte de disponibilidad no puede ser futuro")
    processes = db.query(ProcesoFermentacion).filter_by(cuba_id=c.id)
    if as_of is None:
        processes = processes.filter_by(estado="en_proceso")
    else:
        processes = processes.filter(ProcesoFermentacion.fecha_inicio <= cutoff,
            or_(ProcesoFermentacion.fecha_real_fin.is_(None), ProcesoFermentacion.fecha_real_fin > cutoff))
    proceso_activo = processes.order_by(desc(ProcesoFermentacion.id)).first()

    # Si la cuba no tiene un proceso activo, retornar datasets vacíos de forma segura
    if not proceso_activo:
        return HistoricoCubaOut(
            cuba_id=c.id,
            nombre_cuba=f"Cuba {c.codigo}",
            proceso_id=None,
            as_of=cutoff,
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

    from app.services.simulation_time import process_clock_at, observation_end
    clock = process_clock_at(db, proceso_activo.id, cutoff)
    hasta_tiempo = observation_end(proceso_activo, cutoff, clock)
    desde_tiempo = hasta_tiempo - timedelta(hours=rango_horas)

    # Filtrar por proceso activo y ventana temporal solicitada
    observed = func.coalesce(MensajeTelemetria.observado_en, LecturaTelemetria.timestamp)
    rows = db.query(observed.label("timestamp"), LecturaTelemetria.temp_mosto,
                    LecturaTelemetria.brix, LecturaTelemetria.ph).outerjoin(
        MensajeTelemetria, MensajeTelemetria.lectura_id == LecturaTelemetria.id).filter(
        LecturaTelemetria.fermentacion_id == proceso_activo.id, observed >= desde_tiempo, observed <= hasta_tiempo)
    available = MensajeTelemetria.recibido_en <= cutoff
    if as_of is None and clock is None:
        available = or_(available, MensajeTelemetria.id.is_(None))
    lecturas = rows.filter(available).order_by(observed.desc(), LecturaTelemetria.id.desc()).limit(10001).all()

    # Enough for the full seven-day v2 window (2016 samples). Higher-rate legacy
    # history is bounded explicitly, without silently pretending it is complete.
    truncated = len(lecturas) > 10000
    lecturas = lecturas[:10000]

    # Ordenar cronológicamente (de izquierda a derecha para Chart.js)
    lecturas = list(reversed(lecturas))

    # Formateo de marcas temporales: horario si es <= 24h, fecha/hora si es mayor
    formato_fecha = "%H:%M:%S" if rango_horas <= 24 else "%d/%m %H:%M"
    timestamps_list = [aware(l.timestamp).isoformat() for l in lecturas]
    labels_list = [aware(l.timestamp).strftime(formato_fecha) for l in lecturas]
    temp_list = [float(l.temp_mosto) if l.temp_mosto is not None else None for l in lecturas]
    brix_list = [float(l.brix) if l.brix is not None else None for l in lecturas]
    ph_list = [float(l.ph) if l.ph is not None else None for l in lecturas]

    return HistoricoCubaOut(
        cuba_id=c.id,
        nombre_cuba=f"Cuba {c.codigo}",
        proceso_id=proceso_activo.id,
        as_of=cutoff, observation_as_of=hasta_tiempo,
        simulation_clock=clock.model_dump(mode="json") if clock else None,
        rango_horas=rango_horas,
        total_muestras=len(lecturas),
        timestamps=timestamps_list,
        temperaturas_vino=temp_list,
        grados_brix=brix_list,
        valores_ph=ph_list,
        labels=labels_list,
        truncated=truncated,
        temp=temp_list,
        brix=brix_list
    )


@router.get("/{cuba_id}/ml-prediction", response_model=MLPredictionOut, summary="Predicción de Machine Learning para parada de fermentación")
def obtener_prediccion_ml(cuba_id: int, response: Response, db: Session = Depends(business_db("demo"))):
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
            riesgo_pct=None,
            estado_ia="RECOLECTANDO_DATOS",
            alerta_ia=False,
            mensaje="Cuba sin proceso de fermentación activo"
        )

    pred = _calcular_prediccion_ml(db, proceso_activo.id)
    return pred or MLPredictionOut(
        riesgo_pct=None,
        estado_ia="RECOLECTANDO_DATOS",
        alerta_ia=False,
        mensaje="Datos insuficientes para predicción"
    )


@router.post("/{cuba_id}/simular-anomalia", response_model=SimulacionAnomaliaOut, summary="Inyectar escenario de parada de fermentación para demo en vivo")
def simular_anomalia_parada(cuba_id: int, db: Session = Depends(business_db("demo")), _demo=Depends(require_demo_mode)):
    """
    Inyecta una secuencia de telemetría con consumo de azúcar estancado y alta temperatura
    para provocar que el modelo predictivo clasifique riesgo crítico y active las alertas enológicas.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    require_legacy_tank(db, c.id)
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
            fecha_inicio=ahora - timedelta(minutes=14),
            fecha_estimada_fin=ahora + timedelta(days=14),
            creado_en=ahora
        )
        db.add(proceso_activo)
        db.commit()
        db.refresh(proceso_activo)

    require_legacy_tank(db, c.id)
    ahora = datetime.utcnow()
    dispositivo_id = _resolver_dispositivo_cuba(db, c.id)
    lecturas_creadas = []
    temp_escalones = [29.0, 30.5, 31.8, 32.5, 33.2, 33.8, 34.5, 35.2]
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
    ultima = lecturas_creadas[-1]
    db.refresh(ultima)
    rules_engine.procesar_alertas_lectura(
        db=db,
        lectura=ultima,
        cuba_id=c.id,
        dispositivo_id=dispositivo_id
    )
    lecturas_count = len(lecturas_creadas)

    prediccion = _calcular_prediccion_ml(db, proceso_activo.id)

    return SimulacionAnomaliaOut(
        status="ok",
        mensaje="Escenario de desviación cinética inyectado exitosamente.",
        cuba_id=c.id,
        proceso_id=proceso_activo.id,
        lecturas_inyectadas=lecturas_count,
        prediccion_ml=prediccion
    )


@router.post("/{cuba_id}/restaurar-normalidad", summary="Restaurar cinética normal de fermentación para resetear la demo")
def restaurar_normalidad_cuba(cuba_id: int, db: Session = Depends(business_db("demo")), _demo=Depends(require_demo_mode)):
    """
    Inyecta lecturas con cinética saludable (caída sostenida de Brix a ~22 °C)
    y normaliza el proceso para restablecer la condición de la cuba.
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

    require_legacy_tank(db, c.id)
    ahora = datetime.utcnow()
    dispositivo_id = _resolver_dispositivo_cuba(db, c.id)
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
