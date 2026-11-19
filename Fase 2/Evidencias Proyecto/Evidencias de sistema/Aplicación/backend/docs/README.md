# Documentacion Oficial del Backend MOSTO

Bienvenido a la documentacion tecnica del backend de la plataforma MOSTO, desarrollada con FastAPI, SQLAlchemy y Supabase PostgreSQL, e integrada con microcontroladores ESP32 y ESP8266 para telemetria vitivinicola en tiempo real.

---

## Indice de Documentacion

Esta carpeta contiene guias tecnicas detalladas para que cualquier integrante del equipo de desarrollo o asistente automatizado comprenda de forma inmediata el funcionamiento, la arquitectura y las tareas pendientes:

| Documento | Descripcion |
|---|---|
| [ARQUITECTURA_Y_CONVENCIONES.md](./ARQUITECTURA_Y_CONVENCIONES.md) | Estructura de carpetas, flujo por capas, inyeccion de dependencias, convenciones de Git y buenas practicas de desarrollo. |
| [BACKLOG_TAREAS.md](./BACKLOG_TAREAS.md) | Desglose exhaustivo de las tarjetas de trabajo para los 3 integrantes del equipo, con criterios de aceptacion y alcance delimitado. |
| [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md) | Analisis de los sensores fisicos, circuitos, formulas de calibracion (grados Brix, pH, bateria) y contratos JSON para el firmware de Arduino. |
| [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md) | Esquema relacional, tablas maestras, llaves foraneas, restricciones CHECK y reglas de los triggers PL/pgSQL activos en Supabase. |

---

## Inicio Rapido (Desarrollo con Docker)

El backend se ejecuta dentro de un contenedor Docker optimizado con sincronizacion en tiempo real (Hot-Reload):

```powershell
# 1. Posicionarse en la raiz del proyecto
cd c:\mosto

# 2. Levantar el backend en segundo plano
docker compose up -d

# 3. Ver logs en tiempo real
docker compose logs -f

# 4. Detener el contenedor
docker compose down
```

### URLs Principales:
* Swagger UI (Documentacion interactiva de la API): http://localhost:8000/docs
* ReDoc (Documentacion OpenAPI alternativa): http://localhost:8000/redoc
* Health Check y Estado de Conexion a Supabase: http://localhost:8000/

---

## Asignacion de Responsabilidades por Integrante
* Integrante 1 (IoT y Hardware): Ingesta de sensores ESP32 y ESP8266, calibracion fisica y simulador de telemetria.
* Integrante 2 (Reglas y Auditoria): Motor de reglas enologicas, disparador de alertas y auditoria historica MTTR.
* Integrante 3 (Procesos, Cubas y Hardware Hub): APIs para el frontend (curvas historicas para graficos, panel de dispositivos y perfiles termicos).
