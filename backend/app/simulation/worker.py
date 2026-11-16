"""HTTP-only emitter with a durable outbox. No access to application DB credentials."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import sqlite3
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulation.model import SimulationSpec, Trajectory


class EmitterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    device_id: int = Field(gt=0)
    calibration_id: int = Field(gt=0)
    key_env: str = Field(pattern=r"^MOSTO_SIM_DEVICE_[A-Z0-9_]+$")
    simulation: SimulationSpec


class FleetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    base_url: str
    devices: list[EmitterConfig] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_fleet(self):
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "backend"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("This demo worker requires an explicit local HTTP API origin")
        if len({d.device_id for d in self.devices}) != len(self.devices):
            raise ValueError("Each device can have only one trajectory in this fleet")
        return self


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_id(config):
    # Key rotation does not change identity; only calibration and frozen recipe do.
    value = config.model_dump(mode="json", exclude={"key_env"})
    return str(uuid5(NAMESPACE_URL, "mosto/simulation/" + canonical_json(value)))


@contextmanager
def exclusive_state(path):
    """OS lock released on crash; an existing .lock file is not a stale lease."""
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0"); handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise RuntimeError("Another simulator owns this state file") from None
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


class LocalHTTP:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        parsed = urlsplit(self.base_url)
        self.connection = HTTPConnection(parsed.hostname, parsed.port or 80, timeout=10)

    def close(self):
        self.connection.close()

    def _request(self, method, path, token, body=None):
        # Persistent connection keeps historical backfill efficient. http.client
        # never follows redirects or forwards this credential to another origin.
        try:
            self.connection.request(method, path, body=canonical_json(body) if body is not None else None,
                                    headers={"Content-Type": "application/json", "X-Mosto-Device-Key": token})
            response = self.connection.getresponse()
            raw = response.read(65537)
            if len(raw) > 65536:
                self.close()
                return 502, {}
            if response.status not in (200, 201):
                return response.status, {}
            return response.status, json.loads(raw)
        except (HTTPException, OSError, ValueError):
            self.close()
            return 0, {}

    def __call__(self, payload, token):
        return self._request("POST", "/api/v2/telemetria", token, payload)

    def verify(self, config, token):
        return self._request("GET", f"/api/v2/telemetria/configuracion/{config.device_id}/{config.calibration_id}", token)


class Worker:
    def __init__(self, fleet, state_path, sender=None, keys=None, retry_blocked=False):
        self.fleet = fleet
        self.sender = sender or LocalHTTP(fleet.base_url)
        self.keys = keys if keys is not None else os.environ
        self.verified = set()
        self.trajectories = {d.device_id: Trajectory(d.simulation) for d in fleet.devices}
        # The CLI holds exclusive_state for the lifetime of this connection.
        self.db = sqlite3.connect(state_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, device_id INTEGER UNIQUE NOT NULL, manifest TEXT NOT NULL,
            next_sequence INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'running',
            failures INTEGER NOT NULL DEFAULT 0, retry_after TEXT, last_error TEXT);
          CREATE TABLE IF NOT EXISTS outbox (
            run_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
            truth TEXT NOT NULL, receipt_id INTEGER, PRIMARY KEY(run_id,sequence));
        ''')
        expected_origin = fleet.base_url.rstrip("/")
        origin = self.db.execute("SELECT value FROM metadata WHERE key='api_origin'").fetchone()
        if origin and origin[0] != expected_origin:
            self.db.close()
            raise ValueError("State belongs to a different API origin")
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('api_origin', ?)", (expected_origin,))
        try:
            for config in fleet.devices:
                ident = run_id(config)
                existing = self.db.execute("SELECT run_id FROM runs WHERE device_id=?", (config.device_id,)).fetchone()
                if existing and existing[0] != ident:
                    raise ValueError("State recipe changed; use a new explicit state file for a new run")
                self.db.execute("INSERT OR IGNORE INTO runs(run_id,device_id,manifest) VALUES (?,?,?)",
                                (ident, config.device_id, canonical_json(config.model_dump(mode="json"))))
                if retry_blocked:
                    self.db.execute("UPDATE runs SET status='running', retry_after=NULL, failures=0, last_error=NULL WHERE run_id=? AND status='blocked'", (ident,))
            self.db.commit()
        except Exception:
            self.db.rollback(); self.db.close()
            raise

    def close(self):
        self.db.close()
        if hasattr(self.sender, "close"):
            self.sender.close()

    def statuses(self):
        return [dict(row) for row in self.db.execute(
            "SELECT device_id,next_sequence,status,failures,last_error FROM runs ORDER BY device_id")]

    def tick(self, now=None, max_per_device=12):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("Worker clock must have an explicit timezone")
        now = now.astimezone(timezone.utc)
        if not 1 <= max_per_device <= 100:
            raise ValueError("Batch must contain 1 to 100 samples per device")
        delivered = 0
        for config in self.fleet.devices:
            ident, spec = run_id(config), config.simulation
            for _ in range(max_per_device):
                state = self.db.execute("SELECT * FROM runs WHERE run_id=?", (ident,)).fetchone()
                if state["status"] != "running" or (state["retry_after"] and datetime.fromisoformat(state["retry_after"]) > now):
                    break
                index = state["next_sequence"]
                if index > spec.duration_hours * 12:
                    self.db.execute("UPDATE runs SET status='completed' WHERE run_id=?", (ident,)); self.db.commit()
                    break
                observed = spec.process_start + timedelta(seconds=index * spec.cadence_seconds)
                if observed > now:
                    break  # Wall time never becomes a fabricated future measurement.
                token = self.keys.get(config.key_env)
                if not token:
                    self._fail(ident, now, state["failures"], "missing_key", permanent=True)
                    break
                if ident not in self.verified:
                    code, remote = self.sender.verify(config, token)
                    if code != 200:
                        self._fail(ident, now, state["failures"], f"preflight_http_{code}",
                                   permanent=code not in (0, 408, 425, 429) and code < 500)
                        break
                    if (not isinstance(remote, dict) or remote.get("source") != "simulado" or remote.get("device_id") != config.device_id
                            or remote.get("calibration_id") != config.calibration_id
                            or remote.get("simulation") != spec.model_dump(mode="json")):
                        self._fail(ident, now, state["failures"], "preflight_recipe_mismatch", permanent=True)
                        break
                    self.verified.add(ident)
                pending = self.db.execute("SELECT payload FROM outbox WHERE run_id=? AND sequence=?", (ident, index)).fetchone()
                if pending:
                    body = json.loads(pending[0])
                else:
                    sample = self.trajectories[config.device_id].sample(index)
                    body = dict(schema_version=2, device_id=config.device_id, boot_id=ident,
                                sequence=index, observed_at=observed.isoformat(), calibration_id=config.calibration_id,
                                temperature_c={"value": sample["temperature_c"], "quality": "good"},
                                brix_apparent={"value": sample["brix_apparent"], "quality": "good"})
                    self.db.execute("INSERT INTO outbox VALUES (?,?,?,?,NULL)",
                                    (ident, index, canonical_json(body), canonical_json(sample)))
                    self.db.commit()  # Durable BEFORE the network request.
                code, receipt = self.sender(body, token)
                if code in (200, 201):
                    # Reject redirects/misrouted or malformed success responses.
                    valid = (isinstance(receipt, dict) and isinstance(receipt.get("message_id"), int) and receipt.get("device_id") == config.device_id
                             and receipt.get("process_id") == spec.process_id and receipt.get("source") == "simulado"
                             and receipt.get("brix_apparent", {}).get("quality") == "good"
                             and receipt.get("temperature_c", {}).get("quality") == "good")
                    if not valid:
                        self._fail(ident, now, state["failures"], "invalid_receipt", permanent=True)
                        break
                    with self.db:
                        self.db.execute("UPDATE outbox SET receipt_id=? WHERE run_id=? AND sequence=?", (receipt["message_id"], ident, index))
                        self.db.execute("UPDATE runs SET next_sequence=?,failures=0,retry_after=NULL,last_error=NULL WHERE run_id=?", (index + 1, ident))
                    delivered += 1
                else:
                    self._fail(ident, now, state["failures"], f"http_{code}", permanent=code not in (0, 408, 425, 429) and code < 500)
                    break
        return delivered

    def _fail(self, ident, now, failures, reason, permanent):
        retry = now + timedelta(seconds=min(60, 2 ** min(failures + 1, 6)))
        self.db.execute("UPDATE runs SET status=?,failures=?,retry_after=?,last_error=? WHERE run_id=?",
                        ("blocked" if permanent else "running", failures + 1, retry.isoformat(), reason, ident))
        self.db.commit()
