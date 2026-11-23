"""Temporary legacy simulator boundary, never an authentication scheme for hardware."""
import hmac
from fastapi import Header, HTTPException
from app.database import settings


def require_demo_mode():
    if settings.environment not in {"demo", "test"}:
        raise HTTPException(403, "Simulation is only available in an isolated demo environment")


def require_simulator_key(x_mosto_simulator_key: str = Header(default="")):
    require_demo_mode()
    if not settings.simulator_key or not hmac.compare_digest(x_mosto_simulator_key, settings.simulator_key):
        raise HTTPException(401, "Invalid simulator credential")


def require_legacy_tank(db, cuba_id):
    """Keep demo injection out of provisioned devices and canonical processes."""
    from app.models import Cuba, Dispositivo, AsignacionDispositivo, ProcesoFermentacion, MensajeTelemetria
    devices = db.query(Dispositivo).filter(Dispositivo.id.in_(
        db.query(AsignacionDispositivo.dispositivo_id).filter_by(cuba_id=cuba_id, activo=True)
    )).order_by(Dispositivo.id).with_for_update().all()
    db.query(Cuba).filter_by(id=cuba_id).with_for_update().first()
    canonical = db.query(MensajeTelemetria.id).filter(MensajeTelemetria.fermentacion_id.in_(
        db.query(ProcesoFermentacion.id).filter(
            ProcesoFermentacion.cuba_id == cuba_id, ProcesoFermentacion.fecha_real_fin.is_(None))
    )).first()
    if any(device.origen is not None for device in devices) or canonical:
        raise HTTPException(409, "La cuba utiliza telemetría v2; no admite inyecciones demo legacy")
