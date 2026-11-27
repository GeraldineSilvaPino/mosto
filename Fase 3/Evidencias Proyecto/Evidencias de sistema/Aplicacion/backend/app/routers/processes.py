"""
Router de Ciclo de Vida de Procesos de Fermentación (Vendimia).
Permite iniciar nuevos procesos en cubas disponibles y finalizar procesos en curso.
"""
from typing import List, Optional, Literal
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, select

from app.services.access import business_db, actor_id
from app.services.telemetry_v2 import aware
from app.models import Cuba, ProcesoFermentacion, PerfilFermentacion, Cepa, LecturaTelemetria
from app.schemas import ProcesoIniciarIn, ProcesoFinalizarIn, ProcesoOut
from app.services.kinetic_episodes import KineticRuleConfig, CODE, rule_status

router = APIRouter(prefix="/api/procesos", tags=["Procesos de Fermentación"])


@router.get("/{proceso_id}/cinetica", summary="Cinética causal de Brix aparente, sin riesgo validado")
def obtener_cinetica(proceso_id: int, response: Response,
                     as_of: Optional[AwareDatetime] = None,
                     db: Session = Depends(business_db("operations"))):
    from app.services.kinetics_query import kinetic_window, summarize_kinetics
    from app.services.telemetry_v2 import aware, utc_now

    process = db.query(ProcesoFermentacion).filter_by(id=proceso_id).first()
    if process is None:
        raise HTTPException(404, "Proceso no encontrado")
    now = utc_now()
    cutoff = aware(as_of) if as_of else now
    if cutoff > now or cutoff < aware(process.fecha_inicio):
        raise HTTPException(422, "Instante fuera del historial disponible del proceso")
    response.headers["Cache-Control"] = "no-store"
    from app.services.simulation_time import process_clock_at, observation_end
    clock = process_clock_at(db, process.id, cutoff)
    observation = observation_end(process, cutoff, clock)
    rows = kinetic_window(db, process, observation, cutoff)
    result = summarize_kinetics(process, rows, observation, cutoff)
    result.update(as_of=result["received_as_of"], observation_as_of=observation.isoformat(),
                  simulation_clock=clock.model_dump(mode="json") if clock else None)
    # Configuration/lifecycle is current, explicitly separate from the historical snapshot.
    result["current_kinetic_rule"] = rule_status(db, process.id)
    from app.services.monitoring import monitoring_status
    result["current_monitoring"] = monitoring_status(db, process, now)
    from app.services.process_series import descriptive_metrics
    result["display"] = descriptive_metrics(db, process, observation, cutoff, rows)
    return result


@router.post("/{proceso_id}/regla-cinetica", summary="Activar regla cinética experimental para simulación")
def configurar_regla_cinetica(proceso_id: int, payload: KineticRuleConfig, response: Response,
                             db: Session = Depends(business_db("kinetic_rules"))):
    from app import models as m
    from app.services.access import actor_id
    from app.services.demo_access import require_demo_mode
    from app.services.telemetry_v2 import utc_now

    require_demo_mode()
    process = db.query(ProcesoFermentacion).filter_by(id=proceso_id).first()
    if process is None:
        raise HTTPException(404, "Proceso no encontrado")
    # Same lock as ingestion and closure; configuration cannot race their writes.
    db.query(Cuba).filter_by(id=process.cuba_id).with_for_update().one()
    db.refresh(process)
    if process.fecha_real_fin is not None:
        raise HTTPException(409, "El proceso está cerrado")
    sources = {r[0] for r in db.query(m.MensajeTelemetria.origen).filter_by(fermentacion_id=process.id).distinct()}
    devices = db.query(m.Dispositivo).join(m.AsignacionDispositivo).filter(
        m.AsignacionDispositivo.cuba_id == process.cuba_id, m.AsignacionDispositivo.activo.is_(True)).all()
    if sources - {"simulado"} or not devices or any(d.origen != "simulado" for d in devices):
        raise HTTPException(409, "La regla experimental requiere un proceso y dispositivos exclusivamente simulados")
    config = payload.model_dump()
    state = db.query(m.EstadoRegla).filter_by(fermentacion_id=process.id, codigo=CODE).first()
    if state:
        if any(state.configuracion.get(key) != value for key, value in config.items()):
            raise HTTPException(409, "La configuración está congelada para este proceso; usar un nuevo proceso para otra configuración")
    else:
        now = utc_now()
        from app.services.simulation_time import process_clock_at, observation_end
        watermark = observation_end(process, now, process_clock_at(db, process.id, now))
        state = m.EstadoRegla(fermentacion_id=process.id, codigo=CODE, ultima_observacion=watermark,
            configuracion={**config, "configured_at": now.isoformat(), "configured_by": actor_id(db),
                           "profile_id": process.perfil_id})
        db.add(state)
        db.commit()
        response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return rule_status(db, process.id)


def _procesos_con_detalle(query):
    densidad = (select(LecturaTelemetria.densidad_sg)
        .where(LecturaTelemetria.fermentacion_id == ProcesoFermentacion.id)
        .order_by(LecturaTelemetria.timestamp.desc().nullslast(), LecturaTelemetria.id.desc())
        .limit(1).correlate(ProcesoFermentacion).scalar_subquery())
    return query.add_columns(densidad).options(
        joinedload(ProcesoFermentacion.cuba),
        joinedload(ProcesoFermentacion.perfil).joinedload(PerfilFermentacion.cepa))


def _mapear_proceso_out(p: ProcesoFermentacion, ultima_densidad) -> ProcesoOut:
    """Helper para transformar la entidad ProcesoFermentacion al DTO ProcesoOut."""
    dia_ferm = None
    if p.fecha_inicio:
        delta = (datetime.utcnow().date() - p.fecha_inicio.date()).days
        dia_ferm = max(1, delta + 1)

    cepa_nombre = None
    perfil_nombre = None
    if p.perfil:
        perfil_nombre = p.perfil.nomb_perfil
        if p.perfil.cepa:
            cepa_nombre = p.perfil.cepa.nombre_variedad

    densidad_final = p.densidad_inicial_sg if ultima_densidad is None else ultima_densidad

    return ProcesoOut(
        id=p.id,
        cuba_id=p.cuba_id,
        codigo_cuba=p.cuba.codigo if p.cuba else None,
        perfil_id=p.perfil_id,
        perfil_nombre=p.perfil_snapshot.get("nomb_perfil") if p.perfil_snapshot else perfil_nombre,
        perfil_snapshot=p.perfil_snapshot,
        cepa_nombre=cepa_nombre,
        volumen_litros=float(p.volumen_litros) if p.volumen_litros is not None else None,
        brix_inicial=float(p.brix_inicial) if p.brix_inicial is not None else None,
        brix_objetivo=float(p.brix_objetivo) if p.brix_objetivo is not None else None,
        densidad_inicial_sg=float(p.densidad_inicial_sg) if p.densidad_inicial_sg is not None else None,
        densidad_final_sg=densidad_final,
        estado=p.estado,
        fecha_inicio=aware(p.fecha_inicio) if p.fecha_inicio else None,
        fecha_estimada_fin=aware(p.fecha_estimada_fin) if p.fecha_estimada_fin else None,
        fecha_real_fin=aware(p.fecha_real_fin) if p.fecha_real_fin else None,
        dia_fermentacion=dia_ferm
    )


@router.get("", response_model=List[ProcesoOut], summary="Listar procesos de fermentación")
def listar_procesos(
    cuba_id: Optional[int] = Query(None, description="Filtrar por ID de cuba"),
    estado: Optional[str] = Query(None, description="Filtrar por estado: 'en_proceso', 'finalizada'"),
    db: Session = Depends(business_db("operations"))
):
    """Lista todos los procesos de fermentación registrados con filtros opcionales."""
    query = db.query(ProcesoFermentacion)
    if cuba_id:
        query = query.filter(ProcesoFermentacion.cuba_id == cuba_id)
    if estado:
        query = query.filter(ProcesoFermentacion.estado == estado)

    procesos = _procesos_con_detalle(query).order_by(desc(ProcesoFermentacion.id)).all()
    return [_mapear_proceso_out(*fila) for fila in procesos]


@router.get("/pagina", summary="Procesos autorizados, paginados sin alterar el listado legacy")
def pagina_procesos(response: Response, cuba_id: int | None = Query(None, gt=0),
                    grupo: Literal['todos', 'activos', 'cerrados'] = 'todos',
                    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                    db: Session = Depends(business_db('operations'))):
    query = db.query(ProcesoFermentacion)
    if cuba_id is not None:
        if db.query(Cuba.id).filter_by(id=cuba_id).first() is None:
            raise HTTPException(404, 'Cuba inexistente o fuera del ámbito autorizado')
        query = query.filter(ProcesoFermentacion.cuba_id == cuba_id)
    active = ProcesoFermentacion.estado.in_(['en_proceso', 'detenida'])
    if grupo == 'activos':
        query = query.filter(active)
    elif grupo == 'cerrados':
        query = query.filter(~active)
    total = query.count()
    pagina = _procesos_con_detalle(query).order_by(desc(ProcesoFermentacion.id)).offset(offset).limit(limit)
    items = [_mapear_proceso_out(*fila) for fila in pagina]
    response.headers['Cache-Control'] = 'no-store'
    return dict(items=items, total=total, limit=limit, offset=offset,
                has_more=offset + len(items) < total)


@router.get("/{proceso_id}", response_model=ProcesoOut, summary="Obtener detalle de un proceso")
def obtener_proceso(proceso_id: int, db: Session = Depends(business_db("operations"))):
    """Retorna el detalle completo de un proceso de fermentación por ID."""
    fila = _procesos_con_detalle(db.query(ProcesoFermentacion)).filter(ProcesoFermentacion.id == proceso_id).first()
    if not fila:
        raise HTTPException(status_code=404, detail=f"Proceso con ID {proceso_id} no encontrado")
    return _mapear_proceso_out(*fila)


@router.post("/iniciar", response_model=ProcesoOut, status_code=201, summary="Iniciar nuevo proceso de vendimia")
def iniciar_proceso(payload: ProcesoIniciarIn, db: Session = Depends(business_db("operations"))):
    """
    Inicia un nuevo proceso de fermentación:
    1. Valida que la cuba exista.
    2. Impide iniciar si la cuba ya tiene un proceso activo ('en_proceso').
    3. Valida que el volumen no supere la capacidad de la cuba (trigger fn_validar_proceso).
    4. Valida consistencia de bodega entre el perfil y la cuba.
    5. Actualiza el estado operativo de la cuba a 'en_uso'.
    """
    # 1. Validar cuba
    cuba = db.query(Cuba).filter(Cuba.id == payload.cuba_id).with_for_update().first()
    if not cuba:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {payload.cuba_id} no encontrada")

    # 2. Validar que la cuba no tenga proceso activo
    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(
            ProcesoFermentacion.cuba_id == cuba.id,
            ProcesoFermentacion.estado.in_(["en_proceso", "detenida"])
        )
        .first()
    )
    if proceso_activo:
        raise HTTPException(
            status_code=400,
            detail=f"La Cuba {cuba.codigo} ya tiene un proceso activo (ID {proceso_activo.id}). Debe finalizarlo antes de iniciar uno nuevo."
        )

    # 3. Validar capacidad de la cuba vs volumen de vendimia
    if cuba.estado_operativo != "disponible":
        raise HTTPException(409, "La cuba no está disponible para iniciar un proceso")
    if cuba.cap_litros is None:
        raise HTTPException(409, "La capacidad de la cuba debe estar configurada")
    cap_max = float(cuba.cap_litros)
    if payload.volumen_litros > cap_max:
        raise HTTPException(
            status_code=400,
            detail=f"El volumen ingresado ({payload.volumen_litros} L) supera la capacidad máxima de la cuba ({cap_max} L)."
        )

    # Los perfiles se configuran explícitamente por un enólogo o administrador.
    query = db.query(PerfilFermentacion).filter(
        PerfilFermentacion.bodega_id == cuba.bodega_id,
        PerfilFermentacion.activo.is_(True))
    if payload.perfil_id:
        query = query.filter(PerfilFermentacion.id == payload.perfil_id)
    elif payload.cepa_id:
        query = query.filter(PerfilFermentacion.cepa_id == payload.cepa_id)
    candidates = query.with_for_update().limit(2).all()
    if not candidates:
        raise HTTPException(404, "No hay un perfil activo autorizado para esta cuba")
    if len(candidates) != 1:
        raise HTTPException(422, "Debe seleccionar explícitamente el perfil de fermentación")
    perfil = candidates[0]
    from app.services.profile_versions import record_version
    frozen_profile = record_version(db, perfil).configuracion

    ahora = datetime.utcnow()
    dias_est = payload.dias_estimados or 14
    estimada_fin = ahora + timedelta(days=dias_est)

    nuevo_proceso = ProcesoFermentacion(
        cuba_id=cuba.id,
        perfil_id=perfil.id if perfil else None,
        perfil_snapshot=dict(frozen_profile),
        volumen_litros=payload.volumen_litros,
        brix_inicial=payload.brix_inicial or 24.5,
        brix_objetivo=payload.brix_objetivo or 1.0,
        densidad_inicial_sg=payload.densidad_inicial_sg or 1.1000,
        estado="en_proceso",
        fecha_inicio=ahora,
        fecha_estimada_fin=estimada_fin
    )
    db.add(nuevo_proceso)

    # Actualizar estado operativo de la cuba
    cuba.estado_operativo = "en_uso"

    db.commit()
    db.refresh(nuevo_proceso)

    return obtener_proceso(nuevo_proceso.id, db)


@router.patch("/{proceso_id}/finalizar", response_model=ProcesoOut, summary="Finalizar proceso y liberar cuba")
def finalizar_proceso(
    proceso_id: int,
    payload: Optional[ProcesoFinalizarIn] = None,
    db: Session = Depends(business_db("operations"))
):
    """
    Finaliza un proceso de fermentación:
    1. Marca el estado como 'finalizada'.
    2. Registra la fecha real de fin.
    3. Cambia el estado operativo de la cuba a 'disponible'.
    """
    proceso = db.query(ProcesoFermentacion).filter(ProcesoFermentacion.id == proceso_id).first()
    if not proceso:
        raise HTTPException(status_code=404, detail=f"Proceso con ID {proceso_id} no encontrado")

    # All process lifecycle writes lock tank first, then re-read the process.
    cuba = db.query(Cuba).filter(Cuba.id == proceso.cuba_id).with_for_update().first()
    db.refresh(proceso)
    if proceso.estado not in ("en_proceso", "detenida"):
        raise HTTPException(
            status_code=400,
            detail=f"El proceso se encuentra en estado '{proceso.estado}', no puede ser finalizado nuevamente."
        )

    proceso.estado = "finalizada"
    proceso.fecha_real_fin = datetime.utcnow()
    from app.services.episodes import close_process_conditions
    close_process_conditions(db, proceso, actor_id(db))

    # Liberar la cuba
    cuba = db.query(Cuba).filter(Cuba.id == proceso.cuba_id).first()
    if cuba:
        cuba.estado_operativo = "disponible"

    db.commit()
    db.refresh(proceso)

    return obtener_proceso(proceso.id, db)
