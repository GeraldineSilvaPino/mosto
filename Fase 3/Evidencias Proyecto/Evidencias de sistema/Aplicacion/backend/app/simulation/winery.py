"""Provision a fleet on empty operational tables; caller owns the transaction."""
from datetime import datetime, timedelta, timezone
import secrets
from uuid import uuid4

from app import models as m
from app.services.profile_versions import record_version
from app.services.telemetry_v2 import token_hash
from app.simulation.model import SimulationSpec, MODEL_VERSION
from app.simulation.worker import FleetConfig, EmitterConfig
from app.telemetry_contract import CalibrationCreate


def create_winery_fleet(db, warehouse, profile, material, model, actor):
    if db.query(m.Cuba).filter_by(bodega_id=warehouse.id).first():
        raise ValueError("Fleet creation requires an empty tank inventory")
    if profile.bodega_id != warehouse.id or not profile.activo or actor.empresa_id != warehouse.empresa_id:
        raise ValueError("Check winery, active profile and operator")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    frozen = record_version(db, profile, actor.id).configuracion
    devices, keys = [], {}
    # Stage ages in hours. Samples are delivered for the final hour, then live.
    batches = [
        ("healthy", 12, 23.5, 21.0, 3.48),
        ("healthy", 38, 24.1, 22.0, 3.55),
        ("cold_shock", 68, 23.8, 21.5, 3.50),
        ("nutrient_depletion", 93, 24.4, 22.5, 3.60),
        ("slow", 122, 24.0, 20.5, 3.53),
    ]
    for index, (scenario, age, brix, temp, ph) in enumerate(batches, 1):
        start = now - timedelta(hours=age)
        tank = m.Cuba(codigo=f"SIM-{index:02}", bodega_id=warehouse.id, material_id=material.id,
                      sector_cuba="Fermentación", cap_litros=10000, estado_operativo="en_uso")
        device = m.Dispositivo(mac_address=f"02:4D:53:54:00:{index:02X}", empresa_id=warehouse.empresa_id,
                               modelo_id=model.id, tipo_dispositivo="DUAL", firmware_version=MODEL_VERSION,
                               estado="activo", origen="simulado")
        db.add_all([tank, device])
        db.flush()
        process = m.ProcesoFermentacion(cuba_id=tank.id, perfil_id=profile.id, perfil_snapshot=frozen,
                                        volumen_litros=8000, estado="en_proceso", brix_inicial=brix,
                                        brix_objetivo=2, fecha_inicio=start, fecha_estimada_fin=start+timedelta(days=30))
        db.add_all([process, m.AsignacionDispositivo(cuba_id=tank.id, dispositivo_id=device.id,
                                                     activo=True, asignado_en=start)])
        db.flush()
        spec = SimulationSpec(process_id=process.id, process_start=start, seed=1000+index,
                              scenario=scenario, initial_brix=brix, ambient_c=temp, duration_hours=720)
        params = CalibrationCreate(method="synthetic_identity", version=MODEL_VERSION, valid_from=start, simulation=spec)
        calibration = m.CalibracionDispositivo(dispositivo_id=device.id, version=params.version, metodo=params.method,
                                               parametros=params.model_dump(mode="json"), valida_desde=start,
                                               creada_por=actor.id, creada_en=now)
        ident = str(uuid4())
        token = f"mosto_v2.{ident}.{secrets.token_urlsafe(32)}"
        db.add_all([calibration, m.CredencialDispositivo(id=ident, dispositivo_id=device.id, token_hash=token_hash(token),
                    etiqueta=tank.codigo, creada_por=actor.id, creada_en=now, expira_en=now+timedelta(days=90))])
        db.flush()
        key = f"MOSTO_SIM_DEVICE_{device.id}"
        keys[key] = token
        devices.append(EmitterConfig(device_id=device.id, calibration_id=calibration.id, simulation=spec,
                                     key_env=key, first_sequence=(age-1)*12, initial_ph=ph))
    db.add(m.Cuba(codigo="REAL-06", bodega_id=warehouse.id, material_id=material.id,
                  sector_cuba="Sensores físicos", cap_litros=10000, estado_operativo="disponible"))
    db.flush()
    return FleetConfig(base_url="http://backend:8000", devices=devices), keys
