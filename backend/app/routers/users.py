"""Company administration; effective permissions live in USUARIO_BODEGA."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import Usuario, Rol, UsuarioBodega, Bodega, EmpresaCliente
from app.schemas import UsuarioOut, UsuarioCreateIn, UsuarioUpdateRolIn, UsuarioUpdateEstadoIn
from app.services.access import business_db, actor_id, normalize_role, KNOWN_ROLES
from app.services.auth_service import hash_password

router = APIRouter(prefix="/api/usuarios", tags=["Gestión de Usuarios y Roles"])


def _normalizar_rol(value):
    role = normalize_role((value or "").strip().lower())
    if role not in KNOWN_ROLES:
        raise HTTPException(422, "Rol desconocido")
    return role


def _mapear_usuario_out(u):
    memberships = [{"bodega_id": a.bodega_id, "bodega_nombre": a.bodega.nombre,
                    "role": normalize_role(a.rol.codigo)} for a in u.bodega_asignaciones]
    roles = {a["role"] for a in memberships}
    display_role = next(iter(roles)) if len(roles) == 1 else "multiple" if roles else "sin_acceso"
    return UsuarioOut(id=u.id, name=u.nomb_compl, email=u.correo_elec,
                      role="operario" if display_role == "operador" else display_role,
                      active=bool(u.activo), phone=u.telefono, created_at=u.creado_en,
                      memberships=memberships)


def _user(db, ident):
    user = db.query(Usuario).filter_by(id=ident).first()
    if user is None:
        raise HTTPException(404, "Usuario no encontrado")
    return user


def _role(db, value):
    code = _normalizar_rol(value)
    role = db.query(Rol).filter(Rol.codigo.in_([code, "operario"] if code == "operador" else [code])).first()
    if role is None:
        raise HTTPException(409, "Rol sin aprovisionar en el catálogo")
    return code, role


def _warehouse(db, ident):
    query = db.query(Bodega)
    if ident is not None:
        query = query.filter_by(id=ident)
    rows = query.limit(2).all()
    if not rows:
        raise HTTPException(404, "Bodega no encontrada")
    if len(rows) != 1:
        raise HTTPException(422, "Debe indicar bodega_id")
    return rows[0]


def _lock_company(db):
    # Serialize administrative changes in PostgreSQL, including the last-admin check.
    db.query(EmpresaCliente).with_for_update().one()
    # A competing administrator may have revoked this request while it waited.
    actor = db.query(Usuario).filter_by(id=actor_id(db), activo=True).first()
    grants = dict(db.query(UsuarioBodega.bodega_id, Rol.codigo).join(Rol).filter(
        UsuarioBodega.usuario_id == actor_id(db)).all())
    if actor is None or any(normalize_role(grants.get(i)) != "admin"
                            for i in db.info["access"].warehouses):
        raise HTTPException(403, "Los permisos administrativos han cambiado")


def _preserve_admins(db, user, memberships):
    if not user.activo:
        return
    for assignment in memberships:
        role = db.query(Rol).filter_by(id=assignment.rol_id).one()
        if normalize_role(role.codigo) != "admin":
            continue
        others = db.query(UsuarioBodega.id).join(Usuario).join(Rol).filter(
            UsuarioBodega.bodega_id == assignment.bodega_id,
            UsuarioBodega.usuario_id != user.id,
            Usuario.activo.is_(True), Rol.codigo == "admin").count()
        if not others:
            raise HTTPException(409, "No se puede dejar una bodega sin administrador activo")


@router.get("", response_model=List[UsuarioOut])
def listar_usuarios(rol: Optional[str] = Query(None), activo: Optional[bool] = Query(None),
                    db: Session = Depends(business_db("admin"))):
    query = db.query(Usuario)
    if activo is not None:
        query = query.filter(Usuario.activo == activo)
    if rol and rol not in {"todos", "all"}:
        code = _normalizar_rol(rol)
        query = query.join(UsuarioBodega).join(Rol).filter(
            Rol.codigo.in_([code, "operario"] if code == "operador" else [code]))
    return [_mapear_usuario_out(user) for user in query.order_by(Usuario.id).all()]


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(payload: UsuarioCreateIn, db: Session = Depends(business_db("admin"))):
    _lock_company(db)
    warehouse = _warehouse(db, payload.bodega_id)
    code, role = _role(db, payload.role)
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Correo inválido")
    user = Usuario(nomb_compl=payload.name.strip(), correo_elec=email,
                   telefono=payload.phone, activo=True, empresa_id=db.info["access"].company_id,
                   password_hash=hash_password(payload.password), rol=code)
    try:
        db.add(user)
        db.flush()
        db.add(UsuarioBodega(usuario_id=user.id, bodega_id=warehouse.id, rol_id=role.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "No se pudo registrar el usuario con los datos proporcionados")
    db.refresh(user)
    return _mapear_usuario_out(user)


@router.patch("/{id}/rol", response_model=UsuarioOut)
def actualizar_rol(id: int, payload: UsuarioUpdateRolIn, db: Session = Depends(business_db("admin"))):
    _lock_company(db)
    user = _user(db, id)
    code, role = _role(db, payload.role)
    query = db.query(UsuarioBodega).filter_by(usuario_id=id)
    if payload.bodega_id is not None:
        query = query.filter_by(bodega_id=payload.bodega_id)
    memberships = query.all()
    if not memberships:
        raise HTTPException(404, "Asignación no encontrada")
    if len(memberships) != 1:
        raise HTTPException(422, "Debe indicar la bodega cuyo rol desea modificar")
    if code != "admin":
        _preserve_admins(db, user, memberships)
    memberships[0].rol_id = role.id
    user.rol = code  # Legacy display only; never used to authorize a request.
    db.commit()
    db.refresh(user)
    return _mapear_usuario_out(user)


@router.patch("/{id}/estado", response_model=UsuarioOut)
def actualizar_estado(id: int, payload: UsuarioUpdateEstadoIn, db: Session = Depends(business_db("admin"))):
    _lock_company(db)
    user = _user(db, id)
    if not payload.active:
        if id == actor_id(db):
            raise HTTPException(409, "No puede suspender su propia sesión")
        _preserve_admins(db, user, db.query(UsuarioBodega).filter_by(usuario_id=id).all())
    user.activo = payload.active
    db.commit()
    db.refresh(user)
    return _mapear_usuario_out(user)


@router.delete("/{id}")
def eliminar_usuario(id: int, db: Session = Depends(business_db("admin"))):
    actualizar_estado(id, UsuarioUpdateEstadoIn(active=False), db)
    return {"status": "ok", "mensaje": "Usuario suspendido"}
