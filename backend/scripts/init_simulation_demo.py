"""Initialize a NEW isolated winery and export a private emitter configuration."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Create a fresh demo with five virtual tanks and one reserved physical channel")
    parser.add_argument("--env-file", type=Path, required=True, help="Explicit demo configuration; never backend/.env")
    parser.add_argument("--output", type=Path, required=True, help="New private directory for fleet manifest and device keys")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=False)
    from app.database import settings, SessionLocal
    from app.config import validate_isolated_database
    from app.migrations import upgrade_local
    from app.demo_seed import seed_demo
    from app.models import EmpresaCliente
    from app.simulation.provision_demo import provision_fleet, demo_process_starts
    from app.simulation.worker import FleetConfig
    if settings.environment != "demo":
        raise SystemExit("Use MOSTO_ENV=demo and a fresh local database")
    validate_isolated_database(settings.database_url, "demo")
    if args.output.exists():
        raise SystemExit("Output directory already exists; preserve its keys and state")
    password = os.environ.get("MOSTO_DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set MOSTO_DEMO_PASSWORD with at least 12 characters")
    # Validate the destination before touching a database.
    from app.simulation.model import SimulationSpec
    from datetime import datetime, timezone
    FleetConfig(base_url=args.base_url, devices=[dict(device_id=1, calibration_id=1, key_env="MOSTO_SIM_DEVICE_1",
                simulation=SimulationSpec(process_id=1, process_start=datetime.now(timezone.utc), seed=1, scenario="healthy"))])
    from sqlalchemy.engine import make_url
    destination = make_url(settings.database_url)
    if destination.get_backend_name() == "sqlite" and destination.database != ":memory:":
        Path(destination.database).resolve().parent.mkdir(parents=True, exist_ok=True)
    upgrade_local(settings.database_url, "demo")
    with SessionLocal() as db:
        if db.query(EmpresaCliente).first():
            raise SystemExit("Database is not empty; existing demos are never overwritten")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        seed_demo(db, password, process_starts=demo_process_starts(now), commit=False)
        fleet, keys = provision_fleet(db, args.base_url, now=now)
        args.output.mkdir(parents=True, mode=0o700)
        (args.output / "fleet.json").write_text(fleet.model_dump_json(indent=2), encoding="utf-8")
        secret_path = args.output / "device-keys.env"
        with secret_path.open("x", encoding="utf-8") as stream:
            os.chmod(secret_path, 0o600)
            stream.write("\n".join(f"{key}={value}" for key, value in keys.items()) + "\n")
        db.commit()
    print("Created five simulated devices and one inactive physical reserve. No telemetry generated yet.")
    print(f"Manifest and private device keys: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
