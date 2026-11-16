"""Read-only provenance of registered synthetic trajectories, scoped by process."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.services.access import business_db
from app.services.telemetry_v2 import aware, utc_now
from app.simulation.model import SimulationSpec, phase_at, phase_weights

router = APIRouter(prefix="/api/simulaciones", tags=["Simulación enológica"])


@router.get("/procesos/{process_id}")
def process_simulation(process_id: int, db: Session = Depends(business_db("operations"))):
    process = db.query(m.ProcesoFermentacion).filter_by(id=process_id).first()
    if process is None:
        raise HTTPException(404, "Proceso no encontrado")
    latest = db.query(m.MensajeTelemetria).filter_by(fermentacion_id=process.id).order_by(
        m.MensajeTelemetria.observado_en.desc()).first()
    if latest:
        calibrations = db.query(m.CalibracionDispositivo).filter_by(id=latest.calibracion_id).all()
    else:
        devices = db.query(m.AsignacionDispositivo.dispositivo_id).filter_by(cuba_id=process.cuba_id, activo=True)
        calibrations = db.query(m.CalibracionDispositivo).filter(m.CalibracionDispositivo.dispositivo_id.in_(devices)).order_by(
            m.CalibracionDispositivo.id.desc()).all()
    for calibration in calibrations:
        recipe = calibration.parametros.get("simulation")
        if recipe is None or recipe.get("process_id") != process.id:
            continue
        spec = SimulationSpec.model_validate(recipe)
        if aware(process.fecha_inicio) != spec.process_start:
            continue
        now = utc_now()
        observed = aware(latest.observado_en) if latest else None
        age = (observed - spec.process_start).total_seconds() / 3600 if observed else None
        stop = min(now, aware(process.fecha_real_fin)) if process.fecha_real_fin else now
        calendar_age = max(0, (stop - spec.process_start).total_seconds() / 3600)
        lag = max(0, (stop - observed).total_seconds()) if observed else None
        return {
            "registered": True, "source": "simulado", "model_version": spec.model_version,
            "scenario": spec.scenario, "seed": spec.seed, "process_id": process.id,
            "calibration_id": calibration.id, "device_id": calibration.dispositivo_id,
            "cadence_seconds": spec.cadence_seconds, "process_start": spec.process_start,
            "duration_hours": spec.duration_hours, "clock": "wall_utc", "speed": 1,
            "observed_age_hours": age, "calendar_age_hours": calendar_age,
            "phase": phase_at(age) if age is not None else None,
            "phase_weights": phase_weights(age) if age is not None else None,
            "observed_at": observed, "received_at": aware(latest.recibido_en) if latest else None,
            "lag_seconds": lag, "process_closed": process.fecha_real_fin is not None,
            "calibration_revoked": calibration.revocada_en is not None,
            "coverage": "sin_muestras" if latest is None else "atrasado" if lag > 600 else "al_dia",
            "interpretation": "Fase programada del generador; no es una inferencia sobre levaduras reales",
        }
    return {"registered": False, "process_id": process.id}
