"""Physics invariants, durable delivery and real API boundaries for synthetic fleets."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from app.simulation.model import SimulationSpec, Trajectory, phase_weights
from app.simulation.worker import Worker, FleetConfig, EmitterConfig, exclusive_state
from app.simulation.provision_demo import provision_fleet, demo_process_starts
from app.database import SessionLocal
from app import models as m

pytestmark = pytest.mark.empty_db


def spec(**overrides):
    return SimulationSpec(**dict(process_id=1, process_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                                 seed=42, scenario="healthy", **overrides))


def test_phase_weights_are_continuous_normalized_and_cover_all_phases():
    for hours in (0, 15, 20, 25, 65, 70, 80, 145, 150, 170, 336):
        weights = phase_weights(hours)
        assert sum(weights.values()) == pytest.approx(1)
        assert all(0 <= v <= 1 for v in weights.values())
        nearby = phase_weights(hours + 1e-6)
        assert max(abs(weights[k] - nearby[k]) for k in weights) < 1e-6


@pytest.mark.parametrize("scenario", ["healthy", "cold_shock", "heat_stress", "nutrient_depletion", "slow"])
def test_trajectories_have_no_latent_sugar_creation_or_phase_jumps(scenario):
    model = Trajectory(spec().model_copy(update={"scenario": scenario}))
    previous = model.sample(0)
    for index in range(1, 336 * 12 + 1):
        sample = model.sample(index)
        assert -1 <= sample["latent_brix"] <= previous["latent_brix"]
        assert abs(sample["latent_brix"] - previous["latent_brix"]) < 0.06
        # Severe thermal faults evolve over hours, not instantaneous phase jumps.
        assert abs(sample["latent_temperature"] - previous["latent_temperature"]) < 0.3
        assert 0 < sample["viability"] <= 1
        previous = sample


def test_faults_separate_thermal_and_nutrient_causes_without_claiming_measured_nutrients():
    curves = {name: Trajectory(spec().model_copy(update={"scenario": name})) for name in
              ("healthy", "cold_shock", "heat_stress", "nutrient_depletion", "slow")}
    healthy = curves["healthy"].sample(120 * 12)
    for name in ("cold_shock", "heat_stress", "nutrient_depletion", "slow"):
        failed = curves[name].sample(120 * 12)
        assert failed["latent_brix"] > healthy["latent_brix"] + 1
    assert curves["cold_shock"].sample(120 * 12)["temperature_c"] < 12
    assert curves["heat_stress"].sample(120 * 12)["temperature_c"] > 33
    assert 18 < curves["nutrient_depletion"].sample(120 * 12)["temperature_c"] < 26
    stuck = curves["nutrient_depletion"]
    assert stuck.sample(120 * 12)["latent_brix"] - stuck.sample(144 * 12)["latent_brix"] < 0.05


def test_noise_and_restart_are_reproducible_without_flattening_real_dynamics():
    original = Trajectory(spec())
    sample = original.sample(850)
    assert Trajectory(spec()).sample(850) == sample
    assert original.sample(1) == Trajectory(spec()).sample(1)
    assert Trajectory(spec().model_copy(update={"seed": 43})).sample(850) != sample
    residual = [original.sample(i)["brix_apparent"] - original.sample(i)["latent_brix"] for i in range(200)]
    assert any(x > 0 for x in residual) and any(x < 0 for x in residual)
    assert abs(sum(residual) / len(residual)) < .01


@pytest.fixture
def fleet(client):
    from app.demo_seed import seed_demo
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with SessionLocal() as db:
        seed_demo(db, "test-only-password-2026", process_starts=demo_process_starts(now))
        config, keys = provision_fleet(db, now=now)
        db.commit()
    return config, keys


class APISender:
    def __init__(self, client):
        self.client = client
        self.drop_next_response = False
        self.sent = []

    def verify(self, config, token):
        response = self.client.get(f"/api/v2/telemetria/configuracion/{config.device_id}/{config.calibration_id}",
                                   headers={"X-Mosto-Device-Key": token})
        return response.status_code, response.json()

    def __call__(self, body, token):
        self.sent.append(body)
        response = self.client.post("/api/v2/telemetria", json=body, headers={"X-Mosto-Device-Key": token})
        if self.drop_next_response:
            self.drop_next_response = False
            return 0, {}
        return response.status_code, response.json()


def one_device(fleet):
    config, keys = fleet
    return config.model_copy(update={"devices": config.devices[:1]}), keys


def test_http_fleet_emits_synthetic_only_and_exposes_programmed_phase(client, fleet, tmp_path):
    config, keys = fleet
    worker = Worker(config, tmp_path / "state.db", APISender(client), keys)
    try:
        assert worker.tick(max_per_device=2) == 10
    finally:
        worker.close()
    with SessionLocal() as db:
        messages = db.query(m.MensajeTelemetria).all()
        assert len(messages) == 10 and all(x.origen == "simulado" for x in messages)
        assert not db.query(m.LecturaTelemetria).filter_by(dispositivo_id=6).first()
        assert db.get(m.Dispositivo, 6).estado == "inactivo"
    summary = client.get("/api/simulaciones/procesos/1").json()
    assert summary["registered"] and summary["phase"] == "lag" and summary["coverage"] == "atrasado"
    assert summary["observed_age_hours"] == pytest.approx(1 / 12)
    assert client.get("/api/cubas/1/ml-prediction").json()["riesgo_pct"] is None


def test_outbox_survives_lost_response_and_restart_without_new_noise_or_duplicate(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    sender = APISender(client); sender.drop_next_response = True
    path = tmp_path / "state.db"
    now = datetime.now(timezone.utc)
    worker = Worker(config, path, sender, keys)
    assert worker.tick(now, max_per_device=1) == 0
    assert worker.statuses()[0]["next_sequence"] == 0
    worker.close()
    resumed = Worker(config, path, sender, keys)
    try:
        assert resumed.tick(now + timedelta(seconds=3), max_per_device=1) == 1
        assert resumed.statuses()[0]["next_sequence"] == 1
    finally:
        resumed.close()
    assert sender.sent[0] == sender.sent[1]
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 1


def test_worker_never_emits_future_samples_and_honors_cadence(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    sender = APISender(client)
    worker = Worker(config, tmp_path / "clock.db", sender, keys)
    start = config.devices[0].simulation.process_start
    try:
        assert worker.tick(start - timedelta(seconds=1)) == 0
        assert worker.tick(start) == 1
        assert worker.tick(start + timedelta(seconds=299)) == 0
        assert worker.tick(start + timedelta(seconds=300)) == 1
    finally:
        worker.close()
    assert [b["sequence"] for b in sender.sent] == [0, 1]


def test_manifest_mismatch_blocks_before_ingestion(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    changed = config.devices[0].model_copy(update={"simulation": config.devices[0].simulation.model_copy(update={"seed": 44})})
    worker = Worker(config.model_copy(update={"devices": [changed]}), tmp_path / "bad.db", APISender(client), keys)
    try:
        assert worker.tick() == 0
        assert worker.statuses()[0]["last_error"] == "preflight_recipe_mismatch"
    finally:
        worker.close()
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 0


def test_revoked_key_blocks_only_its_device_and_other_tanks_continue(client, fleet, tmp_path):
    config, keys = fleet
    cred = client.get("/api/dispositivos/1/credenciales").json()[0]
    assert client.delete(f"/api/dispositivos/1/credenciales/{cred['credential_id']}").status_code == 200
    worker = Worker(config, tmp_path / "revoked.db", APISender(client), keys)
    try:
        assert worker.tick(max_per_device=1) == 4
        assert worker.statuses()[0]["status"] == "blocked"
        assert all(s["next_sequence"] == 1 for s in worker.statuses()[1:])
    finally:
        worker.close()


def test_bound_trajectory_cannot_follow_device_into_another_process(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    sender = APISender(client)
    worker = Worker(config, tmp_path / "moved.db", sender, keys)
    assert worker.tick(max_per_device=1) == 1
    assert client.post("/api/dispositivos/vincular", json={"dispositivo_id": 1, "cuba_id": 2}).status_code == 200
    body = dict(sender.sent[0], sequence=97, observed_at=(config.devices[0].simulation.process_start + timedelta(seconds=97*300)).isoformat())
    # Today's new-assignment timestamp is after the original start + eight hours.
    with SessionLocal() as db:
        assignment = db.query(m.AsignacionDispositivo).filter_by(dispositivo_id=1, activo=True).one()
        from app.services.telemetry_v2 import aware
        body["observed_at"] = aware(assignment.asignado_en).isoformat()
    response = client.post("/api/v2/telemetria", json=body, headers={"X-Mosto-Device-Key": keys[config.devices[0].key_env]})
    assert response.status_code == 409
    worker.close()


def test_config_endpoint_and_simulation_metadata_are_authorized(client, fleet):
    config, keys = fleet
    assert client.get("/api/v2/telemetria/configuracion/1/1").status_code == 401
    assert client.get("/api/v2/telemetria/configuracion/2/2", headers={"X-Mosto-Device-Key": keys[config.devices[0].key_env]}).status_code == 403
    from app.services.auth_service import create_access_token
    with SessionLocal() as db:
        company = m.EmpresaCliente(nomb_emp="Other")
        db.add(company); db.flush()
        warehouse = m.Bodega(nombre="Other", empresa_id=company.id)
        actor = m.Usuario(nomb_compl="Other", correo_elec="other@example.invalid", empresa_id=company.id)
        db.add_all([warehouse, actor]); db.flush()
        db.add(m.UsuarioBodega(usuario_id=actor.id, bodega_id=warehouse.id, rol_id=1)); db.commit()
        ident = actor.id
    client.headers["Authorization"] = "Bearer " + create_access_token({"sub": ident})
    assert client.get("/api/simulaciones/procesos/1").status_code == 404


def test_state_has_single_process_owner_and_rejects_changed_recipe(fleet, tmp_path):
    config, keys = one_device(fleet)
    path = tmp_path / "owned.db"
    with exclusive_state(path):
        with pytest.raises(RuntimeError, match="Another simulator"):
            with exclusive_state(path):
                pass
    with exclusive_state(path):
        worker = Worker(config, path, keys=keys); worker.close()
    changed = config.devices[0].model_copy(update={"calibration_id": 999})
    with pytest.raises(ValueError, match="recipe changed"):
        Worker(config.model_copy(update={"devices": [changed]}), path, keys=keys)


def test_worker_checks_physical_origin_before_any_post(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    sender = APISender(client)
    sender.verify = lambda *_: (200, {"device_id": 1, "calibration_id": 1, "source": "fisico",
                                     "simulation": config.devices[0].simulation.model_dump(mode="json")})
    worker = Worker(config, tmp_path / "physical.db", sender, keys)
    try:
        assert worker.tick() == 0 and sender.sent == []
        assert worker.statuses()[0]["status"] == "blocked"
    finally:
        worker.close()


def test_bound_simulator_rejects_wrong_clock_and_stops_at_closed_process(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    sender = APISender(client)
    worker = Worker(config, tmp_path / "closed.db", sender, keys)
    assert worker.tick(max_per_device=1) == 1
    body = dict(sender.sent[0], sequence=1)
    assert sender(body, keys[config.devices[0].key_env])[0] == 422
    body["sequence"] = 9223372036854775807
    assert sender(body, keys[config.devices[0].key_env])[0] == 422
    assert client.patch("/api/procesos/1/finalizar").status_code == 200
    future_index = 97  # Process was created eight hours ago; this sample is after closure.
    start = config.devices[0].simulation.process_start
    body.update(sequence=future_index, observed_at=(start + timedelta(seconds=300*future_index)).isoformat())
    from app.services import telemetry_v2
    from unittest.mock import patch
    with patch.object(telemetry_v2, "utc_now", return_value=start + timedelta(hours=9)):
        assert sender(body, keys[config.devices[0].key_env])[0] == 409
    worker.close()
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 1


def test_missing_keys_are_not_sent_and_are_resumable_after_explicit_retry(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    path = tmp_path / "keys.db"
    sender = APISender(client)
    worker = Worker(config, path, sender, {})
    assert worker.tick() == 0 and sender.sent == []
    worker.close()
    worker = Worker(config, path, sender, keys, retry_blocked=True)
    try:
        assert worker.tick(max_per_device=1) == 1
    finally:
        worker.close()


def test_same_recipe_in_separate_state_replays_same_server_messages(client, fleet, tmp_path):
    config, keys = one_device(fleet)
    for path in (tmp_path / "first.db", tmp_path / "second.db"):
        worker = Worker(config, path, APISender(client), keys)
        assert worker.tick(max_per_device=2) == 2
        worker.close()
    with SessionLocal() as db:
        assert db.query(m.MensajeTelemetria).count() == 2


def test_http_transport_reuses_connection_and_does_not_follow_redirects():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from app.simulation.worker import LocalHTTP
    ports = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            ports.append(self.client_address[1])
            status = 302 if len(ports) == 3 else 201
            body = b'{"message_id":1}'
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Type", "application/json")
            if status == 302:
                self.send_header("Location", "http://127.0.0.1:1/forbidden")
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    sender = LocalHTTP(f"http://127.0.0.1:{server.server_port}")
    try:
        assert sender({}, "test-only")[0] == 201
        assert sender({}, "test-only")[0] == 201
        assert ports[0] == ports[1]
        assert sender({}, "test-only") == (302, {})
        assert len(ports) == 3
    finally:
        sender.close(); server.shutdown(); server.server_close(); thread.join(timeout=5)


@pytest.mark.parametrize("url", ["https://example.com", "http://localhost@evil.invalid", "http://127.0.0.1/api", "http://127.0.0.1/?redirect=remote"])
def test_fleet_cannot_target_remote_or_ambiguous_origins(url):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        FleetConfig(base_url=url, devices=[EmitterConfig(device_id=1, calibration_id=1,
                    key_env="MOSTO_SIM_DEVICE_1", simulation=spec())])


def test_history_keeps_full_five_minute_window_and_unambiguous_timestamps(client, fleet):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for index in range(300):
            db.add(m.LecturaTelemetria(dispositivo_id=2, fermentacion_id=2,
                    timestamp=now - timedelta(minutes=5 * index + 1), temp_mosto=22, brix=20))
        db.commit()
    response = client.get("/api/cubas/2/historico?rango_horas=24")
    assert response.status_code == 200
    body = response.json()
    assert body["total_muestras"] == 288 and not body["truncated"] and body["timezone"] == "UTC"
    times = [datetime.fromisoformat(t) for t in body["timestamps"]]
    assert all(t.tzinfo is not None for t in times)
    assert times[-1] - times[0] == timedelta(minutes=287 * 5)
    assert client.get("/api/cubas/2/historico?rango_horas=169").status_code == 422


def test_empty_history_does_not_fall_back_to_measurements_outside_requested_window(client, fleet):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add(m.LecturaTelemetria(dispositivo_id=2, fermentacion_id=2,
                                 timestamp=now - timedelta(hours=25), temp_mosto=22, brix=20))
        db.commit()
    assert client.get("/api/cubas/2/historico?rango_horas=24").json()["total_muestras"] == 0
