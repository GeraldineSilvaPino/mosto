"""Run tests on a NEW isolated PostgreSQL cluster, never on a system service.

Usage: python -m scripts.test_postgres --pg-bin "C:/Program Files/PostgreSQL/18/bin"
Extra arguments after -- are passed to pytest. Only this script's own cluster is
stopped and removed. No existing PostgreSQL service/database is contacted.
"""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import URL


def stop_temporary_cluster(run, data, timeout=180):
    """Request shutdown once, then observe it without killing a slow checkpoint."""
    run("pg_ctl", "-D", data, "-m", "fast", "-W", "stop")
    deadline = time.monotonic() + timeout
    while True:
        status = run("pg_ctl", "-D", data, "status").returncode
        if status == 3:  # pg_ctl: server is not running
            return True
        if status != 0 or time.monotonic() >= deadline:
            return False
        print("Waiting for temporary PostgreSQL shutdown...", flush=True)
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--restore-drill", action="store_true",
                        help="Migrate, seed and restore into a second empty local database")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    binaries = args.pg_bin.resolve()
    suffix = ".exe" if os.name == "nt" else ""
    if args.restore_drill and args.pytest_args:
        parser.error("--restore-drill runs separately from pytest")
    for tool in (("initdb", "pg_ctl", "pg_dump", "pg_restore") if args.restore_drill
                 else ("initdb", "pg_ctl")):
        if not (binaries / (tool + suffix)).is_file():
            parser.error(f"Missing PostgreSQL executable: {tool}")
    backend = Path(__file__).resolve().parents[1]
    artifacts = (backend / "artifacts").resolve()
    artifacts.mkdir(exist_ok=True)
    cluster_root = Path(tempfile.mkdtemp(prefix="mosto-pg-", dir=artifacts)).resolve()
    data = cluster_root / "data"
    password_file = cluster_root / "password.txt"
    password = secrets.token_hex(32)
    password_file.write_text(password, encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(tool, *arguments):
        # On Windows the detached server can inherit a PIPE handle and prevent
        # communicate() from reaching EOF even after pg_ctl has exited.
        with (cluster_root / "launcher.log").open("ab") as output:
            return subprocess.run([str(binaries / (tool + suffix)), *map(str, arguments)],
                                  stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                  creationflags=flags, timeout=60)

    started = False
    try:
        result = run("initdb", "-D", data, "-U", "mosto_bootstrap", "--auth=scram-sha-256",
                     "--pwfile", password_file, "--encoding=UTF8", "--locale=C")
        password_file.unlink()
        if result.returncode:
            print(f"initdb failed; inspect {cluster_root / 'launcher.log'}")
            return result.returncode
        started = True  # A timed-out pg_ctl may still have started its server.
        result = run("pg_ctl", "-D", data, "-l", cluster_root / "server.log", "-w", "start",
                     "-o", f"-h 127.0.0.1 -p {port} -c timezone=UTC -c max_connections=30")
        if result.returncode:
            print(f"pg_ctl failed; inspect {cluster_root / 'launcher.log'}")
            return result.returncode
        admin = psycopg2.connect(host="127.0.0.1", port=port, dbname="postgres",
                                 user="mosto_bootstrap", password=password, connect_timeout=10)
        try:
            admin.autocommit = True
            with admin.cursor() as cur:
                cur.execute(sql.SQL("CREATE ROLE mosto_test LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(sql.Literal(password)))
                cur.execute("CREATE DATABASE mosto_test OWNER mosto_test")
                if args.restore_drill:
                    cur.execute("CREATE DATABASE mosto_test_restore OWNER mosto_test")
                cur.execute("SELECT version()")
                print(cur.fetchone()[0], flush=True)
        finally:
            admin.close()
        url = URL.create("postgresql+psycopg2", username="mosto_test", password=password,
                         host="127.0.0.1", port=port, database="mosto_test")
        env = dict(os.environ, MOSTO_TEST_DATABASE_URL=url.render_as_string(hide_password=False))
        if args.restore_drill:
            os.environ.update(MOSTO_ENV="test", DATABASE_URL=env["MOSTO_TEST_DATABASE_URL"],
                              JWT_SECRET_KEY=secrets.token_hex(32))
            from scripts.postgres_restore_drill import run_restore_drill
            run_restore_drill(binaries, cluster_root / "snapshot.dump")
            return 0
        test_args = args.pytest_args
        if test_args[:1] == ["--"]:
            test_args = test_args[1:]
        return subprocess.run([sys.executable, "-m", "pytest", *(
            test_args or ["-q", "-p", "no:cacheprovider", "--tb=short", "--disable-warnings"])],
            cwd=backend.parent, env=env).returncode
    finally:
        safe_to_remove = not started
        if started:
            try:
                safe_to_remove = stop_temporary_cluster(run, data)
            except (subprocess.TimeoutExpired, OSError) as error:
                safe_to_remove = False
                print(f"Shutdown check failed: {type(error).__name__}", flush=True)
            print("Temporary PostgreSQL stopped." if safe_to_remove else
                  f"Stop failed; cluster retained at {cluster_root}", flush=True)
            if not safe_to_remove:
                raise RuntimeError(f"Temporary cluster shutdown unconfirmed: {cluster_root}")
        # Resolve and verify the absolute path before recursive cleanup on Windows.
        if safe_to_remove and cluster_root.parent == artifacts and cluster_root.name.startswith("mosto-pg-"):
            shutil.rmtree(cluster_root)


if __name__ == "__main__":
    raise SystemExit(main())
