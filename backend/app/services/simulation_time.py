"""Resolve immutable simulation clocks; physical observations keep real UTC."""
from app import models as m
from app.simulation.clock import SimulationClock


def message_clock(db, message):
    if message.origen != 'simulado' or message.calibracion_id is None:
        return None
    calibration = db.get(m.CalibracionDispositivo, message.calibracion_id)
    if calibration is None:
        return None
    data = calibration.parametros.get('simulation_clock')
    if data is None:
        return None
    spec = calibration.parametros.get('simulation') or {}
    if calibration.dispositivo_id != message.dispositivo_id or spec.get('process_id') != message.fermentacion_id:
        raise ValueError('Simulation clock does not belong to the message scope')
    # Revocation must not rewrite the meaning of historical observations.
    return SimulationClock.model_validate(data)
