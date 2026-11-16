"""Request-scoped authorization. Memberships, never JWT roles, grant access.

Business sessions are separate from the authentication session, so their identity
map cannot contain entities loaded before the scope was installed. Core SQL and
bulk mutations are deliberately unavailable to business routers.
"""
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import and_, event, inspect, or_, select
from sqlalchemy.orm import with_loader_criteria

from app import models as m
from app.database import SessionLocal
from app.services.auth_service import get_current_user


def normalize_role(value):
    return {"operario": "operador", "enólogo": "enologo"}.get(value, value)


@dataclass(frozen=True)
class AccessContext:
    user_id: int
    company_id: int
    warehouses: tuple[int, ...]
    company_admin: bool
    policy: str
    writable: bool


WRITE_ROLES = {
    "operations": {"admin", "enologo", "operador"},
    "devices": {"admin", "operador"},
    "profiles": {"admin", "enologo"},
    "admin": {"admin"},
    "demo": {"admin"},
    "catalogs": set(),
    "provision": {"admin"},
}
KNOWN_ROLES = {"admin", "enologo", "operador", "lector"}


def actor_id(db):
    context = db.info.get("access")
    if context is None:
        raise HTTPException(403, "Se requiere una sesión con ámbito de autorización")
    return context.user_id


def scope_predicates(ctx):
    # Core subqueries avoid recursive injection of ORM loader criteria.
    c, p, d, a, u = (x.__table__.c for x in
                     (m.Cuba, m.ProcesoFermentacion, m.Dispositivo,
                      m.AsignacionDispositivo, m.Usuario))
    cube_ids = select(c.id).where(c.bodega_id.in_(ctx.warehouses))
    process_ids = select(p.id).where(p.cuba_id.in_(cube_ids))
    # A current assignment outside the scope excludes the entire device. A
    # historical assignment alone never grants access to its current state.
    outside = select(a.dispositivo_id).where(
        a.activo.is_(True), ~a.cuba_id.in_(cube_ids))
    device_ids = select(d.id).where(d.empresa_id == ctx.company_id,
                                    ~d.id.in_(outside))
    own_users = select(u.id).where(u.empresa_id == ctx.company_id)
    alerts = m.EventoAlerta.__table__.c
    alert_ids = select(alerts.id).where(or_(alerts.fermentacion_id.in_(process_ids), and_(
        alerts.fermentacion_id.is_(None), alerts.dispositivo_id.in_(device_ids))))
    note_scope = or_(m.BitacoraIntervencion.cuba_id.in_(cube_ids), and_(
        m.BitacoraIntervencion.cuba_id.is_(None),
        m.BitacoraIntervencion.fermentacion_id.is_(None),
        m.BitacoraIntervencion.usuario_id.in_(own_users) if ctx.company_admin
        else m.BitacoraIntervencion.usuario_id == ctx.user_id))
    return {
        m.EmpresaCliente: m.EmpresaCliente.id == ctx.company_id,
        m.Bodega: and_(m.Bodega.empresa_id == ctx.company_id,
                      m.Bodega.id.in_(ctx.warehouses)),
        m.Cuba: m.Cuba.bodega_id.in_(ctx.warehouses),
        m.PerfilFermentacion: m.PerfilFermentacion.bodega_id.in_(ctx.warehouses),
        m.ProcesoFermentacion: m.ProcesoFermentacion.cuba_id.in_(cube_ids),
        m.Dispositivo: m.Dispositivo.id.in_(device_ids),
        m.AsignacionDispositivo: and_(m.AsignacionDispositivo.cuba_id.in_(cube_ids),
                                      m.AsignacionDispositivo.dispositivo_id.in_(device_ids)),
        m.LecturaTelemetria: m.LecturaTelemetria.fermentacion_id.in_(process_ids),
        m.TelemetriaEstadoNodo: m.TelemetriaEstadoNodo.dispositivo_id.in_(device_ids),
        m.EventoAlerta: or_(m.EventoAlerta.fermentacion_id.in_(process_ids), and_(
            m.EventoAlerta.fermentacion_id.is_(None),
            m.EventoAlerta.dispositivo_id.in_(device_ids))),
        m.BitacoraIntervencion: note_scope,
        m.Usuario: m.Usuario.empresa_id == ctx.company_id,
        m.UsuarioBodega: and_(m.UsuarioBodega.bodega_id.in_(ctx.warehouses),
                              m.UsuarioBodega.usuario_id.in_(own_users)),
        m.CredencialDispositivo: m.CredencialDispositivo.dispositivo_id.in_(device_ids),
        m.CalibracionDispositivo: m.CalibracionDispositivo.dispositivo_id.in_(device_ids),
        m.MensajeTelemetria: m.MensajeTelemetria.fermentacion_id.in_(process_ids),
        m.EstadoRegla: m.EstadoRegla.fermentacion_id.in_(process_ids),
        m.AuditoriaAlerta: m.AuditoriaAlerta.alerta_id.in_(alert_ids),
    }


def install_scope(db, context):
    db.info["access"] = context
    predicates = scope_predicates(context)

    def filter_queries(state):
        if not state.is_select or not state.is_orm_statement:
            raise HTTPException(403, "La sesión de negocio no permite SQL directo ni mutaciones masivas")
        catalogs = {m.Rol, m.Cepa, m.TipoMaterialCuba, m.ModeloDispositivo}
        if any(mapper.class_ not in predicates and mapper.class_ not in catalogs
               for mapper in state.all_mappers):
            raise HTTPException(403, "Entidad sin política de acceso")
        state.statement = state.statement.options(*(
            with_loader_criteria(model, predicate, include_aliases=True,
                                 propagate_to_loaders=False)
            for model, predicate in predicates.items()))

    def visible(model, key):
        if key is None or db.query(model.id).filter(model.id == key).first() is None:
            raise HTTPException(404, "Referencia inexistente o fuera del ámbito autorizado")

    def validate_flush(session, *_):
        changed = session.new.union(session.dirty).union(session.deleted)
        if changed and not context.writable:
            raise HTTPException(403, "Esta sesión es de solo lectura")
        allowed = {
            "operations": {m.Cuba, m.ProcesoFermentacion, m.EventoAlerta, m.BitacoraIntervencion, m.EstadoRegla, m.AuditoriaAlerta},
            "profiles": {m.PerfilFermentacion},
            "devices": {m.Dispositivo, m.AsignacionDispositivo},
            "admin": {m.Usuario, m.UsuarioBodega, m.EmpresaCliente, m.Bodega,
                      m.LecturaTelemetria, m.EventoAlerta},
            "demo": {m.ProcesoFermentacion, m.Dispositivo, m.AsignacionDispositivo,
                     m.LecturaTelemetria, m.EventoAlerta},
            "provision": {m.Dispositivo, m.CredencialDispositivo, m.CalibracionDispositivo},
        }.get(context.policy, set())
        for obj in changed:
            if type(obj) not in allowed:
                raise HTTPException(403, "La operación no permite modificar esta entidad")
            state = inspect(obj)
            if state.persistent:
                visible(type(obj), obj.id)
                # Moving historical entities invalidates their audit trail.
                for field in ("id", "empresa_id", "bodega_id", "cuba_id", "fermentacion_id", "dispositivo_id"):
                    if field in state.attrs and state.attrs[field].history.has_changes():
                        raise HTTPException(409, "No se permite trasladar registros entre ámbitos")
            if hasattr(obj, "empresa_id") and obj.empresa_id != context.company_id:
                raise HTTPException(404, "Empresa fuera del ámbito autorizado")
            if hasattr(obj, "bodega_id") and obj.bodega_id not in context.warehouses:
                raise HTTPException(404, "Bodega fuera del ámbito autorizado")
            for field, model in (("cuba_id", m.Cuba), ("perfil_id", m.PerfilFermentacion),
                                 ("fermentacion_id", m.ProcesoFermentacion),
                                 ("dispositivo_id", m.Dispositivo), ("usuario_id", m.Usuario)):
                key = getattr(obj, field, None)
                if key is not None:
                    visible(model, key)
            if isinstance(obj, (m.AuditoriaAlerta, m.BitacoraIntervencion)) and obj.alerta_id is not None:
                visible(m.EventoAlerta, obj.alerta_id)
            if isinstance(obj, m.AuditoriaAlerta) and (state.persistent or obj in db.deleted):
                raise HTTPException(409, "La auditoría de alertas es inmutable")
            if isinstance(obj, m.BitacoraIntervencion) and obj.usuario_id != context.user_id:
                raise HTTPException(403, "El autor debe ser el usuario autenticado")
            if isinstance(obj, m.ProcesoFermentacion) and obj.perfil_id:
                cube = db.query(m.Cuba).filter_by(id=obj.cuba_id).one()
                profile = db.query(m.PerfilFermentacion).filter_by(id=obj.perfil_id).one()
                if cube.bodega_id != profile.bodega_id:
                    raise HTTPException(409, "Cuba y perfil deben pertenecer a la misma bodega")

    event.listen(db, "do_orm_execute", filter_queries)
    event.listen(db, "before_flush", validate_flush)


@lru_cache
def business_db(policy="operations"):
    if policy not in WRITE_ROLES:
        raise ValueError("Política de autorización desconocida")

    def dependency(request: Request, user=Depends(get_current_user)):
        with SessionLocal() as db:
            company = db.query(m.EmpresaCliente).filter_by(id=user.empresa_id, activo=True).first()
            if company is None:
                raise HTTPException(403, "Empresa inactiva o sin configurar")
            company_ids = {row[0] for row in db.query(m.Bodega.id).filter_by(empresa_id=company.id)}
            rows = db.query(m.UsuarioBodega.bodega_id, m.Rol.codigo).join(m.Rol).join(
                m.Bodega, m.Bodega.id == m.UsuarioBodega.bodega_id).filter(
                m.UsuarioBodega.usuario_id == user.id, m.Bodega.empresa_id == company.id).all()
            roles = {}
            for warehouse, role in rows:
                role = normalize_role(role)
                if warehouse in roles or role not in KNOWN_ROLES:
                    raise HTTPException(403, "Asignaciones de permisos ambiguas o desconocidas")
                roles[warehouse] = role
            company_admin = bool(company_ids) and all(roles.get(i) == "admin" for i in company_ids)
            writable = request.method not in {"GET", "HEAD", "OPTIONS"}
            if policy == "admin" and not company_admin:
                raise HTTPException(403, "Requiere administración de todas las bodegas de la empresa")
            warehouses = tuple(sorted(i for i, role in roles.items()
                                      if not writable or role in WRITE_ROLES[policy]))
            if not warehouses:
                raise HTTPException(403, "Sin permisos para esta operación")
            # Authentication/provisioning reads must not survive in this identity map.
            db.expunge_all()
            install_scope(db, AccessContext(user.id, company.id, warehouses,
                                            company_admin, policy, writable))
            try:
                yield db
            except Exception:
                db.rollback()
                raise
    return dependency
