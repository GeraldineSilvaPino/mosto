# Mosto — Auditoría técnica y plan maestro de profundización

Fecha: 14 de noviembre de 2026. Fase 1, sin modificación de código ni migraciones. Estado examinado: `feat/ml-stuck-fermentation-prediction`, commit `c310b91`, sobre `develop` en `c6c9edc`.


> **Actualización con nueva evidencia:** el notebook aportado después de esta auditoría reproduce exactamente el CSV y permite reconstruir el test 80/20. Las incertidumbres de procedencia y partición de la sección 1.3 quedan resueltas en la [adenda del notebook](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/Adenda_Notebook_ML.md). Accuracy sintética de test: 93,375 %; AUROC: 0,98019. No se observó leakage por ventanas compartidas. Se mantienen los problemas temporales y la ausencia de validación de eventos futuros.

## Dictamen ejecutivo

Mosto tiene una integración funcional aprovechable: FastAPI recibe telemetría, persiste lecturas, evalúa reglas y un clasificador real, genera alertas y entrega resultados a Vue. No es solamente una maqueta. Sin embargo, **no está preparado para operar como SaaS industrial ni para afirmar predicción temprana validada de paradas de fermentación**. El problema principal es la confiabilidad de la cadena completa: identidad, procedencia de los datos, tiempo físico, estado del proceso, evidencia del modelo y trazabilidad de las intervenciones.

Recomiendo conservar FastAPI, Vue, PostgreSQL, el dominio general y parte de los componentes; reconstruir los contratos de ingesta, el pipeline científico y el ciclo de incidentes; y rediseñar las pantallas a partir de esos contratos. Cambiar inmediatamente a una LSTM más grande no corregiría los problemas encontrados.

No recomiendo integrar la rama ML en `develop` como funcionalidad terminada. Se puede preservar como referencia experimental y extraer posteriormente sus piezas útiles mediante cambios revisables. La validación de una demostración sintética y la validación en vino real deben constituir entregables separados.

### Alcance y límites de la evidencia

- Inventario de los **104 archivos versionados del checkout**: fuente, configuración, documentación, 18 DOCX, PDF de presentación, imagen del modelo relacional, CSV y artefacto serializado. El anexo enumera cada archivo y el método de inspección. Se extrajo contenido documental, se analizaron estructuras y referencias, y se revisaron los recorridos funcionales del código. Esto no equivale a ejecutar cada línea ni a certificar ausencia de errores.
- Inspección de **39 referencias Git locales/remotas almacenadas**, ancestría y diferencias; además, extracción del prototipo alternativo de 26 archivos en `MatiasGonzalez`. No se realizó `fetch`; las conclusiones corresponden a las referencias disponibles localmente. No se examinó cada revisión histórica de cada archivo como si fuera un producto independiente.
- Lectura del PDF adjunto de 31 páginas físicas y comprobación visual de ecuaciones y tablas relevantes. Sus instrucciones editoriales y las rúbricas académicas se trataron como contenido documental, no como órdenes para esta tarea.
- Inspección **solo de lectura** del esquema PostgreSQL configurado: tablas, índices, restricciones, triggers, funciones y rol de conexión. No se realizaron escrituras ni pruebas destructivas sobre esa base.
- Pruebas ejecutadas en SQLite aislado; build de frontend fuera del repositorio; revisión visual de nueve pantallas y una vista móvil con respuestas API interceptadas y ficticias. Estas capturas verifican presentación, no integración con producción.
- No se dispone de firmware ni prototipo calibrado, datos reales etiquetados de paradas, pipeline de entrenamiento original o resultados independientes del modelo. No se ha demostrado exactitud enológica, resistencia a carga, seguridad de infraestructura o recuperación ante desastre.
- `node_modules`, `venv`, cachés y objetos internos de Git no son código propio auditado línea por línea. Los valores de secretos locales no se incorporan al informe. Se preservó el cambio previo del usuario en `backend/app/ml/README.md`.

### Hallazgos prioritarios

| Prioridad | Hallazgo comprobado | Consecuencia | Acción propuesta |
|---|---|---|---|
| P0 | Solo `/api/auth/me` exige identidad; el resto de operaciones de negocio carece de autorización efectiva | Lectura, modificación y suplantación de autor sin control de empresa/bodega | Autenticación obligatoria, RBAC por bodega y aislamiento tenant |
| P0 | Clave JWT de respaldo fija en fuente; no está configurada una sustituta en el entorno local inspeccionado | Firma de sesiones basada en un secreto público | Configuración obligatoria y renovación de sesiones/claves |
| P0 | Credencial PostgreSQL literal en documentación versionada | Exposición de un secreto, aunque su vigencia no está demostrada | Verificar revocación, rotar si sigue vigente y retirar del historial de forma coordinada |
| P1 | Ingesta pública autoaprovisiona dispositivos, cubas y procesos; completa medidas ausentes con valores inventados | Contaminación de telemetría y reinicio de procesos cerrados | Aprovisionamiento explícito; datos faltantes nulos; ciclo de vida independiente |
| P1 | Pendientes ML por número de muestra y ventanas sin duración temporal | Riesgo dependiente de la frecuencia de envío | Features sobre tiempo real, ventana y calidad explícitas |
| P1 | Auditoría muestra incidentes ficticios con API vacía; GET de bitácora puede sembrar intervenciones ficticias | Historial y MTTR sin valor probatorio | Eliminar fallbacks y siembras fuera de un entorno demo explícito |
| P1 | Acciones de alertas con ID ≥1000 pueden quedarse solo en Vue | El usuario cree que atendió/resolvió algo que no se persistió | Eliminar heurística de ID; confirmar resultado del servidor |
| P1 | No hay generador/entrenador reproducible ni evaluación independiente del clasificador | Métricas y probabilidades no defendibles | Pipeline versionado, splits por proceso y validación temporal |
| P2 | Esquema ORM incompleto frente a PostgreSQL, sin migraciones | Entornos nuevos y pruebas no reproducen producción | Migraciones verificadas y pruebas PostgreSQL |
| P2 | UI móvil desborda; controles y diagnósticos parcialmente decorativos | Operación confusa y pérdida de confianza | Rediseño operativo con contratos verificables |

La contraseña documentada **no coincide** con la configurada actualmente en el `.env` inspeccionado. No afirmo que esa contraseña antigua siga siendo válida ni que haya ocurrido una intrusión. Su publicación sigue siendo un defecto que debe resolverse. La exposición externa real de los endpoints depende también del despliegue, que no fue auditado.

## 1. Auditoría forense de la rama ML

### 1.1 Qué cambió exactamente

La rama agrega un único commit respecto de `develop`: 15 archivos, 5.845 líneas añadidas y 19 eliminadas, además del binario. Gran parte del volumen corresponde a las 4.001 líneas del CSV; el tamaño del diff no representa profundidad algorítmica.

| Archivo | Cambio | Función real |
|---|---:|---|
| `backend/app/ml/README.md` | +128 | Documentación de inferencia y demostración |
| `backend/app/ml/dataset_fermentacion_kontogiannis.csv` | +4001 | 4.000 vectores de features y etiqueta |
| `backend/app/ml/modelo_parada_fermentacion.pkl` | 245.177 bytes | Clasificador serializado |
| `backend/app/services/ml_service.py` | +179 | Extracción de cinco features y `predict_proba` |
| `backend/app/services/rules_engine.py` | +114 | Alerta por riesgo ML y deduplicación básica |
| `backend/app/routers/cubas.py` | +305/−8 | Predicción en DTO, endpoint ML y dos acciones demo |
| `backend/app/routers/alerts.py` | +7 | Presentación del tipo de alerta ML |
| `backend/app/schemas.py` | +25 | DTO de predicción y simulación |
| `backend/requirements.txt` | +5 | Dependencias científicas |
| `backend/scripts/simulate_esp.py` | +56/−7 | Escenario artificial de estancamiento caliente |
| `backend/tests/test_ml_prediction.py` | +145 | Casos sintéticos y endpoints |
| `backend/tests/test_full_integration.py` | +2/−1 | Ajuste de prueba existente |
| `frontend/src/services/cubaService.js` | +35 | Llamadas ML y demo |
| `frontend/src/views/CubaDetailView.vue` | +741 | Panel de riesgo, métricas y controles demo |
| `frontend/src/views/DashboardView.vue` | +102/−3 | Indicadores ML en resumen |

Las ramas de monitoreo, ingesta, procesos, dispositivos, umbrales, alertas, auditoría e integración ya están incorporadas en la historia relevante. `feat/redesign-ui` es ancestro del estado actual. Las ramas antiguas `feat/alerts-view`, `feat/devices-view`, `feat/thresholds-view`, `feat/alert-audit-view` y `feat/be-cubas-monitoring` tienen commits con hashes diferentes pero cambios equivalentes detectados por `git cherry`; no deben interpretarse automáticamente como trabajo funcional pendiente de integrar.

`MatiasGonzalez` contiene otro prototipo, bajo `Mosto_Vue3_FastAPI/`, con demo en memoria, integración parcial PostgREST, Auth de Supabase, SQL de transiciones, formularios y gráficos. Su separación explícita demo/real y sus transiciones son referencias útiles. No es un sustituto listo para fusionar: supone nombres de tablas distintos, deja la ingesta real bloqueada, usa un componente principal grande y requiere adaptar permisos/SQL. No se ejecutó ese prototipo histórico.

### 1.2 Arquitectura efectiva del modelo

El binario contiene un `GradientBoostingClassifier`: 100 estimadores, `learning_rate=0.08`, profundidad máxima 4, `subsample=0.85`, `random_state=42`, pérdida `log_loss`. No contiene V-LSTM, fuzzy autoencoder ni un modelo explícito de fases.

El servicio recibe **dos listas sin timestamps**, combina con `zip`, elimina pares con `None`, exige cuatro pares y toma como máximo los últimos doce. Calcula:

1. Media de las tres últimas medidas de Brix.
2. Media de las tres últimas temperaturas.
3. Pendiente de Brix mediante regresión lineal contra `0,1,...,n−1`.
4. Pendiente térmica calculada del mismo modo.
5. Desviación estándar de Brix sin eliminar tendencia.

Las unidades de las pendientes son °Bx/muestra y °C/muestra. La propia tarjeta ML y el README lo expresan así; el defecto es **usarlas como cinética comparable entre frecuencias y dispositivos**, no un supuesto etiquetado universal en °Bx/h. La desviación estándar mezcla ruido y descenso normal; no justifica llamarla turbulencia física.

Si la media Brix es ≤2,5, el servicio devuelve `FINALIZADA`, riesgo 0, antes de consultar el modelo. Para los demás casos toma la probabilidad de clase 1: ≥70 % crítico, ≥40 % advertencia. No hay evidencia de selección/calibración de estos cortes con costes operacionales. Un error de inferencia devuelve `ERROR` pero también 0 %; la ausencia de predicción debe representarse con `null`, nunca como ausencia de riesgo.

La carga es un singleton `joblib`, con compatibilidad manual de un módulo interno de sklearn y supresión de warnings. Debe reemplazarse por un artefacto confiable, firmado o verificado por hash, dependencias exactas y manifiesto. La documentación oficial advierte que cargar modelos entre versiones distintas de sklearn no está soportado y que pickle/joblib requieren confiar en el origen. [Persistencia de modelos, scikit-learn](https://scikit-learn.org/stable/model_persistence.html).

### 1.3 Dataset, métricas y límites de lo demostrable

El CSV tiene 4.000 filas, cinco features y etiqueta binaria: 2.776 normales y 1.224 positivas; no se detectaron nulos ni filas duplicadas. Brix suavizado cubre aproximadamente 2,31–17,60, temperatura 9,22–36,42 °C. No aparecen edad, timestamps, ID de fermentación, semilla, escenario, momento de falla, horizonte o partición train/test.

No existe en el repositorio actual el código que genere ese CSV ni que entrene el pickle. Por tanto, **no se puede reconstruir ni validar su procedencia, definición de etiqueta o separación de entrenamiento y evaluación**. El nombre Kontogiannis no acredita que sean datos publicados por los autores. Tampoco permite afirmar, sin pruebas, que hubo leakage: lo correcto es decir que no puede descartarse ni auditarse.

Al evaluar el binario sobre el CSV suministrado se obtuvo accuracy 96,05 %, AUROC 0,99260 y matriz `[[2719,57],[101,1123]]`. Estos son resultados de concordancia sobre ese archivo, **no rendimiento de test independiente**, porque se desconoce qué filas vio el entrenamiento. Las importancias internas son aproximadamente 11,7 % Brix, 20,7 % temperatura, 58,3 % pendiente Brix, 6,8 % pendiente térmica y 2,6 % desviación. No equivalen a causalidad ni a explicaciones por incidente.

Pruebas directas, sin escribir en la base real:

| Entrada controlada | Resultado |
|---|---|
| Brix 24 constante, temperatura 22 constante, 12 muestras | 97,8 % crítico; no puede distinguir una fase Lag normal |
| Descenso físico constante −0,06 °Bx/h, muestras cada 5 s | 97,6 % crítico |
| Misma tasa física, muestras cada 5 min | 97,1 % crítico |
| Misma tasa física, muestras cada 1 h | 1,0 % normal |
| Brix ≤2,5 | Finalizada por regla, sin evidencia del estado biológico |
| NaN | Error de modelo, riesgo 0 y métricas NaN |
| Texto no numérico | `ValueError` anterior al bloque de captura |
| Listas de tamaños distintos | Truncamiento silencioso por `zip` |

En el experimento temporal también cambian duración de la ventana y nivel final, porque el servicio siempre usa doce puntos. No atribuyo todo el cambio numérico a una sola feature: demuestra que el contrato actual no conserva una cinética física comparable. Una pendiente de −0,03 por muestra equivale a −21,6 °Bx/h a 5 s, −0,36 a 5 min y −0,03 a una hora.

### 1.4 Integración y endpoints

La integración existe: lectura → reglas → consulta de últimas lecturas → clasificador → `EventoAlerta`; además, GET de cubas calcula predicciones y Vue las visualiza. Los endpoints nuevos son `GET /api/cubas/{id}/ml-prediction`, `POST .../simular-anomalia` y `POST .../restaurar-normalidad`.

Sus limitaciones: inferencia repetida en ingesta y polling, falta de registro histórico/versionado de la predicción, sin control de frescura/calidad, sin horizonte futuro, sin proyección de curva y sin vínculo estructurado a una intervención. Las listas usan consultas por cuba y se recalculan cada cinco segundos. Las acciones demo insertan lecturas retrodatadas en procesos ordinarios; restaurar puede cerrar alertas y alterar MTTR sin una recuperación real. Además, los puntos retrodatados pueden quedar fuera de las doce lecturas recientes cuando sigue entrando telemetría.

### 1.5 Qué aporta realmente SmartBarrel

El adjunto es el preprint v1 del 27/05/2025, DOI `10.20944/preprints202505.2143.v1`. Existe una versión publicada en *Sensors* 2025, 25(13), 3877, según la ficha editorial. Las observaciones de ecuaciones de este informe corresponden al **PDF adjunto**, sin asumir que todas persisten en la versión final. [Registro editorial y enlace a la publicación](https://www.preprints.org/manuscript/202505.2143).

El trabajo combina sondas, reglas difusas y generación sintética de seis variables, para alimentar un predictor multivariable V-LSTM. El llamado autoencoder actúa principalmente como generador basado en reglas/cinética; no debe confundirse automáticamente con una red neuronal encoder-decoder que aprende a reconstruir entradas. Describe 1.200 fermentaciones sintéticas de 21 días, resolución de cinco minutos y una predicción de 24 h, además de datos piloto y curvas experimentales de referencia.

En las ecuaciones/tablas de fases —páginas físicas 14–16— hay puntos que requieren interpretación crítica:

- Las membresías difusas se solapan; Lag 0–20 h, exponencial 20–70 h, estacionaria 70–150 h y declive posterior son una parametrización, no un reloj biológico universal para cualquier variedad, levadura, temperatura y tamaño de tanque.
- El azúcar está expresado en g/L, no en °Brix. La expresión exponencial y la curva estacionaria no se unen necesariamente si se aplican como tramos rígidos. Con los valores de tabla, el cambio alrededor de 70 h puede elevar artificialmente el azúcar. No copiar los tramos sin asegurar continuidad y balance.
- La tabla 2 menciona 25 °C en Lag, mientras otras expresiones/tabla 3 usan aproximadamente 15 °C. La temperatura está muy controlada; el paper no valida por sí mismo un simulador de estrés térmico caliente/frío como el requerido aquí.
- La estabilización sintética a 20 g/L no constituye una definición de vino seco ni se debe traducir en una regla universal de fin por Brix.
- Hay inconsistencias entre parámetros tabulados y narrados de ventana/capas V-LSTM. El RMSE agregado cercano a 0,16 de las tablas finales no es un error de 0,16 °Brix ni una métrica de anticipación de paradas para Mosto.

La adaptación correcta es metodológica: cinética temporal, fases suaves, incertidumbre y evaluación de proyección. **No es reproducir sus cifras como garantía de nuestro producto.**

### 1.6 Corrección metrológica indispensable

El MPU-6050 mide aceleración/inclinación; la flotabilidad permite inferir densidad tras calibración. Un valor convertido a escala Brix durante fermentación no es automáticamente concentración de azúcar residual: alcohol, temperatura y otros componentes alteran la relación. Se debe mostrar **°Brix aparente estimado**, registrar el método y distinguirlo de un análisis de glucosa/fructosa. AWRI explica que la hidrometría mide densidad y necesita corrección térmica; las escalas Brix/Baumé no son mediciones químicas directas de azúcar. [Densidad e hidrometría](https://www.awri.com.au/industry_support/winemaking_resources/laboratory_methods/chemical/density/), [AWRI: interpretación de Brix/Baumé](https://www.awri.com.au/wp-content/uploads/2018/04/s1809.pdf).

Dos variables permiten detectar patrones compatibles con lentitud o estancamiento, pero no identificar inequívocamente falta de nutrientes, baja viabilidad, contaminación o sensor adherido. Las causas deben presentarse como hipótesis. Los estados biológicos son estimados, no observaciones directas de biomasa.

### 1.7 Pipeline propuesto

**Contrato temporal.** Una librería compartida entre entrenamiento e inferencia recibe tiempos UTC, Brix aparente, temperatura, máscara de validez, edad del proceso y metadatos permitidos. Rejilla nominal de cinco minutos con tolerancia, sin rellenar huecos largos. Ventanas iniciales candidatas: 1, 3, 6, 12 y 24 h; se seleccionan con evaluación, no por estética.

**Features causales.** Medianas/EMA o regresión robusta usando únicamente el pasado; pendiente en °Bx/h sobre tiempo transcurrido, cambio de pendiente, diferencia frente a tasa esperada por etapa, avance respecto del inicio, duración de meseta, pendientes térmicas, exposición acumulada fuera del perfil en °C·h, máximos y cambios recientes. Desviación de residuales tras quitar tendencia, cobertura, gaps, edad de la última muestra, consistencia entre calibración y observación. Un filtro gaussiano centrado sobre toda la serie no es apropiado para inferencia online porque usa futuro.

Para una ventana válida: `vB = Σw(t−t̄)(B−B̄) / Σw(t−t̄)²`, con `t` en horas. La política de mínimo de datos exige **duración y cobertura**, no solamente cuatro registros. Debe abstenerse frente a calibración ausente, sensor retenido, datos viejos o estado fuera del dominio entrenado.

**Dos problemas diferentes.** (a) Detector de estancamiento presente y calidad de datos. (b) Riesgo de inicio de parada dentro de un horizonte futuro, por ejemplo 6, 12 o 24 h. Definir el evento mediante una tasa persistentemente baja cuando todavía hay fermentación pendiente, descartando Lag y término normal según evidencia disponible. La duración y umbrales son parámetros a validar con el enólogo; no constantes universales. Para riesgo futuro, etiquetar por el primer inicio sostenido en `(t,t+H]`, excluir ventanas ya detenidas y tratar series censuradas sin futuro suficiente.

**Modelo base.** Mantener un clasificador de árboles como candidato, enfrentado a una regla cinética y a regresión logística. La sencillez facilita analizar fallos con pocos procesos. Una LSTM/TCN compacta puede ser candidata posterior si aporta mejora en procesos independientes; diez capas por analogía al paper no están justificadas.

**Proyección 24 h.** Comparar persistencia, extrapolación robusta y un modelo cinético condicionado por temperatura/perfil. Entrenar regresión de trayectoria/residuales con cuantiles si mejora esos baselines. Dibujar mediana y bandas con cobertura comprobada; separar escenarios de evolución térmica si no se conoce el control futuro. Una banda no validada no se denomina intervalo de confianza. Una proyección de Brix aparente tampoco es una medida química de azúcar residual.

**Evaluación.** Dividir primero por fermentación/semilla/familia de simulación; mantener ventanas de un mismo proceso en una sola partición. Para validación temporal, purgar solapamientos de lookback+horizonte. Ajustar escalas, selección y calibración únicamente dentro del conjunto permitido. Reservar escenarios y combinaciones de parámetros fuera de entrenamiento, no solo otra semilla del mismo patrón. Después realizar evaluación real prospectiva en modo observación. [Prevención de leakage, scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html).

Medir PR-AUC, sensibilidad por evento a un presupuesto de falsas alertas por cuba-día, distribución de anticipación, eventos omitidos, Brier/calibración y abstenciones. Para forecast: MAE/RMSE en unidades observadas por horizonte, error frente a baselines, cobertura y anchura de bandas. Separar métricas sintéticas y reales; informar incertidumbre por proceso, no tratar miles de ventanas correlacionadas como miles de ensayos independientes.

**Explicación y operación.** Persistir predicción con modelo, feature-schema, versión de calibración, ventana, calidad, score bruto/calibrado, razones y horizonte. Ejemplo de explicación verificable: “La tasa estimada cayó respecto de las seis horas anteriores y hay exposición térmica fuera del perfil”; nunca afirmar “faltan nutrientes” a partir de dos sensores. Las recomendaciones se vinculan a una revisión/intervención humana y a su posterior evaluación.

## 2. Simulación continua y prototipo físico

### 2.1 Estado actual

`simulate_esp.py` envía dos mensajes por cuba a `/api/telemetria/nodo-cuba` y `/api/telemetria/flotador`, simulando ESP32 y ESP8266. El esquema procede de un diseño anterior con pH/DHT y no del nodo único solicitado. El intervalo de Compose es de cinco segundos y las cubas están preseleccionadas. No existe broker ni implementación MQTT operativa.

El descenso de Brix se aplica por iteración, sin relación consistente con tiempo físico. La temperatura sigue una oscilación acotada; el escenario de parada fija Brix alrededor de 14,5 y fuerza calentamiento. Hay ruido, pero no conservación, fases suaves, agotamiento, adaptación, enfriamiento causante de parada o recuperación modelada. Algunas propiedades recalculan ruido al acceder: el valor impreso puede no ser el transmitido. La generación de MAC usa módulo del ID y puede colisionar con cubas separadas por 90 IDs. Reiniciar pierde el estado y la continuidad.

La ingesta convierte inclinación con una recta fija `(ángulo−25)×0,60`, limita el resultado a 0–35 y aproxima SG con factores inconsistentes entre caminos. No guarda una calibración trazable ni el dato crudo suficiente para recalcular. El caso `az=0` se omite aunque `atan2` permite tratarlo. Los límites silenciosos ocultan medidas fuera de rango.

El canal térmico completa Brix/pH/ambiente con lectura previa o constantes; el canal flotador completa temperatura. Se marcan como válidos y frescos. Un fallo de un sensor puede quedar oculto por el otro. Los dos nodos usan el mismo origen lógico que sensores reales; no hay segregación confiable de simulación. El tiempo registrado es recepción del servidor, sin secuencia de origen ni idempotencia de reenvío.

Autoaprovisionar desde una MAC desconocida mezcla ingesta con administración. La ingesta puede crear una fermentación nueva después de finalizar la anterior o volver a asociar un dispositivo desvinculado. Las múltiples confirmaciones de transacción permiten resultados parciales. Si el motor de reglas falla después de guardar la lectura, el cliente puede recibir error y reenviar una lectura ya persistida.

### 2.2 Contrato común propuesto

Un ESP32 real con dos canales y N dispositivos virtuales deben producir el mismo sobre validado: `schema_version`, `device_id`, `boot_id`, `sequence`, `observed_at`, medidas y unidades, estado/calidad de cada canal, versión de firmware/calibración y metadatos técnicos disponibles. `received_at` lo pone el servidor. La identidad autenticada determina empresa, dispositivo y origen autorizado; el payload no puede proclamarse físico ni elegir otra empresa/cuba.

Conservar aceleración/ángulo como dato crudo de diagnóstico y derivar Brix con calibración versionada. No inventar batería, RSSI, pH o temperatura ambiente si no se miden. Las dos variables primarias siguen siendo Brix aparente y temperatura; los metadatos de calidad no son nuevas variables enológicas sensadas.

Credencial revocable por dispositivo y TLS; clave de idempotencia `(device_id,boot_id,sequence)`. Verificar asignación y proceso vigentes **en el tiempo observado**, límites físicos, duplicados, retraso y reloj. Un evento tardío válido puede completar historia sin retroactivamente producir una alerta operacional engañosa. La política debe estar documentada. Telemetría sin proceso puede guardarse como diagnóstico del nodo, pero no crear un lote.

Ingesta transaccional guarda lectura y evento de trabajo pendiente; un worker procesa calidad, features, inferencia y reglas con idempotencia. Esto evita bloquear la confirmación del dispositivo por ML. Para la escala del proyecto basta inicialmente una outbox PostgreSQL y un worker; no es necesario introducir Kafka o muchos microservicios.

HTTP es suficiente para integrar el primer prototipo. Si el firmware requiere MQTT, añadir un adaptador que autentique tópicos por dispositivo y entregue el mismo comando de ingesta; QoS no sustituye la idempotencia de aplicación. Las acciones de reinicio deben tener confirmación del dispositivo, timeout y auditoría antes de ofrecerlas en UI.

### 2.3 Simulador basado en fases y mecanismos

Definir por escenario condiciones iniciales, perfil térmico, parámetros de velocidad/viabilidad, tiempos de transición, perturbaciones y semilla. Separar tiempo simulado de tiempo de pared: si una demo acelera 60×, guardar ambos y rotularla. No enseñar tasas aceleradas como tasas de una fermentación real.

Una formulación inicial defendible integra una **tasa de consumo positiva**, en lugar de pegar niveles discontinuos:

`dS/dt = −qmax · Xv · fT(T) · fN(N) · S/(Ks+S)`

`m·cp·dT/dt = Qfermentación − UA(T−Tamb) − Qrefrigeración`

`S`, nutrientes y viabilidad pueden ser estados latentes internos del simulador; no se entregan al modelo como si los midiera el hardware. Cada término debe tener unidades compatibles y parámetros documentados. Con membresías difusas normalizadas se modulan tasas/viabilidad y duración de fases manteniendo continuidad. La temperatura influye en velocidad y estrés acumulado, con recuperación gradual; no usar una función creciente sin límite que haga beneficioso cualquier calentamiento.

La observación debe modelarse aparte: `B_aparente = g(densidad(S,etanol,T), calibración) + ruido + sesgo`. Si no hay parametrización defendible de esa relación, usar una curva fenomenológica explícitamente etiquetada y validar su envolvente; no llamarla química exacta. La señal latente de azúcar puede ser monótona sin exigir que cada lectura ruidosa lo sea.

| Escenario | Mecanismo | Qué debe distinguir el DSS |
|---|---|---|
| Sana | Lag variable, aceleración, consumo y final progresivo | Inicio plano y fin lento normales |
| Frío | Caída gradual/choque térmico, menor actividad y adaptación | Estrés compatible con enfriamiento |
| Calor | Exposición sostenida y pérdida de viabilidad | Deterioro, no solo umbral instantáneo |
| Nutrientes limitantes | Agotamiento latente con temperatura normal | Estancamiento sin atribuir causa definitiva |
| Lenta | Menor tasa sostenida pero consumo consistente | Lentitud frente a parada |
| Falla instrumental | Sensor retenido, salto, deriva, desconexión | Problema de medición frente a biología |
| Intervención | Cambio térmico/control con respuesta retardada | Evaluar recuperación sin declararla instantánea |

Ruido de observación gaussiano pequeño es solo un componente. Añadir autocorrelación, sesgos entre dispositivos, datos faltantes, transmisión irregular y perturbaciones ocasionales; evaluar esos regímenes por separado. Guardar estado, RNG, versión y reloj para reiniciar sin saltos. Las semillas y perfiles del conjunto de demostración no deben convertirse en el test independiente del modelo.

Un panel de escenarios puede habilitar falla/recuperación únicamente en cubas simuladas y con auditoría. Las credenciales y permisos deben impedir que dicho motor escriba sobre el prototipo físico.

## 3. Arquitectura full-stack y profundidad funcional

### 3.1 Base de datos y operación

PostgreSQL tiene 18 tablas públicas; el ORM representa 17 y omite `UMBRAL_FERMENTACION`. Se inspeccionaron 76 restricciones y tres triggers. **Sí existen** índices únicos parciales para proceso activo por cuba y asignación activa por dispositivo. No sería correcto afirmar que esas garantías faltan en la base real. El problema es su ausencia en una definición migrable reproducible y en el entorno de pruebas.

La unicidad de código de cuba también difiere: el esquema real permite distinguir por bodega, mientras el ORM declara unicidad global. El trigger de lectura verifica una asignación histórica del dispositivo, pero no su vigencia temporal/estado activo. El trigger de proceso protege correspondencia perfil–bodega y capacidad; no sustituye todas las validaciones de entrada.

RLS está habilitado en las tablas, pero el rol de la conexión inspeccionada tiene `rolbypassrls=True`. Por ello, habilitar RLS en Supabase no prueba aislamiento para este backend. Debe usarse un rol de aplicación limitado y una estrategia coherente de tenant en consultas/políticas; probar con dos empresas y accesos negativos.

`create_all` al importar la app no es una migración; excepciones capturadas y un health siempre positivo ocultan estados parciales. SQLite con `BigInteger` como PK no reproduce automáticamente el comportamiento de las identidades PostgreSQL. No se debe prometer fallback operativo a SQLite por una caída remota si el código solo lo elige cuando falta configuración.

### 3.2 Revisión por módulo

| Módulo | Implementación aprovechable | Defectos y profundización necesaria |
|---|---|---|
| Cubas | Lista, detalle, última lectura, histórico y predicción | Falta CRUD completo de bodegas/cubas/estados; valores de lote/capacidad/variedad por defecto; consultas N+1; separar cuba física de lote/proceso y calidad de lectura |
| Procesos | Inicio/finalización y validaciones parciales de capacidad/perfil | Validar volumen positivo, perfil activo, cuba disponible y fechas; finalizar ignora medidas finales/razón; faltan detener/cancelar; ingesta no debe reabrir; historial de procesos cerrados accesible |
| Dispositivos | Alta, consulta, vincular/desvincular y historial de asignaciones | Datos técnicos inventados; alta puede terminar parcialmente asignada; roles ausentes; estado administrativo incompleto; credenciales y calibración inexistentes; faltan actualización/estado y control temporal de reasignación |
| Umbrales | CRUD de perfiles y validación de rangos | Caída mínima Brix almacenada pero no evaluada; override por proceso ausente pese a tabla real; desactivar vía PUT puede evitar protección de borrado; historial de cambios/versiones pendiente |
| Alertas | Reglas térmicas/pH, alerta ML, atención/resolución, CSV | Duplicados por cooldown, transiciones repetibles, pérdida de valor/mensaje, sin evidencia/política versionada ni recuperación sostenida |
| Auditoría/MTTR | Cálculo backend y pantalla conectada | Fallback ficticio, fecha de resolución reescribible, filtros inconsistentes y poblaciones diferentes entre tabla/KPI/exportación |
| Bitácora | Crear/listar notas con asociación parcial | Autor elegido por nombre o primer usuario; GET siembra acciones inventadas; sin firma real, vínculo de incidente/medición ni correcciones trazables |
| Usuarios | Login, alta/lista, rol, estado y borrado lógico | Autorización ausente; rol arbitrario y bodega ignorada en caminos; invitación y recuperación no implementadas realmente; proteger último administrador y membresías múltiples |
| Empresa/configuración | Persistencia de configuración | Primera empresa global; GET crea datos de ejemplo; cuotas y flags de notificación no respaldados por servicios; límites no aplicados; carga de logo sin controles suficientes |
| Catálogos | Cepas/materiales | GET puede sembrar; faltan contratos completos de modelos/roles; catálogo administrado explícitamente, sin efectos laterales de lectura |

Detalles que requieren corrección concreta:

- **Históricos:** límite de 200 filas recientes no es agregación temporal. A cinco minutos, un único emisor cubre unas 16 h 35 min entre extremos; dos emisores reducen esa cobertura. A cinco segundos y dos emisores se ve aproximadamente ocho minutos. Pedir siete días no devuelve siete días representativos. El fallback a lecturas antiguas puede aparentar frescura. Devolver timestamps completos, cobertura real y agregación por buckets; preservar mínimos/máximos y puntos de eventos.
- **Device Hub:** offline a los 120 segundos contradice un periodo nominal de cinco minutos. El umbral debe derivarse del periodo esperado más tolerancia; batería/RSSI desconocidos deben permanecer desconocidos. El frontend añade un dispositivo ficticio y simula ping/reinicio sin ejecución real.
- **Reglas:** se construyen claves `valor_leido`/`descripcion` y se leen `valor_actual`/`mensaje`; se pierden valor y explicación. También difieren nombres `temperatura_alta` y `temp_alta`. El fallback al primer perfil activo ignora la pertenencia. Centralizar enum/contrato y probar el evento persistido, no únicamente que exista una fila.
- **Deduplicación:** cooldown de 15 minutos permite repetir alertas del mismo episodio persistente. La deduplicación ML es mejor —busca alerta activa— pero sigue sin garantía transaccional de unicidad y recuperación. Implementar episodio único, histéresis, tiempo de persistencia y escalamiento.
- **Estado de alertas:** repetir atención/resolución reescribe timestamps y altera métricas. Separar eventos inmutables y estado actual; transiciones válidas e idempotentes; autor derivado de sesión. La resolución administrativa no prueba recuperación biológica.
- **MTTR:** el numerador omite fechas ausentes, pero el denominador incluye todas las resueltas; eso puede reducir artificialmente la media. El código limita duraciones negativas a cero, ocultando problemas de cronología. Informar exclusiones y datos inválidos. Calcular MTTA, tiempo de resolución, edad de pendientes y percentiles, con el mismo filtro temporal/tenant/origen en KPI, tabla y exportación. Separar métricas físicas y simuladas.
- **CSV:** exportación real, pero sin política suficiente para grandes volúmenes ni neutralización de fórmulas en campos de texto. No permitir que exportar suponga cargar todo el histórico en memoria; aplicar autorización y filtros idénticos.
- **Frontend de alertas:** condición `id < 1000` para llamar API; casos de IDs superiores se actualizan localmente. Sensor aislado y verificaciones manuales también pueden ser solo estado de pantalla. No equiparar silencio de alertas con cuarentena de un sensor.
- **Umbrales UI:** asignar perfil a cuba cambia estado local y muestra éxito, sin persistencia equivalente. Campos avanzados como duración de estancamiento o límites de inclinación no viajan al backend. El mapeo espera un objeto de proceso/perfil que el DTO de cuba no contiene.
- **Modales:** varios cierres exitosos se llaman mientras `isAssigning`, `isUnlinking`, `isCreating` o `isDeleting` siguen activos; el propio cierre retorna sin cerrar. Finalizar estado de carga antes del cierre o separar cierre interno y cancelación.
- **Bitácora:** resolver cuba por dígitos y coincidencias parciales de código es ambiguo. Usar IDs explícitos de proceso, incidente e intervención. Una lectura manual requiere campos estructurados, unidad, método y evidencia; no solo texto.
- **Auth:** PBKDF2 existe, pero implementación propia y comparación ordinaria; revisar biblioteca mantenida y parámetros. Tokens largos sin revocación/refresh; recuperación declara envío sin entregar un flujo real. Crear usuario no envía una invitación utilizable. Evitar mensajes que revelen existencia de cuentas.
- **Polling y errores:** llamadas solapadas, respuestas fuera de orden y errores silenciosos pueden mantener información antigua como actual. Cancelar solicitudes al cambiar de cuba, impedir solapamientos y mostrar edad/calidad/error. El interceptor Axios pierde detalles al sustituir el error por uno genérico.

### 3.3 Arquitectura objetivo y modelo de datos

Conservar un monolito modular: routers → servicios de aplicación → repositorios/transacciones → PostgreSQL. Separar módulos `identity`, `assets`, `fermentation`, `telemetry`, `quality`, `prediction`, `incidents`, `interventions` y `simulation`; worker independiente del proceso HTTP. Generación/entrenamiento offline en paquete versionado. UI consume DTOs explícitos, sin inferir reglas de negocio de textos o IDs.

Añadir mediante migraciones: credenciales de dispositivo; versiones de calibración; origen autorizado y canales; evento de lectura con identidad/idempotencia/calidad; estado persistente de simulación; configuración efectiva/versionada por proceso; predicciones y puntos de forecast; episodios y eventos de alerta; intervenciones y mediciones manuales; outbox y entregas de notificación. Mantener claves de empresa/bodega y restricciones compuestas coherentes. No duplicar valores derivados sin su versión/metodología.

Flujo objetivo: **lectura → calidad → features → predicción/regla → episodio → responsable → intervención → observación de recuperación → cierre documentado**. Una recomendación es una propuesta, una intervención es una acción confirmada, y una recuperación es una observación posterior; son entidades distintas.

Los procedimientos DSS deben comenzar verificando sensor, calibración y contexto del lote, luego revisar condiciones térmicas y solicitar comprobación enológica cuando corresponda. Con dos variables no se deben prescribir automáticamente adiciones ni afirmar una causa nutricional. Registrar responsable, motivo, acción, hora y respuesta de la curva.

### 3.4 Despliegue, rendimiento y documentación

Compose usa backend con reload y simulador habilitado sobre la misma configuración de base; `depends_on` no acredita readiness. Separar perfiles demo/desarrollo/producción, impedir simulación accidental sobre datos reales, añadir health/readiness, migración como paso explícito, configuración obligatoria, logs estructurados, métricas y backup con restauración ensayada.

Las dependencias Python tienen rangos abiertos sin lock compatible con el pickle. El frontend sí dispone de lockfile, pero no hay scripts de pruebas/lint. El build correcto no verifica lógica, accesibilidad ni permisos. No se realizó un escaneo completo de vulnerabilidades de dependencias ni una prueba de penetración.

A cinco minutos, un nodo produce 288 observaciones/día; veinte cubas producen 2.102.400/año. Un único PostgreSQL con índices `(tenant/proceso, observed_at)` y consultas acotadas puede ser una base razonable; decidir particionado y agregados después de medir. Evitar importar Timescale o infraestructura adicional sin necesidad demostrada. El backlog exige menos de dos segundos con volumen anual: hay que probarlo con datos representativos, no presumirlo por contar con índices.

La documentación académica contiene objetivos de +15–20 % de producción, −20 % de mermas y −60 % de tiempo manual. Son hipótesis de impacto que necesitan línea base y estudio operativo; no son resultados demostrados por una demo. Actualizar la trazabilidad de 40 HU: seguridad por bodega, credenciales IoT, overrides, invalidación de lecturas, procesos cerrados, notificaciones y reportes siguen incompletos. Retirar referencias de hardware/variables antiguas sin borrar la trazabilidad histórica. Las guías duplicadas de conexión deben tener una fuente única.

## 4. Diagnóstico y rediseño UI/UX

### 4.1 Crítica del estado actual

El rediseño existente no es ausencia de diseño: tiene iconos coherentes, tarjetas, componentes Chart.js, filtros, navegación y dual eje en detalle. Hay trabajo recuperable. Su orientación explícita a un dashboard SaaS genérico produce una jerarquía poco enológica: ranking, índice global y grandes indicadores compiten con las decisiones reales de una bodega.

El problema más serio es semántico. El dashboard combina valores actuales con series históricas fijas, comparativas y variaciones decorativas; la salud global se deriva de fórmulas sin validación. La cabecera dice “En vivo” sin depender de la edad de cada señal. El panel de IA muestra el nombre del algoritmo, un gauge dominante y umbrales técnicos; faltan horizonte, cobertura, evidencia y acción útil. El botón de simulación aparece dentro del flujo operacional. La curva relevante queda desplazada hacia abajo.

La vista de detalle ya tiene dos ejes: hay que mejorarla, no prometerla como algo totalmente inexistente. Al alternar variables, el camino de actualización conserva metadatos del dataset si no cambia su cantidad; debe recrear/actualizar etiquetas, color y eje además de los puntos. Los labels horarios sin tiempo absoluto distribuyen visualmente igual intervalos que pueden ser distintos.

Los archivos grandes concentran demasiadas responsabilidades: `CubaDetailView.vue` tiene 3.796 líneas, `AlertsView.vue` 2.295 y `DevicesView.vue` 2.243. Se inspeccionaron scripts, templates y estilos de los 13 SFC; hay aproximadamente 179.536 caracteres de CSS dentro de ellos, además del global. El problema no es una cifra aislada, sino duplicación de modales, colores, reglas y estados.

En navegador local con fixtures, las nueve pantallas de escritorio no desbordaron el ancho de 1.536 px. A 390 px, el dashboard produjo **702 px de ancho de contenido**, con sidebar permanente y zona útil recortada. Es un defecto responsive observado, no una preferencia estética. Las capturas usaron fuentes de respaldo al bloquear recursos externos; no se evaluó la tipografía remota final.

Capturas de referencia —datos de prueba, no telemetría real—:

- [Dashboard actual](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/ui-dashboard.png)
- [Detalle actual](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/ui-detail.png)
- [Auditoría con incidentes ficticios pese a API vacía](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/ui-audit.png)
- [Desbordamiento móvil](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/ui-mobile.png)

### 4.2 Dirección visual

Proponer una identidad de bodega técnica: fondo marfil frío `#F5F3EF`, superficies `#FFFFFF`, texto grafito `#20262D`, marca borgoña `#76263D`, Brix ámbar `#B97716`, temperatura azul `#277C9D`. Riesgo usa semántica independiente de la marca: verde oscuro, ámbar y rojo accesibles; desconocido gris. Estos colores son punto de partida sujeto a medición de contraste, no certificación WCAG.

Tipografía sans legible, números tabulares y unidades consistentes; escala de espacios de 4/8 px; bordes discretos y profundidad reservada a agrupación/interacción. Evitar rojo de marca para elementos normales que compitan con alertas. No convertir el producto en una ilustración temática de vino; su identidad debe venir también del vocabulario y los datos.

### 4.3 Arquitectura de información

1. **Bodega en vivo:** qué lotes requieren atención, qué datos están atrasados y qué cambió desde la última revisión.
2. **Fermentaciones:** activas y cerradas, con búsqueda por lote/cuba/variedad y comparación válida.
3. **Incidentes:** cola priorizada, responsable, evidencia, acción y recuperación; auditoría como otra vista del mismo dominio.
4. **Dispositivos:** real/simulado, asignación, salud, calibración y diagnóstico.
5. **Perfiles y administración:** permisos adecuados, versiones y configuración efectiva.

La bitácora contextual pertenece al lote; puede conservar una vista global de consulta. “Detalle de cuba” no debe ser un destino vacío fijo en la navegación. La cuba es el contenedor; la fermentación concreta es la unidad temporal de análisis.

### 4.4 Pantallas y componentes propuestos

**Vista general:** franja compacta de cubas activas, incidentes prioritarios, dispositivos atrasados y cobertura de datos. Tabla operacional con cuba/lote, fuente, Brix aparente, tasa en °Bx/h, temperatura frente a perfil, fase estimada, riesgo con horizonte, última lectura y responsable. Sparkline de curva real con gaps. Ordenar por necesidad de intervención; “desconocido” no cuenta como sano. Comparar solo perfiles/etapas compatibles; mostrar tamaño de muestra y datos ausentes.

**Detalle de fermentación:** encabezado con lote, volumen, edad, dispositivo, fuente y estado. Curva principal inmediatamente visible: Brix y temperatura sobre eje temporal UTC presentado en hora local, tooltips sincronizados, zoom/rango, bandas de perfil, eventos/intervenciones y fase estimada con incertidumbre. Observado sólido; forecast discontinuo, inicio claramente delimitado y bandas calibradas. No interpolar huecos largos como si hubiera mediciones.

Al lado, tarjeta de decisión compacta: “riesgo de parada en próximas 12 h”, validez/calidad y dos o tres evidencias; estado “sin evaluación fiable” cuando proceda. Acción para abrir incidente o registrar revisión. Los detalles de algoritmo/versión se despliegan en una ficha técnica secundaria. Debajo: cinética y contexto, bitácora correlacionada y datos exportables.

**Incidente:** timeline inmutable de detección, evidencia, atención, intervención, evolución y cierre. Distinguir resuelto administrativamente, recuperación observada, descartado por dato inválido y reabierto. No ofrecer una casilla local de “sensor aislado” que simule un cambio de ingesta.

**Dispositivo:** una tarjeta para el ESP32 con sus dos canales, curva de calibración, fecha/versión, señal y frescura reales. Cubas virtuales agrupadas con escenario, velocidad de simulación y estado. Un controlador de escenario separado del detalle físico evita confusión durante la demostración.

**Configuración:** enseñar origen de cada umbral —perfil, override, versión—, vista previa de su impacto sobre historia y auditoría del cambio. No mostrar controles editables sin soporte backend.

Extraer `FermentationChart`, `RiskAssessment`, `TelemetryQuality`, `SourceBadge`, `IncidentTimeline`, `MetricCard`, `DataTable`, `ModalDialog` y composables para datos/polling. Contratos tipados pueden incorporarse gradualmente, sin reescribir toda Vue. Probar foco/teclado, etiquetas, Escape, lectores de pantalla, contraste y estados vacíos/error/carga. En móvil: navegación plegable, priorización de indicadores y tabla con presentación adaptada; no encoger toda la interfaz de escritorio.

## 5. Hoja de ruta de implementación

Los sprints se ordenan por dependencias y tienen puertas de aceptación. Son unidades de entrega, no promesas de duración sin conocer disponibilidad del equipo/calendario. Puede alinearse cada uno con ciclos de una o dos semanas según capacidad, reduciendo alcance secundario antes de debilitar las garantías fundamentales.

| Sprint | Entregable | Criterio verificable para cerrar |
|---|---|---|
| 0 — Contención y reproducción | Configuración segura, retirar fallbacks demo operacionales, inventario de secretos, lock de dependencias, entorno PostgreSQL de pruebas y CI mínima | Arranque limpio reproducible; pruebas nunca conectan a base real; secreto obligatorio; demo aislada; baseline de fallos documentado |
| 1 — Identidad y esquema | Migraciones, rol DB limitado, autorización por empresa/bodega, membresías y actores reales | Matriz negativa entre dos empresas y roles; mismo esquema desde cero; ningún endpoint de negocio público; último administrador protegido |
| 2 — Dispositivos e ingesta | Nodo único dual, credenciales, calibración, timestamps, calidad, idempotencia y outbox | Reenvío no duplica; dispositivo ajeno/inactivo rechazado; missing no se inventa; proceso cerrado no se recrea; cambios de asignación respetan tiempo |
| 3 — Procesos, incidentes y bitácora | Máquina de estados, perfil versionado/override, reglas cinéticas base, episodios, intervenciones y métricas coherentes | Un episodio por condición persistente; atención/resolución idempotentes; identidad real; MTTR reproducible; historia cerrada consultable |
| 4 — Simulación científica | Motor continuo, escenarios sanos/frío/calor/nutrientes/lento/sensor, persistencia y reloj acelerable | Sin saltos injustificados; semilla reproducible; reinicio conserva continuidad; fuente simulada visible; no puede escribir en dispositivo físico |
| 5 — ML y forecast | Generación etiquetada, features causales, entrenamiento reproducible, baselines, calibración y model card | Splits por proceso y escenarios; tests de leakage/invariancia temporal; reporte de métricas/horizonte; abstención; forecast comparado con baseline |
| 6 — UI operacional | Sistema visual, overview, detalle de curvas, incidentes, dispositivo/calibración y estados fiables | Todos los controles persistentes verificados; sin cifras ficticias; desktop/móvil/teclado; curva con tiempo real, forecast y procedencia |
| 7 — DSS e integración física | Recomendaciones trazables, intervención/seguimiento, ESP32 conectado, tolerancia a cortes | Flujo completo de dato físico a revisión registrada; reconexión sin duplicados; calidad/calibración visible; causas expresadas como hipótesis |
| 8 — Entrega y validación | Rendimiento, observabilidad, backups, despliegue, manual, matriz de requisitos y defensa técnica | Restauración ensayada; carga objetivo medida; build reproducible; casos críticos E2E; limitaciones científicas explícitas |

### Puertas específicas de ML

No fijar ahora accuracy arbitraria como aceptación. Antes de entrenar, acordar el evento, horizonte, mínimo de anticipación útil y presupuesto de falsas alarmas. Después publicar resultados por escenario, proceso y origen. Una demo debe superar baselines en un conjunto reservado y mostrar fallos conocidos. Habilitar ML sobre el prototipo inicialmente en **modo observación**, sin desplazar reglas deterministas ni decisiones del enólogo. La validación industrial requiere más de un lote/prototipo; un prototipo prueba integración y metrología, no generalización poblacional.

### Pruebas de mayor valor

- Dos usuarios/empresas intentando acceder a todos los recursos y mutaciones ajenas.
- Concurrencia de inicio de proceso, reasignación y creación de episodios; respuestas de conflicto controladas.
- Reenvíos, eventos fuera de orden, reinicio del ESP32, reloj inválido, desconexión y retorno.
- Una variable ausente, sensor retenido, valores fuera de rango y calibración nueva; no convertirlos en valores normales.
- Finalización seguida de nueva telemetría; preservación del lote cerrado y ausencia de reapertura implícita.
- Trayectoria física equivalente muestreada a frecuencias diferentes; features en horas coherentes y decisiones estables dentro de tolerancia.
- Lag sana, fin normal, lenta sin parada, parada sin choque térmico y choque sin parada: controlar falsos positivos y confusión causal.
- IDs de alertas por encima de 1000, repetición de resolución y exportación con filtros idénticos.
- API vacía/caída: pantallas vacías o degradadas explícitas, nunca auditoría inventada.
- Reinicio de simulador/worker, reintento de outbox y fallo ML tras ingesta: no pérdida ni duplicación de lectura/episodio.

### Flujo Git propuesto tras aprobación

Conservar intacta la evidencia `c310b91` y el cambio local previo. Cada sprint debe producir una rama pequeña desde la base de integración acordada, usando el prefijo habitual del equipo si se mantiene `feat/...`, con migraciones y pruebas del comportamiento incluido. Evitar un merge masivo que mezcle reparación de seguridad, cambio científico y nueva UI. Cada PR describe problema, comportamiento final, evidencia y límites; `develop` integra únicamente cuando pasa su puerta. La integración del hardware puede prepararse con el contrato desde el sprint 2, sin esperar la electrónica para desarrollar el resto.

### Definición de terminado del proyecto

Una bodega demo de N cubas y el prototipo real conviven con procedencia inequívoca; cada lectura tiene identidad, tiempo y calidad; cada lote conserva su historia; cada alerta conserva evidencia y responsables; las métricas se recalculan desde eventos verificables; UI y API comparten reglas; el modelo se reproduce y declara qué puede y qué no puede predecir. El sistema debe poder instalarse, observarse, respaldarse y recuperarse. “Blindado” debe traducirse en estas garantías probadas, no en una afirmación de cero errores.

## Evidencia de validación realizada

| Comprobación | Resultado | Interpretación |
|---|---|---|
| `pytest` aislado | 6 aprobadas, 9 fallidas, 90 warnings | La suite no es reproducible limpia; fixtures/usuarios/IDs esperados y divergencia SQLite causan varios fallos. No equivale a nueve regresiones productivas distintas |
| Pruebas ML puras existentes | 4 aprobadas | Demuestran ejemplos puntuales, no capacidad predictiva independiente |
| Build Vue/Vite | Correcto, 1669 módulos | Verifica compilación, no comportamiento ni permisos |
| OpenAPI inspeccionado | 45 operaciones; solo `/api/auth/me` declara seguridad | Corroborado con lectura del código y GETs sin token en base aislada |
| GETs sin token | Cubas, dispositivos, usuarios y alertas devuelven 200; `/me` 401 | Defecto comprobado de autorización en el entorno aislado |
| Playwright local con fixtures | 9 pantallas + móvil, sin errores JS capturados; 53 solicitudes interceptadas, ninguna mutación | Verificación visual controlada; no prueba E2E contra backend |
| Móvil 390 px | Contenido de 702 px | Desbordamiento confirmado |
| Esquema PostgreSQL | Inspección de lectura completada | Restricciones/RLS/rol reales contrastados con ORM; sin modificación |
| Git | Solo modificación previa en README ML | No se cambiaron fuentes ni se hicieron commits/merges |

Los tests actuales importan la aplicación y sus conexiones: ejecutarlos sin sobrescribir `DATABASE_URL` puede tocar la base configurada y producir usuarios, cambios de configuración o datos demo. La ejecución de esta auditoría los aisló deliberadamente. Los logs completos, sondas de modelo, esquema y capturas quedan junto al informe; no incluyen valores de credenciales.

## Archivos de apoyo

- [Anexo de cobertura por archivo, ramas y endpoints](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/Anexo_Cobertura.md)
- [Inventario con tamaños y hashes](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/inventory.json)
- [Resultados de pruebas](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/pytest.txt)
- [Sondas controladas del modelo](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/model-probes.json)
- [Inspección de esquema PostgreSQL](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/pg-schema.json)
- [Resultados de inspección visual](C:/Users/administradorere/.codex/visualizations/2026/11/14/01a1dad7-3c48-7fa3-87ff-5e92e2c2e28c/mosto-audit/visual-results.json)

Fuentes principales: [PDF adjunto SmartBarrel](C:/Users/administradorere/Downloads/smartbarrel.pdf), código de Mosto en `C:/mosto`, documentación académica versionada y referencias primarias enlazadas en el cuerpo. Las propuestas de arquitectura y umbrales de evaluación se identifican como decisiones de diseño, no como resultados ya obtenidos.

## Localizadores de evidencia en código

- [Contrato de inferencia y pendientes](C:/mosto/backend/app/services/ml_service.py:45)
- [Predicción y endpoints demo](C:/mosto/backend/app/routers/cubas.py:335)
- [Reglas e integración ML](C:/mosto/backend/app/services/rules_engine.py:1)
- [Ingesta y conversión](C:/mosto/backend/app/services/telemetry_service.py:1)
- [Dependencia de identidad](C:/mosto/backend/app/services/auth_service.py:74)
- [MTTR](C:/mosto/backend/app/routers/alerts.py:197)
- [Bitácora y siembra](C:/mosto/backend/app/routers/binnacle.py:1)
- [Alertas con límite de ID](C:/mosto/frontend/src/views/AlertsView.vue:367)
- [Fallback de auditoría](C:/mosto/frontend/src/views/AlertsAuditView.vue:508)
- [Pendiente expresada por muestra](C:/mosto/frontend/src/views/CubaDetailView.vue:1509)
- [Contrato de cuba/histórico](C:/mosto/backend/app/schemas.py:103)
