"""
Punto de entrada principal de la API MOSTO en FastAPI.
Configura middlewares de CORS, inicialización de base de datos y routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal, SQLALCHEMY_DATABASE_URL
from . import models
from .routers import telemetry, cubas, processes, devices

# Crear tablas si no existen (en SQLite o PostgreSQL)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Aviso al verificar tablas en la base de datos: {e}")

app = FastAPI(
    title="MOSTO API - Plataforma Vitivinícola IoT",
    description="Backend en FastAPI para monitoreo de fermentación, telemetría de sensores DS18B20 y MPU-6050 y gestión de cubas.",
    version="0.1.0"
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
)

# Incluir Routers
app.include_router(telemetry.router)
app.include_router(cubas.router)
app.include_router(processes.router)
app.include_router(devices.router)


@app.on_event("startup")
def sembrar_datos_iniciales():
    """Siembra datos iniciales de prueba si la base de datos está vacía (solo en SQLite)."""
    if "sqlite" not in SQLALCHEMY_DATABASE_URL:
        return  # En Supabase no inyectamos datos automáticos para no alterar su BD

    db = SessionLocal()
    try:
        if db.query(models.Cuba).count() == 0:
            cubas_iniciales = [
                models.Cuba(id=1, codigo="CB-01", nombre="Cuba 01 · Cabernet Sauvignon", variedad="Cabernet Sauvignon", lote="Lote CS-2026-A", dia_fermentacion=6, dias_estimados=14),
                models.Cuba(id=2, codigo="CB-02", nombre="Cuba 02 · Carménère Reserva", variedad="Carménère", lote="Lote CM-2026-B", dia_fermentacion=4, dias_estimados=12, estado="advertencia"),
                models.Cuba(id=3, codigo="CB-03", nombre="Cuba 03 · Sauvignon Blanc", variedad="Sauvignon Blanc", lote="Lote SB-2026-F", dia_fermentacion=9, dias_estimados=16),
                models.Cuba(id=4, codigo="CB-04", nombre="Cuba 04 · Syrah Gran Corte", variedad="Syrah", lote="Lote SY-2026-C", dia_fermentacion=13, dias_estimados=14)
            ]
            db.add_all(cubas_iniciales)

            dispositivos_iniciales = [
                models.Dispositivo(id=1, codigo="ESP32-CB01-TEMP", nombre="Nodo Térmico Cuba 01", mac="24:6F:28:B4:9C:12", modelo="ESP32", tipo_sensor="DS18B20", cuba_id=1),
                models.Dispositivo(id=2, codigo="ESP32-CB01-TILT", nombre="Cápsula Flotante Cuba 01", mac="3C:71:BF:12:44:88", modelo="ESP8266", tipo_sensor="MPU-6050", cuba_id=1, fuente_energia="battery")
            ]
            db.add_all(dispositivos_iniciales)
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
        "database": "Supabase PostgreSQL" if "pooler.supabase.com" in SQLALCHEMY_DATABASE_URL or "supabase.co" in SQLALCHEMY_DATABASE_URL else "SQLite",
        "version": "0.1.0",
        "docs_url": "/docs"
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
