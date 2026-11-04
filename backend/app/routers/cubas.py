"""
Router de Cubas para consulta del Frontend (Dashboard, CubaDetail).
Controlador REST para monitoreo en tiempo real y curvas de fermentación.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Cuba, ProcesoFermentacion, LecturaTelemetria
from app.schemas import CubaOut, LecturaOut, HistoricoCubaOut

router = APIRouter(prefix="/api/cubas", tags=["Cubas y Monitoreo"])


def _mapear_cuba_out(c: Cuba, proceso_activo: Optional[ProcesoFermentacion], ultima_lectura: Optional[LecturaTelemetria]) -> CubaOut:
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
        ultima_lectura_timestamp=ultima_lectura.timestamp if ultima_lectura else None
    )


@router.get("", response_model=List[CubaOut], summary="Listar todas las cubas con telemetría en tiempo real")
def listar_cubas(db: Session = Depends(get_db)):
    """Lista todas las cubas de la bodega con su última lectura de sensores registrada."""
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
        if proceso_activo:
            ultima_lectura = (
                db.query(LecturaTelemetria)
                .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
                .order_by(desc(LecturaTelemetria.timestamp))
                .first()
            )

        resultado.append(_mapear_cuba_out(c, proceso_activo, ultima_lectura))
        
    return resultado


@router.get("/{cuba_id}", response_model=CubaOut, summary="Obtener detalle de una cuba por ID")
def obtener_cuba(cuba_id: int, db: Session = Depends(get_db)):
    """Obtiene el estado detallado de una cuba y sus sensores."""
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
    if proceso_activo:
        ultima_lectura = (
            db.query(LecturaTelemetria)
            .filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
            .order_by(desc(LecturaTelemetria.timestamp))
            .first()
        )

    return _mapear_cuba_out(c, proceso_activo, ultima_lectura)


@router.get("/{cuba_id}/historico", response_model=HistoricoCubaOut, summary="Curvas históricas de telemetría (para Chart.js)")
def obtener_historico_cuba(
    cuba_id: int,
    rango_horas: int = Query(24, description="Ventana de tiempo en horas (24, 48, 168)"),
    db: Session = Depends(get_db)
):
    """
    Entrega series temporales de temperatura de vino, grados Brix y pH
    listas para renderizar en los gráficos de CubaDetailView.vue.
    """
    c = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {cuba_id} no encontrada")

    proceso_activo = (
        db.query(ProcesoFermentacion)
        .filter(ProcesoFermentacion.cuba_id == c.id)
        .order_by(desc(ProcesoFermentacion.id))
        .first()
    )

    query = db.query(LecturaTelemetria)
    if proceso_activo:
        query = query.filter(LecturaTelemetria.fermentacion_id == proceso_activo.id)
    
    lecturas = query.order_by(desc(LecturaTelemetria.timestamp)).limit(100).all()
    lecturas = list(reversed(lecturas))

    return HistoricoCubaOut(
        cuba_id=c.id,
        nombre_cuba=f"Cuba {c.codigo}",
        proceso_id=proceso_activo.id if proceso_activo else None,
        rango_horas=rango_horas,
        total_muestras=len(lecturas),
        timestamps=[l.timestamp.strftime("%H:%M:%S") if l.timestamp else "" for l in lecturas],
        temperaturas_vino=[float(l.temp_mosto) if l.temp_mosto else None for l in lecturas],
        grados_brix=[float(l.brix) if l.brix else None for l in lecturas],
        valores_ph=[float(l.ph) if l.ph else None for l in lecturas]
    )
