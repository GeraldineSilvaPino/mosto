# Ajustes térmicos auditados por proceso

Cierre local: 18-11-2026. Amplía los [perfiles versionados](PERFILES_VERSIONADOS.md) con excepciones térmicas por proceso. La aprobación corresponde al usuario administrador o enólogo autenticado de la bodega; no es un flujo de doble firma ni una certificación enológica de los valores.

## Contrato y alcance

- `GET /api/procesos/{id}/ajustes-perfil`: banda inicial, configuración vigente, revisión, permisos, episodios abiertos y su configuración, historial paginado (`limit` hasta 100 y `offset`). Consulta sin escrituras y sin caché.
- `POST /api/procesos/{id}/ajustes-perfil`: `request_id` UUID, `expected_revision`, `accion` (`ajustar` o `restaurar`) y `motivo` de 10–2.000 caracteres. Ajustar exige `temp_min` y `temp_max` finitos, mínimo menor que máximo. El intervalo de entrada −50 a 100 °C es una restricción técnica, no una banda recomendada para vino. Restaurar utiliza la configuración inicial conservada y no admite nuevos límites.
- Se requiere proceso abierto y snapshot inicial con banda completa. No se reconstruyen límites históricos ausentes ni se permite desactivar la vigilancia con null. No se ajustan umbrales de Brix/pH, reglas cinéticas, calibraciones de dispositivos ni parámetros del simulador.
- Autor y vigencia proceden del servidor. No se permite programar, retrotraer ni enviar identidad de otro aprobador. La hora debe ser posterior a la última observación recibida y al último ajuste, y no anterior al inicio del proceso. Una observación futura ya admitida puede exigir esperar antes de aprobar.
- Cada cambio crea una revisión inmutable y una entrada de bitácora en la misma transacción. Restaurar añade otra revisión; no borra las anteriores. Se rechazan solicitudes sin cambio y revisiones desactualizadas. Un reintento idéntico con el mismo UUID devuelve el registro original; reutilizarlo con otra solicitud produce 409.

## Aplicación temporal y episodios

La evaluación térmica consulta el ajuste vigente **en la hora observada**, no en la hora de recepción del paquete. El backlog anterior al ajuste utiliza su configuración anterior. Se conserva la política existente: observaciones en o antes de la marca de avance de la regla se almacenan, pero no reescriben episodios.

Sin episodio abierto, cambiar de revisión reinicia la persistencia candidata: no se suman minutos de dos configuraciones para confirmar una desviación. La evidencia de un nuevo episodio incluye los límites, histéresis e identidad, autor y vigencia del ajuste aplicado. Persistencia de diez minutos, calidad y tolerancia de huecos de quince minutos conservan su contrato anterior.

Un episodio abierto conserva sus propios umbrales de confirmación y recuperación hasta recuperarse mediante observaciones utilizables. Aprobar/restaurar no altera su condición, evidencia, auditoría, resolución humana ni MTTR. No abre un episodio paralelo del mismo tipo mientras el anterior sigue abierto. La siguiente evaluación sin episodio puede utilizar la banda nueva. Por ello, la banda vigente del proceso puede diferir de la banda conservada por un incidente; el panel muestra ambas.

La configuración base de `ESTADO_REGLA` y `PROCESO_FERMENTACION.perfil_snapshot` permanece inmutable. `perfil_ajuste_revision` solo identifica la revisión usada para la persistencia candidata. La migración `0008_process_profile_overrides` añade ese campo y `AJUSTE_PERFIL_PROCESO`, con unicidad por proceso/revisión y proceso/UUID. PostgreSQL incorpora trigger contra UPDATE/DELETE del historial; SQLite comprueba las restricciones portables y la guarda de aplicación. La validación SQL directa y concurrente en PostgreSQL sigue pendiente.

La aprobación comparte el bloqueo de cuba con ingesta/cierre y comprueba revisión tras obtenerlo. El aislamiento de empresa/bodega y el rol se aplican en servidor, no solo en Vue.

## Interfaz y validación

El detalle de cuba ofrece banda inicial/vigente, episodios abiertos, formulario de aprobación motivada, restauración e historial paginado. Reutiliza el UUID ante reintentos dentro del componente y actualiza la banda del detalle al guardar. El formulario deja explícita la vigencia desde la aprobación. No persiste formularios ni UUID tras cerrar el navegador.

Dieciséis nuevas pruebas SQLite cubren recuperación con límites originales, nuevos episodios, frontera de persistencia, backlog, restauración, idempotencia, conflictos, contrato, aislamiento, roles e integridad transaccional. Dos casos adicionales PostgreSQL comprueban inmutabilidad SQL y concurrencia cuando ese motor esté disponible. Suite completa: **289 aprobadas y 16 omitidas**, 89,62 s, 90 warnings. Build Vite: 4,11 s. Navegador/API/SQLite desechables: ajuste 5–10 a 5–30 °C, restauración y recarga con ambas revisiones y episodio #1 todavía abierto. Valores exclusivamente sintéticos de prueba.

[Evidencia del cierre](evidencias/ajustes-perfil-2026-11-18.md). El ML v2 continúa NO_VALIDADO; no se reentrena ni se recalibra el modelo congelado. Sin cambios de Supabase ni despliegue.
