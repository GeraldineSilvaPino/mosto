"""Opt-in local load measurement. Run explicitly with pytest -s."""
import asyncio
import math
import socket
import time

import httpx
from sqlalchemy import event
import uvicorn

from app.database import engine
from app.main import app
from app.services.auth_service import create_access_token


async def measure():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if serving.done():
                        await serving
                        raise RuntimeError("Server stopped before startup")
                    await asyncio.sleep(0.01)
            headers = {"Authorization": "Bearer " + create_access_token({"sub": 1})}
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers=headers,
                                         trust_env=False, timeout=10) as client:
                path = "/api/procesos/pagina?limit=1"
                warm = await client.get(path)
                warm.raise_for_status()
                reference = warm.json()
                assert reference["total"] > 0 and len(reference["items"]) == 1
                for concurrency in (1, 4, 8):
                    await measure_stage(client, path, reference, concurrency)
        finally:
            server.should_exit = True
            await serving


async def measure_stage(client, path, reference, concurrency):
    durations = []
    errors = []
    checkouts = []

    def sample_pool(*_):
        checkouts.append(engine.pool.checkedout())

    async def reader():
        for _ in range(12):
            start = time.perf_counter()
            try:
                response = await client.get(path)
                if response.status_code != 200 or response.json() != reference:
                    errors.append(response.status_code)
            except httpx.HTTPError as error:
                errors.append(type(error).__name__)
            durations.append(time.perf_counter() - start)

    event.listen(engine, "checkout", sample_pool)
    try:
        start = time.perf_counter()
        await asyncio.gather(*(reader() for _ in range(concurrency)))
        elapsed = time.perf_counter() - start
    finally:
        event.remove(engine, "checkout", sample_pool)
    p95 = sorted(durations)[math.ceil(len(durations) * 0.95) - 1]
    print(f"clients={concurrency} requests={len(durations)} errors={len(errors)} "
          f"rps={len(durations)/elapsed:.1f} p95_ms={p95*1000:.1f} "
          f"peak_db_connections={max(checkouts, default=0)}", flush=True)
    assert not errors, errors
    assert p95 < 2, "Local demonstration target: p95 under two seconds"


def test_process_page_load():
    asyncio.run(measure())
