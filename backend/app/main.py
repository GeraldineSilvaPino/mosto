"""
Punto de entrada principal de la API MOSTO en FastAPI.
Configura middlewares de CORS, inicialización de base de datos y routers completos.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal, SQLALCHEMY_DATABASE_URL
from . import models
from .routers import (
    auth,
    users,
    company,
    binnacle,
    master,
    telemetry,
    cubas,
    processes,
    devices,
    thresholds,
    alerts
)

# Crear tablas si no existen (en SQLite o PostgreSQL)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Aviso al verificar tablas en la base de datos: {e}")

app = FastAPI(
    title="MOSTO API - Plataforma Vitivinícola IoT",
    description="Backend completo en FastAPI para autenticación, personal, telemetría IoT (DS18B20/MPU-6050), gestión de cubas, bitácora y configuración SaaS.",
    version="1.0.0"
)

# Configuración de CORS para permitir peticiones desde Vite (Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Incluir Routers de MOSTO
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(company.router)
app.include_router(binnacle.router)
app.include_router(master.router)
app.include_router(telemetry.router)
app.include_router(cubas.router)
app.include_router(processes.router)
app.include_router(devices.router)
app.include_router(thresholds.router)
app.include_router(alerts.router)


@app.on_event("startup")
def sembrar_datos_iniciales():
    """Siembra datos iniciales de prueba si la base de datos está vacía (solo en SQLite)."""
    if "sqlite" not in SQLALCHEMY_DATABASE_URL:
        return

    db = SessionLocal()
    try:
        if db.query(models.Cuba).count() == 0:
            cubas_iniciales = [
                models.Cuba(id=1, codigo="CB-01", cap_litros=10000, sector_cuba="Nave A", estado_operativo="en_uso", bodega_id=1, material_id=1),
                models.Cuba(id=2, codigo="CB-02", cap_litros=12000, sector_cuba="Nave A", estado_operativo="en_uso", bodega_id=1, material_id=1),
                models.Cuba(id=3, codigo="CB-03", cap_litros=15000, sector_cuba="Nave B", estado_operativo="disponible", bodega_id=1, material_id=1),
                models.Cuba(id=4, codigo="CB-04", cap_litros=8000, sector_cuba="Nave C", estado_operativo="disponible", bodega_id=1, material_id=1)
            ]
            db.add_all(cubas_iniciales)
            db.commit()
    except Exception as e:
        print(f"Aviso al sembrar datos: {e}")
    finally:
        db.close()


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "app": "MOSTO Backend API",
        "database": "Supabase PostgreSQL" if ("pooler.supabase.com" in SQLALCHEMY_DATABASE_URL or "supabase.co" in SQLALCHEMY_DATABASE_URL) else "SQLite",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
