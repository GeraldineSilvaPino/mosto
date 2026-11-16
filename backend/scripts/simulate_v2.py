"""Run from backend: python -m scripts.simulate_v2 --help."""
import argparse
import json
from pathlib import Path
import signal
from threading import Event

from dotenv import load_dotenv
from app.simulation.worker import FleetConfig, Worker, exclusive_state


def main():
    parser = argparse.ArgumentParser(description="Continuous local v2 fleet; physical sampling every five minutes")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--once", action="store_true", help="One bounded sweep, then exit")
    parser.add_argument("--drain", action="store_true", help="Backfill due samples until caught up or blocked, then exit")
    parser.add_argument("--retry-blocked", action="store_true", help="Retry after explicitly fixing a key/process/configuration problem")
    parser.add_argument("--batch", type=int, default=12, choices=range(1, 101), metavar="1..100")
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    fleet = FleetConfig.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    stopped = Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    with exclusive_state(args.state):
        worker = Worker(fleet, args.state, retry_blocked=args.retry_blocked)
        try:
            previous = None
            while not stopped.is_set():
                count = worker.tick(max_per_device=args.batch)
                status = worker.statuses()
                if status != previous:
                    print(json.dumps({"delivered": count, "devices": status}), flush=True)
                    previous = status
                if args.once or args.drain and not count:
                    return 1 if any(s["status"] == "blocked" or s["failures"] for s in status) else 0
                if all(s["status"] in {"completed", "blocked"} for s in status):
                    return 1 if any(s["status"] == "blocked" for s in status) else 0
                stopped.wait(0.05 if count else 1)
        finally:
            worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
