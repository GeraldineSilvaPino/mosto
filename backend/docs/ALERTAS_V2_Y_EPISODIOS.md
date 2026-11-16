# Episodios térmicos, auditoría y bitácora

Implementación local, 15-11-2026. La ingesta HTTP v2 genera episodios persistentes con evidencia, independientes del clasificador ML experimental. Se aplica tanto a dispositivos físicos aprovisionados como a simulados. No certifica el hardware ni predice paradas de fermentación. Supabase no ha sido modificado.

## Regla implementada

`thermal-v2-1` compara exclusivamente la temperatura con el perfil del proceso. El primer mensaje que encuentra un perfil con ambos límites congela su configuración en `ESTADO_REGLA`, por proceso y código (`temperatura_alta` / `temperatura_baja`). Cambiar posteriormente el perfil no reinterpreta ese proceso. Un perfil sin límites no genera umbrales predeterminados. El versionado completo de perfiles y su gestión visual siguen pendientes.

- Entrada: temperatura estrictamente fuera del rango durante al menos 10 minutos observados, sin un intervalo entre muestras superior a 15 minutos.
- Recuperación: 10 minutos dentro del límite corregido por histéresis. Margen de 0,5 °C, limitado a un cuarto de la amplitud del rango.
- Calidad: solo temperatura `good`; un canal Brix inválido no invalida una temperatura utilizable. Temperatura ausente o inválida reinicia las ventanas y deja una condición abierta como `desconocida`.
- Huecos mayores de 15 minutos reinician la confirmación/recuperación; el silencio por sí solo nunca acredita recuperación. No hay todavía un watchdog que genere eventos mientras no lleguen mensajes.
- La continuidad entre muestras es una aproximación operativa a la cadencia de cinco minutos, no una observación física continua.
- Severidad según desviación absoluta del límite: `media` por debajo de 2 °C; `alta` desde 2 °C; `critica` desde 5 °C. Una condición abierta puede escalar y registra el evento, sin reemplazar la evidencia inicial. Estos valores son reglas iniciales de producto, no umbrales validados por el paper.

No se infiere agotamiento de nutrientes, estrés de levadura, fase biológica ni causa de una parada a partir de esta regla. Tales hipótesis necesitan más evidencia y validación.

## Dos ciclos de vida

| Dimensión | Estados | Qué acredita |
| --- | --- | --- |
| Condición observada | `activa`, `desconocida`, `recuperada`, `cerrada_proceso` | Resultado de la regla sobre la telemetría disponible o cierre administrativo del proceso |
| Gestión humana | `pendiente`, `atendida`, `resuelta` | Atención o revisión registrada por un usuario autenticado |

Resolver humanamente no cierra la condición y no provoca alertas repetidas mientras persista el mismo desvío. Recuperar la temperatura no resuelve el trabajo humano. Después de recuperación, una nueva condición sostenida crea otro episodio. Finalizar un proceso marca `cerrada_proceso`, sin declarar recuperación ni resolución humana.

El registro original conserva `inicio_condicion`, observación de confirmación, fecha de recepción/disponibilidad, mensaje de evidencia, valor medido, límites y versión. `ultima_observacion` indica el último dato evaluado, no la última consulta del usuario. Las fichas advierten cuando una condición abierta no tiene observaciones recientes.

## Transacciones, concurrencia y fuentes

El mensaje canónico, su lectura compatible, la regla, el episodio, la auditoría y la recepción del dispositivo se confirman en una misma transacción. Si falla la auditoría, se revierte también la lectura; el mensaje puede reintentarse. La ingesta serializa por cuba y la unicidad parcial de episodios abiertos protege `(proceso, código)` sin depender del estado humano.

Cada regla mantiene una marca temporal. Mensajes anteriores o iguales a ella se conservan en telemetría, pero no reconstruyen retroactivamente episodios ni acciones humanas. Un backfill reproducible debe enviarse en orden temporal. No se ejecuta automáticamente una reconstrucción del histórico al aplicar la migración.

La API rechaza mezclar mensajes canónicos físicos y simulados dentro de un proceso, incluso tras cambiar de dispositivo. Este control se realiza bajo el bloqueo de ingesta; no es una nueva restricción SQL para escrituras externas. Las lecturas legacy anteriores no se reclasifican.

Atención y resolución bloquean la fila de alerta. Repetir la misma acción conserva fecha y autor originales; una nota distinta en una acción ya registrada devuelve 409 y debe añadirse como nueva intervención. Un `usuario_id` enviado por el cliente no cambia el actor autenticado. Las resoluciones v2 exigen al menos diez caracteres; las notas de acción admiten hasta 4000.

`AUDITORIA_ALERTA` guarda creación, escalamiento, cambios de condición, atención, resolución y cierre de proceso. En PostgreSQL los eventos no admiten UPDATE/DELETE; también se comprueba correspondencia de proceso, evidencia y empresa del actor. Los scopes de API protegen lectura y escritura según empresa/bodega. SQLite no certifica esas guardas ni la concurrencia de PostgreSQL.

## Bitácora y métricas

- `POST /api/bitacora` acepta `alerta_id` y/o `fermentacion_id`. El vínculo debe corresponder al mismo proceso/cuba autorizado, aunque el proceso esté cerrado.
- Resolver un episodio v2 crea una nota vinculada dentro de la misma transacción, una sola vez. Añadir una nota o medición manual no resuelve automáticamente la alerta. Las mediciones de contraste son declaraciones del operador, no calibraciones certificadas.
- `GET /api/alertas/{id}/eventos` devuelve la auditoría persistida; `GET /api/bitacora?alerta_id=...` devuelve las intervenciones vinculadas.
- MTTR = promedio de `fecha_resolucion - timestamp` únicamente entre alertas resueltas con ambas fechas válidas y duración no negativa. `timestamp` v2 es disponibilidad en plataforma, no el inicio histórico de la desviación. Sin muestras válidas, el resultado es `null`, mostrado como N/D.
- `muestras_mttr` informa el denominador; `resueltas_sin_tiempos_validos` informa las exclusiones. `condiciones_sin_recuperacion` cuenta condiciones abiertas aunque su gestión esté resuelta.
- Listado, métricas y CSV aceptan estado, severidad, tipo, origen y cuba. La interfaz de auditoría aplica únicamente la cuba a sus métricas globales y declara este alcance. Las tablas muestran hasta 500 registros recientes y filtros locales; no representan paginación ilimitada del histórico.

El MTTR mide gestión de incidencias, no duración del fallo físico ni eficacia de una intervención. Los orígenes pueden separarse mediante el filtro de API; mezclar datos sintéticos y reales en un indicador no valida el desempeño de una bodega real.

## Cambios en Vue

Las acciones de alertas llaman siempre al servidor, incluidos IDs ≥1000. Se eliminaron la generación de alertas solo en memoria y el falso control de anulación del sensor. Atención/resolución usan el actor, fecha y estado devueltos por la API. Notas y contraste manual se guardan en bitácora. `EpisodeEvidence.vue` presenta configuración aplicada, procedencia, condición separada de gestión y trazabilidad persistida en ambas fichas.

La lista vacía ya no afirma que la fermentación esté sana. La auditoría no inventa un operador, una estabilización térmica, una variedad, un lote ni una duración mínima de un minuto. Los errores de consulta se muestran; las acciones fallidas no anuncian éxito.

## Migración y comprobaciones

`0004_alert_episodes` añade `ESTADO_REGLA` y `AUDITORIA_ALERTA`, campos de episodio/resolución y enlace de bitácora. Total: 23 tablas de dominio más `alembic_version`. Mantiene los datos y contratos legacy; no completa retrospectivamente tiempos o autores ausentes.

Las pruebas cubren persistencia, histéresis, huecos, calidad parcial, mensajes atrasados/repetidos, perfil congelado, escalamiento, falta de perfil, rollback, cierre de proceso, acciones idempotentes, vínculos históricos, aislamiento, origen y MTTR. PostgreSQL añade confirmación/resolución concurrentes, unicidad e inmutabilidad de auditoría. La evidencia consolidada y el estado de la prueba de navegador figuran en [Estado del plan](ESTADO_PLAN_MAESTRO.md).

## Pendientes del bloque funcional más amplio

Reglas causales de cinética de Brix y cobertura; watchdog de silencio; diagnóstico visible de reglas sin perfil; perfiles versionados completos; paginación y filtros globales de UI; intervenciones estructuradas con seguimiento; métricas de recuperación y respuesta; recomendaciones DSS revisables; ML con horizonte futuro validado. Esta entrega no cierra esos elementos ni habilita control de actuadores.
