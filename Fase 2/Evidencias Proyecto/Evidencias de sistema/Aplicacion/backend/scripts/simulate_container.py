"""Run a pre-provisioned synthetic device; Supabase is the delivery checkpoint.

No schema changes or seeding. Credentials are restricted to the selected demo
device and expire with the registered trajectory. Never modifies physical data.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import signal
import tempfile
from threading import Event
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from app import models as m
from app.database import engine, SessionLocal, settings
from app.services.telemetry_v2 import aware, token_hash
from app.simulation.model import SimulationSpec
from app.simulation.worker import EmitterConfig, FleetConfig, Worker, run_id


def provision_config():
    device_id = int(os.environ['MOSTO_SIMULATION_DEVICE_ID'])
    with SessionLocal.begin() as db:
        device = db.get(m.Dispositivo, device_id)
        if device is None or device.origen != 'simulado':
            raise ValueError('Configured device must already be explicitly simulated')
        calibration = db.query(m.CalibracionDispositivo).filter_by(
            dispositivo_id=device_id, revocada_en=None).order_by(m.CalibracionDispositivo.id.desc()).first()
        if calibration is None or calibration.metodo != 'synthetic_identity':
            raise ValueError('Missing synthetic calibration')
        params = calibration.parametros
        if params.get('simulation_clock') or params.get('emitter_faults'):
            raise ValueError('Container emitter supports ordinary wall-clock trajectories only')
        spec = SimulationSpec.model_validate(params['simulation'])
        process = db.get(m.ProcesoFermentacion, spec.process_id)
        tank = db.get(m.Cuba, process.cuba_id)
        warehouse = db.get(m.Bodega, tank.bodega_id)
        actor = db.get(m.Usuario, calibration.creada_por)
        if (tank.codigo not in {'DEMO-LIVE', 'DEMO-ML'} or warehouse.empresa_id != device.empresa_id
                or actor is None or actor.empresa_id != device.empresa_id
                or not actor.activo or process.fecha_real_fin is not None
                or process.estado != 'en_proceso' or aware(process.fecha_inicio) != spec.process_start):
            raise ValueError('Demo ownership or process does not match the approved trajectory')
        assignment = db.query(m.AsignacionDispositivo).filter_by(
            dispositivo_id=device.id, cuba_id=tank.id, activo=True).one()
        if aware(assignment.asignado_en) > spec.process_start:
            raise ValueError('Assignment does not cover trajectory')
        # Key never leaves the backend; a JWT key rotation creates a new device key.
        secret = hmac.new(settings.jwt_secret.encode(),
                          f'mosto/container-emitter/{device.id}/{calibration.id}'.encode(),
                          hashlib.sha256).hexdigest()
        ident = str(uuid5(NAMESPACE_URL, f'mosto/container-key/{device.id}/{token_hash(secret)}'))
        token = f'mosto_v2.{ident}.{secret}'
        expires = spec.process_start + timedelta(hours=spec.duration_hours, minutes=10)
        if expires <= datetime.now(timezone.utc):
            raise ValueError('Demo trajectory has finished; explicit renewal is required')
        # Transaction-scoped advisory lock works through Supabase transaction pooler.
        db.execute(text('SELECT pg_advisory_xact_lock(746522004, :device)'), {'device': device.id})
        credential = db.get(m.CredencialDispositivo, ident)
        if credential is None:
            db.add(m.CredencialDispositivo(id=ident, dispositivo_id=device.id,
                token_hash=token_hash(token), etiqueta=f'Docker {tank.codigo}',
                creada_en=datetime.now(timezone.utc), expira_en=expires, creada_por=actor.id))
        elif credential.revocada_en is not None or aware(credential.expira_en) <= datetime.now(timezone.utc):
            raise ValueError('Container credential revoked or expired')
        config = EmitterConfig(device_id=device.id, calibration_id=calibration.id,
                               key_env=f'MOSTO_SIM_DEVICE_{device.id}', simulation=spec)
    fleet = FleetConfig(base_url=f"http://127.0.0.1:{int(os.environ.get('PORT', '8000'))}", devices=[config])
    return fleet, {config.key_env: token}


def restore_checkpoint(worker, config, connection):
    ident = run_id(config)
    seq = list(connection.execute(select(m.MensajeTelemetria.secuencia).where(
        m.MensajeTelemetria.dispositivo_id == config.device_id,
        m.MensajeTelemetria.boot_id == ident).order_by(m.MensajeTelemetria.secuencia)).scalars())
    # Only an acknowledged contiguous prefix is safe to skip; gaps are replayed.
    next_sequence = 0
    for number in seq:
        if number != next_sequence:
            break
        next_sequence += 1
    local = worker.db.execute('SELECT next_sequence FROM runs WHERE run_id=?', (ident,)).fetchone()[0]
    if next_sequence > local:
        with worker.db:
            worker.db.execute('DELETE FROM outbox WHERE run_id=? AND sequence<?', (ident, next_sequence))
            worker.db.execute('UPDATE runs SET next_sequence=?,generated_sequence=MAX(generated_sequence,?) WHERE run_id=?',
                              (next_sequence, next_sequence, ident))
    return next_sequence


def main():
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    fleet, keys = provision_config()
    config = fleet.devices[0]
    with tempfile.TemporaryDirectory(prefix='mosto-emitter-') as directory:
        worker = Worker(fleet, Path(directory) / 'state.sqlite', keys=keys)
        previous = None
        try:
            while not stopped.is_set():
                try:
                    with engine.begin() as connection:
                        acquired = connection.execute(text('SELECT pg_try_advisory_xact_lock(746522005, :device)'),
                                                      {'device': config.device_id}).scalar()
                        if acquired:
                            restore_checkpoint(worker, config, connection)
                            delivered = worker.tick(max_per_device=12)
                            status = worker.statuses()
                            if delivered or status != previous:
                                print(json.dumps({'simulation_device': config.device_id, 'delivered': delivered, 'devices': status}), flush=True)
                                previous = status
                            if any(s['status'] in {'blocked', 'completed'} for s in status):
                                return
                except Exception as exc:
                    # No SQL parameters, credentials or tokens in logs.
                    print(f'[simulation] Temporary failure: {type(exc).__name__}', flush=True)
                    stopped.wait(20)
                stopped.wait(5)
        finally:
            worker.close()


if __name__ == '__main__':
    main()
