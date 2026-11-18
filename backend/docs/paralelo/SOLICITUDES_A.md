# Solicitudes / contratos publicados por A

## A-API-004 — reloj de una receta registrada

GET `/api/simulaciones/procesos/{process_id}`, JWT y permisos de lectura del
proceso. Sin receta se conserva `{"registered":false,"process_id":1}`.
Con receta 1× legacy devuelve `clock="wall_utc"`, `speed=1` y
`simulation_clock=null`. Con reloj explícito devuelve `clock="simulated_utc"`,
el factor en `speed` y, por ejemplo,
`"simulation_clock":{"real_anchor":"2026-11-18T12:00:00Z","simulated_anchor":"2026-11-17T12:00:00Z","factor":60}`.
`calendar_age_hours` expresa horas de trayectoria hasta la consulta o cierre.
`expected_delivery_at` es la hora real programada de la última observación;
`lag_seconds` usa segundos reales. Ambos son null sin muestra. B puede mostrar
el reloj como configuración y `coverage="sin_muestras"` cuando corresponda.
La ingesta de estas recetas sigue cerrada. 404 para proceso ajeno/inexistente,
401 sin identidad. Prueba HTTP en test_simulation_provenance_clock.

## A-API-003 — abstención en la predicción de cuba

GET `/api/cubas/{id}/ml-prediction`, mismo JWT y ámbito de bodega. Para una
cuba sin proceso activo o un proceso sin suficientes pares Brix/temperatura,
HTTP 200 con `{"riesgo_pct":null,"estado_ia":"RECOLECTANDO_DATOS","alerta_ia":false,...}`.
Si falla la inferencia legacy, el estado es `ERROR` y el riesgo también es null.
El valor opcional ya formaba parte del DTO. El detalle y listado que incluyen
predicción consumen el mismo cálculo. B debe mostrar ausencia de estimación
cuando llegue null. Cuba ajena/inexistente conserva 404 y falta de JWT, 401.
Cobertura en test_ml_prediction y test_access.

## A-API-002 — disponible: correlación HTTP

Respuestas manejadas incluyen X-Request-ID (UUID del servidor), expuesto por CORS.
B puede mostrarlo/capturarlo para diagnóstico; no implica éxito ni debe sustituir
request_id de idempotencia de operaciones. No obligatorio para peticiones.
Errores 500 no manejados pueden carecer de cabecera. No hay cambio de cuerpos.

## A-API-001 — disponible: listado paginado de procesos

GET `/api/procesos/pagina?grupo=todos&limit=20&offset=0&cuba_id=1`.
JWT y ámbito empresa/bodega como el listado existente. `cuba_id` opcional;
`grupo`: todos/activos/cerrados (activos incluye en_proceso y detenida).
limit 1–100, offset >=0. Orden ID descendente. Respuesta:
`{"items": [ProcesoOut], "total": 42, "limit": 20, "offset": 0, "has_more": true}`.
Items conservan exactamente el DTO actual, no hay cambios al GET /api/procesos.
404 cuba ajena/inexistente, 401 sin identidad, 422 parámetros inválidos;
Cache-Control no-store. total y páginas pueden variar si hay escrituras concurrentes:
no es snapshot/cursor estable entre solicitudes. B puede usarlo para navegación
histórica y cargar opciones por páginas. Confirmar consumo en SOLICITUDES_B.
Pruebas: 12 aprobadas de paginación y aislamiento (SQLite, 3,71 s).

Sin cambios de contrato respecto de la base común todavía. A escribe aquí;
B consulta por git show. Formato: ID, estado, endpoint, ejemplos, compatibilidad,
permisos, evidencia, commit y acción requerida de B.
