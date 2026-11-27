"""Read-only adapter for immutable v2 observations and historical availability."""
from datetime import timedelta

from app.models import MensajeTelemetria
from app.services.kinetics import Observation, extract, utc
from app.services.telemetry_v2 import aware


def kinetic_window(db, process, as_of, received_as_of):
    return db.query(
        MensajeTelemetria.fermentacion_id, MensajeTelemetria.observado_en, MensajeTelemetria.recibido_en,
        MensajeTelemetria.brix, MensajeTelemetria.temperatura, MensajeTelemetria.calidad_brix,
        MensajeTelemetria.calidad_temperatura, MensajeTelemetria.calibracion_id,
        MensajeTelemetria.dispositivo_id, MensajeTelemetria.origen,
    ).filter(
        MensajeTelemetria.fermentacion_id == process.id,
        MensajeTelemetria.observado_en >= as_of - timedelta(hours=24),
        MensajeTelemetria.observado_en <= as_of,
        MensajeTelemetria.recibido_en <= received_as_of,
    ).order_by(MensajeTelemetria.observado_en, MensajeTelemetria.id).all()


def summarize_kinetics(process, rows, as_of, received_as_of):
    observations = [Observation(
        process_id=r.fermentacion_id, observed_at=aware(r.observado_en),
        received_at=aware(r.recibido_en), brix=r.brix, temperature=r.temperatura,
        brix_quality=r.calidad_brix, temperature_quality=r.calidad_temperatura,
        calibration_id=r.calibracion_id, device_id=r.dispositivo_id, source=r.origen,
    ) for r in rows]
    result = extract(observations, process_id=process.id,
                     process_start=aware(process.fecha_inicio), as_of=as_of,
                     received_as_of=received_as_of)
    result.update(estado_ia="NO_VALIDADO", riesgo_pct=None, alerta_ia=False,
                  forecast_brix_24h=None, process_closed=process.fecha_real_fin is not None)
    return result


def process_kinetics(db, process, as_of, *, received_as_of=None):
    as_of = utc(as_of)
    received_as_of = as_of if received_as_of is None else utc(received_as_of)
    rows = kinetic_window(db, process, as_of, received_as_of)
    return summarize_kinetics(process, rows, as_of, received_as_of)
