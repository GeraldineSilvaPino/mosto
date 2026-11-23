# Resultado de incertidumbre — 17-11-2026

Ejecutado localmente en Windows/Python 3.11.4. Contrato y supuestos en [Incertidumbre ML](../INCERTIDUMBRE_ML.md). No se reentrenó el modelo ni se cambiaron su calibración de riesgo o umbral. Sin Supabase, migración ni despliegue.

## Calibración del forecast

Se utilizaron exclusivamente los 15 procesos de `calibration` del dataset original: 975 ventanas de forecast, agrupadas en 15 máximos de error absoluto. Nivel nominal predefinido 90 %, rango `ceil(16*0,9)=15`, radio **3,856764 °Bx**, ancho **7,713527 °Bx**. La banda es amplia; no se acredita su utilidad enológica. A nivel nominal 95 %, con esos mismos 15 procesos la regla exigiría el rango 16: no hay banda finita, sin recortar el rango al máximo disponible.

- Modelo original SHA-256: `3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3`.
- Artefacto de intervalos SHA-256: `b296a0b568374cad111f5193dcaeac88107438d305a73e679ee57c24db5de331`.
- Inputs usados en calibración SHA-256: `3acc972e5e1b65ad10398bb8e62b3d8ee4ebb137444812331db3a1304e7f8f31`.
- Código del módulo SHA-256: `8990b70a87d45e9237d8f52932c59d9871b28c8a4596a2f18cd134c05d9ffc64`.

Scores completos, procesos y versiones: [artefacto de intervalos](incertidumbre-ml-intervals.json). Métricas, conteos y bootstrap: [evaluación](incertidumbre-ml-evaluation.json). Las salidas por ventana quedan en `backend/artifacts/uncertainty-v1-20261117-evaluation/forecast_intervals.json`, regenerables con los comandos del contrato.

## Cobertura retrospectiva

| Datos/condición | Disponibilidad de banda en ventanas con target | Cobertura de ventanas emitidas | Procesos con todas sus bandas emitidas cubiertas | Procesos con todos sus targets atendidos y cubiertos |
| --- | ---: | ---: | ---: | ---: |
| Test original limpio | 100 % | 100 % | 15/15 | 15/15 |
| Stress limpio | 100 % | 100 % | 20/20 | 20/20 |
| Brix ausente | 81,54 % | 100 % | 20/20 | 0/20 |
| Temperatura ausente | 81,54 % | 100 % | 20/20 | 0/20 |
| Sensor retenido | 100 % | 96,08 % | 8/20 | 8/20 |
| Deriva | 100 % | 90,31 % | 0/20 | 0/20 |
| Pérdida de mensajes | 82,08 % | 100 % | 20/20 | 0/20 |
| Entrega acumulada | 93,85 % | 100 % | 20/20 | 0/20 |
| Latencia 2 h | 0 % | N/D | N/D, sin bandas | 0/20 |

La unidad nominal es la trayectoria de forecasts emitidos. El 90,31 % de cobertura por ventana con deriva no satisface esa unidad: todas las trayectorias tienen algún target fuera de banda. La condición retenida cubre completamente solo ocho. Para canales ausentes, las bandas emitidas cubren sus targets, pero faltan bandas durante los huecos; por eso no se declara servicio completo. Ninguna abstención se convierte en acierto ni en banda de ancho cero.

Las condiciones limpias quedan completamente cubiertas en estas muestras pequeñas. Eso no demuestra cobertura del 100 % en procesos futuros, en otras bodegas o en fallas no ensayadas. Test original y stress se habían consultado en bloques anteriores: esta evaluación es retrospectiva, no una nueva reserva ciega.

## Variabilidad por trayectoria

Bootstrap de 2.000 réplicas, semilla 20261118, remuestreo estratificado por escenario y pareado entre condiciones. Modelo y calibración fijos. Rangos percentiles aproximados al 95 %, no garantías poblacionales:

| Resultado | Estimación | Rango bootstrap |
| --- | ---: | ---: |
| Recall de eventos, test original | 44,44 % (4/9) | 33,33–66,67 % |
| MAE, test original | 0,3209 °Bx | 0,3026–0,3406 |
| Brier, test original | 0,04021 | 0,03416–0,04538 |
| Recall de eventos, stress limpio | 50,00 % (6/12) | 33,33–66,67 % |
| MAE, stress limpio | 0,3061 °Bx | 0,2890–0,3273 |
| MAE, sensor retenido | 0,7505 °Bx | 0,6169–0,8976 |
| MAE, deriva | 1,3101 °Bx | 1,1638–1,4710 |
| Cobertura de trayectoria emitida, sensor retenido | 40,00 % | 20,00–60,00 % |

La diferencia pareada de MAE frente al limpio queda entre **+0,3102 y +0,5946 °Bx** con sensor retenido, y entre **+0,8549 y +1,1722 °Bx** con deriva. Se usaron exactamente los mismos procesos remuestreados en cada par.

Los rangos [1,1] en cobertura limpia y [0,0] en cobertura por trayectoria con deriva se marcan `degenerate=true`. La muestra no contiene variación en esa estadística; el bootstrap no prueba certeza ni descarta errores no observados. Los rangos por escenario se basan en solo tres o cuatro procesos. No incluyen incertidumbre del ajuste del modelo, del radio, ni de cambios en la mezcla de escenarios.

## Comprobaciones y cierre

Doce pruebas nuevas: cuantil/rango sin recorte, niveles inválidos, score máximo por proceso, contaminación de otros splits, rechazo de procesos de calibración sin targets, estratos/multiplicidad de bootstrap, métricas no definidas, abstención y disponibilidad, límites sin recorte, prohibición de fit, reconstrucción del artefacto, reproducibilidad y preservación del modelo.

Suite completa: **217 aprobadas, 11 omitidas**, 90 warnings, 178,91 s, SQLite temporal. La salida se conserva en [evidencia pytest](uncertainty-tests-final.txt). No se modificó frontend ni se repitió build/navegador. PostgreSQL sigue pendiente en este equipo.

Se cierra la implementación/evaluación experimental de incertidumbre, no su validación operacional. ML v2 conserva `NO_VALIDADO`, riesgo y forecast null. Siguiente bloque local: fallas programables en la flota HTTP/outbox y recuperación de comunicaciones, manteniendo separados recuperación de datos, resolución humana y recuperación biológica.
