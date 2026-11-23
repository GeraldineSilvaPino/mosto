"""Silence watchdog for the configured installation. Runs as a separate process.

From backend, supply MOSTO_ENV=demo and a validated local DATABASE_URL, then:
python -m scripts.watchdog --once (or --interval-seconds 60).
"""
import argparse
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if not 10 <= args.interval_seconds <= 300:
        parser.error("interval-seconds must be between 10 and 300")
    from app.config import load_settings, validate_isolated_database
    settings = load_settings()
    if settings.environment != "production":
        validate_isolated_database(settings.database_url, settings.environment)
    from app.database import SessionLocal
    from app.services.monitoring import sweep_silence
    from app.services.telemetry_v2 import utc_now
    try:
        while True:
            with SessionLocal() as db:
                changed = sweep_silence(db, utc_now())
                db.commit()
            print(f"Silence sweep: {changed} conditions marked unknown", flush=True)
            if args.once:
                return
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
