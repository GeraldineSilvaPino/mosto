# Ficha del modelo cinético experimental de MOSTO

**Estado de uso: NO_VALIDADO.** El pipeline se ejecuta fuera de la API para
comparar métodos sobre fermentaciones simuladas. Sus salidas son una puntuación
experimental de evento a 12 h y un pronóstico de Brix aparente a 24 h.
El uso en lotes físicos y las decisiones sobre tratamientos requieren evidencia
independiente y revisión enológica.

## Datos y método

La referencia contiene 100 trayectorias de 240 h del simulador mosto-phases-1,
con cinco escenarios y 7.300 ventanas. La unidad de partición es la trayectoria.
Se usan 55 para entrenamiento, 15 para calibración, 15 para selección de umbral
y 15 para evaluación. La etiqueta proviene del evento latente del generador.
Las entradas se extraen de las últimas 24 h de temperatura y Brix aparente
disponibles al corte. El extractor registra calidad, cobertura y motivos de
abstención. La logística estandarizada se calibra sobre calibración; Ridge
(alpha 10) estima el valor futuro. Las comparaciones incluyen prevalencia,
regla cinética, persistencia y extrapolación lineal.

## Réplica del 18-11-2026

Sobre Windows y Python 3.14.6, se instalaron las versiones fijadas en
`requirements-tested-windows-py314.txt`. Se generaron datos y modelos en
directorios nuevos con las semillas e hiperparámetros publicados, sin ajustar
con el test. Se ejecutaron los siete comandos de generación, entrenamiento,
calibración y evaluación de los protocolos de referencia y estrés.
[Pipeline causal](CINETICA_Y_PIPELINE_ML.md) · [Robustez](ROBUSTEZ_PIPELINE_ML.md) · [Intervalos](INCERTIDUMBRE_ML.md)

| Resultado sintético | Réplica |
| --- | --- |
| Logística calibrada, 564 ventanas de riesgo, 31 positivas | Brier 0,04021; PR-AUC 0,46135; 4/9 eventos detectados; 2 ventanas falsas positivas |
| Prevalencia y regla cinética | 0/9 y 1/9 eventos detectados respectivamente |
| Pronóstico, 975 ventanas | MAE Ridge 0,321 °Bx; persistencia 1,478 °Bx; extrapolación 0,622 °Bx |
| Estrés con 20 trayectorias adicionales | 6/12 eventos detectados en limpio; 1/12 con Brix ausente; 0/12 con 2 h de latencia |
| Intervalo nominal del 90 % | Radio 3,856764 °Bx; bajo deriva ninguna de las 20 trayectorias conserva todos sus targets cubiertos |

Se compararon los JSON con la evidencia versionada de Python 3.11 usando
tolerancia numérica absoluta y relativa de 1e-8. Coincidieron los 1.845 valores
comunes de cobertura y métricas del experimento causal, incluidos los desgloses
por proceso y escenario. El informe actual añade `calibration_bins` en desgloses.
Coincidieron también las ocho condiciones de estrés, los scores de calibración,
el radio y los resultados con 2.000 réplicas bootstrap. Los binarios y datasets
tienen huellas distintas entre ejecuciones. Huellas SHA-256 de esta réplica:

| Artefacto | SHA-256 |
| --- | --- |
| Dataset causal | `333b34f6da93d4cc5b670ff1e226e34e6684b7c1724fa17e41a2b1513512c377` |
| Modelo serializado | `99a602b89b720055b9c21d347e7d05c24ce617eca42440561d617b6f700c76b2` |
| Dataset de estrés | `beafaf691d017c749d8257fb743f7f4038e7c93ab7d88f3b9b39ab56531ae188` |

## Límites y próxima evidencia

Las ventanas de un lote están correlacionadas. Las ocho condiciones de estrés
comparten las mismas 20 trayectorias. La deriva sin bandera deteriora la cobertura
y la pérdida de datos elimina oportunidades de aviso. La generación de escenarios
conocidos limita la generalización a otras bodegas, instrumentos y vendimias.
Un score o una pendiente de Brix no establece la causa de una parada.

Los resultados de test y estrés son retrospectivos. Una futura mitigación
requiere congelar por adelantado otra reserva de trayectorias. Para lotes
físicos quedan pendientes las referencias instrumentales, adjudicación ciega,
seguimiento y criterios de aceptación acordados. [Protocolo de validación](VALIDACION_ENOLOGICA.md)
