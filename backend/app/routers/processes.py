"""
Router de Ciclo de Vida de Procesos de Fermentación (Vendimia).
Permite iniciar nuevos procesos en cubas disponibles y finalizar procesos en curso.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Cuba, ProcesoFermentacion, PerfilFermentacion, Cepa, LecturaTelemetria
from app.schemas import ProcesoIniciarIn, ProcesoFinalizarIn, ProcesoOut

router = APIRouter(prefix="/api/procesos", tags=["Procesos de Fermentación"])


def _mapear_proceso_out(p: ProcesoFermentacion) -> ProcesoOut:
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

    # Obtener última densidad registrada en telemetría si existe
    densidad_final = float(p.densidad_inicial_sg) if p.densidad_inicial_sg is not None else None
    if p.lecturas:
        ultima_lectura = sorted(p.lecturas, key=lambda l: l.timestamp or datetime.min, reverse=True)[0]
        if ultima_lectura.densidad_sg is not None:
            densidad_final = float(ultima_lectura.densidad_sg)

    return ProcesoOut(
        id=p.id,
        cuba_id=p.cuba_id,
        codigo_cuba=p.cuba.codigo if p.cuba else None,
        perfil_id=p.perfil_id,
        perfil_nombre=perfil_nombre,
        cepa_nombre=cepa_nombre,
        volumen_litros=float(p.volumen_litros) if p.volumen_litros is not None else None,
        brix_inicial=float(p.brix_inicial) if p.brix_inicial is not None else None,
        brix_objetivo=float(p.brix_objetivo) if p.brix_objetivo is not None else None,
        densidad_inicial_sg=float(p.densidad_inicial_sg) if p.densidad_inicial_sg is not None else None,
        densidad_final_sg=densidad_final,
        estado=p.estado,
        fecha_inicio=p.fecha_inicio,
        fecha_estimada_fin=p.fecha_estimada_fin,
        fecha_real_fin=p.fecha_real_fin,
        dia_fermentacion=dia_ferm
    )


@router.get("", response_model=List[ProcesoOut], summary="Listar procesos de fermentación")
def listar_procesos(
    cuba_id: Optional[int] = Query(None, description="Filtrar por ID de cuba"),
    estado: Optional[str] = Query(None, description="Filtrar por estado: 'en_proceso', 'finalizada'"),
    db: Session = Depends(get_db)
):
    """Lista todos los procesos de fermentación registrados con filtros opcionales."""
    query = db.query(ProcesoFermentacion)
    if cuba_id:
        query = query.filter(ProcesoFermentacion.cuba_id == cuba_id)
    if estado:
        query = query.filter(ProcesoFermentacion.estado == estado)

    procesos = query.order_by(desc(ProcesoFermentacion.id)).all()
    return [_mapear_proceso_out(p) for p in procesos]


@router.get("/{proceso_id}", response_model=ProcesoOut, summary="Obtener detalle de un proceso")
def obtener_proceso(proceso_id: int, db: Session = Depends(get_db)):
    """Retorna el detalle completo de un proceso de fermentación por ID."""
    p = db.query(ProcesoFermentacion).filter(ProcesoFermentacion.id == proceso_id).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"Proceso con ID {proceso_id} no encontrado")
    return _mapear_proceso_out(p)


@router.post("/iniciar", response_model=ProcesoOut, status_code=201, summary="Iniciar nuevo proceso de vendimia")
def iniciar_proceso(payload: ProcesoIniciarIn, db: Session = Depends(get_db)):
    """
    Inicia un nuevo proceso de fermentación:
    1. Valida que la cuba exista.
    2. Impide iniciar si la cuba ya tiene un proceso activo ('en_proceso').
    3. Valida que el volumen no supere la capacidad de la cuba (trigger fn_validar_proceso).
    4. Valida consistencia de bodega entre el perfil y la cuba.
    5. Actualiza el estado operativo de la cuba a 'en_uso'.
    """
    # 1. Validar cuba
    cuba = db.query(Cuba).filter(Cuba.id == payload.cuba_id).first()
    if not cuba:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {payload.cuba_id} no encontrada")

    # 2. Validar que la cuba no tenga proceso activo
    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(
            ProcesoFermentacion.cuba_id == cuba.id,
            ProcesoFermentacion.estado == "en_proceso"
        )
        .first()
    )
    if proceso_activo:
        raise HTTPException(
            status_code=400,
            detail=f"La Cuba {cuba.codigo} ya tiene un proceso activo (ID {proceso_activo.id}). Debe finalizarlo antes de iniciar uno nuevo."
        )

    # 3. Validar capacidad de la cuba vs volumen de vendimia
    cap_max = float(cuba.cap_litros) if cuba.cap_litros else 10000.0
    if payload.volumen_litros > cap_max:
        raise HTTPException(
            status_code=400,
            detail=f"El volumen ingresado ({payload.volumen_litros} L) supera la capacidad máxima de la cuba ({cap_max} L)."
        )

    # 4. Validar o resolver Perfil de Fermentación
    perfil = None
    if payload.perfil_id:
        perfil = db.query(PerfilFermentacion).filter(PerfilFermentacion.id == payload.perfil_id).first()
        if not perfil:
            raise HTTPException(status_code=404, detail=f"Perfil con ID {payload.perfil_id} no encontrado")
        if perfil.bodega_id != cuba.bodega_id:
            raise HTTPException(
                status_code=400,
                detail=f"El perfil pertenece a la bodega {perfil.bodega_id}, distinta a la bodega de la cuba ({cuba.bodega_id})."
            )
    elif payload.cepa_id:
        perfil = (
            db.query(PerfilFermentacion)
            .filter(
                PerfilFermentacion.bodega_id == cuba.bodega_id,
                PerfilFermentacion.cepa_id == payload.cepa_id
            )
            .first()
        )
        if not perfil:
            cepa = db.query(Cepa).filter(Cepa.id == payload.cepa_id).first()
            nomb = f"Perfil {cepa.nombre_variedad}" if cepa else "Perfil Estándar"
            perfil = PerfilFermentacion(
                nomb_perfil=nomb,
                bodega_id=cuba.bodega_id,
                cepa_id=payload.cepa_id,
                temp_min=16.0,
                temp_max=26.0,
                brix_caida_min_dia=1.5,
                ph_min=3.2,
                ph_max=3.8,
                activo=True
            )
            db.add(perfil)
            db.flush()
    else:
        perfil = db.query(PerfilFermentacion).filter(PerfilFermentacion.bodega_id == cuba.bodega_id).first()
        if not perfil:
            perfil = PerfilFermentacion(
                nomb_perfil="Perfil Fermentación Estándar",
                bodega_id=cuba.bodega_id,
                temp_min=16.0,
                temp_max=26.0,
                brix_caida_min_dia=1.5,
                ph_min=3.2,
                ph_max=3.8,
                activo=True
            )
            db.add(perfil)
            db.flush()

    ahora = datetime.utcnow()
    dias_est = payload.dias_estimados or 14
    estimada_fin = ahora + timedelta(days=dias_est)

    nuevo_proceso = ProcesoFermentacion(
        cuba_id=cuba.id,
        perfil_id=perfil.id if perfil else None,
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

    return _mapear_proceso_out(nuevo_proceso)


@router.patch("/{proceso_id}/finalizar", response_model=ProcesoOut, summary="Finalizar proceso y liberar cuba")
def finalizar_proceso(
    proceso_id: int,
    payload: Optional[ProcesoFinalizarIn] = None,
    db: Session = Depends(get_db)
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

    if proceso.estado != "en_proceso":
        raise HTTPException(
            status_code=400,
            detail=f"El proceso se encuentra en estado '{proceso.estado}', no puede ser finalizado nuevamente."
        )

    proceso.estado = "finalizada"
    proceso.fecha_real_fin = datetime.utcnow()

    # Liberar la cuba
    cuba = db.query(Cuba).filter(Cuba.id == proceso.cuba_id).first()
    if cuba:
        cuba.estado_operativo = "disponible"

    db.commit()
    db.refresh(proceso)

    return _mapear_proceso_out(proceso)
