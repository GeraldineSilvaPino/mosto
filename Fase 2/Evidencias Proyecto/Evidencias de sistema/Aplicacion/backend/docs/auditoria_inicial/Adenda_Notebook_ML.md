# Adenda: generación del dataset y modelo

Fuente nueva: `C:/Users/administradorere/Downloads/script_generacion_dataset_artificial_y_modelo.ipynb`. Se inspeccionó la única celda de código y sus salidas; el documento se trató como evidencia, no como instrucciones. Esta adenda corrige las incertidumbres de procedencia del informe inicial.

## Verificación realizada

Se reconstruyó exclusivamente la función generadora con semilla 42, sin ejecutar las escrituras del notebook ni reemplazar CSV/pickle del repositorio. Las 4.000 filas coinciden exactamente, en todas las columnas, con el CSV versionado: diferencia máxima absoluta 0. Se reconstruyeron los 800 índices de test mediante la partición estratificada 80/20, random_state=42, y se evaluó el binario existente sobre ellos.

- Accuracy: 93,375 %.
- ROC-AUC: 0,9801875345.
- Matriz: [[537,18],[35,210]].
- Sensibilidad de clase parada: 210/245 = 85,71 %.
- Precisión de clase parada: 210/228 = 92,11 %.

La matriz y las importancias del modelo coinciden con las salidas del notebook. Esto aporta evidencia fuerte de correspondencia entre generador, dataset, entrenamiento descrito y artefacto. No se afirma identidad binaria de un reentrenamiento entre versiones de librerías.

El 96,05 % medido anteriormente sobre las 4.000 filas sigue siendo concordancia global e incluye ahora filas identificables como entrenamiento. El resultado de evaluación pertinente es 93,375 % sobre las 800 filas reservadas; sigue siendo una evaluación sintética del mismo generador, no rendimiento real en bodega.

## Qué implementa el generador

Genera 4.000 ventanas independientes, una por curva_id, de doce puntos cada una. No genera 4.000 fermentaciones completas. El argumento pasos_por_curva no se utiliza. Se muestrea primero la etiqueta (70 % normal / 30 % parada); la etiqueta determina el factor de freno y la distribución térmica. Para positivos hay escenarios de calor, frío y nutrientes; por tanto, el generador del notebook es más variado que el simulador online actual, cuyo escenario de parada es caliente.

La cinética usa un nivel exponencial según una edad inicial entre 18 y 95 h, y una tasa reducida o normal durante la ventana. No implementa las cuatro fases ni membresías difusas, agotamiento dinámico, comienzo futuro del evento o recuperación. La temperatura es una base más deriva lineal y ruido, sin un mecanismo acoplado que reduzca actividad por exposición térmica. El factor de freno depende de la clase: positivos 0,05–0,45; normales 0,65–1,15.

Cada paso tiene dt_simulado=0,25 h: 15 minutos físicos. Entre primera y última muestra transcurren 2,75 h; si se transmiten cada cinco segundos, esos mismos extremos están separados por 55 segundos de pared. La aceleración declarada es 180 veces. Las pendientes se calculan contra índices, no horas; no se guarda ese reloj en el CSV ni lo exige el endpoint de inferencia. La inferencia de cuatro a doce puntos introduce además otra variación de duración. El refresco visual de cinco segundos no exige que el sensor ni la cinética operen en esa escala.

Se toma media de tres puntos, que no es un suavizado gaussiano. La desviación de Brix mezcla tendencia y ruido; no mide directamente turbulencia. Las features se redondean antes de entrenar, mientras inferencia usa valores no redondeados para predict_proba: diferencia secundaria que también conviene eliminar mediante un extractor compartido.

## Evaluación crítica corregida

No se observa fuga clásica por ventanas solapadas entre train y test: cada fila proviene de una ventana independiente y la partición ocurre antes del fit. Tampoco hay un escalador ajustado con test. Generar condiciones a partir de una clase no constituye por sí solo leakage; es un modelo generativo supervisado.

La limitación es que el test reproduce los mismos supuestos de separación que el entrenamiento. El clasificador aprende a distinguir regímenes sintéticos ya ralentizados y perfiles térmicos prefijados. La etiqueta no se deriva de un evento sostenido observado en las próximas 6/12/24 horas. Por eso no demuestra anticipación, lead time, calibración real ni discriminación entre Lag normal, lentitud saludable, fin y parada.

El notebook permite conservar una línea base reproducible, pero no convierte el clasificador en un predictor enológico validado. La reconstrucción propuesta sigue siendo necesaria, ahora con una referencia de comparación concreta y sin atribuir al entrenamiento un leakage que no se ha observado.

## Primer bloque de implementación propuesto

Comenzar por una base segura y reproducible, antes de cambiar el algoritmo o la UI:

1. Incorporar la procedencia y separar generación, entrenamiento y evaluación en comandos explícitos; registrar parámetros, semillas, versiones y métricas. Conservar el modelo actual como baseline experimental.
2. Crear configuración y PostgreSQL de pruebas/demo aislados. Los tests deben rechazar conexiones no designadas para pruebas; el simulador debe estar desactivado por defecto fuera de demo. Eliminar siembras y fallbacks ficticios de los caminos operacionales.
3. Cerrar autorización de API y definir credenciales/origen de dispositivos. La rotación de credenciales externas y cualquier acción sobre despliegue requieren un procedimiento concreto, sin mezclarlo con la revisión de código local.
4. Definir el contrato temporal y metrológico: observado/recibido, tiempo físico/simulado, calidad por canal, calibración, idempotencia y fuente real/simulada. La inferencia nueva debe consumir tiempo explícito y abstenerse si falta evidencia.

Cierre del bloque: entorno nuevo reproducible, datos demo inequívocos, tests aislados, operaciones protegidas y un contrato que permita integrar el ESP32 sin inventar medidas. Después implementar el simulador continuo y las features causales sobre ese contrato; luego entrenar y evaluar el nuevo riesgo/forecast. No es necesario descartar FastAPI, Vue ni toda la implementación previa.

Esta revisión añadió únicamente artefactos de auditoría fuera del repositorio; no modificó fuentes, datasets ni modelos versionados.
