"""Supervise API and optional demonstration emitter in one Docker container."""
import os
import signal
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    port = int(os.environ.get('PORT', '8000'))
    children = []
    emitter_envs = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                            '--host', '0.0.0.0', '--port', str(port)])
    children.append(api)
    try:
        if os.environ.get('MOSTO_SIMULATION_ENABLED', '0') == '1':
            while not stopping and api.poll() is None:
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/ready', timeout=3) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    pass
                time.sleep(2)
            if not stopping and api.poll() is None:
                ids = os.environ.get('MOSTO_SIMULATION_DEVICE_IDS', os.environ.get('MOSTO_SIMULATION_DEVICE_ID', '')).split(',')
                for ident in dict.fromkeys(ids):
                    env = {**os.environ, 'MOSTO_SIMULATION_DEVICE_ID': str(int(ident.strip()))}
                    emitter_envs.append(env)
                    children.append(subprocess.Popen([sys.executable, '-m', 'scripts.simulate_container'], env=env))
        while not stopping and api.poll() is None:
            failed = [i for i in range(1, len(children)) if children[i].poll() is not None]
            if failed:
                print('[simulation] Emitter stopped; restarting in 30 seconds', flush=True)
                for _ in range(30):
                    if stopping or api.poll() is not None:
                        break
                    time.sleep(1)
                if not stopping and api.poll() is None:
                    for i in failed:
                        children[i] = subprocess.Popen([sys.executable, '-m', 'scripts.simulate_container'], env=emitter_envs[i - 1])
            time.sleep(1)
        return 0 if stopping else (api.returncode or 1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
