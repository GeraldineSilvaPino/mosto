"""
Router de Bitácora Enológica y Registro de Intervenciones (Módulo 4).
Gestiona el timeline cronológico de notas, alertas, cambios de configuración y lecturas manuales en Supabase.
"""
from typing import List, Optional
from datetime import datetime, timedelta
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.services.access import business_db, actor_id
from app.services.telemetry_v2 import aware, utc_now
from app.models import BitacoraIntervencion, Usuario, Cuba, ProcesoFermentacion, EventoAlerta
from app.schemas import BitacoraOut, BitacoraCreateIn

router = APIRouter(prefix="/api/bitacora", tags=["Bitácora Enológica"])


def _resolver_cuba_label(cuba_id: Optional[int], db: Session) -> str:
    """Convierte un ID de cuba a slug de frontend ej: 'cuba-01' o 'general'."""
    if not cuba_id:
        return "general"
    cuba = db.query(Cuba).filter(Cuba.id == cuba_id).first()
    if cuba and cuba.codigo:
        # Formato 'CB-01' -> 'cuba-01'
        codigo = cuba.codigo.lower().replace("cb-", "cuba-").replace("cb", "cuba-")
        return codigo if "cuba" in codigo else f"cuba-{cuba_id:02d}"
    return f"cuba-{cuba_id:02d}"


def _resolver_cuba_id(cuba_slug: Optional[str], db: Session) -> Optional[int]:
    """Convierte un slug como 'cuba-01' o '1' a un ID numérico de cuba en DB."""
    if not cuba_slug or cuba_slug == "general":
        return None
    match = re.fullmatch(r"(?:cuba-)?(\d+)", cuba_slug.lower())
    query = db.query(Cuba)
    if match:
        query = query.filter(Cuba.id == int(match.group(1)))
    else:
        query = query.filter(func.lower(Cuba.codigo) == cuba_slug.lower())
    matches = query.limit(2).all()
    if len(matches) == 1:
        return matches[0].id
    if len(matches) > 1:
        raise HTTPException(422, "Código de cuba ambiguo; use el identificador numérico")
    raise HTTPException(404, "Cuba inexistente o fuera del ámbito autorizado")


def _mapear_bitacora_out(b: BitacoraIntervencion, db: Session) -> BitacoraOut:
    autor_nombre = b.usuario.nomb_compl if b.usuario else "Sistema IoT"
    cuba_slug = _resolver_cuba_label(b.cuba_id, db)

    return BitacoraOut(
        id=b.id,
        alerta_id=b.alerta_id, fermentacion_id=b.fermentacion_id,
        type=b.tipo_intervencion or "nota",
        timestamp=aware(b.fecha_registro) if b.fecha_registro else None,
        cuba=cuba_slug,
        message=b.descripcion,
        author=autor_nombre,
        dosis=b.dosis_aplicada
    )


@router.get("", response_model=List[BitacoraOut])
def listar_entradas_bitacora(
    tipo: Optional[str] = Query(None, description="Filtro por tipo: nota, alerta, config, lectura"),
    cuba: Optional[str] = Query(None, description="Filtro por cuba: general, cuba-01, etc."),
    search: Optional[str] = Query(None, description="Búsqueda por texto libre"),
    alerta_id: Optional[int] = Query(None, gt=0),
    fermentacion_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(business_db("operations"))
):
    """Retorna la lista cronológica de entradas de la bitácora enológica."""
    query = db.query(BitacoraIntervencion)
    if isinstance(alerta_id, int):
        query = query.filter(BitacoraIntervencion.alerta_id == alerta_id)
    if isinstance(fermentacion_id, int):
        query = query.filter(BitacoraIntervencion.fermentacion_id == fermentacion_id)

    if tipo and tipo not in ("todos", "all"):
        query = query.filter(BitacoraIntervencion.tipo_intervencion == tipo.lower().strip())

    if cuba and cuba not in ("todos", "all"):
        cuba_id = _resolver_cuba_id(cuba, db)
        if cuba == "general":
            query = query.filter(BitacoraIntervencion.cuba_id == None)
        elif cuba_id:
            query = query.filter(BitacoraIntervencion.cuba_id == cuba_id)

    if search and search.strip():
        q_clean = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(BitacoraIntervencion.descripcion).like(q_clean))

    entradas = query.order_by(desc(BitacoraIntervencion.fecha_registro)).all()
    return [_mapear_bitacora_out(e, db) for e in entradas]


@router.post("", response_model=BitacoraOut, status_code=status.HTTP_201_CREATED)
def crear_entrada_bitacora(payload: BitacoraCreateIn, db: Session = Depends(business_db("operations"))):
    """Registra una nueva entrada o intervención enológica en Supabase."""
    usuario = db.query(Usuario).filter(Usuario.id == actor_id(db)).one()

    # Resolver cuba y fermentación activa
    cuba_id = _resolver_cuba_id(payload.cuba, db)
    fermentacion_id = None
    if payload.alerta_id is not None or payload.fermentacion_id is not None:
        episode = db.query(EventoAlerta).filter_by(id=payload.alerta_id).first() if payload.alerta_id else None
        if payload.alerta_id and (episode is None or episode.fermentacion_id is None):
            raise HTTPException(404, "Episodio con proceso no encontrado")
        target = payload.fermentacion_id or episode.fermentacion_id
        if episode and episode.fermentacion_id != target:
            raise HTTPException(409, "La intervención y el episodio deben pertenecer al mismo proceso")
        process = db.query(ProcesoFermentacion).filter_by(id=target).first()
        if process is None:
            raise HTTPException(404, "Proceso no encontrado")
        if cuba_id is not None and cuba_id != process.cuba_id:
            raise HTTPException(409, "La cuba no corresponde al proceso de la intervención")
        cuba_id, fermentacion_id = process.cuba_id, process.id
    elif cuba_id:
        proceso = (
            db.query(ProcesoFermentacion)
            .filter(ProcesoFermentacion.cuba_id == cuba_id, ProcesoFermentacion.estado == "en_proceso")
            .order_by(desc(ProcesoFermentacion.id))
            .first()
        )
        if proceso:
            fermentacion_id = proceso.id

    nueva_entrada = BitacoraIntervencion(
        tipo_intervencion=payload.type.lower().strip(),
        descripcion=payload.message.strip(),
        dosis_aplicada=payload.dosis,
        usuario_id=usuario.id,
        cuba_id=cuba_id,
        fermentacion_id=fermentacion_id,
        alerta_id=payload.alerta_id,
        fecha_registro=utc_now()
    )

    db.add(nueva_entrada)
    db.commit()
    db.refresh(nueva_entrada)

    return _mapear_bitacora_out(nueva_entrada, db)

