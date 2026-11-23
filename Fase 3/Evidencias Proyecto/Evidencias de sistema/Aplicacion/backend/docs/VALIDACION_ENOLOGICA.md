# Protocolo propuesto para validar cinética con lotes reales

Estado al 18-11-2026: pendiente de revisión por el equipo enológico. El ensayo
requiere autorización de la bodega para usar las observaciones. El modelo v2
permanece fuera de las decisiones operativas.

## Antes de observar los resultados

La persona responsable de enología define y firma el criterio de parada,
las unidades y el método de referencia, la persistencia mínima y el seguimiento
necesario para descartar un evento. Documenta la regla aplicable a cambios de
receta, tratamientos, final de fermentación, trasiegos y huecos instrumentales.
Cada cambio de criterio recibe versión propia y queda fechado. El equipo fija
la población objetivo, las exclusiones, la anticipación mínima, el presupuesto
de falsas alarmas y los mínimos de cobertura y detección antes de abrir la reserva.

## Registro mínimo por lote

| Registro | Datos necesarios |
| --- | --- |
| Identidad y procedencia | Identificador seudónimo estable de lote y bodega, vendimia, origen físico, inicio y cierre UTC, tanque y cambios de asignación |
| Instrumentación | Dispositivo, calibración y su vigencia, método y unidad de cada canal, hora de observación y de recepción, calidad y períodos sin servicio |
| Referencia independiente | Medición de contraste, método, unidad, hora de toma y hora de disponibilidad, evidencia trazable y motivo si fue anulada |
| Intervenciones | Fecha de aplicación y de registro, tipo, responsable por rol, razón y cambios que afectan la interpretación |
| Adjudicación | Versión de criterio, lote, estado, primera y última hora compatibles con el evento, fin del seguimiento, fuentes usadas, rol revisor y desacuerdos |

El Brix aparente de telemetría y las mediciones de laboratorio conservan sus
métodos y unidades originales. La bodega mantiene la correspondencia entre
identidades reales y seudónimos.

## Etiquetas y revisión

Dos revisores aplican el criterio a las series y contrastes de referencia sin
ver las predicciones. Cada uno clasifica el lote como evento confirmado,
seguimiento completo sin evento, seguimiento censurado o evidencia indeterminada.
Para un evento con comienzo incierto se registra el intervalo compatible. Los
revisores documentan el desacuerdo y la resolución; los casos sin acuerdo
permanecen indeterminados. Se informa su número junto al de lotes excluidos.

## Evaluación prospectiva

1. Congelar versión del extractor, política de abstención, modelo, baselines,
   umbral, horizontes y asignación de lotes a desarrollo y reserva. Mantener un
   lote entero en una partición, incluyendo todos sus dispositivos y ventanas.
   Reservar bodegas o vendimias completas si se va a afirmar generalización a ellas.
2. Reconstruir cada predicción con observaciones disponibles al corte real.
   Reservar el seguimiento posterior solo para adjudicar el desenlace. Marcar
   las ventanas sin seguimiento suficiente y los tratamientos que interrumpen
   la observación. Registrar la razón de cada abstención.
3. Informar denominadores por lote, bodega y escenario de calidad. Comparar
   detección por evento, anticipación y falsas alarmas por lote-día frente a la
   regla y prevalencia. Para el pronóstico a 24 h, comparar error con persistencia
   y extrapolación, junto con cobertura, ancho de banda y disponibilidad.
4. Remuestrear lotes completos para cuantificar incertidumbre y presentar casos
   con deriva, pérdidas y abstención total. Contrastar los resultados con los
   criterios firmados y registrar quién autorizó cada conclusión. Cualquier
   ajuste posterior requiere otra reserva independiente.

La ejecución queda pendiente de lotes físicos, contrastes trazables, acuerdo de
uso de datos y adjudicación firmada. Una eventual aprobación operativa requiere
su propia decisión documentada.
