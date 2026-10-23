# MOSTO — Plataforma IoT de fermentación vitivinícola

**Prototipo navegable basado en los documentos del Proyecto APT Capstone**: modelo relacional de 18 tablas, 10 épicas, HU-01 a HU-40, backlog de 152 puntos y entregables de Fase 1 y Fase 2.

- **Frontend:** Vue 3, Single File Components, Vite, CSS responsive, iconos Lucide.
- **Backend:** Python FastAPI, Pydantic, pruebas con pytest.
- **Base de datos real prevista:** Supabase/PostgreSQL con Supabase Auth, PostgREST y RLS.
- **Modo de presentación predeterminado:** datos de ejemplo **FICTICIOS**, mantenidos solo en memoria en FastAPI. Siempre se identifica como DEMOSTRACIÓN en la interfaz.

> Este repositorio es un **prototipo funcional de interfaz y API de demostración**, NO es una implementación completa y auditada para uso productivo. Lee "Pendiente para producción" más abajo.

## 1. Iniciar en Mac, Windows o Linux

Se requieren Python 3.11 o superior y Node.js 22 o superior. Como alternativa, usa Docker.

**Terminal 1: FastAPI**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2: Vue**

```bash
cd frontend
npm install
npm run dev
```

Abre **http://localhost:5173**. FastAPI estará en **http://localhost:8000/docs** (Swagger).

En modo demo no hay login: los datos están identificados como simulados, puedes registrar cubas, bodegas, dispositivos, perfiles, fermentaciones, intervenciones y atender alertas. Los cambios se borran cuando reinicias la API.

### Alternativa con Docker

Desde la raíz:

```bash
docker compose up --build
```

Abre **http://localhost:8080**; API: **http://localhost:8000/docs**. El Dockerfile del frontend construye Vue con Vite y sirve los archivos mediante nginx, que transmite `/api/` al servicio FastAPI.

## 2. Qué incluye la interfaz

| Pantalla | Funciones visibles | Historias de referencia |
|---|---|---|
| Vista general | KPIs, procesos activos, alertas, monitor de 4 variables, refresco cada 30 s | HU-25, HU-28 |
| Bodegas y cubas | Inventario, registro, estado, filtro por bodega | HU-06 a HU-09 |
| Fermentaciones | Iniciar, cerrar, historial y acceso al monitor | HU-19 a HU-22 |
| Dispositivos | Inventario, batería, RSSI, asignación/desasignación | HU-10 a HU-14 |
| Centro de alertas | Pendientes, atendidas, resueltas con nota | HU-27 a HU-29 |
| Perfiles y umbrales | Rangos por bodega/cepa, lectura de ajustes | HU-15 a HU-18 |
| Bitácora | Intervenciones con fecha y autor | HU-31 a HU-32 |
| Usuarios y permisos | Consulta y asignación de roles; alta de empresa | HU-02, HU-03, HU-37 |
| Catálogos | Cepas, materiales, modelos y roles | HU-16 |
| Reportes | Gráficos de historial y exportación CSV simplificada | HU-34, HU-36 |

Ninguna vista debe presentar lecturas inventadas como si fueran de sensores reales. El **modo demo** usa un conjunto de prueba explícitamente ficticio. El **modo real** solo devuelve filas desde Supabase para el JWT autenticado. Cuando no hay lecturas, muestra un estado vacío; cuando en modo real faltan lecturas recientes, advierte sobre su antigüedad.

## 3. Simular una lectura IoT y una alerta (SOLO demo)

El endpoint de demostración acepta claves sintéticas `mosto-demo-dispositivo-N`, donde `N` es el ID del dispositivo. **Jamás utilices estas claves en producción.**

```bash
curl -X POST http://localhost:8000/api/iot/lecturas \
  -H 'Content-Type: application/json' \
  -H 'X-Device-Key: mosto-demo-dispositivo-1' \
  -d '{
    "dispositivo_id": 1,
    "timestamp": "2026-10-23T20:14:00Z",
    "temp_mosto": 31.0,
    "temp_ambiente": 22.2,
    "densidad_sg": 1.055,
    "brix": 13.4,
    "ph": 3.5
  }'
```

El servidor valida credencial, dispositivo activo, asignación vigente, fermentación activa, duplicados, pH y °Brix. Si el valor está fuera de los umbrales, genera una alerta pendiente sin duplicar otra pendiente del mismo tipo. También compara la caída diaria de °Brix cuando existe una lectura histórica comparable. El navegador refresca las vistas cada 30 segundos. **En modo real, la ruta IoT responde 501** hasta configurar autenticación de dispositivo revocable y transacciones reales.

Para estado del nodo:

```bash
curl -X POST http://localhost:8000/api/iot/estado \
 -H 'Content-Type: application/json' \
 -H 'X-Device-Key: mosto-demo-dispositivo-1' \
 -d '{"dispositivo_id":1,"timestamp":"2026-10-23T20:16:00Z","bateria_pct":87,"bateria_volt":3.91,"rssi_dbm":-65,"estado_red":"conectado"}'
```

## 4. Conexión con Supabase (modo real: integración parcial)

1. Copia `backend/.env.example` a `backend/.env` o exporta variables de entorno:
   - `DEMO_MODE=false`
   - `SUPABASE_URL=https://xxxx.supabase.co`
   - `SUPABASE_ANON_KEY=tu-clave-publicable`
2. Inicia FastAPI con esas variables realmente cargadas. El archivo `.env` **no se carga automáticamente** si usas `uvicorn` sin `--env-file`. Puedes usar `uvicorn app.main:app --env-file .env` después de instalar `python-dotenv`, o exportarlas en tu shell. Con Docker Compose se leen desde la raíz.
3. Inicia sesión en la pantalla Vue con un usuario existente en Supabase Auth.
4. Revisa `backend/app/main.py:TABLE_MAP`. Supone tablas físicas en minúsculas como `proceso_fermentacion`, `evento_alerta`, etc. Si el SQL real usa nombres distintos, **ajusta los nombres y campos**.
5. Verifica y corrige **las políticas RLS por empresa y bodega en las 18 tablas**. El informe de Fase 2 menciona acceso amplio para `authenticated`: eso **no basta** para aislar empresas. No conectar clientes reales hasta completar y probar RLS.
6. Adapta `backend/sql/mosto_rpc.sql` a los tipos/estados/columnas que realmente tengas e instálalo en staging, luego prueba la transición de alertas, intervenciones, cierre de fermentaciones y desasignación.

**Protección de datos:** FastAPI revalida cada JWT mediante el endpoint `/auth/v1/user` de Supabase. Las peticiones PostgREST se hacen con ese JWT y una clave pública, jamás con `service_role`. Debes asegurarte de que las políticas RLS también restrinjan inserciones, modificaciones y lectura. Los RPC usan `SECURITY INVOKER` y necesitan permisos RLS. No confundir esta propuesta con una auditoría de seguridad superada.

## 5. Pendiente para producción (importante)

- **RLS y roles:** diseñar y probar políticas para cada tabla con al menos dos empresas y roles distintos por bodega, incluidos los casos negativos. Restringir endpoints de alta de empresas a `Administrador de plataforma`. La interfaz en demo no implementa identidad y permisos reales.
- **Operaciones de negocio atómicas:** completar constraints, triggers o RPC para creación de fermentación/cambio automático de estado, cambio de roles en vez de duplicados, verificación interempresa, fechas y exclusividad por dispositivo.
- **Ingesta IoT real:** incorporar tabla/servicio de credenciales revocables, comunicación autenticada y almacenamiento transaccional de lecturas/alertas. Los endpoints actuales de ingesta son solo de demostración.
- **Alertas:** separar los umbrales fijos, caída diaria de °Brix y política de severidad/histéresis; realizar pruebas con datos reales y reglas aprobadas por el enólogo.
- **Monitoreo:** intervalos, límites por dispositivo, paginación, permisos por bodega, tratamiento de lecturas parciales, precisión de sensores y alertas por ausencia de datos.
- **HU-26, HU-30, HU-33, HU-35, HU-39, HU-40:** invalidación/reversión de lecturas, notificaciones externas, marcadores sobre gráficos, exportación PDF, credenciales IoT y rendimiento de largo plazo no están terminados.
- **ML:** el motor predictivo de Fase 1 no está construido ni entrenado aquí. No se muestran probabilidades ni fechas predictivas inventadas.
- **Auditoría y despliegue:** pruebas de interfaz Vue, pruebas de integración Supabase, migraciones SQL, protección CSRF/XSS, rate limiting, observabilidad y rotación de claves.
- **Limitaciones del prototipo:** la exportación CSV está limitada a 5000 filas; no hay zoom histórico ni paginación en todas las tablas. La tabla de lecturas demo almacena unas decenas de puntos por proceso.

## 6. Pruebas de backend

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

Pruebas cubiertas: health, datos base, flujo de alerta, límites de volumen, filtro/exportación, unicidad de empresas, reemplazo de roles, cambios de estado prohibidos, credenciales IoT incorrectas, generación de alerta, deduplicación y reenvíos.

## 7. Diseño / trazabilidad

Consulta `TRAZABILIDAD.md`. La vista `vista_previa.html` es **solo una maqueta HTML estática** sin API, incluida para abrir el diseño visual incluso sin instalar dependencias. La web real está en `frontend/src/App.vue` y consume FastAPI.

_Nota de entrega_: este entorno no tuvo resolución DNS hacia el registro npm, de modo que se verificó la sintaxis JavaScript del componente principal y se ejecutaron las pruebas del backend, pero **no se pudo ejecutar `npm install` ni verificar una compilación Vite de extremo a extremo**. En un equipo con acceso a npm se debe ejecutar `npm install && npm run build` antes de desplegar.
