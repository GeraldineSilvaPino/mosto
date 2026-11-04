# 🔌 Guía de Integración Frontend ⇄ Backend — Proyecto MOSTO
## Sistema IoT y Plataforma Web de Monitoreo Enológico de Fermentación

> **Documento Oficial de Integración de Equipo**  
> **Rama Base:** `develop`  
> **Backend:** FastAPI + SQLAlchemy + Docker + PostgreSQL (Supabase) en `http://localhost:8000`  
> **Frontend:** Vue 3 (Composition API `<script setup>`) + Vite + Tailwind/CSS + Vue Router  

---

## 📌 1. Arquitectura y Configuración de la Capa de Comunicación

### 1.1. Ajuste de CORS en Backend (`backend/app/main.py`)
Para permitir que el frontend en Vue 3 (Vite en puerto `5173`) consuma la API sin bloqueos y pueda **descargar archivos CSV directamente leyendo la cabecera `Content-Disposition`**, el middleware de CORS en `backend/app/main.py` debe contemplar:

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

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
    expose_headers=["Content-Disposition"] # Requerido para extracción del nombre de archivo CSV
)
```

---

### 1.2. Variables de Entorno del Frontend (`frontend/.env`)
Crear el archivo `frontend/.env` en la raíz del frontend:

```env
# URL base del Backend FastAPI
VITE_API_BASE_URL=http://localhost:8000

# Timeout de peticiones HTTP en milisegundos (10 segundos)
VITE_API_TIMEOUT_MS=10000
```

---

### 1.3. Instalación de Axios
Ejecutar en la terminal dentro de `c:\mosto\frontend`:

```powershell
npm install axios
```

---

### 1.4. Cliente HTTP Centralizado (`frontend/src/services/api.js`)
Configura la instancia compartida de Axios con timeout, baseURL e interceptores de respuesta unificados para capturar los errores lanzados por FastAPI (`detail`):

```javascript
// frontend/src/services/api.js
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 10000

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// Interceptor de respuesta global para manejo unificado de errores
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.message ||
      'Error de comunicación con el servidor MOSTO'

    console.error(`[API Error ${error.response?.status || 'RED'}]:`, errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default apiClient
```

---

### 1.5. Composable Reutilizable de Estado Asíncrono (`frontend/src/composables/useAsyncState.js`)
Estandariza los estados `loading`, `error` y reintentos en todas las vistas:

```javascript
// frontend/src/composables/useAsyncState.js
import { ref } from 'vue'

export function useAsyncState() {
  const loading = ref(false)
  const error = ref(null)

  const execute = async (asyncFn) => {
    loading.value = true
    error.value = null
    try {
      return await asyncFn()
    } catch (err) {
      error.value = err.message || 'Ocurrió un error inesperado al procesar la solicitud'
      throw err
    } finally {
      loading.value = false
    }
  }

  return { loading, error, execute }
}
```

---

## 👥 2. Matriz de Distribución Equitativa (3 Integrantes)

```
                    ┌────────────────────────────────────────────────────────┐
                    │               DISTRIBUCIÓN DEL EQUIPO                 │
                    └────────────────────────────────────────────────────────┘
                                                 │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
  INTEGRANTE 1                    INTEGRANTE 2                    INTEGRANTE 3
  Monitoreo & Curvas              Centro de Alertas & MTTR        Device Hub & Umbrales
  ─────────────────────           ────────────────────────        ─────────────────────
  • DashboardView.vue             • AlertsView.vue                • DevicesView.vue
  • CubaDetailView.vue            • AlertsAuditView.vue           • ThresholdsView.vue
  • cubaService.js                • alertService.js               • deviceService.js
  • processService.js                                             • profileService.js
```

| Integrante | Rol y Módulo | Vistas Asignadas | Endpoints Backend | Dificultad |
| :--- | :--- | :--- | :--- | :---: |
| **Integrante 1** | Monitoreo en Tiempo Real & Curvas Chart.js | `DashboardView.vue`<br>`CubaDetailView.vue` | `GET /api/cubas`<br>`GET /api/cubas/{id}`<br>`GET /api/cubas/{id}/historico`<br>`POST /api/procesos/iniciar`<br>`PATCH /api/procesos/{id}/finalizar` | Media / Alta |
| **Integrante 2** | Centro de Alertas, Protocolos & Auditoría MTTR | `AlertsView.vue`<br>`AlertsAuditView.vue` | `GET /api/alertas`<br>`GET /api/alertas/metricas`<br>`GET /api/alertas/exportar`<br>`PATCH /api/alertas/{id}/atender`<br>`PATCH /api/alertas/{id}/resolver` | Media / Alta |
| **Integrante 3** | Device Hub IoT & Umbrales Enológicos | `DevicesView.vue`<br>`ThresholdsView.vue` | `GET /api/dispositivos`<br>`POST /api/dispositivos/vincular`<br>`POST /api/dispositivos/desvincular`<br>`GET /api/perfiles`<br>`POST /api/perfiles`<br>`PUT /api/perfiles/{id}`<br>`DELETE /api/perfiles/{id}` | Media / Alta |

---

## 📦 3. Servicios Modulares Frontend (Código Completo)

Para prevenir colisiones en Git, cada integrante trabajará en archivos de servicios independientes dentro de `frontend/src/services/`.

---

### 🍇 SERVICIOS DEL INTEGRANTE 1

#### `frontend/src/services/cubaService.js`
```javascript
import apiClient from './api'

export default {
  /**
   * Obtiene la lista de todas las cubas con telemetría en tiempo real
   */
  listarCubas() {
    return apiClient.get('/api/cubas').then((res) => res.data)
  },

  /**
   * Obtiene el detalle completo de una cuba por su ID
   */
  obtenerCuba(id) {
    return apiClient.get(`/api/cubas/${id}`).then((res) => res.data)
  },

  /**
   * Obtiene la serie histórica de lecturas para Chart.js
   * @param {number|string} id - ID de la cuba
   * @param {number} rangoHoras - Ventana de tiempo (24, 48, 168)
   */
  obtenerHistorico(id, rangoHoras = 24) {
    return apiClient
      .get(`/api/cubas/${id}/historico`, { params: { rango_horas: rangoHoras } })
      .then((res) => res.data)
  }
}
```

#### `frontend/src/services/processService.js`
```javascript
import apiClient from './api'

export default {
  /**
   * Lista los procesos de fermentación con filtros opcionales
   */
  listarProcesos(params = {}) {
    return apiClient.get('/api/procesos', { params }).then((res) => res.data)
  },

  /**
   * Obtiene el detalle de un proceso por ID
   */
  obtenerProceso(id) {
    return apiClient.get(`/api/procesos/${id}`).then((res) => res.data)
  },

  /**
   * Inicia una nueva fermentación (Vendimia)
   * Payload: { cuba_id, perfil_id, cepa_id, volumen_litros, brix_inicial, brix_objetivo, dias_estimados }
   */
  iniciar(payload) {
    return apiClient.post('/api/procesos/iniciar', payload).then((res) => res.data)
  },

  /**
   * Finaliza una fermentación activa y libera la cuba
   * Payload opcional: { densidad_final_sg, observaciones }
   */
  finalizar(procesoId, payload = {}) {
    return apiClient
      .patch(`/api/procesos/${procesoId}/finalizar`, payload)
      .then((res) => res.data)
  }
}
```

---

### 🔔 SERVICIO DEL INTEGRANTE 2

#### `frontend/src/services/alertService.js`
```javascript
import apiClient from './api'

export default {
  /**
   * Lista alertas con filtros dinámicos (estado, severidad, cuba_id, limit, offset)
   */
  listarAlertas(params = {}) {
    return apiClient.get('/api/alertas', { params }).then((res) => res.data)
  },

  /**
   * Obtiene KPIs globales y fórmula MTTR calculada
   */
  obtenerMetricas(cubaId = null) {
    const params = cubaId ? { cuba_id: cubaId } : {}
    return apiClient.get('/api/alertas/metricas', { params }).then((res) => res.data)
  },

  /**
   * Registra el inicio de atención de una alerta por un operador
   */
  atender(id, payload = { usuario_id: 1, nota: '' }) {
    return apiClient.patch(`/api/alertas/${id}/atender`, payload).then((res) => res.data)
  },

  /**
   * Resuelve una incidencia registrando la acción correctiva
   */
  resolver(id, payload = { usuario_id: 1, nota_resolucion: '' }) {
    return apiClient.patch(`/api/alertas/${id}/resolver`, payload).then((res) => res.data)
  },

  /**
   * Descarga directa en el navegador de la bitácora histórica en CSV
   */
  async exportarCsv(params = {}) {
    const response = await apiClient.get('/api/alertas/exportar', {
      params,
      responseType: 'blob'
    })

    // Extraer nombre del archivo de la cabecera Content-Disposition si existe
    let filename = `bitacora_alertas_${new Date().toISOString().slice(0, 10)}.csv`
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) filename = match[1]
    }

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}
```

---

### 📡 SERVICIOS DEL INTEGRANTE 3

#### `frontend/src/services/deviceService.js`
```javascript
import apiClient from './api'

export default {
  /**
   * Lista el inventario de dispositivos con estado online/offline dinámico y RSSI
   */
  listarDispositivos(params = {}) {
    return apiClient.get('/api/dispositivos', { params }).then((res) => res.data)
  },

  /**
   * Obtiene detalle de un dispositivo IoT por ID
   */
  obtenerDispositivo(id) {
    return apiClient.get(`/api/dispositivos/${id}`).then((res) => res.data)
  },

  /**
   * Vincula físicamente un sensor a una cuba
   */
  vincular(dispositivoId, cubaId) {
    return apiClient
      .post('/api/dispositivos/vincular', {
        dispositivo_id: Number(dispositivoId),
        cuba_id: Number(cubaId)
      })
      .then((res) => res.data)
  },

  /**
   * Desvincula un dispositivo de su cuba actual
   */
  desvincular(dispositivoId) {
    return apiClient
      .post('/api/dispositivos/desvincular', {
        dispositivo_id: Number(dispositivoId)
      })
      .then((res) => res.data)
  }
}
```

#### `frontend/src/services/profileService.js`
```javascript
import apiClient from './api'

export default {
  /**
   * Lista todos los perfiles de fermentación y bandas enológicas
   */
  listarPerfiles(params = {}) {
    return apiClient.get('/api/perfiles', { params }).then((res) => res.data)
  },

  /**
   * Obtiene un perfil específico por ID
   */
  obtenerPerfil(id) {
    return apiClient.get(`/api/perfiles/${id}`).then((res) => res.data)
  },

  /**
   * Crea un nuevo perfil enológico con sus bandas térmicas y de acidez
   */
  crearPerfil(payload) {
    return apiClient.post('/api/perfiles', payload).then((res) => res.data)
  },

  /**
   * Actualiza umbrales de un perfil existente
   */
  actualizarPerfil(id, payload) {
    return apiClient.put(`/api/perfiles/${id}`, payload).then((res) => res.data)
  },

  /**
   * Desactiva (soft-delete) un perfil de fermentación
   */
  desactivarPerfil(id) {
    return apiClient.delete(`/api/perfiles/${id}`).then((res) => res.data)
  }
}
```

---

## 🗺️ 4. Diccionario de Mapeo de Datos (Backend ⇄ Frontend)

Para evitar desajustes en nombres de variables al reemplazar la data mock en los archivos `.vue`:

### 4.1. Cubas y Telemetría (`DashboardView.vue` y `CubaDetailView.vue`)
| Propiedad en Mock Frontend | Campo en DTO Backend (`CubaOut`) | Tipo | Notas |
| :--- | :--- | :--- | :--- |
| `cuba.id` | `id` | `Integer` | ID primario de la cuba |
| `cuba.codigo` | `codigo_cuba` | `String` | Ej: `"CB-01"`, `"CB-02"` |
| `cuba.nombre` | `nombre` | `String` | Ej: `"Cuba CB-01"` |
| `cuba.variedad` | `variedad` | `String` | Obtenida de la cepa del proceso activo |
| `cuba.lote` | `lote` | `String` | Código de lote enológico |
| `cuba.temperatura` | `ultima_temperatura` | `Float` | Última lectura DS18B20 (°C) |
| `cuba.brix` | `ultimos_brix` | `Float` | Grados Brix del flotador MPU-6050 |
| `cuba.volumenActual` | `volumen_actual_lts` | `Float` | Litros cargados en el proceso |
| `cuba.tempMin` | `temp_min_perfil` | `Float` | Límite inferior óptimo |
| `cuba.tempMax` | `temp_max_perfil` | `Float` | Límite superior óptimo |
| `cuba.fase` | `estado_operativo` | `String` | `"en_uso"` o `"disponible"` |
| `cuba.dia` | `dia_fermentacion` | `Integer` | Días transcurridos desde inicio |

### 4.2. Histórico para Gráficos Chart.js (`CubaDetailView.vue`)
| Formato Esperado por Chart.js | Campo en DTO Backend (`HistoricoCubaOut`) | Contenido |
| :--- | :--- | :--- |
| `chartData.labels` | `labels` o `timestamps` | Array de horas formateadas: `["14:00", "14:15", ...]` |
| `dataset[0].data` (Temperatura) | `temp` o `temperaturas_vino` | Array de floats: `[24.5, 24.6, 24.8, ...]` |
| `dataset[1].data` (Brix) | `brix` o `grados_brix` | Array de floats: `[18.2, 18.0, 17.8, ...]` |
| `dataset[2].data` (pH) | `valores_ph` | Array de floats: `[3.45, 3.46, ...]` |

### 4.3. Dispositivos de Hardware (`DevicesView.vue`)
> [!NOTE]
> El DTO `DispositivoOut` del backend fue diseñado de forma idéntica a los nombres de atributos mock en `DevicesView.vue`:
- `code` ➔ `"ESP32-DEV-01"`
- `sensorType` ➔ `"DS18B20"`, `"MPU-6050"`, `"PH-4502C"`
- `status` ➔ `"online"` (si transmitió en los últimos 120s), `"offline"`, `"maintenance"`
- `signalQuality` ➔ `"excellent"`, `"good"`, `"weak"`, `"none"`
- `powerSource` ➔ `"battery"` o `"mains"`
- `batteryLevel` ➔ Nivel de batería `0 - 100` (%)
- `lastTelemetry` ➔ String legible en español: `"Hace 12 seg"`, `"Hace 4 min"`

### 4.4. Alertas e Incidencias (`AlertsView.vue` y `AlertsAuditView.vue`)
- `id` ➔ ID de la alerta
- `cuba_codigo` / `cuba_nombre` ➔ Código y nombre de la cuba asociada
- `tipo_alerta` ➔ `"temp_alta"`, `"temp_baja"`, `"ph_alto"`, `"ph_bajo"`, etc.
- `severidad` ➔ `"critica"`, `"alta"`, `"media"`, `"baja"`
- `estado` ➔ `"pendiente"`, `"atendida"`, `"resuelta"`
- `operador_nombre` ➔ Nombre del usuario que atendió la alerta
- `timestamp` ➔ Fecha y hora de detección (ISO 8601 UTC)

---

## 🚀 5. Procedimiento de Ejecución y Pruebas del Equipo

Para probar el flujo completo con datos vivos y fluctuaciones en tiempo real:

### Paso 1: Iniciar el Backend
```powershell
cd c:\mosto
docker compose up -d
# O alternativamente con uvicorn local:
cd backend
uvicorn app.main:app --reload --port 8000
```
Verificar que responda `http://localhost:8000/api/health` ➔ `{"status": "healthy"}`.

### Paso 2: Ejecutar el Simulador de Sensores IoT
En una segunda terminal:
```powershell
cd c:\mosto\backend
python simulate_esp.py
```
> El simulador inyecta lecturas cada 3 segundos en las cubas con procesos activos, alternando estados normales y alertas térmicas.

### Paso 3: Iniciar el Frontend (Vite)
En una tercera terminal:
```powershell
cd c:\mosto\frontend
npm run dev
```
Abrir `http://localhost:5173` en el navegador.

---

## 🌿 6. Convención de Ramas Git y Pull Requests

Cada integrante creará su rama derivada directamente de `develop`:

```bash
# Actualizar base
git checkout develop
git pull origin develop

# Integrante 1
git checkout -b feat/fe-dashboard-cubas-api
git checkout -b feat/fe-cuba-detail-chartjs

# Integrante 2
git checkout -b feat/fe-alerts-management
git checkout -b feat/fe-alerts-audit-mttr

# Integrante 3
git checkout -b feat/fe-devices-hub-api
git checkout -b feat/fe-thresholds-crud-api
```

### Reglas de Integración:
1. No hacer `push` directo a `develop` ni `main`.
2. Crear Pull Request hacia `develop` al finalizar los criterios de aceptación de cada tarjeta.
3. Verificar que no queden errores en la consola del navegador (`F12`).
4. Solicitar revisión cruzada (Peer Review) a al menos uno de los otros dos integrantes antes de mergear.

