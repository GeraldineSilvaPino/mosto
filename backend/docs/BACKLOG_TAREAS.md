# Backlog Detallado de Tareas de Backend (Trello)

Este documento desglosa el trabajo del backend de MOSTO en **tareas modulares y digeribles (historias tecnicas cortas)**, distribuidas equitativamente entre los **3 integrantes** del equipo.

Cada tarea esta acotada a 1 o 2 archivos como maximo para facilitar su implementacion, revision de codigo (Code Review) y seguimiento en las columnas de Trello (*Backlog*, *En Progreso*, *En Revision*, *Completado*).

---

## 1. Documentacion Tecnica de Referencia

Cada tarea incluye enlaces directos a sus especificaciones tecnicas:

* **Arquitectura y Capas:** Ver [ARQUITECTURA_Y_CONVENCIONES.md](./ARQUITECTURA_Y_CONVENCIONES.md) para estructura de routers, schemas, services y models.
* **Hardware y Sensores:** Ver [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md) para circuitos, pines, formulas de conversion y contratos JSON.
* **Base de Datos:** Ver [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md) para restricciones CHECK y triggers PL/pgSQL de Supabase.
* **Despliegue Local:** Ver [README.md](./README.md) para ejecucion y logs con Docker.

---

## 2. Mapa General de Tareas Modulares (12 Tareas en Total)

```
 ┌───────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
 │           INTEGRANTE 1            │           INTEGRANTE 2            │           INTEGRANTE 3            │
 │     Telemetria IoT y Hardware     │      Reglas, Alertas y MTTR       │     Cubas, Procesos y Hub         │
 ├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
 │ TASK-BE-01A: Ingesta ESP32 (Vino) │ TASK-BE-03A: Reglas Termicas/pH   │ TASK-BE-05A: Monitoreo Cubas Base │
 │ TASK-BE-01B: Ingesta ESP8266(Brix)│ TASK-BE-03B: Disparador Anti-Spam │ TASK-BE-05B: Historico Chart.js   │
 │ TASK-BE-01C: Salud Nodos (Bateria)│ TASK-BE-04A: API Listado/Atencion │ TASK-BE-05C: Ciclo de Vendimia    │
 │ TASK-BE-02A: Script Simulador     │ TASK-BE-04B: Resolucion/MTTR/CSV  │ TASK-BE-06A: Device Hub (Online)  │
 │ TASK-BE-02B: Inyector Anomalias   │                                   │ TASK-BE-06B: CRUD Perfiles/Cepa   │
 └───────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

---

## 3. Desglose de Tareas por Integrante

---

### INTEGRANTE 1: Telemetria Hardware, Ingesta y Simulacion

#### TASK-BE-01A: Ingesta de Sonda Termica y Sensor de pH (ESP32)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-telemetry-esp32`
* **Archivos:** `backend/app/schemas.py`, `backend/app/services/telemetry_service.py`, `backend/app/routers/telemetry.py`
* **Referencia Tecnica:** [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md#2-nodo-1-esp32-sonda-termica-y-de-ph) (Formula Nernst y divisor 2.0x).
* **Alcance:**
  * Endpoint `POST /api/telemetria/nodo-cuba`.
  * Recibe temperatura de vino (DS18B20), temperatura/humedad ambiental (DHT22) y voltaje analógico de pH (PH-4502C).
  * Convierte voltaje analógico a pH enológico ($pH = 7.0 - \frac{V - 2.50}{0.18}$) e inserta en tabla `LECTURA_TELEMETRIA`.
* **Criterios de Aceptacion:**
  - [x] Validar payload con DTO `TelemetriaESP32In`.
  - [x] Calcular pH y registrar lectura asociada a la cuba y proceso activo.
  - [x] Respuesta HTTP 201 en menos de 200 ms.

---

#### TASK-BE-01B: Ingesta de Inclinometro Hidrometro Flotante (ESP8266)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-telemetry-esp8266`
* **Archivos:** `backend/app/schemas.py`, `backend/app/services/telemetry_service.py`, `backend/app/routers/telemetry.py`
* **Referencia Tecnica:** [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md#3-nodo-2-esp8266-flotador-hidrometro--densimetro-iot) (Calculo angular e inclinacion a Brix).
* **Alcance:**
  * Endpoint `POST /api/telemetria/flotador`.
  * Recibe angulo de inclinacion o componentes de aceleracion `ax`, `ay`, `az` desde el sensor MPU-6050 (`esp86xyz.ino`).
  * Convierte grados de inclinacion a grados Brix y gravedad especifica SG e inserta en `LECTURA_TELEMETRIA`.
* **Criterios de Aceptacion:**
  - [x] Validar payload con DTO `TelemetriaESP8266In`.
  - [x] Derivar grados Brix y gravedad especifica (SG) a partir del angulo de flotacion.
  - [x] Persistir en Supabase cumpliendo restricciones de valores no nulos.

---

#### TASK-BE-01C: Monitoreo de Salud de Nodos (Bateria y Wi-Fi RSSI)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-node-health`
* **Archivos:** `backend/app/services/telemetry_service.py`, `backend/app/models.py`
* **Referencia Tecnica:** [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md#4-metricas-de-salud-de-hardware) (Curva de descarga Li-Po 1S y rangos dBm).
* **Alcance:**
  * Almacenar metricas de salud de microcontroladores en la tabla `TELEMETRIA_ESTADO_NODO`.
  * Calcular porcentaje restante de bateria Li-Po (3.3V a 4.2V) y categorizar senal Wi-Fi (Excelente, Buena, Regular, Debil).
* **Criterios de Aceptacion:**
  - [x] Cumplir restricciones CHECK `ck_nodo_bateria` ($0 \le \text{pct} \le 100$) y `ck_nodo_rssi` ($\text{rssi} \le 0$).
  - [x] Actualizar registro de nodo por cada transmision de hardware.

---

#### TASK-BE-02A: Script Simulador de Nodos ESP32 y ESP8266
* **Estado:** Pendiente
* **Rama Git:** `feat/be-iot-simulator-base`
* **Archivos a Crear:** `backend/scripts/simulate_esp.py`
* **Referencia Tecnica:** [HARDWARE_Y_TELEMETRIA.md](./HARDWARE_Y_TELEMETRIA.md#5-contratos-de-comunicacion-http-para-el-firmware-arduino) (Formato JSON de envio).
* **Alcance:**
  * Script independiente en Python ejecutable desde terminal (`python backend/scripts/simulate_esp.py --cuba 1 --interval 5`).
  * Envia peticiones HTTP POST periodicas a `/api/telemetria/nodo-cuba` y `/api/telemetria/flotador` simulando una fermentacion real (°Brix descendiendo de 24° a 2°, temperatura oscilando en torno a 18.5°C).
* **Criterios de Aceptacion:**
  - [ ] Transmitir paquetes validos a ambos endpoints en bucle configurable.
  - [ ] Manejo de excepciones ante perdida de conexion con el servidor backend.

---

#### TASK-BE-02B: Inyector de Anomalias y Pruebas de Estres de Hardware
* **Estado:** Pendiente
* **Rama Git:** `feat/be-iot-simulator-faults`
* **Archivos a Intervenir:** `backend/scripts/simulate_esp.py`
* **Alcance:**
  * Agregar parametros CLI para forzar situaciones criticas en la fermentacion:
    * `--spike-temp 33.0`: Simula sobrecalentamiento subito para probar disparador de alertas.
    * `--drain-battery 3.2`: Simula descarga de bateria para probar alerta de hardware.
    * `--drop-ph 2.8`: Simula desviacion de acidez.
* **Criterios de Aceptacion:**
  - [ ] Parametros CLI documentados con `--help`.
  - [ ] Salida visual limpia en consola indicando codigo HTTP de respuesta de cada paquete enviado.

---

### INTEGRANTE 2: Motor de Reglas Vitivinicolas, Alertas y Auditoria

#### TASK-BE-03A: Servicio de Deteccion de Desviaciones Termicas y Acidez
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-rules-thermal-ph`
* **Archivos a Crear:** `backend/app/services/rules_engine.py`
* **Referencia Tecnica:** [ARQUITECTURA_Y_CONVENCIONES.md](./ARQUITECTURA_Y_CONVENCIONES.md#3-responsabilidad-estricta-de-cada-modulo) (Servicios de negocio).
* **Alcance:**
  * Crear la clase `RulesEngine` que evalue cada lectura contra los limites de `PERFIL_FERMENTACION` de la cuba.
  * Detecta: temperatura por sobre el maximo optimo, temperatura bajo el minimo optimo y pH fuera de rango.
* **Criterios de Aceptacion:**
  - [x] Metodo `evaluar_lectura(db: Session, lectura: LecturaTelemetria, cuba_id: int) -> list[dict]`.
  - [x] Asignacion de nivel de severidad segun magnitud del desvio (`'alta'`, `'media'`, `'critica'`).

---

#### TASK-BE-03B: Disparador de Alertas con Control Anti-Spam (Debounce)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-rules-alert-dispatcher`
* **Archivos a Intervenir:** `backend/app/services/rules_engine.py`, `backend/app/services/telemetry_service.py`
* **Referencia Tecnica:** [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md#3-restricciones-check-de-integridad) (Restricciones CHECK `ck_alerta_estado` y `ck_alerta_severidad`).
* **Alcance:**
  * Si `RulesEngine` detecta una transgresion, inserta un registro en la tabla `EVENTO_ALERTA` con estado `'pendiente'`.
  * Filtro de enfriamiento temporal: no volver a generar la misma alerta para la misma cuba si existe una abierta generada hace menos de 15 minutos.
* **Criterios de Aceptacion:**
  - [x] Conectar la evaluacion de reglas al final del procesamiento de telemetria.
  - [x] Verificar que no se inserten registros duplicados ante lecturas consecutivas anomalous.

---

#### TASK-BE-04A: API de Consulta y Reconocimiento de Alertas
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-alerts-read-ack`
* **Archivos:** `backend/app/routers/alerts.py`, `backend/app/schemas.py`, `backend/app/models.py`, `backend/app/main.py`
* **Alcance:**
  * Endpoints REST para la vista `AlertsView.vue`:
    * `GET /api/alertas`: Lista alertas con filtros (`?estado=pendiente`, `?severidad=critica`, `?cuba_id=1`).
    * `PATCH /api/alertas/{id}/atender`: Cambia estado a `'atendida'` y registra timestamp del operador.
* **Criterios de Aceptacion:**
  - [x] Endpoint de listado paginado o con limite parametrizable.
  - [x] Cumplimiento de la restriccion `ck_alerta_atencion` (`atendida_por` exige `fecha_atencion`).

---

#### TASK-BE-04B: Resolucion de Incidencias, Metricas MTTR y Exportacion CSV
* **Estado:** Pendiente
* **Rama Git:** `feat/be-alerts-resolve-mttr`
* **Archivos a Intervenir:** `backend/app/routers/alerts.py`, `backend/app/schemas.py`
* **Alcance:**
  * Endpoints REST para la vista `AlertsAuditView.vue`:
    * `PATCH /api/alertas/{id}/resolver`: Cambia estado a `'resuelta'` y guarda nota de accion correctiva.
    * `GET /api/alertas/metricas`: Calcula total de alertas activas, criticas y promedio MTTR en minutos.
    * `GET /api/alertas/exportar`: Retorna bitacora historica en formato `text/csv`.
* **Criterios de Aceptacion:**
  - [ ] Formula MTTR calculada sobre alertas con estado `'resuelta'`:
    $$\text{MTTR} = \frac{\sum (\text{fecha\_resolucion} - \text{fecha\_generacion})}{\text{Total Resueltas}}$$
  - [ ] Cabecera de respuesta `Content-Type: text/csv` con descarga directa en el navegador.

---

### INTEGRANTE 3: Cubas, Procesos, Perfiles y Dispositivos

#### TASK-BE-05A: API de Monitoreo de Cubas y Resumen en Tiempo Real
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-cubas-monitoring`
* **Archivos:** `backend/app/routers/cubas.py`, `backend/app/schemas.py`
* **Referencia Tecnica:** [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md#3-restricciones-check-de-integridad) (Restriccion `ck_cuba_estado`).
* **Alcance:**
  * `GET /api/cubas`: Catalogo de cubas con su ultimo estado operativo y lecturas de telemetria agregadas (temperatura actual, grados Brix, pH).
  * `GET /api/cubas/{id}`: Detalle individual de una cuba y su proceso activo.
* **Criterios de Aceptacion:**
  - [x] Consultas optimizadas con orden descendente por fecha.
  - [x] Mapeo de campos a DTO `CubaOut`.

---

#### TASK-BE-05B: Generador de Series Temporales para Chart.js (CubaDetailView)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-cubas-history-chart`
* **Archivos:** `backend/app/routers/cubas.py`, `backend/app/schemas.py`
* **Alcance:**
  * `GET /api/cubas/{id}/historico`: Entrega series temporales con arrays paralelos listos para graficos:
    * `timestamps`: Lista de etiquetas horarias (`HH:MM:SS`).
    * `temperaturas_vino`: Valores en °C.
    * `grados_brix`: Curva de densidad de azucar.
    * `valores_ph`: Mediciones de acidez.
  * Filtro por parametro `rango_horas` (24, 48, 168 horas).
* **Criterios de Aceptacion:**
  - [x] Retornar arrays ordenados cronologicamente de izquierda a derecha.
  - [x] Formato compatible con la configuracion de datasets de Chart.js del frontend.

---

#### TASK-BE-05C: Ciclo de Vida de Procesos de Fermentacion (Vendimia)
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-processes-lifecycle`
* **Archivos:** `backend/app/routers/processes.py`, `backend/app/schemas.py`, `backend/app/main.py`
* **Referencia Tecnica:** [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md#4-disparadores-triggers-plpgsql) (Trigger `fn_validar_proceso`).
* **Alcance:**
  * `POST /api/procesos/iniciar`: Vincula una cuba a una cepa (`CEPA`), perfil de fermentacion y volumen de vendimia.
  * `PATCH /api/procesos/{id}/finalizar`: Cambia estado a `'finalizada'`, calcula densidad final obtenida y libera la cuba.
* **Criterios de Aceptacion:**
  - [x] Validar que `volumen_litros <= cuba.cap_litros` para no infringir el trigger de Supabase.
  - [x] Impedir iniciar un proceso si la cuba ya tiene una fermentacion con estado `'en_proceso'`.

---

#### TASK-BE-06A: API de Device Hub e Inventario de Hardware
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-devices-hub`
* **Archivos a Crear:** `backend/app/routers/devices.py`, `backend/app/schemas.py`
* **Referencia Tecnica:** [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md#4-disparadores-triggers-plpgsql) (Trigger `fn_validar_asignacion_empresa`).
* **Alcance:**
  * Endpoints REST para la vista `DevicesView.vue`:
    * `GET /api/dispositivos`: Listado de microcontroladores (ESP32 y ESP8266), direccion MAC, nivel de bateria, senal RSSI y cuba asociada.
    * Calculo de estado dinamico: si `now() - ultima_conexion > 120s` -> marcar como `'offline'`.
    * `POST /api/dispositivos/vincular`: Asocia un dispositivo a una cuba, cerrando asignaciones previas con `desasignado_en = now()`.
* **Criterios de Aceptacion:**
  - [x] Respetar la restriccion `ck_asignacion_activo` (`activo = (desasignado_en IS NULL)`).
  - [x] Respetar coincidencia de empresa cliente entre dispositivo y bodega.

---

#### TASK-BE-06B: CRUD de Perfiles de Fermentacion y Bandas Termicas
* **Estado:** COMPLETADA
* **Rama Git:** `feat/be-thresholds-profiles`
* **Archivos a Crear:** `backend/app/routers/thresholds.py`, `backend/app/schemas.py`
* **Referencia Tecnica:** [BASE_DE_DATOS_SUPABASE.md](./BASE_DE_DATOS_SUPABASE.md#3-restricciones-check-de-integridad) (Restricciones CHECK `ck_perfil_temp` y `ck_perfil_ph`).
* **Alcance:**
  * Endpoints REST para la vista `ThresholdsView.vue`:
    * `GET /api/perfiles`: Lista perfiles de fermentacion y sus bandas optimas/criticas.
    * `POST /api/perfiles`: Crea un perfil para una cepa vinifera.
    * `PUT /api/perfiles/{id}`: Modifica umbrales de temperatura y pH de un perfil existente.
* **Criterios de Aceptacion:**
  - [x] Validar que `temp_min <= temp_max` y `ph_min <= ph_max` antes de persistir.
  - [x] Integracion probada desde Swagger UI en `http://localhost:8000/docs`.
