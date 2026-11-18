# Estado A

## 18-11 — A4, reproducción del pipeline y protocolo de lotes reales

Finalizaron los siete comandos de referencia, robustez e intervalos en un venv
limpio Python 3.14.6. Directorio local ignorado
`backend/artifacts/replica-a-1a907655-b399-420e-8ab7-ef6270c610f8`. Métricas
reproducidas dentro de 1e-8, con hashes distintos de los de Python 3.11.
Quedan registrados comparación, particiones, límites y hashes en
[FICHA_MODELO_EXPERIMENTAL](../FICHA_MODELO_EXPERIMENTAL.md). Protocolo de
etiquetas y reserva real en [VALIDACION_ENOLOGICA](../VALIDACION_ENOLOGICA.md).
Pendientes externos: lotes, revisión instrumental y adjudicación enológica.
ML continúa NO_VALIDADO. A4 hardware/DSS sigue abierto.

CI de A3 confirmada para `9d910d9`: ambos trabajos, Windows y PostgreSQL Linux,
con resultado satisfactorio en [GitHub Actions](https://github.com/GeraldineSilvaPino/mosto/actions/runs/44391742537).

## 18-11 — A3, instalación limpia y primera carga de lectura

Restauración PostgreSQL publicada en `7ddf03c`. En Windows, venv nuevo con Python
3.14.6, instalación desde requirements-tested-windows-py314.txt y pip check
correctos. Suite SQLite completa en ese entorno: 329 aprobadas, 16 omitidas,
3961 advertencias, 114,53 s. Docker CLI instalado, motor Linux inaccesible
(falta el pipe dockerDesktopLinuxEngine); ensayo Compose pendiente.

Carga objetivo local: lecturas autenticadas de /api/procesos/pagina?limit=1
sobre la semilla demo, 12 peticiones consecutivas por cliente con 1, 4 y 8
clientes, cero errores y p95 inferior a 2 s por escalón. Uvicorn por TCP local,
PostgreSQL 18.4 desechable. Desde backend:

```powershell
python -m scripts.test_postgres --pg-bin "C:/Program Files/PostgreSQL/18/bin" -- backend/tests/bench_process_page.py -qs --disable-warnings
```

| Clientes | Peticiones | Errores | Peticiones/s | p95 ms | Pico de conexiones del pool en uso |
| --- | --- | --- | --- | --- | --- |
| 1 | 12 | 0 | 44,6 | 32,1 | 2 |
| 4 | 48 | 0 | 36,7 | 275,4 | 8 |
| 8 | 96 | 0 | 39,1 | 363,9 | 15 |

Una prueba aprobada y apagado confirmado. A ocho clientes el pool alcanzó su
capacidad predeterminada (5 + 10). La medición cubre una página sobre pocos datos
con un usuario; quedan por caracterizar escritura IoT, históricos grandes y
carga sostenida. Siguiente A1: vincular el reloj a proceso incluso si cambia el
dispositivo. Pendientes A3 externos: Docker operativo y evidencia de CI remota.

## 18-11 — A3, restauración PostgreSQL verificada

Reanudación en `0e4cd61` con árbol limpio, sin pytest ni worker Python activo.
Los registros de dos clústeres anteriores confirman apagado. Otro directorio
histórico conserva un postmaster.pid cuyo PID ya no existe. Se conservaron
esos artefactos. B seguía en la base común sin solicitudes tras fetch.

Desde `backend`, ejecutar con el Python del entorno:

```powershell
python -m scripts.test_postgres --pg-bin "C:/Program Files/PostgreSQL/18/bin" --restore-drill
```

El lanzador crea un clúster local y dos bases vacías. Migra y siembra la primera,
hace pg_dump con el propietario limitado, modifica un valor testigo y restaura en
la segunda con pg_restore en una transacción. PostgreSQL 18.4 recuperó 30 tablas,
26 filas totales, el valor previo y la revisión 0008_process_profile_overrides.
Coincidieron cantidades por tabla e inventario de 306 restricciones (nombre, tipo,
tabla y validación). La restauración rechazó estado inválido, cambio de propiedad
histórica y referencia huérfana. Apagado del clúster confirmado.
Alcance local con datos demo; RPO/RTO de operación real pendientes.
Punto siguiente de A3: carga HTTP concurrente e instalación limpia.

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
