"""
Router de Gestión de Personal, Usuarios y Roles RBAC (Módulo 5).
Permite administrar los colaboradores de la viña (enólogos, operarios, administradores).
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Usuario, Rol, UsuarioBodega, EmpresaCliente, Bodega
from app.schemas import (
    UsuarioOut,
    UsuarioCreateIn,
    UsuarioUpdateRolIn,
    UsuarioUpdateEstadoIn
)
from app.services.auth_service import hash_password

router = APIRouter(prefix="/api/usuarios", tags=["Gestión de Usuarios y Roles"])


def _normalizar_rol(rol_str: Optional[str]) -> str:
    """Normaliza variantes como 'operador' a 'operario' para coherencia con el frontend."""
    if not rol_str:
        return "operario"
    r = rol_str.lower().strip()
    if r in ("operador", "operario"):
        return "operario"
    if r in ("enologo", "enólogo"):
        return "enologo"
    if r == "admin":
        return "admin"
    return r


def _mapear_usuario_out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=u.id,
        name=u.nomb_compl,
        email=u.correo_elec,
        role=_normalizar_rol(u.rol),
        active=bool(u.activo),
        phone=u.telefono,
        created_at=u.creado_en
    )


@router.get("", response_model=List[UsuarioOut])
def listar_usuarios(
    rol: Optional[str] = Query(None, description="Filtrar por rol: admin, enologo, operario"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    db: Session = Depends(get_db)
):
    """Retorna la lista de usuarios y personal de la viña."""
    query = db.query(Usuario)

    if activo is not None:
        query = query.filter(Usuario.activo == activo)

    usuarios = query.order_by(Usuario.id.asc()).all()

    if rol and rol not in ("todos", "all"):
        rol_norm = _normalizar_rol(rol)
        usuarios = [u for u in usuarios if _normalizar_rol(u.rol) == rol_norm]

    return [_mapear_usuario_out(u) for u in usuarios]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(payload: UsuarioCreateIn, db: Session = Depends(get_db)):
    """Invita o crea un nuevo usuario en la base de datos de Supabase."""
    email_clean = payload.email.strip().lower()

    existente = db.query(Usuario).filter(func.lower(Usuario.correo_elec) == email_clean).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El correo electrónico '{payload.email}' ya se encuentra registrado en el sistema."
        )

    # Obtener empresa_id por defecto si no viene
    empresa_id = 5
    emp = db.query(EmpresaCliente).first()
    if emp:
        empresa_id = emp.id

    rol_asignado = _normalizar_rol(payload.role)
    password_hash_str = hash_password(payload.password or "mosto2026")

    nuevo_usuario = Usuario(
        nomb_compl=payload.name.strip(),
        correo_elec=email_clean,
        telefono=payload.phone or "+56912345678",
        activo=True,
        empresa_id=empresa_id,
        password_hash=password_hash_str,
        rol=rol_asignado,
        creado_en=datetime.utcnow()
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    # Vincular en USUARIO_BODEGA si existen bodega y rol
    try:
        bodega = db.query(Bodega).first()
        rol_db = db.query(Rol).filter(func.lower(Rol.codigo).in_([rol_asignado, "operador" if rol_asignado == "operario" else rol_asignado])).first()
        if bodega and rol_db:
            asignacion = UsuarioBodega(
                usuario_id=nuevo_usuario.id,
                bodega_id=bodega.id,
                rol_id=rol_db.id,
                asignado_en=datetime.utcnow()
            )
            db.add(asignacion)
            db.commit()
    except Exception as e:
        print(f"Aviso al asignar usuario en bodega: {e}")
        db.rollback()

    return _mapear_usuario_out(nuevo_usuario)


@router.patch("/{id}/rol", response_model=UsuarioOut)
def actualizar_rol(id: int, payload: UsuarioUpdateRolIn, db: Session = Depends(get_db)):
    """Actualiza el rol operativo de un usuario."""
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    nuevo_rol = _normalizar_rol(payload.role)
    usuario.rol = nuevo_rol
    db.commit()
    db.refresh(usuario)

    # Actualizar tabla intermedia si existe
    try:
        rol_db = db.query(Rol).filter(func.lower(Rol.codigo).in_([nuevo_rol, "operador" if nuevo_rol == "operario" else nuevo_rol])).first()
        if rol_db:
            asig = db.query(UsuarioBodega).filter(UsuarioBodega.usuario_id == usuario.id).first()
            if asig:
                asig.rol_id = rol_db.id
                db.commit()
    except Exception:
        db.rollback()

    return _mapear_usuario_out(usuario)


@router.patch("/{id}/estado", response_model=UsuarioOut)
def actualizar_estado(id: int, payload: UsuarioUpdateEstadoIn, db: Session = Depends(get_db)):
    """Activa o suspende el acceso de un usuario."""
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    usuario.activo = payload.active
    db.commit()
    db.refresh(usuario)
    return _mapear_usuario_out(usuario)


@router.delete("/{id}")
def eliminar_usuario(id: int, db: Session = Depends(get_db)):
    """Desactiva un usuario (soft-delete)."""
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    usuario.activo = False
    db.commit()
    return {"status": "ok", "mensaje": f"Usuario {usuario.nomb_compl} suspendido correctamente."}
