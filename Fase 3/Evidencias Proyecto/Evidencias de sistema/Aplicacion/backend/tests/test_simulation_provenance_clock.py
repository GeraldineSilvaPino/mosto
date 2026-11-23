from datetime import datetime, timedelta, timezone

from app import models as m
from app.database import SessionLocal
from app.routers import simulations
from app.services.telemetry_v2 import aware


def test_summary_uses_registered_clock_even_before_first_sample(client, monkeypatch):
    with SessionLocal() as db:
        start = aware(db.get(m.ProcesoFermentacion, 1).fecha_inicio)
    real = datetime.now(timezone.utc) - timedelta(minutes=20)
    monkeypatch.setattr(simulations, "utc_now", lambda: real + timedelta(minutes=10))
    assert client.post("/api/dispositivos/1/credenciales", json={
        "source": "simulado", "label": "resumen"}).status_code == 201
    response = client.post("/api/dispositivos/1/calibraciones", json={
        "version": "resumen", "method": "synthetic_identity", "valid_from": start.isoformat(),
        "simulation": {"process_id": 1, "process_start": start.isoformat(), "seed": 42, "scenario": "healthy"},
        "simulation_clock": {"simulated_anchor": start.isoformat(), "real_anchor": real.isoformat(), "factor": 60},
    })
    assert response.status_code == 201
    summary = client.get("/api/simulaciones/procesos/1").json()
    assert summary["clock"] == "simulated_utc" and summary["speed"] == 60
    assert summary["simulation_clock"] == response.json()["simulation_clock"]
    assert summary["calendar_age_hours"] == 10
    assert summary["expected_delivery_at"] is None and summary["lag_seconds"] is None
    assert summary["coverage"] == "sin_muestras" and summary["observed_age_hours"] is None
