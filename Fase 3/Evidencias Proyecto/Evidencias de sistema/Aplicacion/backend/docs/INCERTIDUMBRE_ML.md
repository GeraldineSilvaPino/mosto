# Incertidumbre por trayectoria e intervalos de forecast

Contrato `trajectory-uncertainty-v1`, 17-11-2026. Extensión offline del modelo causal congelado. No modifica API, UI, simulador, Supabase ni valores ML operacionales.

## Banda de forecast: calibración separada

La banda utiliza exclusivamente la partición `calibration` del dataset original. El forecaster Ridge sigue ajustado únicamente con train. La calibración de probabilidad del clasificador, el escalado, sus pesos y su umbral permanecen intactos; la nueva banda es un artefacto JSON separado.

Para cada proceso de calibración se calcula el máximo error absoluto del forecast a 24 h entre todas sus ventanas elegibles con target disponible. Cada proceso aporta **un** score, aunque contenga muchas ventanas solapadas. Con `n` scores y nivel nominal `1−alpha`, se selecciona el estadístico de orden `ceil((n+1)*(1−alpha))`. La banda es `[forecast−q, forecast+q]`, sin recorte a cero ni al rango observado de Brix. Brix aparente negativo puede ser admisible y un recorte alteraría la cobertura.

Esta es una adaptación experimental a scores de trayectorias de la construcción split conformal de [Angelopoulos y Bates](https://arxiv.org/abs/2107.07511). Su garantía teórica necesita intercambiabilidad de las unidades de calibración y evaluación; **no se afirma esa garantía en este experimento**: se usa una mezcla sintética estratificada de mecanismos, con pocas trayectorias, y las fallas introducen cambios de distribución. No se garantiza cobertura por escenario, por horizonte distinto de 24 h, ni en vino real.

La unidad de cobertura nominal elegida es la trayectoria completa de **forecasts emitidos** sobre la rejilla del experimento, no cada fila independiente, una curva continua ni una banda para todo tiempo futuro. En el dataset de 240 h hay 65 forecasts por proceso (cortes de 24 a 216 h, cada 3 h). El target conserva la observación original de Brix aparente a +24 h, no azúcar residual ni el sensor corrompido.

Si el rango solicitado excede `n`, no se sustituye por el mayor error disponible: `radius_brix=null` y estado `insufficient_calibration_trajectories`. Corresponde a no disponer de una banda finita justificable con esa regla, no a una banda de ancho cero. Si un proceso de calibración carece de targets elegibles, el comando rechaza el conjunto en lugar de eliminarlo silenciosamente. Los defaults se fijaron antes de evaluar: alpha 0,10; 2.000 réplicas bootstrap; semilla 20261118.

## Incertidumbre de métricas

El bootstrap remuestrea procesos completos con reemplazo, dentro de cada escenario, conservando el número original de procesos por estrato. Esto mantiene la estructura temporal interna y la composición experimental. Se mantiene la misma selección de procesos en todas las condiciones de fallas para calcular diferencias pareadas; un proceso seleccionado dos veces cuenta dos veces, también en el denominador de eventos. La unidad nunca es una ventana suelta ni una variante como si fuera otro proceso.

El principio de conservar grupos completos corresponde al cluster bootstrap descrito en [Loy y Korobova, The R Journal](https://journal.r-project.org/articles/RJ-2023-015/). Aquí se aplica a estadísticas de evaluación mediante sumas por proceso, no a un modelo de efectos mixtos. Se publican percentiles 2,5 y 97,5 como rangos aproximados del 95 %, condicionados al modelo, a la banda calibrada y a la mezcla de escenarios observada. No incluyen incertidumbre del entrenamiento, del propio cuantil de calibración, de la mezcla de escenarios ni de la transferencia a bodegas reales.

Métricas incluidas: abstención, recall sobre todos los eventos (incluso sin aviso elegible), Brier, falsas ventanas positivas por día elegible, MAE de forecast, disponibilidad de intervalos, cobertura por ventana, ancho medio y cobertura por proceso. Las métricas de ventanas se agregan mediante sus numeradores y denominadores; no se promedian ratios por proceso con ponderaciones implícitas.

La cobertura por proceso se publica de dos maneras:

- `trajectory_emitted_coverage`: todos los intervalos **emitidos** cubren sus targets; excluye procesos sin ningún intervalo. Debe leerse junto a disponibilidad.
- `trajectory_all_targets_served_and_covered`: todas las ventanas con target disponible recibieron un intervalo y quedaron cubiertas. Las abstenciones cuentan como falta de servicio, aunque no se consideren errores de predicción.

Así un proceso con muchos huecos no aparenta cobertura operacional completa. Sin intervalos, cobertura condicional es null y disponibilidad es cero. Si una métrica no está definida en alguna réplica, se conservan los recuentos de réplicas definidas y se omiten sus límites. Con menos de dos procesos en un estrato no se presentan límites bootstrap. Los rangos con extremos iguales llevan `degenerate=true`: un remuestreo de aciertos idénticos no puede inventar fallos no observados, por lo que `[1,1]` no demuestra certeza poblacional. Con solo tres o cuatro procesos por escenario, incluso rangos no degenerados son aproximaciones exploratorias.

## Artefactos, integridad y comandos

Desde `C:/mosto/backend`, con artefactos locales de confianza y directorios nuevos:

```powershell
.\venv\Scripts\python.exe -m ml.uncertainty calibrate --reference-dataset-dir artifacts/causal-v1-final-dataset --model-dir artifacts/causal-v1-final-model --output-dir artifacts/uncertainty-v1-20261117-intervals
.\venv\Scripts\python.exe -m ml.uncertainty evaluate --reference-dataset-dir artifacts/causal-v1-final-dataset --model-dir artifacts/causal-v1-final-model --interval-dir artifacts/uncertainty-v1-20261117-intervals --stress-dataset-dir artifacts/robustness-v1-20261117-dataset --output-dir artifacts/uncertainty-v1-20261117-evaluation
```

`calibrate` produce `intervals.json` con scores por proceso, rango, radio, inputs de calibración, contratos y hashes. `evaluate` reconstruye la calibración con esa misma partición para rechazar alteraciones del radio o sus entradas. Requiere identidad coherente entre manifiesto, filas y particiones del artefacto original; verifica los hashes del modelo antes y después. No llama a fit, no selecciona un nivel o umbral a partir del resultado, no importa base de datos y no sobrescribe salidas. Joblib se carga solo después de verificar la referencia local de confianza; un checksum no convierte un pickle malicioso en seguro.

`evaluation.json` conserva estadísticas por proceso/escenario/condición, réplicas definidas y rangos de diferencias pareadas. `forecast_intervals.json` registra cada forecast puntuado, target, extremos y cobertura; las ventanas sin forecast no figuran como predicciones, pero permanecen en los denominadores de disponibilidad del informe. El radio depende solo de calibración: su huella de inputs no contiene filas de train, validation o test. La huella del dataset completo se conserva aparte como procedencia.

La evaluación de test original y stress ya vistos es **retrospectiva**, no una nueva evaluación ciega. Los resultados no se usarán para estrechar la banda, elegir otro alpha ni ajustar una mitigación sobre la misma reserva. Las pruebas comprueban invariancia al contaminar splits ajenos a calibración, reintentos reproducibles, multiplicidad de clusters y preservación del modelo.

## Alcance del cierre

Implementados intervalos experimentales e incertidumbre de métricas por trayectoria; no se acredita utilidad enológica de su ancho ni cobertura operacional. [Resultados ejecutados y evidencia](evidencias/incertidumbre-ml-2026-11-17.md). Permanecen `NO_VALIDADO`, riesgo y forecast null en v2.

Siguiente trabajo local del plan: fallas programables y recuperación del simulador HTTP/outbox, sin inferir recuperación biológica a partir de restaurar comunicaciones. Sigue pendiente una evaluación externa independiente antes de habilitar modelos o bandas en operación.
