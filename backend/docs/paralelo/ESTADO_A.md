# Estado A

## 18-11: A3, respaldo/restauración SQLite local

Implementado scripts/sqlite_backup.py y guía RESPALDO_SQLITE.md. Snapshot por API
SQLite, manifiesto/hash, comprobación de integridad/FKs/revisión y cantidades;
rechazo de sobrescritura. Cuatro pruebas aprobadas (1,30 s), incluida restauración
del esquema Mosto actual con datos. Corregido cierre explícito de conexiones para
permitir limpieza del archivo fallido en Windows. No certifica PostgreSQL ni RPO/RTO.
Siguiente trabajo A3: ensayo equivalente PostgreSQL aislado, carga e instalación
limpia. A1 aún requiere migración temporal; no se habilitó ingesta acelerada.
Revisión remota B al iniciar: sin solicitudes. Frontend y archivos B intactos.

## 18-11: A3, correlación HTTP

Middleware registra request_id propio, método, plantilla de ruta, status y duración;
no query, cuerpo ni credenciales. Cabecera visible en CORS. Configuración explícita
backend/logging.json y guía OBSERVABILIDAD.md. Cinco pruebas SQLite aprobadas
(correlación, errores manejados, CORS y paginación), 1,97 s. No certifica retención,
carga ni redacción de logs ajenos. A3 parcial: faltan instalación limpia, Docker,
backup/restauración, carga y CI remota. A1 sigue pendiente de migración temporal.
Commit anterior A2: e4ba4c8, publicado. No se modificó ningún archivo de B.

Inicio: base común, 18-11-2026. Ningún bloque nuevo A1–A5 cerrado en paralelo aún.
Activo siguiente: A1, migración e integración temporal del reloj.

## 18-11: A2, paginación de procesos publicada

Nuevo endpoint aditivo /api/procesos/pagina; filtros activos/cerrados/cuba,
orden estable por ID, totales y límites. API legacy intacta. 12 pruebas SQLite
aprobadas (paginación y matriz de acceso), 3,71 s. Contrato A-API-001 en
SOLICITUDES_A. A2 parcial: faltan métricas/listas restantes y peticiones B.
Siguiente independiente: A3 logs correlacionados sin datos sensibles.
A1 sigue abierto; no se ha retirado la guarda de ingesta acelerada.

Actualizar tras cada sección: fecha, objetivo, archivos, pruebas/resultados,
limitaciones, commit, dependencias externas/solicitudes y siguiente tarea ejecutable.
Si bloqueado en A1, avanzar A2/A3/A4 independientes; no detenerse por cierre parcial.
