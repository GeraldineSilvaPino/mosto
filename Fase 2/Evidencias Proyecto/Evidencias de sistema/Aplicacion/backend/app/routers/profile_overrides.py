from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from sqlalchemy.orm import Session

from app import models as m
from app.services.access import actor_id, business_db, normalize_role, WRITE_ROLES
from app.services.telemetry_v2 import aware, utc_now
from app.services.profile_overrides import applied_profile
from app.routers.interventions import require, lock_process, request_data, check_retry

router = APIRouter(prefix='/api/procesos', tags=['Ajustes de perfil por proceso'])
scope = business_db('profile_overrides')


class Override(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    accion: Literal['ajustar', 'restaurar'] = 'ajustar'
    temp_min: FiniteFloat | None = Field(None, ge=-50, le=100, strict=True)
    temp_max: FiniteFloat | None = Field(None, ge=-50, le=100, strict=True)
    motivo: str = Field(min_length=10, max_length=2000)

    @model_validator(mode='after')
    def bounds(self):
        if self.accion == 'ajustar':
            if self.temp_min is None or self.temp_max is None or self.temp_min >= self.temp_max:
                raise ValueError('Se requiere una banda térmica completa y creciente')
        elif self.temp_min is not None or self.temp_max is not None:
            raise ValueError('Restaurar usa la banda inicial sin nuevos valores')
        return self


def out(row):
    return {**{key: getattr(row, key) for key in ('id', 'revision', 'usuario_id', 'bitacora_id', 'accion', 'motivo', 'configuracion')},
            'vigente_desde': aware(row.vigente_desde)}


@router.get('/{process_id}/ajustes-perfil')
def history(process_id: int, response: Response, limit: int = Query(20, ge=1, le=100),
            offset: int = Query(0, ge=0), db: Session = Depends(scope)):
    process = require(db, m.ProcesoFermentacion, process_id)
    cube = require(db, m.Cuba, process.cuba_id)
    role = db.query(m.Rol.codigo).join(m.UsuarioBodega).filter(
        m.UsuarioBodega.usuario_id == actor_id(db), m.UsuarioBodega.bodega_id == cube.bodega_id).scalar()
    rows = db.query(m.AjustePerfilProceso).filter_by(fermentacion_id=process_id)
    latest = rows.order_by(m.AjustePerfilProceso.revision.desc()).first()
    profile = db.get(m.PerfilFermentacion, process.perfil_id) if process.perfil_id else None
    episodes = db.query(m.EventoAlerta).filter(m.EventoAlerta.fermentacion_id == process_id,
        m.EventoAlerta.tipo_alerta.in_(['temperatura_alta', 'temperatura_baja']),
        m.EventoAlerta.version_regla.isnot(None), m.EventoAlerta.fin_condicion.is_(None)).all()
    response.headers['Cache-Control'] = 'no-store'
    return dict(revision=latest.revision if latest else 0, initial=process.perfil_snapshot,
        applied=applied_profile(db, process, profile, utc_now()),
        can_approve=normalize_role(role) in WRITE_ROLES['profile_overrides'],
        can_adjust=process.perfil_snapshot is not None and process.perfil_snapshot.get('temp_min') is not None and process.perfil_snapshot.get('temp_max') is not None and process.estado in {'en_proceso', 'detenida'} and process.fecha_real_fin is None,
        open_episodes=[dict(id=e.id, configuration=(e.evidencia or {}).get('configuration')) for e in episodes],
        total=rows.count(), items=[out(row) for row in rows.order_by(m.AjustePerfilProceso.revision.desc()).offset(offset).limit(limit)])


@router.post('/{process_id}/ajustes-perfil', status_code=201)
def approve(process_id: int, payload: Override, db: Session = Depends(scope)):
    process = lock_process(db, process_id)
    rows = db.query(m.AjustePerfilProceso).filter_by(fermentacion_id=process_id)
    previous = rows.filter_by(request_id=str(payload.request_id)).first()
    request = request_data(payload, db)
    if previous:
        check_retry(previous, request)
        return out(previous)
    if process.perfil_snapshot is None:
        raise HTTPException(409, 'El proceso no conserva un perfil inicial verificable')
    if process.perfil_snapshot.get('temp_min') is None or process.perfil_snapshot.get('temp_max') is None:
        raise HTTPException(409, 'El perfil inicial debe conservar una banda térmica completa')
    if process.estado not in {'en_proceso', 'detenida'} or process.fecha_real_fin is not None:
        raise HTTPException(409, 'No se ajusta el perfil de un proceso cerrado')
    latest = rows.order_by(m.AjustePerfilProceso.revision.desc()).first()
    revision = latest.revision if latest else 0
    if revision != payload.expected_revision:
        raise HTTPException(409, 'El perfil aplicado cambió; recarga antes de aprobar')
    now = utc_now()
    if now < aware(process.fecha_inicio):
        raise HTTPException(409, 'El proceso aún no ha comenzado')
    last_message = db.query(m.MensajeTelemetria).filter_by(fermentacion_id=process_id).order_by(m.MensajeTelemetria.observado_en.desc()).first()
    if (last_message and aware(last_message.observado_en) >= now) or (latest and aware(latest.vigente_desde) >= now):
        raise HTTPException(409, 'La hora actual debe superar la última observación y ajuste; reintenta después')
    config = dict(latest.configuracion if latest else process.perfil_snapshot)
    if payload.accion == 'restaurar':
        config = dict(process.perfil_snapshot)
    else:
        config.update(temp_min=payload.temp_min, temp_max=payload.temp_max)
    low, high = config.get('temp_min'), config.get('temp_max')
    if low is None or high is None or low >= high:
        raise HTTPException(409, 'La configuración inicial no tiene una banda térmica completa para restaurar')
    current = latest.configuracion if latest else process.perfil_snapshot
    if config == current:
        raise HTTPException(409, 'La solicitud no cambia la configuración aplicada')
    entry = m.BitacoraIntervencion(usuario_id=actor_id(db), cuba_id=process.cuba_id, fermentacion_id=process_id,
        fecha_registro=now, tipo_intervencion='ajuste_perfil',
        descripcion=f'Ajuste térmico aprobado · revisión {revision + 1} · {low}–{high} °C · vigente desde {now.isoformat()}\n{payload.motivo}')
    db.add(entry); db.flush()
    row = m.AjustePerfilProceso(fermentacion_id=process_id, revision=revision + 1, usuario_id=actor_id(db),
        bitacora_id=entry.id, vigente_desde=now, accion=payload.accion, motivo=payload.motivo,
        configuracion=config, request_id=str(payload.request_id), solicitud=request)
    db.add(row); db.flush(); db.commit()
    return out(row)
