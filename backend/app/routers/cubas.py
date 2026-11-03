"""
Router de Cubas para consulta del Frontend (Dashboard, CubaDetail).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/cubas", tags=["Cubas y Monitoreo"])


@router.get("", response_model=List[schemas.CubaOut])
def listar_cubas(db: Session = Depends(get_db)):
    """Lista todas las cubas con su última temperatura y grados Brix registrados."""
    cubas = db.query(models.Cuba).all()
    resultado = []
    for c in cubas:
        # Obtener última lectura registrada
        ultima_lectura = (
            db.query(models.LecturaTelemetria)
            .filter(models.LecturaTelemetria.cuba_id == c.id)
            .order_by(desc(models.LecturaTelemetria.timestamp))
            .first()
        )
        c_dict = schemas.CubaOut(
            id=c.id,
            codigo=c.codigo,
            nombre=c.nombre,
            variedad=c.variedad,
            lote=c.lote,
            capacidad_litros=c.capacidad_litros,
            volumen_actual=c.volumen_actual,
            dia_fermentacion=c.dia_fermentacion,
            dias_estimados=c.dias_estimados,
            estado=c.estado,
            ultima_temperatura=ultima_lectura.temp_vino if ultima_lectura else None,
            ultimos_brix=ultima_lectura.brix_calculado if ultima_lectura else None
        )
        resultado.append(c_dict)
    return resultado


@router.get("/{cuba_id}", response_model=schemas.CubaOut)
def obtener_cuba(cuba_id: int, db: Session = Depends(get_db)):
    """Obtiene el detalle de una cuba específica."""
    cuba = db.query(models.Cuba).filter(models.Cuba.id == cuba_id).first()
    if not cuba:
        raise HTTPException(status_code=404, detail="Cuba no encontrada")

    ultima_lectura = (
        db.query(models.LecturaTelemetria)
        .filter(models.LecturaTelemetria.cuba_id == cuba.id)
        .order_by(desc(models.LecturaTelemetria.timestamp))
        .first()
    )

    return schemas.CubaOut(
        id=cuba.id,
        codigo=cuba.codigo,
        nombre=cuba.nombre,
        variedad=cuba.variedad,
        lote=cuba.lote,
        capacidad_litros=cuba.capacidad_litros,
        volumen_actual=cuba.volumen_actual,
        dia_fermentacion=cuba.dia_fermentacion,
        dias_estimados=cuba.dias_estimados,
        estado=cuba.estado,
        ultima_temperatura=ultima_lectura.temp_vino if ultima_lectura else None,
        ultimos_brix=ultima_lectura.brix_calculado if ultima_lectura else None
    )


@router.get("/{cuba_id}/historico", response_model=List[schemas.LecturaOut])
def obtener_historico_cuba(cuba_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Obtiene el histórico de lecturas temporales para alimentar los gráficos de Chart.js."""
    lecturas = (
        db.query(models.LecturaTelemetria)
        .filter(models.LecturaTelemetria.cuba_id == cuba_id)
        .order_by(desc(models.LecturaTelemetria.timestamp))
        .limit(limit)
        .all()
    )
    return list(reversed(lecturas))

