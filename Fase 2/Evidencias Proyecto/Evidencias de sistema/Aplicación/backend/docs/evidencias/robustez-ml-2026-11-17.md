# Resultado del ensayo de robustez — 17-11-2026

Ejecutado localmente en Windows/Python 3.11.4. Contrato [sensor-stress-v1](../ROBUSTEZ_PIPELINE_ML.md). Sin Supabase, migración, despliegue ni promoción del modelo.

## Experimento congelado

- Referencia: 100 trayectorias originales del pipeline causal; se conservó el artefacto entrenado y el umbral `0.2188870880231169`.
- Nuevos datos: semilla maestra 20261117, 20 trayectorias de 240 h, cuatro por escenario, semillas distintas de las 100 originales. Ocho condiciones pareadas, 11.680 ventanas, 1.460 por condición.
- Hay 12 eventos latentes: cuatro de choque frío, cuatro de estrés térmico y cuatro de agotamiento simulado. Healthy/slow no tienen eventos según la etiqueta experimental.
- Modelo SHA-256: `3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3`.
- Dataset de referencia SHA-256: `29a9747d4e39a995ff44fe49a53e244d029aa489d0e8c0cf6479e76ea1dc1039`.
- Dataset de estrés SHA-256: `5ad5f5929cca9a8a6305d26c240a6ce9eb532e7d78eec53f9ede4dfcddcd545d`.
- Código del ensayo SHA-256: `06b76fce9fdb55c3c9592418b22e896e40c1f998b21f623692533afa16d0ede9`.

Las recetas, versiones y huellas se conservan en [manifiesto](robustez-ml-manifest.json). El desglose completo por condición/escenario/proceso está en [evaluación](robustez-ml-evaluation.json). Los archivos grandes `windows.jsonl` y `predictions.json` permanecen en los directorios locales indicados en los comandos de reproducción; no se reemplaza ningún CSV/pickle legacy.

## Resultados

| Condición | Abstención de features | Eventos detectados / 12 | Ventanas falsas positivas | MAE Ridge a 24 h (°Bx) |
| --- | ---: | ---: | ---: | ---: |
| Limpia | 0,00 % | 6 / 12 | 16 | 0,3061 |
| Brix ausente 12 h | 16,44 % | 1 / 12 | 12 | 0,2807 |
| Temperatura ausente 12 h | 16,44 % | 1 / 12 | 12 | 0,2807 |
| Brix retenido sin bandera 24 h | 0,00 % | 6 / 12 | 40 | 0,7505 |
| Deriva sin bandera 48 h | 0,00 % | 6 / 12 | 31 | 1,3101 |
| Pérdida de mensajes 12 h | 15,96 % | 1 / 12 | 13 | 0,2806 |
| Entrega acumulada tras 12 h | 5,48 % | 4 / 12 | 13 | 0,2972 |
| Latencia constante 2 h | 100,00 % | 0 / 12 | N/D | N/D |

Las falsas positivas son ventanas, no incidentes; sus denominadores varían cuando hay abstención. La condición limpia puntúa 808 ventanas de riesgo. Las dos condiciones de canal ausente puntúan 636; la pérdida 641 y la entrega acumulada 740. La latencia total no produce puntuaciones: no se registra una falsa certeza de riesgo cero.

La condición limpia detecta 2/4 eventos de choque frío, 4/4 de estrés térmico y 0/4 de agotamiento simulado. Se repite el límite del experimento anterior frente a agotamiento, sin reinterpretarlo como diagnóstico de nutrientes.

La caída de MAE a 0,2807 con canal ausente **no es una mejora del modelo**: sobre las mismas ventanas supervivientes, el forecast limpio tiene exactamente el mismo MAE. Cinco de los doce eventos se quedan sin ninguna ventana de aviso evaluable; solo uno se detecta. Las métricas condicionales por sí solas ocultarían esta pérdida.

El sensor retenido y la deriva no activan las guardas actuales de cobertura/calidad: siguen declarando datos buenos. El sensor retenido eleva las falsas ventanas positivas de 16 a 40 y cambia 33 decisiones de alarma respecto del limpio; la deriva eleva las falsas positivas a 31 y cambia 26 decisiones. En las ventanas expuestas, el MAE llega a 2,1316 y 2,9813 °Bx, respectivamente. Es un límite observado del sistema actual, no una prueba superada de robustez.

La entrega acumulada recupera elegibilidad cuando los datos efectivamente llegan. No mejora retrospectivamente el aviso que no podía emitirse antes de la recepción. El extractor y el umbral no se alteraron a partir de estos resultados.

## Comprobaciones y alcance del cierre

- Ocho pruebas nuevas de fallos, causalidad, pares, separación de semillas, checksum, inmutabilidad del modelo y no entrenamiento. La generación pequeña repetida produce hashes idénticos de datos y manifiesto.
- Suite completa: **205 aprobadas, 11 omitidas**, 90 warnings, 161,34 s, SQLite temporal. Evidencia: [salida de pytest](robustness-tests-final.txt). PostgreSQL no reejecutado; las omisiones dependen de ese motor.
- Este bloque solo añade código offline y documentación: no hubo cambios de UI ni nueva prueba de navegador/build. La evidencia frontend anterior permanece identificada en el estado maestro.
- Sin intervalos de confianza ni validación poblacional: 20 trayectorias del mismo simulador y versiones correlacionadas. Falta incertidumbre por trayectoria, intervalos de forecast, escenarios biológicos externos, fallos programables en la flota HTTP y validación física independiente.
- Los resultados no permiten habilitar ML v2. Se conservan `NO_VALIDADO`, riesgo y forecast null. Siguiente bloque: incertidumbre de evaluación por trayectoria e intervalos predictivos calibrados con la partición de calibración, sin utilizar estos resultados para ajustar el modelo.
