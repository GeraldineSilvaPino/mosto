"""
Router de Bitácora Enológica y Registro de Intervenciones (Módulo 4).
Gestiona el timeline cronológico de notas, alertas, cambios de configuración y lecturas manuales en Supabase.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import BitacoraIntervencion, Usuario, Cuba, ProcesoFermentacion
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
    # Extraer dígitos
    num_str = "".join(ch for ch in cuba_slug if ch.isdigit())
    if num_str:
        num = int(num_str)
        cuba = db.query(Cuba).filter(Cuba.id == num).first()
        if cuba:
            return cuba.id
        # Buscar por código
        cuba_cod = db.query(Cuba).filter(func.lower(Cuba.codigo).like(f"%{num:02d}%")).first()
        if cuba_cod:
            return cuba_cod.id
    return None


def _mapear_bitacora_out(b: BitacoraIntervencion, db: Session) -> BitacoraOut:
    autor_nombre = b.usuario.nomb_compl if b.usuario else "Sistema IoT"
    cuba_slug = _resolver_cuba_label(b.cuba_id, db)

    return BitacoraOut(
        id=b.id,
        type=b.tipo_intervencion or "nota",
        timestamp=b.fecha_registro,
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
    db: Session = Depends(get_db)
):
    """Retorna la lista cronológica de entradas de la bitácora enológica."""
    # Si la tabla está vacía, sembrar entradas iniciales
    if db.query(BitacoraIntervencion).count() == 0:
        _sembrar_bitacora_inicial(db)

    query = db.query(BitacoraIntervencion)

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
def crear_entrada_bitacora(payload: BitacoraCreateIn, db: Session = Depends(get_db)):
    """Registra una nueva entrada o intervención enológica en Supabase."""
    # Resolver usuario autor
    usuario = None
    if payload.author:
        usuario = db.query(Usuario).filter(func.lower(Usuario.nomb_compl).like(f"%{payload.author.strip().lower()}%")).first()
    if not usuario:
        usuario = db.query(Usuario).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="No se encontró un usuario para registrar la entrada.")

    # Resolver cuba y fermentación activa
    cuba_id = _resolver_cuba_id(payload.cuba, db)
    fermentacion_id = None
    if cuba_id:
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
        fecha_registro=datetime.utcnow()
    )

    db.add(nueva_entrada)
    db.commit()
    db.refresh(nueva_entrada)

    return _mapear_bitacora_out(nueva_entrada, db)


def _sembrar_bitacora_inicial(db: Session):
    """Siembra datos iniciales de bitácora enológica para reflejar el historial de bodega."""
    usuario = db.query(Usuario).first()
    if not usuario:
        return

    ahora = datetime.utcnow()
    cuba = db.query(Cuba).first()
    cuba_id = cuba.id if cuba else None

    entradas_demo = [
        BitacoraIntervencion(
            tipo_intervencion="alerta",
            descripcion="Temperatura elevada detectada: 30.1°C (umbral máx: 28°C)",
            usuario_id=usuario.id,
            cuba_id=cuba_id,
            fecha_registro=ahora - timedelta(hours=2)
        ),
        BitacoraIntervencion(
            tipo_intervencion="nota",
            descripcion="Agregado SO₂ correctivo (35 mg/L). Mosto en buenas condiciones generales.",
            dosis_aplicada="35 mg/L",
            usuario_id=usuario.id,
            cuba_id=cuba_id,
            fecha_registro=ahora - timedelta(hours=5)
        ),
        BitacoraIntervencion(
            tipo_intervencion="lectura",
            descripcion="Lectura manual: 17.5°C / 18.5 °Bx. Fermentación activa día 3.",
            usuario_id=usuario.id,
            cuba_id=cuba_id,
            fecha_registro=ahora - timedelta(hours=8)
        ),
        BitacoraIntervencion(
            tipo_intervencion="config",
            descripcion="Umbral de pH ajustado de 3.2 a 3.4 para todas las cubas de tinto.",
            usuario_id=usuario.id,
            cuba_id=None,
            fecha_registro=ahora - timedelta(days=1, hours=3)
        ),
        BitacoraIntervencion(
            tipo_intervencion="nota",
            descripcion="Fermentación entrando en fase final. Brix en 3.4, cercano a sequedad.",
            usuario_id=usuario.id,
            cuba_id=cuba_id,
            fecha_registro=ahora - timedelta(days=1, hours=6)
        )
    ]
    try:
        db.add_all(entradas_demo)
        db.commit()
    except Exception as e:
        print(f"Aviso al sembrar bitácora inicial: {e}")
        db.rollback()

