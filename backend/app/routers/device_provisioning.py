"""Administrator provisioning; plaintext credentials are returned only on issue."""
from datetime import timedelta
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models as m
from app.services.access import business_db, actor_id
from app.services.telemetry_v2 import utc_now, aware, token_hash
from app.telemetry_contract import CalibrationCreate, CredentialCreate

router = APIRouter(prefix="/api/dispositivos/{device_id}", tags=["Aprovisionamiento IoT"])


def _device(db, ident):
    device = db.query(m.Dispositivo).filter_by(id=ident).with_for_update().first()
    if device is None:
        raise HTTPException(404, "Dispositivo no encontrado")
    return device


def _credential_metadata(credential):
    return {"credential_id": credential.id, "label": credential.etiqueta,
            "created_at": aware(credential.creada_en), "expires_at": aware(credential.expira_en),
            "revoked_at": aware(credential.revocada_en) if credential.revocada_en else None}


@router.post("/credenciales", status_code=201)
def issue_credential(device_id: int, payload: CredentialCreate, response: Response,
                     db: Session = Depends(business_db("provision"))):
    device = _device(db, device_id)
    if device.origen is not None and device.origen != payload.source:
        raise HTTPException(409, "El origen de un dispositivo aprovisionado no se puede cambiar")
    device.origen = payload.source
    # The database guard validates source before inserting the credential.
    # Both writes remain in this transaction; rollback preserves the old state.
    db.flush()
    ident, now = str(uuid4()), utc_now()
    token = "mosto_v2." + ident + "." + secrets.token_urlsafe(32)
    credential = m.CredencialDispositivo(id=ident, dispositivo_id=device.id,
        token_hash=token_hash(token), etiqueta=payload.label, creada_en=now,
        expira_en=now + timedelta(days=payload.expires_days), creada_por=actor_id(db))
    db.add(credential)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {**_credential_metadata(credential), "token": token, "source": device.origen}


@router.get("/credenciales")
def list_credentials(device_id: int, db: Session = Depends(business_db("provision"))):
    _device(db, device_id)
    return [_credential_metadata(row) for row in db.query(m.CredencialDispositivo).filter_by(dispositivo_id=device_id)]


@router.delete("/credenciales/{credential_id}")
def revoke_credential(device_id: int, credential_id: UUID,
                      db: Session = Depends(business_db("provision"))):
    _device(db, device_id)
    credential = db.query(m.CredencialDispositivo).filter_by(id=str(credential_id), dispositivo_id=device_id).first()
    if credential is None:
        raise HTTPException(404, "Credencial no encontrada")
    if credential.revocada_en is None:
        credential.revocada_en = utc_now()
        db.commit()
    return _credential_metadata(credential)


def _calibration_metadata(row):
    return {"calibration_id": row.id, "device_id": row.dispositivo_id,
            **row.parametros, "created_at": aware(row.creada_en),
            "revoked_at": aware(row.revocada_en) if row.revocada_en else None}


@router.post("/calibraciones", status_code=201)
def create_calibration(device_id: int, payload: CalibrationCreate,
                       db: Session = Depends(business_db("provision"))):
    device = _device(db, device_id)
    expected = {"fisico": "tilt_polynomial", "simulado": "synthetic_identity"}.get(device.origen)
    if expected is None or payload.method != expected:
        raise HTTPException(409, "Aprovisione el dispositivo y use el método correspondiente a su origen")
    if payload.simulation is not None:
        spec = payload.simulation
        process = db.query(m.ProcesoFermentacion).filter_by(id=spec.process_id).first()
        if process is None:
            raise HTTPException(404, "Proceso de simulación no encontrado")
        if process.fecha_inicio is None or aware(process.fecha_inicio) != spec.process_start:
            raise HTTPException(409, "El reloj del simulador debe coincidir con el inicio del proceso")
        if payload.valid_from > spec.process_start:
            raise HTTPException(422, "La calibración debe cubrir el comienzo de la trayectoria")
        assignment = db.query(m.AsignacionDispositivo).filter_by(
            dispositivo_id=device.id, cuba_id=process.cuba_id, activo=True).first()
        if assignment is None or aware(assignment.asignado_en) > spec.process_start:
            raise HTTPException(409, "El dispositivo debe estar asignado desde el inicio de la simulación")
    calibration = m.CalibracionDispositivo(dispositivo_id=device.id, version=payload.version,
        metodo=payload.method, parametros=payload.model_dump(mode="json"), valida_desde=payload.valid_from,
        valida_hasta=payload.valid_until, creada_en=utc_now(), creada_por=actor_id(db))
    db.add(calibration)
    db.commit()
    return _calibration_metadata(calibration)


@router.get("/calibraciones")
def list_calibrations(device_id: int, db: Session = Depends(business_db("provision"))):
    _device(db, device_id)
    return [_calibration_metadata(row) for row in db.query(m.CalibracionDispositivo).filter_by(dispositivo_id=device_id)]


@router.delete("/calibraciones/{calibration_id}")
def revoke_calibration(device_id: int, calibration_id: int,
                       db: Session = Depends(business_db("provision"))):
    _device(db, device_id)
    calibration = db.query(m.CalibracionDispositivo).filter_by(id=calibration_id, dispositivo_id=device_id).first()
    if calibration is None:
        raise HTTPException(404, "Calibración no encontrada")
    if calibration.revocada_en is None:
        calibration.revocada_en = utc_now()
        db.commit()
    return _calibration_metadata(calibration)
