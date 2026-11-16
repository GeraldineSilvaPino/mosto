"""MOSTO API: no DDL or sample-data writes during import or startup."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config
from pathlib import Path
from .database import engine, settings
from .services.auth_service import get_current_user
from .services.demo_access import require_simulator_key
from .routers import auth, users, company, binnacle, master, telemetry, cubas, processes, devices, thresholds, alerts
from .routers import device_provisioning, telemetry_v2, simulations

app = FastAPI(title="MOSTO API - Plataforma Vitivinícola IoT", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.include_router(auth.router)
for router in (users.router, company.router, binnacle.router, master.router, cubas.router,
               processes.router, devices.router, thresholds.router, alerts.router):
    app.include_router(router, dependencies=[Depends(get_current_user)])
# Individual device credentials are independent of browser JWT authentication.
app.include_router(device_provisioning.router, dependencies=[Depends(get_current_user)])
app.include_router(telemetry_v2.audit_router, dependencies=[Depends(get_current_user)])
app.include_router(telemetry_v2.ingest_router)
app.include_router(simulations.router, dependencies=[Depends(get_current_user)])
# Legacy ingestion remains confined to demo/test.
app.include_router(telemetry.router, dependencies=[Depends(require_simulator_key)])


@app.exception_handler(IntegrityError)
async def integrity_conflict(request, exc):
    # Never expose SQL, constraint parameters, or another tenant's identifiers.
    return JSONResponse(status_code=409, content={
        "detail": "La operación entra en conflicto con el estado actual o las reglas de integridad."})


@app.get("/", tags=["Health"])
def root():
    return {"app": "MOSTO Backend API", "environment": settings.environment,
            "database": engine.dialect.name, "version": app.version, "docs_url": "/docs"}


@app.get("/api/health", tags=["Health"])
def health_check():
    """Liveness only; does not imply a healthy database or model."""
    return {"status": "alive", "environment": settings.environment}


@app.get("/api/ready", tags=["Health"])
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT id FROM "EMPRESA_CLIENTE" LIMIT 1'))
            scripts = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
            if set(MigrationContext.configure(connection).get_current_heads()) != set(scripts.get_heads()):
                return JSONResponse(status_code=503, content={"status": "not_ready", "database": "migration_required"})
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable_or_uninitialized"})
    return {"status": "ready", "database": "reachable", "environment": settings.environment}
