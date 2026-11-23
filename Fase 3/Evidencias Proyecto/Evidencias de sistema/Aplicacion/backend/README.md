> El [README de la aplicación](../README.md) describe el arranque con Docker, la conexión con Supabase y la demo local.

> **Canal IoT actual:** [Telemetría v2](docs/TELEMETRIA_V2.md) documenta credenciales individuales, calibración, idempotencia, pruebas y límites. Aplicar las [migraciones locales](docs/MIGRACIONES_Y_POSTGRESQL.md) antes de arrancar una demo nueva.

> **Demostración de bodega:** [Simulador enológico continuo](docs/SIMULADOR_ENOLOGICO.md), con cinco escenarios virtuales, historial reanudable por HTTP y una reserva física sin mediciones ficticias. Este es el flujo nuevo; `simulate_esp.py` se conserva como demo legacy.

# MOSTO - Backend API (FastAPI)

Backend en Python con FastAPI y SQLAlchemy. La instalación con Supabase usa PostgreSQL. Las pruebas locales también admiten SQLite.

---

## 🚀 Requisitos e Instalación

### 1. Crear y activar el entorno virtual de Python
Desde `C:\mosto\Fase 3\Evidencias Proyecto\Evidencias de sistema\Aplicacion`:

```bash
cd backend
python -m venv venv
```

Activar el entorno:
* **En Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
* **En Windows (CMD):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar el servidor de desarrollo
```bash
uvicorn app.main:app --reload --port 8000
```

* **API en vivo:** [http://localhost:8000](http://localhost:8000)
* **Documentación interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Documentación alternativa (ReDoc):** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Docker y Supabase

El Compose se ejecuta desde la carpeta `Aplicacion`. La [guía de arranque](../README.md) incluye la configuración de la cuenta SQL, el certificado TLS, el monitor y los comandos de demo. La instalación principal publica la aplicación y su API bajo el mismo origen en el puerto 8080.

---

## 📡 Endpoints de Ingesta IoT (Hardware)

### 1. ESP32 (Sonda DS18B20 + DHT22 + pH)
* **Ruta:** `POST /api/telemetria/nodo-cuba`
* **JSON:**
  ```json
  {
    "device_mac": "24:6F:28:C8:11:50",
    "cuba_id": 1,
    "temp_vino": 24.5,
    "temp_ambiente": 19.2,
    "humedad_ambiente": 58.0,
    "voltaje_ph": 2.15
  }
  ```

### 2. ESP8266 (Inclinómetro MPU-6050 / Flotador)
* **Ruta:** `POST /api/telemetria/flotador`
* **JSON:**
  ```json
  {
    "device_mac": "3C:71:BF:12:44:88",
    "cuba_id": 1,
    "inclinacion": 42.5,
    "ax": 0.12,
    "ay": 0.65,
    "az": 0.74
  }
  ```

# Migraciones y PostgreSQL

La inicialización local y las pruebas utilizan Alembic. Consulta [revisiones, comandos, diferencias con Supabase y validación](docs/MIGRACIONES_Y_POSTGRESQL.md) antes de inicializar una base. El baseline solo admite bases vacías; no se ha migrado Supabase.

