"""Canonical ingestion: authenticate, resolve time, calibrate, commit exactly once."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.telemetry_contract import CalibrationCreate, TelemetryAccepted

MAX_FUTURE_SKEW = timedelta(minutes=2)
DELAY_THRESHOLD = timedelta(minutes=10)


def utc_now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_device(db, token, device_id, received_at):
    invalid = HTTPException(401, "Credencial de dispositivo inválida o revocada")
    try:
        prefix, key_id, secret = (token or "").split(".")
        if prefix != "mosto_v2" or not 32 <= len(secret) <= 128:
            raise ValueError()
        key_id = str(UUID(key_id))
    except (ValueError, TypeError):
        raise invalid
    credential = db.query(m.CredencialDispositivo).filter_by(id=key_id).first()
    if credential is None or not hmac.compare_digest(credential.token_hash, token_hash(token)):
        raise invalid
    if credential.dispositivo_id != device_id:
        raise HTTPException(403, "La credencial no autoriza este dispositivo")
    device = db.query(m.Dispositivo).filter_by(id=device_id).with_for_update().one()
    # Rotation/revocation also locks this device; refresh after waiting for it.
    db.refresh(credential)
    if credential.revocada_en is not None or aware(credential.expira_en) <= utc_now():
        raise invalid
    company = db.query(m.EmpresaCliente).filter_by(id=device.empresa_id, activo=True).first()
    if company is None or device.estado != "activo" or device.origen not in {"fisico", "simulado"}:
        raise HTTPException(403, "Dispositivo o empresa no habilitados para transmitir")
    return device, credential


def accepted(message, duplicate=False):
    return TelemetryAccepted(
        message_id=message.id, duplicate=duplicate, device_id=message.dispositivo_id,
        process_id=message.fermentacion_id, source=message.origen,
        observed_at=aware(message.observado_en), received_at=aware(message.recibido_en),
        temperature_c={"value": message.temperatura, "quality": message.calidad_temperatura},
        brix_apparent={"value": message.brix, "quality": message.calidad_brix},
        out_of_order=message.fuera_de_orden, delayed=message.retrasado,
        diagnostics=message.diagnosticos)


def _existing(db, payload, digest):
    message = db.query(m.MensajeTelemetria).filter_by(
        dispositivo_id=payload.device_id, boot_id=str(payload.boot_id), secuencia=payload.sequence).first()
    if message is not None and message.payload_hash != digest:
        raise HTTPException(409, "La secuencia ya fue utilizada con un contenido distinto")
    return message


def evaluate_channels(device, payload, calibration):
    temp_quality, brix_quality = payload.temperature_c.quality, payload.brix_apparent.quality
    temperature = payload.temperature_c.value if temp_quality == "good" else None
    brix = payload.brix_apparent.value if brix_quality == "good" else None
    diagnostics = []
    if temperature is not None and not -55 <= temperature <= 125:
        temperature, temp_quality = None, "invalid"
        diagnostics.append("temperature_outside_sensor_range")
    if brix_quality != "good":
        return temperature, temp_quality, None, brix_quality, diagnostics
    if calibration is None or calibration.revocada_en is not None or (
        payload.observed_at < aware(calibration.valida_desde) or
        calibration.valida_hasta is not None and payload.observed_at >= aware(calibration.valida_hasta)
    ):
        diagnostics.append("calibration_not_valid")
        return temperature, temp_quality, None, "uncalibrated", diagnostics
    parameters = CalibrationCreate.model_validate(calibration.parametros)
    if device.origen == "simulado" and parameters.method == "synthetic_identity":
        return temperature, temp_quality, brix, brix_quality, diagnostics
    if parameters.method != "tilt_polynomial":
        diagnostics.append("calibration_method_mismatch")
        return temperature, temp_quality, None, "uncalibrated", diagnostics
    tilt = payload.tilt_degrees
    if tilt is None or not parameters.tilt_min <= tilt <= parameters.tilt_max:
        diagnostics.append("tilt_missing_or_outside_calibration")
        return temperature, temp_quality, None, "uncalibrated", diagnostics
    if parameters.temperature_coefficient and temperature is None:
        diagnostics.append("temperature_required_for_calibration")
        return temperature, temp_quality, None, "uncalibrated", diagnostics
    calculated = sum(coefficient * tilt ** index for index, coefficient in enumerate(parameters.coefficients))
    if parameters.temperature_coefficient:
        calculated += parameters.temperature_coefficient * (temperature - parameters.reference_temperature)
    if not math.isfinite(calculated) or abs(calculated - brix) > parameters.tolerance + 1e-9:
        diagnostics.append("reported_brix_disagrees_with_calibration")
        return temperature, temp_quality, None, "invalid", diagnostics
    # The authoritative value is computed from the frozen calibration, not the payload's sugar claim.
    return temperature, temp_quality, calculated, "good", diagnostics


def ingest(db, payload, token):
    received_at = utc_now()
    device, credential = authenticate_device(db, token, payload.device_id, received_at)
    raw = payload.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    previous = _existing(db, payload, digest)
    if previous is not None:
        # Replays return the original receipt, even if process/calibration later changed.
        return accepted(previous, duplicate=True)
    observed = payload.observed_at
    if observed > received_at + MAX_FUTURE_SKEW:
        raise HTTPException(422, "La hora de medición supera la tolerancia futura de dos minutos")
    assignments = db.query(m.AsignacionDispositivo).filter(
        m.AsignacionDispositivo.dispositivo_id == device.id,
        m.AsignacionDispositivo.asignado_en <= observed,
        or_(m.AsignacionDispositivo.desasignado_en.is_(None), m.AsignacionDispositivo.desasignado_en > observed)
    ).limit(2).all()
    if len(assignments) != 1:
        raise HTTPException(409, "No hay una asignación temporal inequívoca para esta medición")
    assignment = assignments[0]
    cube = db.query(m.Cuba).filter_by(id=assignment.cuba_id).with_for_update().one()
    warehouse = db.query(m.Bodega).filter_by(id=cube.bodega_id).one()
    if warehouse.empresa_id != device.empresa_id:
        raise HTTPException(409, "La asignación no es coherente con la empresa del dispositivo")
    processes = db.query(m.ProcesoFermentacion).filter(
        m.ProcesoFermentacion.cuba_id == cube.id, m.ProcesoFermentacion.fecha_inicio <= observed,
        or_(m.ProcesoFermentacion.fecha_real_fin.is_(None), m.ProcesoFermentacion.fecha_real_fin > observed)
    ).limit(2).all()
    if len(processes) != 1:
        raise HTTPException(409, "No hay un proceso temporal inequívoco para esta medición")
    process = processes[0]
    first_source = db.query(m.MensajeTelemetria.origen).filter_by(fermentacion_id=process.id).order_by(m.MensajeTelemetria.id).first()
    if first_source is not None and first_source[0] != device.origen:
        raise HTTPException(409, "Un proceso no puede mezclar telemetría física y simulada")
    calibration = None
    if payload.calibration_id is not None:
        calibration = db.query(m.CalibracionDispositivo).filter_by(
            id=payload.calibration_id, dispositivo_id=device.id).first()
        if calibration is None:
            raise HTTPException(409, "Referencia de calibración no disponible para este dispositivo")
        if calibration.parametros.get("simulation_clock") is not None:
            raise HTTPException(409, "Reloj registrado; ingesta acelerada todavía no habilitada")
        spec = calibration.parametros.get("simulation")
        if spec is not None:
            from app.simulation.model import SimulationSpec
            spec = SimulationSpec.model_validate(spec)
            if device.origen != "simulado" or process.id != spec.process_id or aware(process.fecha_inicio) != spec.process_start:
                raise HTTPException(409, "La trayectoria simulada pertenece a otro proceso o reloj")
            if payload.sequence > spec.duration_hours * 12:
                raise HTTPException(422, "La secuencia supera la duración de la simulación")
            expected = spec.process_start + timedelta(seconds=payload.sequence * spec.cadence_seconds)
            if observed != expected:
                raise HTTPException(422, "La medición no coincide con la secuencia y el reloj de la simulación")
    temperature, tq, brix, bq, diagnostics = evaluate_channels(device, payload, calibration)
    # The legacy projection has numeric(5,2) fields; reject overflow without inventing/clipping a value.
    if brix is not None and not -999.99 <= brix <= 999.99:
        brix, bq = None, "invalid"
        diagnostics.append("brix_outside_storage_range")
    latest = db.query(m.MensajeTelemetria).filter_by(dispositivo_id=device.id).order_by(
        m.MensajeTelemetria.observado_en.desc(), m.MensajeTelemetria.id.desc()).first()
    out_of_order = latest is not None and observed < aware(latest.observado_en)
    delayed = received_at - observed > DELAY_THRESHOLD
    reading = m.LecturaTelemetria(
        dispositivo_id=device.id, fermentacion_id=process.id, timestamp=observed,
        temp_mosto=temperature, brix=brix, temp_ambiente=None, ph=None, densidad_sg=None,
        origen_dato="v2_" + device.origen, lectura_valida=tq == "good" and bq == "good")
    try:
        db.add(reading)
        db.flush()
        message = m.MensajeTelemetria(
            dispositivo_id=device.id, credencial_id=credential.id, boot_id=str(payload.boot_id),
            secuencia=payload.sequence, observado_en=observed, recibido_en=received_at,
            origen=device.origen, payload_hash=digest, payload=raw, asignacion_id=assignment.id,
            fermentacion_id=process.id, calibracion_id=payload.calibration_id, lectura_id=reading.id,
            calidad_temperatura=tq, calidad_brix=bq, temperatura=temperature, brix=brix,
            diagnosticos=diagnostics, fuera_de_orden=out_of_order, retrasado=delayed)
        db.add(message)
        db.flush()
        from app.services.episodes import evaluate_thermal
        evaluate_thermal(db, process, message)
        from app.services.kinetic_episodes import evaluate_kinetic
        evaluate_kinetic(db, process, message)
        device.ultima_recepcion = received_at
        db.commit()
    except IntegrityError:
        db.rollback()
        # Covers a concurrent retry on engines without SELECT FOR UPDATE.
        previous = _existing(db, payload, digest)
        if previous is not None:
            return accepted(previous, duplicate=True)
        raise HTTPException(409, "Conflicto de integridad o timestamp ya registrado; no se guardó el mensaje")
    db.refresh(message)
    return accepted(message)
