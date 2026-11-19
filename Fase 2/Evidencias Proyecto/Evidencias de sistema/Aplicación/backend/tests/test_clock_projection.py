from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy.exc import IntegrityError

from app import models as m
from app.database import SessionLocal, settings
from app.migrations import migration_config
from app.services.telemetry_v2 import aware
from app.simulation.clock import SimulationClock


def test_database_checks_scheduled_pair_and_preserves_evidence_on_downgrade(client):
    issued = client.post("/api/dispositivos/1/credenciales", json={"source": "simulado", "label": "ensayo"})
    assert issued.status_code == 201
    with SessionLocal() as db:
        start = aware(db.get(m.ProcesoFermentacion, 1).fecha_inicio)
    real = datetime.now(timezone.utc) - timedelta(minutes=5)
    clock = SimulationClock(real_anchor=real, simulated_anchor=start, factor=7)
    result = client.post("/api/dispositivos/1/calibraciones", json={
        "version": "proyeccion", "method": "synthetic_identity", "valid_from": real.isoformat(),
        "simulation": {"process_id": 1, "process_start": start.isoformat(), "seed": 42, "scenario": "healthy"},
        "simulation_clock": clock.model_dump(mode="json"),
    })
    assert result.status_code == 201
    calibration = result.json()["calibration_id"]
    observed = start + timedelta(seconds=300)
    due = clock.real_at(observed)
    reading_values = dict(dispositivo_id=1, fermentacion_id=1, reloj_calibracion_id=calibration,
                          timestamp=due, origen_dato="v2_simulado", brix=20)
    with SessionLocal() as db:
        for invalid in ({"fermentacion_id": 2}, {"dispositivo_id": 2}, {"origen_dato": "v2_fisico"},
                        {"timestamp": real - timedelta(seconds=1)}):
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(m.LecturaTelemetria(**{**reading_values, **invalid}))
                db.flush()
        reading = m.LecturaTelemetria(**reading_values)
        db.add(reading)
        db.flush()
        envelope = dict(dispositivo_id=1, credencial_id=issued.json()["credential_id"], boot_id=str(uuid4()),
                        secuencia=1, observado_en=observed, recibido_en=due, origen="simulado",
                        payload_hash="0"*64, payload={}, asignacion_id=1, fermentacion_id=1,
                        calibracion_id=calibration, lectura_id=reading.id, calidad_temperatura="missing",
                        calidad_brix="good", brix=20, diagnosticos=[], fuera_de_orden=False, retrasado=False)
        for invalid in ({"secuencia": 2}, {"calibracion_id": None}, {"asignacion_id": 2},
                        {"observado_en": due}, {"recibido_en": due - timedelta(microseconds=1)}):
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(m.MensajeTelemetria(**{**envelope, **invalid}))
                db.flush()
        db.add(m.MensajeTelemetria(**envelope))
        db.commit()
        with pytest.raises(IntegrityError), db.begin_nested():
            reading.timestamp = observed
            db.flush()
    config = migration_config(settings.database_url, "test")
    with pytest.raises(IntegrityError):
        command.downgrade(config, "0009_process_clock_registry")
    with SessionLocal() as db:
        assert aware(db.query(m.LecturaTelemetria).one().timestamp) == due
        assert aware(db.query(m.MensajeTelemetria).one().observado_en) == observed
