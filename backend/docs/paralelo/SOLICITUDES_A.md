# Solicitudes / contratos publicados por A

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
