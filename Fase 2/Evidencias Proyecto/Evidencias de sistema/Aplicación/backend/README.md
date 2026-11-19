> **Continuación por otro desarrollador/Codex:** [Guía de traspaso](../CONTINUAR_MOSTO.md) y [estado actual](docs/ESTADO_PLAN_MAESTRO.md).

> **Arranque actualizado:** consulta [Base segura y reproducible](docs/BASE_SEGURA_Y_REPRODUCIBLE.md). Ya no se crean tablas/datos al arrancar; se requiere JWT_SECRET_KEY y la ingesta legacy es solo demo.

> **Canal IoT actual:** [Telemetría v2](docs/TELEMETRIA_V2.md) documenta credenciales individuales, calibración, idempotencia, pruebas y límites. Aplicar las [migraciones locales](docs/MIGRACIONES_Y_POSTGRESQL.md) antes de arrancar una demo nueva.

> **Demostración de bodega:** [Simulador enológico continuo](docs/SIMULADOR_ENOLOGICO.md), con cinco escenarios virtuales, historial reanudable por HTTP y una reserva física sin mediciones ficticias. Este es el flujo nuevo; `simulate_esp.py` se conserva como demo legacy.

# MOSTO - Backend API (FastAPI)

Backend en Python con **FastAPI**, **SQLAlchemy** y **SQLite** para la plataforma de monitoreo vitivinícola e ingesta de telemetría IoT.

---

## 🚀 Requisitos e Instalación

### 1. Crear y activar el entorno virtual de Python
Desde la carpeta raíz del proyecto (`c:\mosto\backend`):

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

## 🐳 Ejecución con Docker (Recomendado para Producción y Entrega)

Si tienes **Docker Desktop** instalado:

1. Asegúrate de tener configurado tu archivo `.env` en la carpeta `backend/` con las credenciales de Supabase.
2. Desde la raíz del proyecto (`c:\mosto`), ejecuta:
   ```bash
   docker compose up --build
   ```
3. El contenedor compilará la imagen de FastAPI, inyectará las variables de entorno y expondrá la API automáticamente en:
   * **API:** [http://localhost:8000](http://localhost:8000)
   * **Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
4. Para detener los contenedores:
   ```bash
   docker compose down
   ```

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

