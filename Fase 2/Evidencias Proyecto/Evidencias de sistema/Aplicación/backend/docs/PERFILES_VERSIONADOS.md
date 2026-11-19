# Versiones de perfiles y configuración aplicada

Implementación local, 16-11-2026. Migración `0005_profile_versions`: añade
`VERSION_PERFIL`, revisión actual del perfil y `perfil_snapshot` del proceso.
24 tablas de dominio más Alembic. Se ejecuta únicamente mediante las guardas
locales demo/test; no se ha migrado Supabase ni desplegado producción.

## Contrato de edición

- Crear perfil registra versión 1 con usuario autenticado y fecha del servidor.
- Editar bloquea el perfil, registra una nueva versión si cambian sus valores
  persistidos y conserva las anteriores. Un PUT sin cambios no incrementa versión.
- `expected_revision` permite rechazar con 409 una edición basada en versión
  obsoleta. Vue la envía al guardar; clientes antiguos que la omitan conservan
  compatibilidad y no reciben esta protección optimista adicional.
- Archivar registra una versión; repetir el archivado no duplica. Se conserva
  la restricción existente del endpoint DELETE para perfiles en uso activo.
- Cada versión incluye nombre, límites térmicos y pH, caída diaria configurada,
  cepa, bodega y estado activo. La regla cinética experimental tiene su propio
  contrato congelado por proceso: este cambio no la habilita para sensores físicos.
- `GET /api/perfiles/{id}/versiones` devuelve configuración, revisión, autor,
  fecha y origen. Usa permisos por bodega; leer no crea versiones.
- Las versiones no tienen endpoint de edición/borrado. El scope ORM rechaza
  mutaciones y PostgreSQL incluye triggers de inmutabilidad; estos últimos aún
  necesitan ejecución en PostgreSQL en este equipo.

La API conserva null cuando faltan límites; ya no inventa 18/28 °C. En PUT,
omitir un campo lo conserva y enviar null borra un límite opcional. Los valores
no finitos son rechazados. Vue muestra datos ausentes como N/D y no convierte
campos vacíos en cero al guardar. Las bandas críticas derivadas para visualización
siguen siendo heurísticas heredadas; no equivalen a umbrales enológicos certificados.

## Procesos nuevos e historia existente

Iniciar un proceso por `/api/procesos/iniciar` bloquea el perfil y copia todos sus
parámetros con ID/revisión en la misma transacción. La flota de simulación nueva
también conserva la copia, identificando el origen sintético. Los episodios
térmicos nuevos, diagnóstico de límites y límites devueltos para la cuba usan
esa copia. El nombre de perfil presentado en la ficha de proceso queda congelado.
Editar el catálogo después, incluso antes de la primera lectura, no cambia esos
límites. Cerrar un proceso tampoco altera su snapshot.

La migración **no inventa una configuración inicial para procesos existentes**.
Su `perfil_snapshot` queda null. Al editar o usar por primera vez un perfil sin
historial capturado, se registra `captura_existente`, con hora de captura y autor
original desconocido; no se atribuye retrospectivamente al operador actual.
Las reglas de procesos históricos que ya tenían snapshot en `ESTADO_REGLA`
conservan su configuración original. Para reglas aún no evaluadas en procesos
sin snapshot, permanece el comportamiento legacy sobre el perfil disponible.
Los fixtures y caminos de demo legacy siguen identificables sin snapshot; no
se consideran procesos operacionales creados bajo el contrato nuevo.

Si el registro del perfil cambia por fuera del flujo versionado y discrepa de
una versión ya registrada, una edición/inicio posterior devuelve 409 y requiere
reconciliación explícita. No se reescribe la historia para ocultar esa discrepancia.
El ORM de negocio y los triggers de PostgreSQL protegen los snapshots; SQLite
no certifica escrituras externas ni concurrencia de PostgreSQL.

## Verificación y límites

Pruebas de creación/edición/archivo, no-op, conflicto de revisión, permisos,
nulls, rollback, inmutabilidad, rechazo de modificaciones fuera de flujo y
actualización de un esquema local con datos previos. Caso HTTP completo: iniciar
proceso, modificar el perfil, enviar primeras lecturas y confirmar que el episodio
usa la versión inicial. Migración reversible y comparación de esquema con ORM.

Vue incorpora historial expandible y control de revisión al guardar; comprobado
mediante build, sin nueva sesión de navegador para este bloque. El resultado
consolidado está en [Estado del plan](ESTADO_PLAN_MAESTRO.md).

Actualización 18-11: [ajustes térmicos explícitos por proceso](AJUSTES_PERFIL_PROCESO.md)
implementados con motivo, aprobación, vigencia e historial. Conservan el snapshot
inicial y los límites de episodios abiertos. Las intervenciones estructuradas
también están implementadas; ver el estado maestro para el orden actual.
Pendientes: validación concurrente PostgreSQL, adopción de datos remotos y revisión
integral de controles heredados de la pantalla.
