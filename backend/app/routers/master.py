"""
Router de Catálogos Maestros (Cepas, Materiales de Cubas y Bodegas).
Provee datos canónicos para selectores dinámicos en toda la aplicación.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cepa, TipoMaterialCuba, Bodega
from app.schemas import CepaOut, TipoMaterialCubaOut

router = APIRouter(prefix="/api", tags=["Catálogos Maestros"])


@router.get("/cepas", response_model=List[CepaOut])
def listar_cepas(db: Session = Depends(get_db)):
    """Retorna el catálogo oficial de cepas viníferas."""
    if db.query(Cepa).count() == 0:
        cepas_base = [
            Cepa(nombre_variedad="Cabernet Sauvignon", tipo_uva="Tinto"),
            Cepa(nombre_variedad="Carménère", tipo_uva="Tinto"),
            Cepa(nombre_variedad="Sauvignon Blanc", tipo_uva="Blanco"),
            Cepa(nombre_variedad="Syrah", tipo_uva="Tinto"),
            Cepa(nombre_variedad="Chardonnay", tipo_uva="Blanco"),
            Cepa(nombre_variedad="Malbec", tipo_uva="Tinto"),
            Cepa(nombre_variedad="Merlot", tipo_uva="Tinto"),
            Cepa(nombre_variedad="Pinot Noir", tipo_uva="Tinto")
        ]
        try:
            db.add_all(cepas_base)
            db.commit()
        except Exception:
            db.rollback()

    cepas = db.query(Cepa).order_by(Cepa.id.asc()).all()
    return [CepaOut(id=c.id, name=c.nombre_variedad, tipo_uva=c.tipo_uva) for c in cepas]


@router.get("/materiales-cuba", response_model=List[TipoMaterialCubaOut])
def listar_materiales(db: Session = Depends(get_db)):
    """Retorna los tipos de material para tanques y cubas."""
    if db.query(TipoMaterialCuba).count() == 0:
        materiales_base = [
            TipoMaterialCuba(nombre="Acero Inoxidable 316L"),
            TipoMaterialCuba(nombre="Roble Francés"),
            TipoMaterialCuba(nombre="Roble Americano"),
            TipoMaterialCuba(nombre="Hormigón Epóxico")
        ]
        try:
            db.add_all(materiales_base)
            db.commit()
        except Exception:
            db.rollback()

    materiales = db.query(TipoMaterialCuba).order_by(TipoMaterialCuba.id.asc()).all()
    return [TipoMaterialCubaOut(id=m.id, nombre=m.nombre) for m in materiales]
