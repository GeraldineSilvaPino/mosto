"""Device-key HTTP ingress; JWT and shared demo keys do not authorize ingestion."""
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.telemetry_v2 import ingest, accepted, authenticate_device, utc_now
from app.services.access import business_db
from app.telemetry_contract import TelemetryV2, TelemetryAccepted
from app.models import MensajeTelemetria, CalibracionDispositivo

ingest_router = APIRouter(prefix="/api/v2/telemetria", tags=["Telemetría v2"])
audit_router = APIRouter(prefix="/api/v2/telemetria", tags=["Auditoría de telemetría"])


@ingest_router.get("/configuracion/{device_id}/{calibration_id}")
def emitter_configuration(device_id: int, calibration_id: int, response: Response,
                          device_key: str | None = Header(default=None, alias="X-Mosto-Device-Key"),
                          db: Session = Depends(get_db)):
    from fastapi import HTTPException
    device, _ = authenticate_device(db, device_key, device_id, utc_now())
    calibration = db.query(CalibracionDispositivo).filter_by(id=calibration_id, dispositivo_id=device.id).first()
    if calibration is None or calibration.revocada_en is not None:
        raise HTTPException(409, "Calibración no disponible")
    response.headers["Cache-Control"] = "no-store"
    return {"device_id": device.id, "source": device.origen, "calibration_id": calibration.id,
            "simulation": calibration.parametros.get("simulation"),
            "simulation_clock": calibration.parametros.get("simulation_clock"),
            "emitter_faults": calibration.parametros.get("emitter_faults")}


@ingest_router.post("", response_model=TelemetryAccepted, status_code=201)
def receive(payload: TelemetryV2, response: Response,
            device_key: str | None = Header(default=None, alias="X-Mosto-Device-Key"),
            db: Session = Depends(get_db)):
    result = ingest(db, payload, device_key)
    response.status_code = 200 if result.duplicate else 201
    response.headers["Cache-Control"] = "no-store"
    return result


@audit_router.get("/{message_id}", response_model=TelemetryAccepted)
def get_receipt(message_id: int, response: Response, db: Session = Depends(business_db("operations"))):
    from fastapi import HTTPException
    message = db.query(MensajeTelemetria).filter_by(id=message_id).first()
    if message is None:
        raise HTTPException(404, "Mensaje no encontrado")
    response.headers["Cache-Control"] = "no-store"
    return accepted(message)
