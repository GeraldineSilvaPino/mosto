"""
Router de Perfiles de Fermentación y Bandas Térmicas / Acidez (TASK-BE-06B).
Controlador REST para configuración de umbrales enológicos (ThresholdsView.vue).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import PerfilFermentacion, Cepa, Bodega, ProcesoFermentacion
from app.schemas import PerfilCreateIn, PerfilUpdateIn, PerfilOut

router = APIRouter(prefix="/api/perfiles", tags=["Perfiles de Fermentación y Umbrales"])


def _mapear_perfil_out(p: PerfilFermentacion) -> PerfilOut:
    """Helper para transformar la entidad PerfilFermentacion al DTO PerfilOut."""
    t_min = float(p.temp_min) if p.temp_min is not None else 18.0
    t_max = float(p.temp_max) if p.temp_max is not None else 28.0

    return PerfilOut(
        id=p.id,
        nomb_perfil=p.nomb_perfil,
        temp_min=t_min,
        temp_max=t_max,
        ph_min=float(p.ph_min) if p.ph_min is not None else None,
        ph_max=float(p.ph_max) if p.ph_max is not None else None,
        brix_caida_min_dia=float(p.brix_caida_min_dia) if p.brix_caida_min_dia is not None else None,
        activo=bool(p.activo) if p.activo is not None else True,
        bodega_id=p.bodega_id,
        bodega_nombre=p.bodega.nombre if p.bodega else None,
        cepa_id=p.cepa_id,
        cepa_nombre=p.cepa.nombre_variedad if p.cepa else None,
        crit_min=round(t_min - 4.0, 1),
        crit_max=round(t_max + 3.0, 1)
    )


@router.get("", response_model=List[PerfilOut], summary="Listar perfiles de fermentación y bandas enológicas")
def listar_perfiles(
    cepa_id: Optional[int] = Query(None, description="Filtrar por cepa vinífera"),
    bodega_id: Optional[int] = Query(None, description="Filtrar por ID de bodega"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los perfiles de fermentación registrados, permitiendo filtrar por cepa o bodega.
    Entrega bandas óptimas y críticas para visualización gráfica en el frontend.
    """
    query = db.query(PerfilFermentacion)

    if isinstance(cepa_id, int):
        query = query.filter(PerfilFermentacion.cepa_id == cepa_id)

    if isinstance(bodega_id, int):
        query = query.filter(PerfilFermentacion.bodega_id == bodega_id)

    if isinstance(activo, bool):
        query = query.filter(PerfilFermentacion.activo == activo)

    perfiles = query.order_by(PerfilFermentacion.id.asc()).all()
    return [_mapear_perfil_out(p) for p in perfiles]


@router.get("/{perfil_id}", response_model=PerfilOut, summary="Obtener detalle de un perfil por ID")
def obtener_perfil(perfil_id: int, db: Session = Depends(get_db)):
    """Retorna la configuración detallada de un perfil de fermentación."""
    p = db.query(PerfilFermentacion).filter(PerfilFermentacion.id == perfil_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Perfil de fermentación con ID {perfil_id} no encontrado"
        )
    return _mapear_perfil_out(p)


@router.post("", response_model=PerfilOut, status_code=status.HTTP_201_CREATED, summary="Crear nuevo perfil de fermentación")
def crear_perfil(payload: PerfilCreateIn, db: Session = Depends(get_db)):
    """
    Crea un nuevo perfil enológico con sus bandas térmicas y de acidez:
    1. Valida que temp_min <= temp_max (restricción CHECK ck_perfil_temp).
    2. Valida que ph_min <= ph_max (restricción CHECK ck_perfil_ph).
    3. Valida la existencia de la cepa y la bodega si fueron proporcionadas.
    4. Persiste en la tabla PERFIL_FERMENTACION.
    """
    # 1. Validación estricta de rangos térmicos (ck_perfil_temp)
    if payload.temp_min > payload.temp_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inconsistencia térmica: temp_min ({payload.temp_min}°C) no puede ser mayor que temp_max ({payload.temp_max}°C) [ck_perfil_temp]."
        )

    # 2. Validación estricta de acidez (ck_perfil_ph)
    if payload.ph_min is not None and payload.ph_max is not None and payload.ph_min > payload.ph_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inconsistencia de acidez: ph_min ({payload.ph_min}) no puede ser mayor que ph_max ({payload.ph_max}) [ck_perfil_ph]."
        )

    # 3. Validar existencia de Cepa
    cepa = db.query(Cepa).filter(Cepa.id == payload.cepa_id).first()
    if not cepa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cepa vinífera con ID {payload.cepa_id} no encontrada"
        )

    # 4. Validar existencia de Bodega
    bodega = db.query(Bodega).filter(Bodega.id == payload.bodega_id).first()
    if not bodega:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bodega con ID {payload.bodega_id} no encontrada"
        )

    nuevo_perfil = PerfilFermentacion(
        nomb_perfil=payload.nomb_perfil.strip(),
        temp_min=payload.temp_min,
        temp_max=payload.temp_max,
        ph_min=payload.ph_min,
        ph_max=payload.ph_max,
        brix_caida_min_dia=payload.brix_caida_min_dia,
        cepa_id=payload.cepa_id,
        bodega_id=payload.bodega_id,
        activo=payload.activo if payload.activo is not None else True
    )

    db.add(nuevo_perfil)
    db.commit()
    db.refresh(nuevo_perfil)

    return _mapear_perfil_out(nuevo_perfil)


@router.put("/{perfil_id}", response_model=PerfilOut, summary="Actualizar umbrales y parámetros de un perfil")
def actualizar_perfil(perfil_id: int, payload: PerfilUpdateIn, db: Session = Depends(get_db)):
    """
    Modifica umbrales de temperatura y pH de un perfil existente:
    1. Verifica que el perfil exista.
    2. Valida que los nuevos valores cumplan temp_min <= temp_max y ph_min <= ph_max.
    3. Actualiza y persiste los cambios.
    """
    perfil = db.query(PerfilFermentacion).filter(PerfilFermentacion.id == perfil_id).first()
    if not perfil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Perfil de fermentación con ID {perfil_id} no encontrado"
        )

    # Calcular valores finales proyectados para verificar consistencia
    t_min_final = payload.temp_min if payload.temp_min is not None else (float(perfil.temp_min) if perfil.temp_min is not None else None)
    t_max_final = payload.temp_max if payload.temp_max is not None else (float(perfil.temp_max) if perfil.temp_max is not None else None)
    ph_min_final = payload.ph_min if payload.ph_min is not None else (float(perfil.ph_min) if perfil.ph_min is not None else None)
    ph_max_final = payload.ph_max if payload.ph_max is not None else (float(perfil.ph_max) if perfil.ph_max is not None else None)

    # Validación de integridad de rangos térmicos
    if t_min_final is not None and t_max_final is not None and t_min_final > t_max_final:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inconsistencia térmica: temp_min ({t_min_final}°C) no puede ser superior a temp_max ({t_max_final}°C) [ck_perfil_temp]."
        )

    # Validación de integridad de rangos de pH
    if ph_min_final is not None and ph_max_final is not None and ph_min_final > ph_max_final:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inconsistencia de acidez: ph_min ({ph_min_final}) no puede ser superior a ph_max ({ph_max_final}) [ck_perfil_ph]."
        )

    # Validar Cepa si se actualiza
    if payload.cepa_id is not None:
        cepa = db.query(Cepa).filter(Cepa.id == payload.cepa_id).first()
        if not cepa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cepa vinífera con ID {payload.cepa_id} no encontrada"
            )
        perfil.cepa_id = payload.cepa_id

    # Validar Bodega si se actualiza
    if payload.bodega_id is not None:
        bodega = db.query(Bodega).filter(Bodega.id == payload.bodega_id).first()
        if not bodega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bodega con ID {payload.bodega_id} no encontrada"
            )
        perfil.bodega_id = payload.bodega_id

    # Aplicar actualizaciones de campos
    if payload.nomb_perfil is not None:
        perfil.nomb_perfil = payload.nomb_perfil.strip()
    if payload.temp_min is not None:
        perfil.temp_min = payload.temp_min
    if payload.temp_max is not None:
        perfil.temp_max = payload.temp_max
    if payload.ph_min is not None:
        perfil.ph_min = payload.ph_min
    if payload.ph_max is not None:
        perfil.ph_max = payload.ph_max
    if payload.brix_caida_min_dia is not None:
        perfil.brix_caida_min_dia = payload.brix_caida_min_dia
    if payload.activo is not None:
        perfil.activo = payload.activo

    db.commit()
    db.refresh(perfil)

    return _mapear_perfil_out(perfil)


@router.delete("/{perfil_id}", status_code=status.HTTP_200_OK, summary="Desactivar o archivar perfil de fermentación")
def desactivar_perfil(perfil_id: int, db: Session = Depends(get_db)):
    """
    Desactiva un perfil (soft-delete). Si el perfil está siendo utilizado
    por un proceso activo en curso, bloquea la eliminación para preservar la consistencia operativa.
    """
    perfil = db.query(PerfilFermentacion).filter(PerfilFermentacion.id == perfil_id).first()
    if not perfil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Perfil de fermentación con ID {perfil_id} no encontrado"
        )

    # Verificar si está en uso por un proceso activo
    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(
            ProcesoFermentacion.perfil_id == perfil.id,
            ProcesoFermentacion.estado == "en_proceso"
        )
        .first()
    )
    if proceso_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede desactivar el perfil: está asignado al proceso de fermentación activo ID {proceso_activo.id}."
        )

    perfil.activo = False
    db.commit()

    return {"status": "ok", "mensaje": f"Perfil '{perfil.nomb_perfil}' desactivado con éxito"}
