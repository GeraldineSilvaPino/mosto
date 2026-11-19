"""
Router de Catálogos Maestros (Cepas, Materiales de Cubas y Bodegas).
Provee datos canónicos para selectores dinámicos en toda la aplicación.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services.access import business_db
from app.models import Cepa, TipoMaterialCuba, Bodega
from app.schemas import CepaOut, TipoMaterialCubaOut

router = APIRouter(prefix="/api", tags=["Catálogos Maestros"])


@router.get("/bodegas")
def listar_bodegas(db: Session = Depends(business_db("catalogs"))):
    return [{"id": b.id, "nombre": b.nombre} for b in db.query(Bodega).order_by(Bodega.id)]


@router.get("/cepas", response_model=List[CepaOut])
def listar_cepas(db: Session = Depends(business_db("catalogs"))):
    """Retorna el catálogo oficial de cepas viníferas."""
    cepas = db.query(Cepa).order_by(Cepa.id.asc()).all()
    return [CepaOut(id=c.id, name=c.nombre_variedad, tipo_uva=c.tipo_uva) for c in cepas]


@router.get("/materiales-cuba", response_model=List[TipoMaterialCubaOut])
def listar_materiales(db: Session = Depends(business_db("catalogs"))):
    """Retorna los tipos de material para tanques y cubas."""
    materiales = db.query(TipoMaterialCuba).order_by(TipoMaterialCuba.id.asc()).all()
    return [TipoMaterialCubaOut(id=m.id, nombre=m.nombre) for m in materiales]

