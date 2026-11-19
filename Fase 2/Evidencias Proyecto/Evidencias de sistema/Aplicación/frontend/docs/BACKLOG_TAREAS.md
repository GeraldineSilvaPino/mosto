# Backlog Detallado de Tareas de Conexión Frontend ⇄ Backend (Trello)

Este documento desglosa el trabajo de conexión e integración del Frontend (Vue 3 + Vite) con la API REST del Backend (FastAPI + Supabase) de **MOSTO** en **tareas modulares y técnicas**, distribuidas equitativamente entre los **3 integrantes** del equipo.

Cada tarea está acotada a una vista o flujo específico para facilitar su desarrollo independiente, revisión de código (*Pull Requests*) y seguimiento en las columnas de Trello (*Backlog*, *En Progreso*, *En Revisión*, *Completado*).

---

## 1. Documentación Técnica de Referencia

Cada tarea cuenta con especificaciones técnicas detalladas en los siguientes documentos del repositorio:

* **Guía de Conexión y Servicios:** Ver [04_guia_conexion_api_backend.md](./04_guia_conexion_api_backend.md) para la arquitectura de Axios, composables y servicios modulares.
* **Colección Oficial de Endpoints:** Ver `backend/docs/MOSTO_API_Postman_Collection.json` con todos los contratos de request/response validados.
* **Simulador de Sensores:** Ver `backend/simulate_esp.py` para generar telemetría y anomalías térmicas y de acidez en tiempo real.
* **Diccionario de Modelos y DTOs:** Ver `backend/app/schemas.py` para los esquemas Pydantic (`CubaOut`, `HistoricoCubaOut`, `AlertaOut`, `DispositivoOut`, `PerfilOut`).

---

## 2. Mapa General de Tareas Modulares (9 Tareas de Integración)

```
 ┌───────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
 │           INTEGRANTE 1            │           INTEGRANTE 2            │           INTEGRANTE 3            │
 │   Monitoreo en Tiempo Real y      │   Centro de Alertas, Protocolos   │      Device Hub IoT y             │
 │        Curvas Chart.js            │        y Auditoría MTTR           │     Umbrales Enológicos           │
 ├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
 │ TASK-FE-01A: Dashboard en Vivo    │ TASK-FE-02A: Alertas y Protocolo  │ TASK-FE-03A: Device Hub (Online)  │
 │              (GET /api/cubas)     │              (GET/PATCH alertas)  │              (GET /dispositivos)  │
 ├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
 │ TASK-FE-01B: Detalle e Histórico  │ TASK-FE-02B: Auditoría MTTR       │ TASK-FE-03B: Vincular / Desvincular│
 │              (Chart.js Datasets)  │              (Métricas y Cierre)  │              (Hardware ESP32)     │
 ├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
 │ TASK-FE-01C: Ciclo de Vendimia    │ TASK-FE-02C: Descarga Bitácora    │ TASK-FE-03C: CRUD Perfiles / Cepa │
 │              (Iniciar/Finalizar)  │              (Exportación CSV)    │              (Umbrales Térmicos)  │
 └───────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

---

## 3. Desglose de Tareas por Integrante

---

### 🍇 INTEGRANTE 1: Monitoreo en Tiempo Real y Curvas Chart.js

#### TASK-FE-01A: Conexión de DashboardView con Telemetría en Vivo de Cubas
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-dashboard-cubas-api`
* **Archivos Involucrados:** `frontend/src/services/cubaService.js`, `frontend/src/views/DashboardView.vue`
* **Endpoints Asociados:** `GET /api/cubas`
* **Alcance:**
  * Reemplazar el listado mock en `DashboardView.vue` por el consumo reactivo del servicio `cubaService.listarCubas()`.
  * Mapear atributos del DTO `CubaOut`: `id`, `codigo_cuba`, `variedad`, `ultima_temperatura`, `ultimos_brix`, `volumen_actual_lts`, `estado_operativo`.
  * Implementar cálculo automático de KPIs superiores (total cubas, en fermentación, disponibles, advertencias) mediante `computed`.
  * Configurar auto-refresco periódico (polling) cada 10-15 segundos limpiado correctamente con `onBeforeUnmount`.
* **Criterios de Aceptación:**
  - [ ] Consumo exitoso de `GET /api/cubas` vía `apiClient`.
  - [ ] Estados de interfaz gestionados: spinner/skeleton de carga (`loading`) y mensaje con reintento si falla la red (`error`).
  - [ ] Polling activo que refleja las fluctuaciones generadas por el simulador `simulate_esp.py`.
  - [ ] Navegación hacia `/cubas/:id` preservando el identificador real de la cuba.

---

#### TASK-FE-01B: Conexión de CubaDetailView y Curvas de Fermentación Chart.js
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-cuba-detail-chartjs`
* **Archivos Involucrados:** `frontend/src/services/cubaService.js`, `frontend/src/views/CubaDetailView.vue`
* **Endpoints Asociados:** `GET /api/cubas/{id}`, `GET /api/cubas/{id}/historico?rango_horas={24|48|168}`
* **Alcance:**
  * Cargar la ficha individual de la cuba y su serie temporal de lecturas en paralelo (`Promise.all`).
  * Inyectar los datos en los gráficos de Chart.js registrados en la vista:
    * Eje X: `labels` (timestamps formateados por el backend).
    * Dataset 1: `temp` / `temperaturas_vino` (Sonda DS18B20).
    * Dataset 2: `brix` / `grados_brix` (Flotador MPU-6050).
  * Selector de rango temporal reactivo (24h, 48h, 7 días) que reconsulta el endpoint y actualiza el gráfico con `chartInstance.update()`.
* **Criterios de Aceptación:**
  - [ ] Renderizado sin errores de Chart.js tanto con datos reales como cuando la cuba no tiene lecturas (estado vacío seguro).
  - [ ] Cambio dinámico entre rangos de tiempo (24h/48h/168h) con actualización suave del gráfico.
  - [ ] Información contextual de proceso y cepa sincronizada con los datos de Supabase.

---

#### TASK-FE-01C: Ciclo de Vida de Vendimia (Iniciar y Finalizar Proceso)
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-process-lifecycle`
* **Archivos Involucrados:** `frontend/src/services/processService.js`, `frontend/src/views/CubaDetailView.vue`
* **Endpoints Asociados:** `POST /api/procesos/iniciar`, `PATCH /api/procesos/{id}/finalizar`
* **Alcance:**
  * Permitir iniciar una nueva fermentación si la cuba está en estado `"disponible"` enviando volumen, brix inicial y días estimados.
  * Botón y modal de "Finalizar Fermentación" si el proceso está `"en_proceso"`, liberando la cuba a `"disponible"`.
  * Notificaciones de feedback en pantalla (toasts de éxito / errores de validación de backend).
* **Criterios de Aceptación:**
  - [ ] Validación de volumen contra capacidad máxima antes de enviar `POST /api/procesos/iniciar`.
  - [ ] Al finalizar proceso, confirmar acción con el operador y enviar `PATCH /api/procesos/{id}/finalizar`.
  - [ ] Refresco inmediato del estado operativo de la cuba sin requerir recargar la página.

---

### 🔔 INTEGRANTE 2: Centro de Alertas, Protocolos y Auditoría MTTR

#### TASK-FE-02A: Conexión de AlertsView y Protocolo de Atención
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-alerts-management`
* **Archivos Involucrados:** `frontend/src/services/alertService.js`, `frontend/src/views/AlertsView.vue`
* **Endpoints Asociados:** `GET /api/alertas`, `PATCH /api/alertas/{id}/atender`
* **Alcance:**
  * Sustituir el listado mock por `alertService.listarAlertas()` soportando filtros reactivos por `estado` (`pendiente`, `atendida`, `resuelta`), `severidad` (`baja`, `media`, `alta`, `critica`) y `cuba_id`.
  * Conectar el modal del Protocolo de Revisión del Enólogo con `PATCH /api/alertas/{id}/atender` enviando operador y notas de inspección.
  * Respeto de la restricción de base de datos `ck_alerta_atencion` (registro atómico de `fecha_atencion` y operador).
* **Criterios de Aceptación:**
  - [ ] Tabla reactiva con badges de severidad calculados desde la base de datos real.
  - [ ] Transición inmediata de estado de la alerta a "atendida" en la UI tras confirmar en el modal.
  - [ ] Filtros combinables sin recargar la página (por severidad, estado y búsqueda).

---

#### TASK-FE-02B: Conexión de AlertsAuditView y Métricas MTTR
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-alerts-audit-mttr`
* **Archivos Involucrados:** `frontend/src/services/alertService.js`, `frontend/src/views/AlertsAuditView.vue`
* **Endpoints Asociados:** `GET /api/alertas/metricas`, `PATCH /api/alertas/{id}/resolver`
* **Alcance:**
  * Conectar las tarjetas de KPIs de auditoría con `alertService.obtenerMetricas()`:
    * MTTR Promedio (`mttr_promedio_minutos`).
    * Tasa de Resolución (`tasa_resolucion_pct`).
    * Total Activas y Críticas.
  * En la ficha de detalle de auditoría, conectar botón "Resolver Incidencia" invocando `PATCH /api/alertas/{id}/resolver` con la nota de acción correctiva.
* **Criterios de Aceptación:**
  - [ ] Renderizado de MTTR en minutos con dos decimales y tasa porcentual de resolución.
  - [ ] Registro exitoso de la resolución con timestamp `fecha_resolucion` en base de datos.
  - [ ] Actualización automática de las métricas MTTR tras resolver una incidencia.

---

#### TASK-FE-02C: Descarga Directa de Bitácora Histórica en CSV
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-alerts-export-csv`
* **Archivos Involucrados:** `frontend/src/services/alertService.js`, `frontend/src/views/AlertsAuditView.vue`
* **Endpoints Asociados:** `GET /api/alertas/exportar`
* **Alcance:**
  * Conectar el botón "Exportar Bitácora CSV" usando `alertService.exportarCsv(filtros)` con `responseType: 'blob'`.
  * Crear descarga directa en el navegador vía `window.URL.createObjectURL(blob)`.
  * Extraer el nombre de archivo desde la cabecera `Content-Disposition`.
* **Criterios de Aceptación:**
  - [ ] Descarga automática de archivo `.csv` compatible con Excel (BOM UTF-8 sin caracteres corruptos).
  - [ ] Estado `loading` en el botón durante la generación y descarga.
  - [ ] Los filtros activos (fechas, severidad, estado) deben transmitirse en la petición del CSV.

---

### 📡 INTEGRANTE 3: Device Hub IoT y Umbrales Enológicos

#### TASK-FE-03A: Conexión de DevicesView con el Device Hub IoT
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-devices-hub-api`
* **Archivos Involucrados:** `frontend/src/services/deviceService.js`, `frontend/src/views/DevicesView.vue`
* **Endpoints Asociados:** `GET /api/dispositivos`
* **Alcance:**
  * Listar microcontroladores ESP32 / ESP8266 desde el backend.
  * Renderizar estado dinámico (`online` si transmitió hace $\le 120$ s, `offline` si no).
  * Renderizar barra de calidad de señal Wi-Fi según `signalQuality` (`excellent`, `good`, `weak`, `none`) y porcentaje de batería.
  * Polling automático cada 15-20 segundos para monitorear pérdidas de conexión de nodos.
* **Criterios de Aceptación:**
  - [ ] Mapeo 1:1 con DTO `DispositivoOut` sin errores en consola.
  - [ ] Cálculo dinámico de estado reflejado fielmente cuando el simulador `simulate_esp.py` está transmitiendo o detenido.
  - [ ] Contadores superiores de nodos online/offline sincronizados en tiempo real.

---

#### TASK-FE-03B: Operaciones de Hardware (Vincular y Desvincular de Cubas)
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-devices-link-unlink`
* **Archivos Involucrados:** `frontend/src/services/deviceService.js`, `frontend/src/views/DevicesView.vue`
* **Endpoints Asociados:** `POST /api/dispositivos/vincular`, `POST /api/dispositivos/desvincular`
* **Alcance:**
  * Modal de emparejamiento físico para asociar un sensor libre a una cuba existente (`POST /api/dispositivos/vincular`).
  * Botón de desvinculación rápida que cierra la asignación activa (`POST /api/dispositivos/desvincular`).
  * Validación de reglas de negocio (ej: no vincular dispositivos de empresas/bodegas distintas).
* **Criterios de Aceptación:**
  - [ ] Actualización inmediata de la tarjeta del dispositivo reflejando la nueva cuba o estado "Sin Asignar".
  - [ ] Manejo de errores 400/404 con alertas descriptivas.
  - [ ] Cierre automático de modales tras confirmación exitosa.

---

#### TASK-FE-03C: Conexión de ThresholdsView (CRUD de Perfiles Enológicos)
* **Estado:** BACKLOG
* **Rama Git:** `feat/fe-thresholds-crud-api`
* **Archivos Involucrados:** `frontend/src/services/profileService.js`, `frontend/src/views/ThresholdsView.vue`
* **Endpoints Asociados:** `GET /api/perfiles`, `POST /api/perfiles`, `PUT /api/perfiles/{id}`, `DELETE /api/perfiles/{id}`
* **Alcance:**
  * Reemplazar la persistencia local de `localStorage` por la API REST oficial de `PERFIL_FERMENTACION`.
  * Formulario de calibración de bandas térmicas (`temp_min`, `temp_max`) y de acidez (`ph_min`, `ph_max`).
  * Validación preventiva antes de enviar:
    * `temp_min <= temp_max` (restricción `ck_perfil_temp`).
    * `ph_min <= ph_max` (restricción `ck_perfil_ph`).
  * Desactivación segura (soft-delete): bloquear eliminación si el perfil está en uso por un proceso activo en curso.
* **Criterios de Aceptación:**
  - [ ] CRUD funcional de perfiles con feedback visual (toasts).
  - [ ] Respuestas HTTP 200, 201 y 400 manejadas limpiamente en el formulario.
  - [ ] Persistencia verificable en la base de datos PostgreSQL de Supabase.

---

## 4. Flujo de Trabajo en Git

1. **Bifurcación:** Cada integrante crea su rama desde `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b <nombre-de-rama-sugerido>
   ```
2. **Formato de Commits:** Utilizar la convención del proyecto:
   ```bash
   feat(dashboard): conectar vista con GET /api/cubas y polling (TASK-FE-01A)
   feat(alerts): implementar protocolo de atencion y metricas MTTR (TASK-FE-02A)
   feat(devices): conectar device hub e inventario iot dinamico (TASK-FE-03A)
   ```
3. **Integración:** Abrir Pull Request hacia `develop` indicando los checkboxes completados. Se requiere aprobación de al menos 1 compañero antes del merge.
