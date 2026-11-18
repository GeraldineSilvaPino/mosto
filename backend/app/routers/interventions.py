"""Human-declared workflow. Never mutates alert condition, resolution or telemetry."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app import models as m
from app.services.access import actor_id, business_db, normalize_role, WRITE_ROLES

router = APIRouter(prefix="/api/intervenciones", tags=["Intervenciones"])
db_scope = business_db("operations")


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    fermentacion_id: int = Field(gt=0)
    alerta_id: int | None = Field(default=None, gt=0)
    responsable_id: int | None = Field(default=None, gt=0)
    tipo: Literal["comprobar_sensor", "contraste_manual", "ajuste_termico", "otra"]
    accion: str = Field(min_length=5, max_length=2000)
    motivo: str = Field(min_length=5, max_length=2000)


class Followup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    expected_revision: int = Field(ge=1)
    estado: Literal["ejecutada", "en_seguimiento", "cerrada", "cancelada"]
    descripcion: str = Field(min_length=5, max_length=2000)
    respuesta: Literal["sin_cambio", "mejora_declarada", "empeora_declarado", "no_evaluable"] | None = None

    @model_validator(mode="after")
    def require_response(self):
        if self.estado in {"en_seguimiento", "cerrada"} and self.respuesta is None:
            raise ValueError("El seguimiento y cierre requieren una respuesta declarada")
        if self.estado in {"ejecutada", "cancelada"} and self.respuesta is not None:
            raise ValueError("La respuesta corresponde al seguimiento o cierre")
        return self


def require(db, model, ident, lock=False):
    query = db.query(model).filter(model.id == ident)
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        raise HTTPException(404, "Registro inexistente o fuera del ámbito autorizado")
    return row


def proposal_out(row):
    result = {key: getattr(row, key) for key in (
        "id", "fermentacion_id", "alerta_id", "responsable_id", "usuario_id",
        "tipo", "accion", "motivo", "estado", "revision", "registrado_en")}
    result["registrado_en"] = row.registrado_en.replace(tzinfo=timezone.utc) if row.registrado_en.tzinfo is None else row.registrado_en
    return result


def event_out(row):
    result = {key: getattr(row, key) for key in (
        "id", "intervencion_id", "bitacora_id", "usuario_id", "revision",
        "estado", "descripcion", "respuesta", "registrado_en")}
    result["registrado_en"] = row.registrado_en.replace(tzinfo=timezone.utc) if row.registrado_en.tzinfo is None else row.registrado_en
    return result


def lock_process(db, ident):
    process = require(db, m.ProcesoFermentacion, ident)
    require(db, m.Cuba, process.cuba_id, lock=True)
    db.refresh(process)
    return process


def request_data(payload, db):
    return {**payload.model_dump(mode="json"), "actor_id": actor_id(db)}


def check_retry(row, request):
    if row.solicitud != request:
        raise HTTPException(409, "La clave de solicitud ya se usó con otro contenido o actor")


def append_event(db, row, process, payload, description, response=None):
    now = datetime.now(timezone.utc)
    note = m.BitacoraIntervencion(
        usuario_id=actor_id(db), cuba_id=process.cuba_id, fermentacion_id=process.id,
        alerta_id=row.alerta_id, fecha_registro=now, tipo_intervencion="intervencion",
        descripcion=f"Intervención #{row.id} · {row.estado} · {row.accion}\n{description}"
                    + (f"\nRespuesta declarada: {response}" if response else ""))
    db.add(note)
    db.flush()
    event = m.EventoIntervencion(
        intervencion_id=row.id, bitacora_id=note.id, usuario_id=actor_id(db),
        revision=row.revision, estado=row.estado, descripcion=description, respuesta=response,
        registrado_en=now, request_id=str(payload.request_id), solicitud=request_data(payload, db))
    db.add(event)
    db.flush()
    return event


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "La intervención cambió; recarga antes de continuar")


@router.get("/contexto/{process_id}")
def context(process_id: int, db: Session = Depends(db_scope)):
    process = require(db, m.ProcesoFermentacion, process_id)
    cube = require(db, m.Cuba, process.cuba_id)
    candidates = db.query(m.Usuario.id, m.Usuario.nomb_compl, m.Rol.codigo).join(
        m.UsuarioBodega, m.UsuarioBodega.usuario_id == m.Usuario.id).join(
        m.Rol, m.Rol.id == m.UsuarioBodega.rol_id).filter(
        m.UsuarioBodega.bodega_id == cube.bodega_id, m.Usuario.activo.is_(True)).all()
    responsible = [{"id": ident, "nombre": name} for ident, name, role in candidates
                   if normalize_role(role) in WRITE_ROLES["operations"]]
    return {"responsables": responsible, "usuario_id": actor_id(db),
            "puede_operar": any(row['id'] == actor_id(db) for row in responsible),
            "proceso_activo": process.estado in {"en_proceso", "detenida"}}


@router.get("")
def list_interventions(fermentacion_id: int | None = Query(None, gt=0),
                       alerta_id: int | None = Query(None, gt=0),
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                       db: Session = Depends(db_scope)):
    query = db.query(m.IntervencionOperativa)
    if fermentacion_id is not None:
        require(db, m.ProcesoFermentacion, fermentacion_id)
        query = query.filter_by(fermentacion_id=fermentacion_id)
    if alerta_id is not None:
        require(db, m.EventoAlerta, alerta_id)
        query = query.filter_by(alerta_id=alerta_id)
    return {"total": query.count(), "items": [proposal_out(row) for row in
        query.order_by(m.IntervencionOperativa.id.desc()).offset(offset).limit(limit)]}


@router.post("", status_code=201)
def propose(payload: Proposal, db: Session = Depends(db_scope)):
    process = lock_process(db, payload.fermentacion_id)
    request = request_data(payload, db)
    previous = db.query(m.IntervencionOperativa).filter_by(
        fermentacion_id=process.id, request_id=str(payload.request_id)).first()
    if previous:
        check_retry(previous, request)
        return proposal_out(previous)
    if process.estado not in {"en_proceso", "detenida"}:
        raise HTTPException(409, "No se proponen acciones para un proceso finalizado")
    if payload.alerta_id is not None:
        alert = require(db, m.EventoAlerta, payload.alerta_id)
        if alert.fermentacion_id != process.id:
            raise HTTPException(409, "La alerta debe pertenecer al mismo proceso")
    responsible = require(db, m.Usuario, payload.responsable_id or actor_id(db))
    cube = require(db, m.Cuba, process.cuba_id)
    role = db.query(m.Rol.codigo).join(m.UsuarioBodega).filter(
        m.UsuarioBodega.usuario_id == responsible.id,
        m.UsuarioBodega.bodega_id == cube.bodega_id).scalar()
    if not responsible.activo or normalize_role(role) not in WRITE_ROLES["operations"]:
        raise HTTPException(409, "El responsable debe estar activo y tener permiso operativo en la bodega")
    row = m.IntervencionOperativa(
        fermentacion_id=process.id, alerta_id=payload.alerta_id, responsable_id=responsible.id,
        usuario_id=actor_id(db), tipo=payload.tipo, accion=payload.accion, motivo=payload.motivo,
        estado="propuesta", registrado_en=datetime.now(timezone.utc),
        request_id=str(payload.request_id), solicitud=request)
    db.add(row)
    db.flush()
    append_event(db, row, process, payload, payload.motivo)
    commit(db)
    return proposal_out(row)


@router.get("/{ident}/eventos")
def history(ident: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
            db: Session = Depends(db_scope)):
    require(db, m.IntervencionOperativa, ident)
    query = db.query(m.EventoIntervencion).filter_by(intervencion_id=ident)
    return {"total": query.count(), "items": [event_out(row) for row in query.order_by(
        m.EventoIntervencion.revision.desc()).offset(offset).limit(limit)]}


@router.post("/{ident}/eventos", status_code=201)
def followup(ident: int, payload: Followup, db: Session = Depends(db_scope)):
    # Same tank-first lock order as process closure, then reload workflow.
    initial = require(db, m.IntervencionOperativa, ident)
    process = lock_process(db, initial.fermentacion_id)
    row = db.query(m.IntervencionOperativa).filter_by(id=ident).populate_existing().with_for_update().one()
    previous = db.query(m.EventoIntervencion).filter_by(
        intervencion_id=ident, request_id=str(payload.request_id)).first()
    if previous:
        check_retry(previous, request_data(payload, db))
        return event_out(previous)
    if payload.expected_revision != row.revision:
        raise HTTPException(409, "La intervención cambió; recarga antes de continuar")
    transitions = {"propuesta": {"ejecutada", "cancelada"},
                   "ejecutada": {"en_seguimiento", "cerrada"},
                   "en_seguimiento": {"en_seguimiento", "cerrada"}}
    if payload.estado not in transitions.get(row.estado, set()):
        raise HTTPException(409, "Transición de intervención no permitida")
    if payload.estado == "ejecutada" and process.estado not in {"en_proceso", "detenida"}:
        raise HTTPException(409, "No se registra ejecución sobre un proceso finalizado")
    row.estado = payload.estado
    # Explicit increment also records repeated follow-ups in the same state.
    row.revision += 1
    try:
        event = append_event(db, row, process, payload, payload.descripcion, payload.respuesta)
        commit(db)
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "La intervención cambió; recarga antes de continuar")
    return event_out(event)
