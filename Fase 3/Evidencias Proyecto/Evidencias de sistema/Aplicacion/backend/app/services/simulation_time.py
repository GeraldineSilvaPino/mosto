"""Resolve immutable simulation clocks; physical observations keep real UTC."""
import json
from sqlalchemy import select

from app import models as m
from app.simulation.clock import SimulationClock
from app.services.telemetry_v2 import aware


def process_clock_at(db, process_id, cutoff):
    # The process scope governs this immutable metadata even when its original
    # instrument has since moved. Only check whether registration was known.
    c = m.CalibracionDispositivo.__table__.c
    known = select(c.id).where(c.parametros["simulation"]["process_id"].as_integer() == process_id,
                               c.creada_en <= cutoff).exists()
    row = db.query(m.RelojProceso.clave).filter(m.RelojProceso.fermentacion_id == process_id, known).first()
    if row is None:
        return None
    real, simulated, factor = json.loads(row[0])
    return SimulationClock(real_anchor=real, simulated_anchor=simulated, factor=factor) if real else None


def observation_end(process, cutoff, clock):
    end = min(cutoff, aware(process.fecha_real_fin)) if process.fecha_real_fin else cutoff
    if clock is None:
        return end
    return clock.simulated_at(max(end, clock.real_anchor))


def message_clock(db, message):
    if message.origen != 'simulado' or message.calibracion_id is None:
        return None
    calibration = db.get(m.CalibracionDispositivo, message.calibracion_id)
    if calibration is None:
        return process_clock_at(db, message.fermentacion_id, aware(message.recibido_en))
    data = calibration.parametros.get('simulation_clock')
    if data is None:
        return None
    spec = calibration.parametros.get('simulation') or {}
    if calibration.dispositivo_id != message.dispositivo_id or spec.get('process_id') != message.fermentacion_id:
        raise ValueError('Simulation clock does not belong to the message scope')
    # Revocation must not rewrite the meaning of historical observations.
    return SimulationClock.model_validate(data)
