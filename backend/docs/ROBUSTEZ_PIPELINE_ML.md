# Ensayos offline de sensores y comunicaciones

Contrato `sensor-stress-v1`, 17-11-2026. Evalúa el modelo experimental congelado; no modifica ingesta, reglas operacionales, base de datos ni simulador HTTP. No habilita ML v2.

## Diseño del ensayo

`ml.robustness` genera trayectorias nuevas de los cinco escenarios biológicos de `mosto-phases-1`. Sus semillas e identificadores son únicos y distintos de **todos** los procesos del experimento de referencia, incluidos calibration, validation y test. La semilla maestra predeterminada es 20261117; cuatro trayectorias por escenario, 240 h y ventanas cada 3 h. Son 20 trayectorias independientes con ocho versiones pareadas, no 160 fermentaciones independientes.

La condición inicial, ambiente e inicio de perturbación biológica siguen las distribuciones del generador original. El inicio del fallo instrumental se sortea entre 48 y 96 h, independientemente del evento latente y del inicio de perturbación biológica. Las recetas se fijan en código antes de examinar los resultados. No se reclaman mecanismos biológicos, bodegas o sensores reales reservados.

| Condición | Perturbación de observación |
| --- | --- |
| `clean` | Referencia sin alteraciones |
| `brix_missing` | Brix ausente y calidad `missing` durante 12 h; temperatura conservada |
| `temperature_missing` | Temperatura ausente durante 12 h; Brix conservado |
| `brix_frozen_unflagged` | Último Brix anterior al fallo repetido durante 24 h; calidad declarada buena |
| `brix_drift_unflagged` | Deriva adicional de +0,08 °Bx/h durante 48 h; calidad declarada buena; desaparece al terminar |
| `communication_loss` | Pérdida definitiva de todos los mensajes de 12 h |
| `delivery_backlog` | Mensajes de 12 h recibidos juntos cinco minutos después del fin del corte; se preserva su observación original |
| `latency_2h` | Todas las recepciones retrasadas dos horas |

La retención y deriva sin bandera son ataques a la validez de la medición, no nuevas causas de parada. Sus parámetros son condiciones de estrés arbitrarias y explícitas, no tasas de fallo estimadas de un dispositivo. Los cortes se aplican una vez por trayectoria; no representan una tasa anual de disponibilidad. La entrega acumulada es un ensayo de disponibilidad temporal del extractor, no una prueba de carga HTTP/outbox.

La trayectoria biológica, etiqueta de parada sintética y objetivo de forecast permanecen idénticos en las ocho versiones. El forecast se contrasta con la observación original sin corrupción a +24 h, no con el sensor averiado ni con azúcar residual. El extractor compartido filtra observación y recepción; mensajes que aún no han llegado no participan. No se cambian umbrales ni mecanismos de abstención después de observar el test.

## Evaluación e interpretación

Se comprueban hashes de dataset/modelo, contratos de features/target, código del generador/extractor, recetas de fallos y consistencia entre las ventanas pareadas. La evaluación carga únicamente el artefacto joblib local de confianza tras estas comprobaciones; los hashes no lo hacen seguro frente a un archivo malicioso. Se conserva el modelo, escalado, calibración y umbral originales, sin llamar a `fit` ni seleccionar hiperparámetros.

El informe separa:

- Cobertura y abstenciones, razones y denominadores de ventanas elegibles/etiquetadas. La ausencia de puntuación no equivale a probabilidad cero.
- Métricas de riesgo **condicionadas a las ventanas puntuadas**, con la misma definición de falsas ventanas positivas por día elegible del pipeline original. No son episodios deduplicados.
- Detección sobre **todos** los eventos latentes de las trayectorias, también los que se quedan sin ventanas de aviso elegibles. Se informa oportunidad de aviso, oportunidad evaluable y procesos no detectados. Así la abstención no elimina fallos del denominador.
- MAE/RMSE de Ridge y MAE de persistencia sobre ventanas puntuadas; `null` cuando no hay ninguna. Comparación pareada contra limpio sobre las mismas ventanas: cambio de probabilidad, decisiones que cambian y errores de forecast comunes. El número de ventanas comunes debe acompañar la comparación.
- Desglose por escenario y proceso. Las ventanas expuestas incluyen el fallo y su huella en los 24 h de historia siguientes, con frontera final conservadora inclusiva; el resto permite comparar el proceso completo. La latencia constante expone todas las ventanas.

El informe original de este ensayo contiene métricas descriptivas. Las ventanas se solapan y las ocho versiones comparten trayectoria. No se calculan intervalos de confianza por filas ni se considera la repetición determinista como nueva evidencia. La extensión posterior de [incertidumbre por trayectoria](INCERTIDUMBRE_ML.md) agrega bootstrap e intervalos de forecast en artefactos separados, conservando estos resultados. Tampoco se deduce que cualquier mejora de un indicador agregado constituya una mejora del modelo: puede cambiar el subconjunto evaluado o producirse una cancelación accidental de errores.

Un sensor retenido o con deriva puede conservar cobertura y calidad declarada; este ensayo registra el límite del detector actual. No se introduce una corrección de calidad entrenada sobre estos resultados ni se declara una causa nutricional. Si se desarrolla otra política, requerirá datos de desarrollo y otra evaluación reservada.

## Reproducción

Desde `C:/mosto/backend`, con los artefactos locales de referencia del contrato causal:

```powershell
.\venv\Scripts\python.exe -m ml.robustness generate --reference-dataset-dir artifacts/causal-v1-final-dataset --model-dir artifacts/causal-v1-final-model --output-dir artifacts/robustness-v1-20261117-dataset
.\venv\Scripts\python.exe -m ml.robustness evaluate --dataset-dir artifacts/robustness-v1-20261117-dataset --reference-dataset-dir artifacts/causal-v1-final-dataset --model-dir artifacts/causal-v1-final-model --output-dir artifacts/robustness-v1-20261117-evaluation
```

Si faltan los artefactos de referencia, regenerarlos con los comandos de [Cinética y pipeline](CINETICA_Y_PIPELINE_ML.md), con su código y versiones correspondientes. Las salidas deben ser directorios nuevos: no se sobrescriben. Para repetir, utilizar otro directorio y comparar hashes. `manifest.json` guarda recetas completas, identidad del modelo congelado, versiones y huellas; `windows.jsonl` incluye features, targets, diagnósticos de calidad y procedencia. `evaluation.json` y `predictions.json` permiten revisar métricas y cada salida. Ningún comando importa configuración/base de datos ni envía HTTP.

## Validación

Pruebas de separación de semillas, reproducción idéntica, canal ausente independiente, corte y retorno, frontera de recepción y entrega acumulada, latencia total, retención/deriva sin bandera, invariancia frente a datos futuros, denominadores cuando hay abstención total, ausencia de entrenamiento y preservación de artefactos. Se rechazan hashes alterados, pares incompletos, semillas reutilizadas, targets alterados entre variantes y modelos/umbrales incompatibles.

Resultados ejecutados y huellas: [evidencia del ensayo](evidencias/robustez-ml-2026-11-17.md). ML operacional conserva `NO_VALIDADO` y valores null. Incertidumbre e intervalos experimentales se añadieron después en el documento enlazado. Siguen pendientes fallos programables en la flota HTTP, cambios de dominio biológico y validación real independiente de modelos/bandas.
