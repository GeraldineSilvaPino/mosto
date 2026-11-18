# Cinética causal y pipeline experimental

Contrato `kinetics-v1` / `future-stall-v1`, 16-11-2026. Decisiones de diseño para
evaluación local, no umbrales enológicos validados. No habilita ML operacional.

## Magnitud, tiempo y abstención

Brix **aparente** no equivale a azúcar residual ni permite declarar el fin del
proceso. «Causal» significa aquí disponibilidad temporal, no inferencia de causas.
Cada extracción pertenece a un proceso y a un instante UTC: solo admite muestras
con observación **y recepción** anteriores o iguales a ese instante. La calidad
y calibración son las congeladas al ingerir; una revocación posterior no reescribe
lo que entonces se sabía. La hora de recepción no garantiza visibilidad de commit.

Ventana de 24 h, rejilla de 5 min, retención hacia adelante hasta 15 min como
máximo (nunca interpolación desde el futuro). Cobertura es la fracción de puntos
de rejilla utilizables; se publica también el mayor hueco incluyendo extremos.
Exige cobertura ≥80 %, hueco ≤30 min y última muestra ≤15 min por canal.
Cambiar dispositivo/calibración dentro de la ventana invalida la cinética Brix
hasta reunir una ventana homogénea. Timestamps duplicados son ambiguos y se
rechazan para extracción. Canales ausentes/no finitos/de mala calidad se excluyen
independientemente. Temperatura válida no convierte Brix inválido en utilizable.
Una lectura explícitamente inválida interrumpe la retención del valor anterior;
si es la lectura actual, ese canal se abstiene aunque haya datos buenos recientes.

Features: media de última hora, tasa entre las medias de las dos últimas horas,
pendientes OLS de 6/24 h en unidades por hora, dispersión residual de Brix (no
«turbulencia»), media/rango y pendiente térmica, edad del proceso. La salida
incluye cobertura, huecos, motivos de abstención y evidencia temporal; estos
metadatos no se incluyen automáticamente en los vectores del modelo.

La observación `ralentizacion_observada` compara pendiente reciente >−0,015 °Bx/h
con pendiente de 24 h <−0,04, edad ≥24 h y Brix aparente >5. Es una regla descriptiva
experimental; no probabilidad, diagnóstico nutricional ni evento confirmado.
Su evidencia usa `configuration`, `confirmed_at`, `source` e `interpretation`
como los episodios. La consulta no crea incidentes ni prescribe acciones. Existe
un evaluador persistente separado, opt-in y solo simulado, documentado en
[Episodios](ALERTAS_V2_Y_EPISODIOS.md).

## Evento y etiquetas offline

Objetivo sintético: primer comienzo de una caída latente ≤0,01 °Bx/h sostenida
6 h, tras ≥1 °Bx de caída previa y ≥24 h de edad, con distancia a la asíntota >5
°Bx durante la persistencia. Se detecta sobre toda la trayectoria latente a pasos
horarios, sin usar el nombre del escenario. Onset es el inicio, confirmación es
6 h después; ambos se conservan por separado. No es una etiqueta de parada real.
Lag y final normal quedan excluidos por esas condiciones, no por su nombre.

Etiqueta 1 si el onset está en `(t+2 h, t+12 h]`; 0 si no hay onset en las próximas
12 h. Ventanas a ≤2 h del evento y posteriores al primer onset se excluyen del
riesgo. Sin seguimiento completo hasta `t+18 h` se censura, incluso si no aparece
un evento. Forecast usa observación de Brix aparente en `t+24 h`; sin ella no hay
target. Los valores futuros/latentes se usan solo para etiquetas/evaluación.

## Separación y evaluación

Se reutiliza `mosto-phases-1`, generando trayectorias completas de cinco escenarios
con semillas únicas y variación de condiciones iniciales, ambiente e inicio del
fallo. Cada proceso/semilla pertenece exclusivamente a train, calibration,
validation o test. Calibration ajusta la transformación sigmoide de scores;
validation elige el umbral; test se consulta al evaluar los artefactos congelados.
Los escenarios aparecen en todos los splits: mide nuevas semillas del mismo
generador, **no** generalización a mecanismos o bodegas desconocidos.

Comparación: prevalencia de entrenamiento, regla cinética fija y regresión
logística estandarizada; forecast persistente, extrapolación de pendiente de 6 h
y Ridge. Reportar PR-AUC, ROC-AUC cuando existan ambas clases, Brier, bins de
calibración, precisión/recall, falsas alarmas por día observado elegible,
detección por evento y anticipación, MAE/RMSE a 24 h, desgloses por escenario y
proceso. Ausencia de clase/evento devuelve null donde la métrica no está definida.
El presupuesto experimental para elegir umbral es 0,25 falsas alertas por día
elegible de validación; no es un presupuesto acordado con una bodega.
La unidad concreta es **ventanas positivas falsas** por día de observación
elegible, a una consulta cada 3 h; no son incidentes deduplicados. Las ventanas
solapadas no son observaciones estadísticamente independientes. No se publican
intervalos de confianza por fila ni se infiere rendimiento poblacional.

No existe puerta automática de promoción. Permanecen `NO_VALIDADO`, riesgo null
y sin alertas ML v2. Faltan etiquetas y calibración reales, validación externa,
intervalos de forecast validados y perfiles/etiquetas aprobados. Se implementaron
[bandas e incertidumbre experimentales](INCERTIDUMBRE_ML.md), sin garantía real
ni habilitación operacional. Los episodios cinéticos
persistentes y los [ensayos offline de sensores](ROBUSTEZ_PIPELINE_ML.md) son
experimentales, no validación enológica. Conservar CSV y pickle legacy intactos.

## Consulta y reproducción

`GET /api/procesos/{id}/cinetica` admite `as_of` ISO 8601 con zona horaria,
anterior o igual al presente y posterior o igual al inicio del proceso. Requiere
JWT y acceso al proceso histórico. Devuelve `Cache-Control: no-store`, features,
calidad/evidencia y `NO_VALIDADO`, riesgo null, alerta false y forecast null.
No utiliza lecturas legacy sin contrato temporal/metrológico v2. Un historial
vacío devuelve abstención, no una tasa cero. La UI presenta tasas, calidad,
cobertura y motivos de abstención mediante esta consulta.

Desde `C:/mosto/backend`, con un entorno instalado mediante
`requirements-test.txt`, ejecutar en directorios **nuevos**:

```powershell
.\venv\Scripts\python.exe -m ml.causal_pipeline generate --output-dir artifacts/causal-v1-final-dataset
.\venv\Scripts\python.exe -m ml.causal_pipeline train --dataset-dir artifacts/causal-v1-final-dataset --output-dir artifacts/causal-v1-final-model
.\venv\Scripts\python.exe -m ml.causal_pipeline evaluate --dataset-dir artifacts/causal-v1-final-dataset --model-dir artifacts/causal-v1-final-model --output-dir artifacts/causal-v1-final-evaluation
```

Por defecto: semilla maestra 2026, 20 trayectorias por escenario, duración 240 h,
ventanas de 24 h cada 3 h. El manifiesto conserva las recetas completas para
regenerar observaciones a 5 min, eventos, splits, contratos, versiones y hashes
de código/dataset. `windows.jsonl` conserva features/targets; los datos crudos se
regeneran desde las recetas. `training.json` registra procesos usados y política
de umbral; `evaluation.json` contiene test global, por escenario y por proceso,
y los archivos de predicciones permiten revisar cada decisión y forecast.

Los comandos no importan configuración ni base de datos, no envían HTTP y no
sobrescriben salidas. El modelo se guarda como `experimental.joblib` bajo
artifacts; solo cargar artefactos locales de confianza (joblib puede ejecutar
código al deserializar). El endpoint no carga ese artefacto. Los hashes detectan
cambios accidentales; no son una firma de autenticidad.

La referencia de este cierre y sus límites se conservan en
[evidencia del pipeline](evidencias/cinetica-ml-2026-11-16.md).
