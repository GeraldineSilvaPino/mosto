"""Explicit fixture setup for a fresh local demo. Never run by API startup."""
from datetime import datetime, timedelta, timezone
import secrets
from uuid import uuid4

from app import models as m
from app.simulation.model import SimulationSpec, MODEL_VERSION
from app.simulation.worker import FleetConfig, EmitterConfig
from app.services.telemetry_v2 import token_hash
from app.telemetry_contract import CalibrationCreate

DEMO_SCENARIOS = (("healthy", 8, 60), ("cold_shock", 50, 36), ("heat_stress", 85, 60),
                  ("nutrient_depletion", 120, 80), ("slow", 175, 60))


def demo_process_starts(now):
    return {index: now - timedelta(hours=entry[1]) for index, entry in enumerate(DEMO_SCENARIOS, 1)}


def provision_fleet(db, base_url="http://127.0.0.1:8000", now=None, fault_plans=None):
    """Called immediately after seed_demo on a fresh database; caller commits."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    from app.simulation.faults import FaultPlan
    fault_plans = {int(key): FaultPlan.model_validate(value) for key, value in (fault_plans or {}).items()}
    if not set(fault_plans) <= set(range(1, 6)):
        raise ValueError("Only the five simulated devices can declare emitter faults")
    company = db.get(m.EmpresaCliente, 1)
    if company is None or company.nomb_emp != "MOSTO DEMO · Datos simulados" or db.query(m.LecturaTelemetria).first() or db.query(m.CredencialDispositivo).first():
        raise ValueError("Fleet provisioning requires fresh, unprovisioned demo fixtures")
    virtual_model = m.ModeloDispositivo(marca="MOSTO", modelo=MODEL_VERSION, arquitectura="synthetic")
    physical_model = db.query(m.ModeloDispositivo).filter_by(modelo="ESP32-WROOM-32D").one()
    db.add(virtual_model); db.flush()
    scenarios = DEMO_SCENARIOS
    emitters, keys = [], {}
    from app.services.profile_versions import record_version
    frozen_profile = record_version(db, db.get(m.PerfilFermentacion, 1), origin="captura_demo_sintetica").configuracion
    for index in range(1, 7):
        physical = index == 6
        start = now if physical else now - timedelta(hours=scenarios[index - 1][1])
        if index <= 3:
            tank = db.get(m.Cuba, index)
            device = db.get(m.Dispositivo, index)
            process = db.query(m.ProcesoFermentacion).filter_by(cuba_id=tank.id).one()
            assignment = db.query(m.AsignacionDispositivo).filter_by(dispositivo_id=device.id).one()
            from app.services.telemetry_v2 import aware
            if aware(process.fecha_inicio) != start or aware(assignment.asignado_en) != start:
                raise ValueError("Seed the fresh demo with demo_process_starts; historical assignment clocks are immutable")
        else:
            tank = m.Cuba(codigo=f"DEMO-{index:02}", bodega_id=1, material_id=1, cap_litros=10000, estado_operativo="en_uso")
            device = m.Dispositivo(mac_address=f"02:00:00:00:00:{index:02X}", empresa_id=1,
                                    modelo_id=physical_model.id if physical else virtual_model.id, estado="activo")
            db.add_all([tank, device]); db.flush()
            process = m.ProcesoFermentacion(cuba_id=tank.id, perfil_id=1, volumen_litros=8500,
                        brix_inicial=24, brix_objetivo=2, estado="en_proceso", fecha_inicio=start)
            assignment = m.AsignacionDispositivo(dispositivo_id=device.id, cuba_id=tank.id, activo=True, asignado_en=start)
            db.add_all([process, assignment])
        process.perfil_snapshot = dict(frozen_profile)
        device.modelo_id = physical_model.id if physical else virtual_model.id
        device.tipo_dispositivo = "DUAL"
        device.firmware_version = None if physical else MODEL_VERSION
        device.origen = "fisico" if physical else "simulado"
        device.estado = "inactivo" if physical else "activo"
        process.fecha_estimada_fin = start + timedelta(hours=336)
        db.flush()
        if physical:
            # Reserve the hardware channel, with no readings, credentials or fabricated calibration.
            continue
        scenario, _, fault = scenarios[index - 1]
        spec = SimulationSpec(process_id=process.id, process_start=start, seed=202600 + index,
                              scenario=scenario, fault_at_hours=fault)
        params = CalibrationCreate(version=MODEL_VERSION, method="synthetic_identity", valid_from=start, simulation=spec,
                                   emitter_faults=fault_plans.get(device.id))
        calibration = m.CalibracionDispositivo(dispositivo_id=device.id, version=params.version,
                      metodo=params.method, parametros=params.model_dump(mode="json"), valida_desde=start,
                      creada_en=now, creada_por=1)
        ident = str(uuid4())
        token = f"mosto_v2.{ident}.{secrets.token_urlsafe(32)}"
        credential = m.CredencialDispositivo(id=ident, dispositivo_id=device.id, token_hash=token_hash(token),
                      etiqueta="Simulador continuo local", creada_en=now, expira_en=now + timedelta(days=90), creada_por=1)
        db.add_all([calibration, credential]); db.flush()
        key_env = f"MOSTO_SIM_DEVICE_{device.id}"
        keys[key_env] = token
        emitters.append(EmitterConfig(device_id=device.id, calibration_id=calibration.id, key_env=key_env, simulation=spec,
                                     emitter_faults=params.emitter_faults))
    return FleetConfig(base_url=base_url, devices=emitters), keys
