"""Human observations with explicit methods; never fed to automatic telemetry or ML."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from sqlalchemy.orm import Session, aliased
from sqlalchemy import or_

from app import models as m
from app.services.access import actor_id, business_db, normalize_role, WRITE_ROLES
from app.routers.interventions import require, lock_process, request_data, check_retry

router = APIRouter(prefix="/api/mediciones-manuales", tags=["Mediciones manuales"])
db_scope = business_db("operations")
# Broad input limits, not enological thresholds or proof of calibration.
CATALOG = {
    "temperatura": dict(nombre="Temperatura", unidad="°C", minimo=-50, maximo=150, metodos=["termometro"]),
    "brix_aparente": dict(nombre="Brix aparente", unidad="°Bx", minimo=-10, maximo=90, metodos=["refractometro", "densimetro_brix"]),
    "densidad": dict(nombre="Densidad", unidad="g/mL", minimo=0.5, maximo=2, metodos=["densimetro"]),
    "ph": dict(nombre="pH", unidad="pH", minimo=0, maximo=14, metodos=["phmetro"]),
}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    fermentacion_id: int = Field(gt=0)
    alerta_id: int | None = Field(default=None, gt=0)
    intervencion_id: int | None = Field(default=None, gt=0)
    variable: str
    valor: FiniteFloat = Field(strict=True)
    unidad: str
    metodo: str
    instrumento: str = Field(min_length=3, max_length=200)
    evidencia: str = Field(min_length=5, max_length=2000)
    observado_en: AwareDatetime

    @model_validator(mode="after")
    def validate_measurement(self):
        definition = CATALOG.get(self.variable)
        if definition is None or self.unidad != definition['unidad'] or self.metodo not in definition['metodos']:
            raise ValueError("Variable, unidad y método deben corresponder al catálogo")
        if not definition['minimo'] <= self.valor <= definition['maximo']:
            raise ValueError("Valor fuera del rango de entrada permitido")
        self.observado_en = self.observado_en.astimezone(timezone.utc)
        return self


class Annulment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    motivo: str = Field(min_length=5, max_length=2000)


def measurement_details(query):
    annuller = aliased(m.Usuario)
    return (query.add_columns(m.Usuario.nomb_compl, m.AnulacionMedicion, annuller.nomb_compl)
            .outerjoin(m.Usuario, m.Usuario.id == m.MedicionManual.usuario_id)
            .outerjoin(m.AnulacionMedicion, m.AnulacionMedicion.medicion_id == m.MedicionManual.id)
            .outerjoin(annuller, annuller.id == m.AnulacionMedicion.usuario_id))


def output(row, author, annulment, annulled_by):
    if author is None or (annulment is not None and annulled_by is None):
        raise HTTPException(404, "Registro inexistente o fuera del ámbito autorizado")
    result = {field: getattr(row, field) for field in (
        "id", "fermentacion_id", "alerta_id", "intervencion_id", "bitacora_id", "usuario_id",
        "variable", "valor", "unidad", "metodo", "instrumento", "evidencia")}
    result.update(origen="manual", observado_en=aware(row.observado_en), registrado_en=aware(row.registrado_en))
    result['autor'] = author
    result['anulacion'] = None if annulment is None else dict(
        id=annulment.id, motivo=annulment.motivo, usuario_id=annulment.usuario_id,
        autor=annulled_by,
        registrado_en=aware(annulment.registrado_en), bitacora_id=annulment.bitacora_id)
    return result


def measurement_out(db, row):
    query = db.query(m.MedicionManual).filter_by(id=row.id)
    return output(*measurement_details(query).one())


@router.get("/contexto/{process_id}")
def context(process_id: int, db: Session = Depends(db_scope)):
    process = require(db, m.ProcesoFermentacion, process_id)
    cube = require(db, m.Cuba, process.cuba_id)
    role = db.query(m.Rol.codigo).join(m.UsuarioBodega).filter(
        m.UsuarioBodega.usuario_id == actor_id(db), m.UsuarioBodega.bodega_id == cube.bodega_id).scalar()
    return dict(catalogo=CATALOG, puede_operar=normalize_role(role) in WRITE_ROLES['operations'],
                inicio=aware(process.fecha_inicio), fin=aware(process.fecha_real_fin) if process.fecha_real_fin else None)


@router.get("/intervenciones/{process_id}")
def intervention_options(process_id: int, alerta_id: int | None = Query(None, gt=0),
                         limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                         db: Session = Depends(db_scope)):
    require(db, m.ProcesoFermentacion, process_id)
    if alerta_id is not None:
        alert = require(db, m.EventoAlerta, alerta_id)
        if alert.fermentacion_id != process_id:
            raise HTTPException(409, "La alerta debe pertenecer al mismo proceso")
    query = db.query(m.IntervencionOperativa).filter_by(fermentacion_id=process_id)
    if alerta_id is not None:
        query = query.filter(or_(m.IntervencionOperativa.alerta_id.is_(None),
                                 m.IntervencionOperativa.alerta_id == alerta_id))
    return dict(total=query.count(), items=[dict(id=row.id, accion=row.accion,
                estado=row.estado, alerta_id=row.alerta_id) for row in
                query.order_by(m.IntervencionOperativa.id.desc()).offset(offset).limit(limit)])


@router.get("")
def list_measurements(fermentacion_id: int = Query(..., gt=0), alerta_id: int | None = Query(None, gt=0),
                      limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                      db: Session = Depends(db_scope)):
    require(db, m.ProcesoFermentacion, fermentacion_id)
    query = db.query(m.MedicionManual).filter_by(fermentacion_id=fermentacion_id)
    if alerta_id is not None:
        alert = require(db, m.EventoAlerta, alerta_id)
        if alert.fermentacion_id != fermentacion_id:
            raise HTTPException(409, "La alerta debe pertenecer al mismo proceso")
        query = query.filter_by(alerta_id=alerta_id)
    page = measurement_details(query).order_by(m.MedicionManual.observado_en.desc(), m.MedicionManual.id.desc())
    return dict(total=query.count(), items=[output(*row) for row in page.offset(offset).limit(limit)])


def note(db, process, alert_id, description, now):
    row = m.BitacoraIntervencion(usuario_id=actor_id(db), cuba_id=process.cuba_id,
        fermentacion_id=process.id, alerta_id=alert_id, fecha_registro=now,
        tipo_intervencion="medicion_manual", descripcion=description)
    db.add(row); db.flush()
    return row


@router.post("", status_code=201)
def record(payload: Measurement, db: Session = Depends(db_scope)):
    process = lock_process(db, payload.fermentacion_id)
    request = request_data(payload, db)
    previous = db.query(m.MedicionManual).filter_by(
        fermentacion_id=process.id, request_id=str(payload.request_id)).first()
    if previous:
        check_retry(previous, request)
        return measurement_out(db, previous)
    now = datetime.now(timezone.utc)
    if payload.observado_en > now or payload.observado_en < aware(process.fecha_inicio):
        raise HTTPException(409, "La observación debe estar entre el inicio del proceso y la hora actual")
    if process.estado not in {'en_proceso', 'detenida'} and not process.fecha_real_fin:
        raise HTTPException(409, "Proceso cerrado sin fecha de cierre verificable")
    if process.fecha_real_fin and payload.observado_en > aware(process.fecha_real_fin):
        raise HTTPException(409, "La observación es posterior al cierre del proceso")
    if payload.alerta_id is not None:
        alert = require(db, m.EventoAlerta, payload.alerta_id)
        if alert.fermentacion_id != process.id:
            raise HTTPException(409, "La alerta debe pertenecer al mismo proceso")
    if payload.intervencion_id is not None:
        intervention = require(db, m.IntervencionOperativa, payload.intervencion_id)
        if intervention.fermentacion_id != process.id or (payload.alerta_id is not None and
                intervention.alerta_id is not None and intervention.alerta_id != payload.alerta_id):
            raise HTTPException(409, "La intervención debe corresponder al proceso y alerta indicados")
    entry = note(db, process, payload.alerta_id,
        f"Medición manual · {payload.variable}: {payload.valor} {payload.unidad} · {payload.metodo}\n"
        f"Instrumento: {payload.instrumento} · Observada: {payload.observado_en.isoformat()}\n{payload.evidencia}", now)
    row = m.MedicionManual(**payload.model_dump(exclude={'request_id'}), request_id=str(payload.request_id),
        solicitud=request, usuario_id=actor_id(db), bitacora_id=entry.id, registrado_en=now)
    db.add(row); db.flush(); db.commit()
    return measurement_out(db, row)


@router.post("/{ident}/anular")
def annul(ident: int, payload: Annulment, db: Session = Depends(db_scope)):
    row = require(db, m.MedicionManual, ident)
    process = lock_process(db, row.fermentacion_id)
    previous = db.query(m.AnulacionMedicion).filter_by(medicion_id=ident).first()
    if previous:
        check_retry(previous, request_data(payload, db))
        return measurement_out(db, row)
    now = datetime.now(timezone.utc)
    entry = note(db, process, row.alerta_id, f"Anulación de medición manual #{ident}\n{payload.motivo}", now)
    db.add(m.AnulacionMedicion(medicion_id=ident, bitacora_id=entry.id, usuario_id=actor_id(db),
        motivo=payload.motivo, registrado_en=now, request_id=str(payload.request_id), solicitud=request_data(payload, db)))
    db.flush(); db.commit()
    return measurement_out(db, row)
