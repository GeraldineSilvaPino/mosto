# Comparación de curvas y evidencia manual

Bloque local del 17-11-2026. Contrato `curve-comparison-v1`, consulta de solo lectura sobre telemetría v2 canónica y [mediciones manuales](MEDICIONES_MANUALES.md). Constituye una herramienta descriptiva para revisar evidencia del DSS; no es un motor de recomendaciones ni acredita causalidad, equivalencia entre métodos o eficacia de intervenciones.

## API y alineación

`GET /api/procesos/{process_id}/comparacion` requiere autenticación y acceso a cada proceso. Parámetros:

| Parámetro | Contrato |
| --- | --- |
| `reference_id` | Proceso de referencia opcional, autorizado dentro de las bodegas visibles. Repetir el principal no duplica la serie. |
| `variable` | `brix_aparente` (por defecto), `temperatura`, `densidad` o `ph` |
| `hours` | Ventana de 1 a 168 h; por defecto 24 |
| `as_of` | Corte de información con zona horaria; por defecto ahora. Rechaza futuro o fechas anteriores al inicio de cualquiera de los procesos. |

La edad final es la del proceso principal al corte, limitada por su cierre si existe. La edad inicial es `max(0, edad_final - hours)`. Cada proceso se consulta en ese mismo intervalo de **horas desde su propio inicio**, con fechas de calendario independientes. La referencia queda limitada además por su propio cierre y por el corte actual: una referencia más joven puede aportar solo una parte del intervalo o ninguna muestra. No se prolonga la curva para completar edades que aún no ocurrieron.

La respuesta informa inicio de cada proceso, extremos de ventana, fuentes, segmentos, puntos manuales, cantidades/límites y motivos de evidencia incompleta. `current_state` es metadato actual de ciclo de vida, separado explícitamente de la fotografía histórica de observaciones. La hora de cierre también es un dato del proceso actual, no un historial versionado de estados.

## Disponibilidad temporal y calidad

- Telemetría: `observado_en` dentro de la ventana y `recibido_en <= as_of`. Se consulta `MENSAJE_TELEMETRIA`, no se rellenan valores a partir del histórico legacy.
- Manuales: observación dentro de la ventana y `registrado_en <= as_of`. Cada punto conserva método, instrumento, unidad, autor, evidencia y vínculos opcionales.
- Una anulación solo se muestra y afecta al gráfico si `registrado_en <= as_of`. Una anulación posterior no cambia la evidencia que se conocía antes. No se expone su motivo antes de esa fecha.
- El gráfico automático admite valores finitos con calidad `good`; Brix exige calibración. Una muestra inválida/ausente corta la línea, aunque haya una lectura buena anterior. La temperatura se evalúa independientemente del Brix.
- Cambios de dispositivo, calibración u origen, o huecos de más de 900 segundos, abren otro segmento. Observaciones con la misma hora dentro del proceso se consideran ambiguas y se excluyen: no se promedian sensores ni se elige uno arbitrariamente.

Las líneas unen observaciones consecutivas dentro de segmentos válidos; no se generan puntos interpolados, extrapolación, suavizados ni bandas de incertidumbre. La separación temporal entre puntos sigue siendo visible en el eje. Las mediciones manuales se dibujan como triángulos sin unir, agrupados por método e instrumento, y las anuladas se conservan solamente en la tabla.

Temperatura usa °C, Brix aparente °Bx, densidad g/mL y pH su escala declarada. No hay canal automático v2 de densidad/pH: para esas variables se muestra solo evidencia manual. No se transforma densidad en Brix, no se corrige alcohol y no se equipara refractometría con azúcar residual. Aunque compartan unidad, los métodos manuales y la señal del flotador no se fusionan ni generan un error automático de calibración.

## Límites y permisos

Por proceso se devuelven hasta 3.000 mensajes y 300 mediciones manuales, ordenados por observación ascendente e ID. Se informan total, devueltos, exclusiones y truncamiento. Al truncar telemetría se excluye del gráfico la última hora devuelta, porque podrían existir más observaciones ambiguas de esa hora fuera del lote. Un resultado truncado exige reducir la ventana para revisar detalle; no es una serie completa.

La consulta permite lectura a los roles autorizados, incluidos lectores, con filtros por empresa/bodega para ambos procesos y sus datos. Una referencia ajena provoca 404 para toda la consulta. Los GET no escriben bitácora, intervenciones, estado de reglas ni alertas, y llevan `Cache-Control: no-store`.

No requiere migración nueva: se conserva `0007_manual_measurements`, con 28 tablas de dominio y Alembic. El modelo y sus hashes originales no cambian. `estado_ia=NO_VALIDADO`, riesgo null y recomendaciones vacías permanecen explícitos.

## Interfaz

Panel en el detalle de cuba con proceso activo: selección de variable, referencia autorizada, ventanas de 24/48/168 h y corte opcional en hora local. El principal se dibuja en burdeos y la referencia en azul con línea discontinua; cada proceso tiene cantidades, procedencia y tabla desplegable de evidencia manual. Se muestran estados vacíos y truncamiento, y se retira la gráfica al cargar o fallar una consulta. El usuario pulsa «Comparar curvas» para refrescar; no cambia el corte silenciosamente mediante polling.

La lista de referencias usa el endpoint existente de procesos visibles, todavía sin búsqueda/paginación. El panel principal requiere un proceso activo en la cuba; referencias cerradas y consulta API de procesos cerrados están admitidas. La navegación UI a un proceso histórico como principal, comparación de más de dos procesos, exportación y representación tabular completa de puntos automáticos siguen pendientes. No se afirma accesibilidad integral ni validación móvil/carga.

## Verificación

`tests/test_curve_comparison.py`: 16 pruebas que cubren fuga temporal por recepción/registro, anulaciones históricas, calidad por canal, huecos, calibraciones, ambigüedad entre dispositivos, límites, edad frente a calendario, procesos cerrados, variables solo manuales, permisos y ausencia de escrituras.

Build Vue y navegador con API/SQLite nuevos: dos trayectorias sintéticas, 97 muestras visibles por proceso y una medición manual por proceso a las siete horas, con métodos distintos y fechas de calendario distintas. Al consultar antes de la recepción/registro, ambos historiales quedan vacíos; al restaurar el corte actual vuelven a mostrarse. Véanse los [resultados de comparación de curvas](evidencias/comparacion-curvas-2026-11-17.md).

Pendiente: overrides explícitos de perfil, validación PostgreSQL, recomendaciones DSS trazables con criterios revisados por enología y evaluación real de utilidad. La coincidencia de edad no controla cepa, perfil, temperatura, método ni intervención; no debe interpretarse como un ensayo causal pareado.
# Exportación de la consulta (18-11-2026)

El botón «Exportar evidencia consultada (JSON)» descarga la respuesta actualmente
mostrada dentro de un sobre `mosto-curve-evidence-v1`, con fecha de exportación y
alcance explícito. Preserva telemetría graficable, manuales incluidas las anuladas,
corte, unidades, métodos, procedencia y advertencias/límites. No realiza una nueva
consulta ni incluye puntos excluidos o fuera del límite. Los filtros editados sin
consultar no alteran el archivo. No constituye exportación CSV ni historial completo.

Validación: build Vite y descarga Edge con API simulada, comparación exacta del
contenido, incluida evidencia multilínea y resultados truncados. Sin cambios en
API, autorización o base de datos para esta función.
