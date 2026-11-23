# Mediciones manuales estructuradas

Implementación local del 17-11-2026, revisión `0007_manual_measurements`. Registra observaciones declaradas por personas con unidad, método, instrumento, fecha y evidencia. Complementa las [intervenciones](INTERVENCIONES_ESTRUCTURADAS.md) y la bitácora. No escribe lecturas instrumentales, no calcula nuevas features ML y no resuelve ni recupera episodios automáticamente.

## Contrato y trazabilidad

`MEDICION_MANUAL` conserva el proceso, alerta/intervención opcionales, autor autenticado, valor finito, unidad, método, referencia de instrumento, evidencia textual, instante observado e instante registrado por el servidor. El origen de salida es siempre `manual`; el usuario no puede sustituir autor, hora de registro ni origen. El ID del autor es estable; su nombre mostrado se consulta del usuario actual.

| Variable | Unidad | Métodos admitidos | Rango de entrada |
| --- | --- | --- | --- |
| `temperatura` | °C | `termometro` | −50 a 150 |
| `brix_aparente` | °Bx | `refractometro`, `densimetro_brix` | −10 a 90 |
| `densidad` | g/mL | `densimetro` | 0,5 a 2 |
| `ph` | pH | `phmetro` | 0 a 14 |

Estos son límites amplios de entrada, no perfiles enológicos ni certificación de exactitud/calibración. No se convierten unidades ni se mezclan métodos. Brix aparente no equivale a azúcar residual; no hay corrección automática por alcohol. La evidencia es una descripción o referencia de muestra/registro de laboratorio, de 5 a 2.000 caracteres, no un archivo adjunto ni un certificado verificado. El instrumento requiere entre 3 y 200 caracteres.

`observado_en` exige zona horaria y se normaliza a UTC. Debe estar dentro del intervalo del proceso y no ser futuro respecto del servidor. Se admite una entrada tardía de un proceso cerrado si su observación pertenece al intervalo histórico. Un cierre histórico sin fecha verificable impide nuevas entradas. La UI muestra las horas locales y conserva ambas fechas: registro tardío no implica observación reciente.

Las referencias a alerta e intervención deben pertenecer al mismo proceso y estar autorizadas. Si ambas se proporcionan y la intervención tiene alerta, deben coincidir. La API y el formulario permiten vincular una intervención opcional. El selector pagina opciones del mismo proceso; desde un incidente incluye intervenciones sin alerta o de ese incidente. Muestra ID, acción y estado, con actualización y reintento. La vinculación no declara ejecución ni recuperación. Endpoint de opciones: GET /api/mediciones-manuales/intervenciones/{process_id}, con alerta_id, limit y offset. Cierre y pruebas: [evidencia del 18-11](evidencias/selector-intervencion-2026-11-18.md).

## API y permisos

- `GET /api/mediciones-manuales/contexto/{process_id}`: catálogo, límites temporales y permiso operativo en esa bodega.
- `GET /api/mediciones-manuales?fermentacion_id=...&alerta_id=...&limit=20&offset=0`: lista ordenada por fecha observada descendente e ID, total, datos originales y eventual anulación. Proceso obligatorio, alerta opcional; límite máximo 100.
- `POST /api/mediciones-manuales`: alta con UUID `request_id`, proceso y campos del contrato. Crea medición y bitácora en la misma transacción.
- `POST /api/mediciones-manuales/{id}/anular`: UUID `request_id` y `motivo` de 5 a 2.000 caracteres. Añade evidencia de anulación y bitácora; no borra ni sustituye el valor original.

Administradores, enólogos y operadores pueden registrar/anular dentro de sus bodegas. Lectores solo consultan. Se aplican los filtros existentes de empresa/bodega a mediciones, anulaciones y referencias. La autorización procede de membresías vigentes, no del rol del JWT.

La clave de alta es única por proceso. Repetir el mismo UUID con contenido normalizado y actor idénticos devuelve el registro existente; otro contenido o actor produce 409. La anulación es única por medición: solo se repite la misma solicitud; no se sobrescribe el motivo. Una nueva corrección se registra como otra medición después de anular la incorrecta, sin enlace automático de sustitución. Las listas incluyen las anuladas explícitamente.

El alta y la anulación bloquean primero la cuba, igual que el cierre del proceso. Esto serializa escrituras concurrentes en PostgreSQL; las pruebas de concurrencia de ese motor están preparadas pero todavía omitidas en este equipo. SQLite comprueba las restricciones portables y la transacción, sin certificar el mismo comportamiento de bloqueo concurrente.

## Inmutabilidad y migración

La revisión añade dos tablas: `MEDICION_MANUAL` y `ANULACION_MEDICION`, con referencias a proceso, actores y bitácora, y unicidad para reintentos/anulación. El esquema suma **28 tablas de dominio y Alembic**. La sesión de negocio rechaza modificaciones y borrados de ambas entidades; PostgreSQL incorpora además triggers de inmutabilidad. SQLite no tiene esos triggers: su protección ante edición pasa por la API/sesión, no por acceso SQL arbitrario.

No se reconstruyen mediciones a partir de notas históricas. Las notas antiguas siguen siendo texto y no se inventan método, unidades ni autoría adicionales. La UI de incidentes reemplaza el antiguo campo libre «Registrar Muestra» por el panel estructurado compartido. No hay edición destructiva ni conversión de notas a lecturas instrumentales.

Aplicar únicamente a una base local explícita conforme a [Migraciones](MIGRACIONES_Y_POSTGRESQL.md). El arranque API no migra tablas y una base con revisión anterior no cumple readiness. Durante este bloque se migraron solo SQLite temporales de pruebas/demo; Supabase y producción permanecieron intactos.

## Interfaz y comprobaciones

Panel en detalle del proceso activo de una cuba y ficha de incidente (incluida auditoría mediante el componente compartido): catálogo, método dependiente de variable, unidad fija, fecha local, evidencia, historial paginado y anulación con motivo. Los lectores reciben vista de consulta. UUID estable por contenido ante reintento mientras el componente permanezca montado; no hay outbox offline del navegador ni garantía de conservar una solicitud tras cerrar la página.

Suite consolidada: **257 aprobadas, 14 omitidas**, SQLite temporal, Python 3.11.4. Incluye 18 pruebas aprobadas nuevas y tres casos PostgreSQL pendientes (triggers y concurrencia). Migración desde cero, downgrade/upgrade, concordancia ORM y SQL PostgreSQL offline comprobados. Build Vite correcto. [Evidencia del cierre](evidencias/mediciones-manuales-2026-11-17.md).

Navegador contra API y SQLite local nuevos: alta de 18,3 °Bx, anulación con motivo y persistencia tras recarga; segunda medición de 24,2 °C vinculada al incidente #1001, bitácora actualizada, recarga persistente y alerta todavía pendiente. No se certificó móvil, accesibilidad completa, carga ni hardware. Comparación de curvas, recomendaciones DSS y validación científica siguen pendientes.
