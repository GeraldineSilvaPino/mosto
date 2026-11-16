# Simulador continuo de fermentación

Entrega local, 15-11-2026. Sustituye las inyecciones puntuales por trayectorias persistentes que se transmiten por la API HTTP v2. No conecta ni modifica Supabase. La ingesta integra ahora [episodios térmicos v2](ALERTAS_V2_Y_EPISODIOS.md); el hardware físico y el nuevo entrenamiento ML siguen pendientes.

## Qué está implementado

- Cinco escenarios: evolución sana, choque por frío, estrés por calor, agotamiento de nutrientes y fermentación lenta.
- Transiciones suaves de fase, descenso continuo de Brix aparente, acoplamiento térmico, variación entre semillas y ruido gaussiano de medición.
- Worker independiente del servidor FastAPI, con cola persistente, reintentos idempotentes, reanudación y bloqueo de doble ejecución sobre el mismo estado.
- Configuración congelada por versión de calibración sintética; vínculo al dispositivo, proceso e instante de inicio.
- Consulta autenticada de configuración por el emisor; consulta de procedencia por usuarios autorizados y visualización de fase programada en Vue.
- Inicializador explícito de una bodega local con cinco cubas simuladas y una reserva física inactiva, sin lecturas ni calibración ficticia para el ESP32.

No se ejecuta una tarea de simulación en cada worker de Uvicorn ni al consultar una pantalla. Cerrar el navegador no detiene el emisor; detener el emisor no detiene la API. La cadencia física no depende del polling de Vue.

## Relación con SmartBarrel y alcance científico

El adjunto corresponde al preprint de Kontogiannis et al., con funciones de pertenencia de fase y cinéticas exponenciales en sus ecuaciones 16–20. Su generador mantiene la temperatura alrededor de un valor nominal con ruido; **no proporciona el modelo de fallas térmicas de Mosto**. También existe una [publicación posterior en Sensors](https://doi.org/10.3390/s25133877); la referencia de adaptación utilizada aquí es el [preprint adjunto, sección 3.6](https://www.preprints.org/manuscript/202505.2143/v1).

El código es un **modelo cinético y térmico simplificado**, inspirado en esas ideas. No implementa ni entrena el fuzzy autoencoder ni el V-LSTM del artículo. Sus parámetros son hipótesis de simulación explícitas, no constantes calibradas en nuestra bodega.

En particular, Brix aparente derivado de flotabilidad no equivale automáticamente a azúcar residual. La variable interna del generador también está expresada en Brix aparente: no es una masa de azúcar ni una concentración de nutrientes medida. Las curvas permiten ejercitar ingesta, gráficos, reglas y, posteriormente, experimentos ML con procedencia conocida; no validan precisión enológica real.

## Modelo `mosto-phases-1`

El paso de integración es fijo: `Δt = 1/12 h`. El calendario de fases toma como referencia las transiciones de 20, 70 y 150 horas, suavizadas en 15–25, 65–80 y 145–170 horas. Se utiliza `smoothstep(x)=3x²−2x³`, acotado entre 0 y 1. Las cuatro pertenencias suman uno; la fase mostrada es la de mayor pertenencia. Es una fase **programada**, incluso si el escenario lento o una falla alteran la evolución de Brix.

Las tasas base por fase son `0,0003 / 0,020 / 0,015 / 0,004 h⁻¹`, combinadas por esas pertenencias. Una semilla fija selecciona una escala de tasa entre 0,88 y 1,12, una constante de intercambio térmico entre 2,5 y 4 horas y el desfase ambiental.

```text
k_eff = k_fase · escala · factor_térmico · viabilidad · nutrientes · lentitud
factor_térmico = exp(−((T − 24)/9)²)
B_siguiente = B_asíntota + (B_actual − B_asíntota) · exp(−k_eff · Δt)
viabilidad_siguiente = viabilidad · exp(−max(0, T − 32) · 0,06 · Δt)
T_siguiente = T_entorno + (T_actual − T_entorno) · exp(−Δt/τ)
              + 1,5 · (B_actual − B_siguiente)
```

La temperatura ambiental incorpora una oscilación diaria de amplitud 0,5 °C. El término térmico final aproxima calor asociado al consumo dentro de este modelo; no constituye un balance energético calibrado con geometría, masa y refrigeración reales. Brix evoluciona sin saltos de nivel en las fronteras de fase y sin crecimiento del estado interno. Las observaciones sí pueden subir ligeramente por ruido.

| Escenario | Alteración programada |
| --- | --- |
| `healthy` | Evolución nominal |
| `cold_shock` | El entorno baja 13 °C; la supresión térmica reduce la tasa |
| `heat_stress` | El entorno sube 17 °C; además se acumula pérdida de viabilidad |
| `nutrient_depletion` | El factor de nutrientes cae de 1 a 0,002; la temperatura puede permanecer normal |
| `slow` | Multiplicador de velocidad 0,30 desde el inicio |

Las fallas tienen una rampa suave de seis horas desde `fault_at_hours`. La viabilidad no se recupera automáticamente en el escenario de calor. El factor de nutrientes es una causa latente del escenario, **no algo identificable de forma unívoca midiendo solo temperatura y Brix**.

Por defecto se observan Brix con desviación 0,025 °Bx y temperatura con desviación 0,06 °C. El ruido se añade después de evolucionar el estado interno, usando una secuencia pseudoaleatoria determinista por versión, semilla e índice. Reenviar una muestra no genera otro ruido. Las trayectorias tienen horizonte explícito de hasta 720 horas; el predeterminado es 336 horas. Al completarlo, el worker marca `completed` y no cierra el proceso de negocio.

## Reloj y carga histórica

Se utiliza exclusivamente tiempo de pared UTC, a velocidad **1×**. Para cada índice:

```text
observed_at = process_start + sequence · 300 segundos
```

El worker no emite fechas futuras. La API comprueba que la receta corresponde al mismo proceso, que su inicio coincide y que secuencia/hora están dentro del horizonte. Una reasignación del dispositivo no traslada el escenario a otro proceso. Un proceso cerrado sigue admitiendo muestras retrasadas de su intervalo histórico; las posteriores al cierre se rechazan y el emisor queda bloqueado hasta una revisión explícita.

La demostración evita esperar días creando procesos sintéticos con edades iniciales de 8, 50, 85, 120 y 175 horas. El worker genera su historial pasado y, al ponerse al día, espera la siguiente muestra de cinco minutos. `received_at` siempre indica cuándo la API recibió cada paquete: cargar pasado no finge una recepción histórica. Esos paquetes aparecen como retrasados según el contrato v2.

No existe todavía reproducción acelerada. Una aceleración futura debe tener un reloj de simulación independiente y visible; no puede lograrse cambiando cinco minutos físicos por cinco segundos manteniendo etiquetas temporales incorrectas.

## Persistencia, seguridad y recuperación

La receta se guarda en `CALIBRACION_DISPOSITIVO.parametros.simulation`, usando el JSON e inmutabilidad de la revisión `0003_telemetry_v2`. No se requiere una migración adicional de tablas. Una calibración física rechaza esa receta. Las versiones sintéticas antiguas sin receta siguen siendo compatibles con la ingesta, pero no habilitan este worker.

Antes del primer POST de cada dispositivo, el emisor consulta `GET /api/v2/telemetria/configuracion/{device_id}/{calibration_id}` con su clave individual. Exige origen simulado y coincidencia exacta de receta. El endpoint nunca devuelve secretos. La API comprueba nuevamente autenticación, vigencia, calibración, calidad y vínculo temporal al aceptar cada muestra.

El manifiesto `fleet.json` no contiene claves: referencia nombres de variables `MOSTO_SIM_DEVICE_*`. `device-keys.env` es privado y se crea fuera del contenido versionado. En POSIX se solicita modo 0600; en Windows la privacidad depende también de las ACL heredadas del directorio. El worker no recibe credenciales de base de datos ni JWT administrativo. Este lanzador de demostración admite únicamente orígenes HTTP locales explícitos (`127.0.0.1`, `localhost` o el servicio `backend`) y no sigue redirecciones.

El SQLite del emisor tiene:

- `runs`: receta, siguiente secuencia, estado, fallos y siguiente reintento.
- `outbox`: sobre exacto, estado interno sintético separado y comprobante de aceptación.
- `metadata`: origen de API asociado al archivo de estado.

Antes de enviar se confirma la escritura en la cola. Solo después de una respuesta válida 200/201 se guarda el comprobante y avanza la secuencia. Si la API guarda pero la respuesta se pierde, el mismo mensaje se reenvía; la idempotencia del servidor devuelve el comprobante original. El UUID de emisión es estable por receta/dispositivo/calibración, por lo que recrear accidentalmente el estado con la misma configuración tampoco duplica las muestras del servidor.

Errores de red, 408, 425, 429 y 5xx usan espera creciente hasta 60 segundos. Credenciales ausentes/revocadas, receta incompatible y rechazos permanentes bloquean solo ese dispositivo. Los demás continúan. Después de corregir la causa se usa `--retry-blocked`; no se cambia automáticamente de cuba, identidad o calibración para esquivar un rechazo.

El CLI mantiene un bloqueo del sistema operativo sobre su estado; se libera al terminar o caer el proceso. No se borra un archivo `.lock` para recuperar una ejecución. No compartir un estado entre bases/API distintas ni editar las recetas a mitad de ejecución. Cambiar el modelo numérico requiere una nueva versión y nuevas recetas; no se presenta la reproducibilidad entre versiones distintas de Python como identidad binaria garantizada.

## Ejecución local

Desde `C:/mosto/backend`, con el entorno virtual y dependencias del backend instalados:

1. Copiar `.env.simulation.example` a `.env.simulation`. Elegir una base **nueva**, con prefijo `mosto_demo`, y completar `JWT_SECRET_KEY` y `MOSTO_SIMULATOR_KEY` con secretos aleatorios de al menos 32 bytes, y una contraseña demo de al menos 12 caracteres. No reutilizar `backend/.env`.
2. Preparar una sola vez la bodega; el comando rechaza bases no vacías y directorios de salida existentes:

```powershell
python -m scripts.init_simulation_demo --env-file .env.simulation --output artifacts/simulation-fleet --base-url http://127.0.0.1:8000
```

3. Arrancar la API:

```powershell
python -m uvicorn app.main:app --env-file .env.simulation --host 127.0.0.1 --port 8000
```

4. En otra terminal, arrancar el worker. Primero carga pasado y después continúa en vivo:

```powershell
python -m scripts.simulate_v2 --manifest artifacts/simulation-fleet/fleet.json --env-file artifacts/simulation-fleet/device-keys.env --state artifacts/simulation-fleet/emitter.db --batch 100
```

5. Arrancar Vue desde `frontend` con `npm run dev`. Iniciar sesión como `demo@example.invalid`, usando la contraseña elegida. Device Hub muestra cinco simulados y una reserva física. El detalle presenta la curva y las pertenencias de fase.

`--once` ejecuta un lote acotado por dispositivo y termina. `--drain` carga las muestras vencidas hasta ponerse al día o encontrar errores y termina; no acelera el reloj. Ctrl+C detiene limpiamente el worker. Repetir el mismo comando con el mismo archivo de estado reanuda; no volver a inicializar la bodega.

La reserva física se crea inactiva, sin clave ni calibración. Su futura puesta en servicio exige activar el dispositivo, emitir su credencial y registrar una calibración obtenida del prototipo, mediante el flujo de [telemetría v2](TELEMETRIA_V2.md). El worker nunca incluye ese dispositivo en su manifiesto.

El inicializador confirma los fixtures y el aprovisionamiento en una transacción; las migraciones se aplican antes. Si falla la escritura de archivos, se conserva cualquier salida parcial para inspección y no se sobrescribe al reintentar. Los secretos del entorno del proceso tienen precedencia sobre el archivo explícito, de acuerdo con la configuración existente: revisar variables antiguas antes de lanzar otra demo.

## Visualización y contrato histórico

`GET /api/simulaciones/procesos/{id}` requiere JWT y acceso al proceso. Expone versión, escenario, semilla, cadencia, edad de la última observación, pertenencias de fase y retraso. No es un clasificador de fallas. `Historial al día` describe cobertura temporal, no certifica que un worker siga vivo. Una detención se hace visible al crecer el retraso.

Vue presenta cuatro fases con sus pertenencias y diferencia una carga histórica atrasada de datos al día. La fase corresponde a la última observación, no a una fecha futura calculada en el navegador. Los datos físicos no reciben una fase sintética. Riesgo ML continúa como N/D; las desviaciones térmicas sostenidas generan episodios persistidos con MTTR de gestión y evidencia separada de recuperación.

El histórico ya no recorta silenciosamente a 200 muestras ni rellena una ventana vacía con datos antiguos. Admite de 1 a 168 horas, incluye timestamps ISO 8601 con UTC y conserva etiquetas legibles separadas. Hay un límite explícito de 10.000 puntos, suficiente para siete días a cinco minutos; si se supera por mayor frecuencia, devuelve `truncated: true` y Vue lo informa. No interpola muestras ausentes ni inventa pH.

## Validación y siguientes bloques

Las pruebas cubren continuidad, pertenencias normalizadas, dinámica latente monótona, ruido reproducible, efectos térmicos frente a agotamiento de nutrientes, cadencia, reinicios, respuestas perdidas, revocación, aislamiento entre empresas, bloqueo de configuraciones físicas, reasignación, cierre, límites temporales, conexión HTTP persistente y rechazo de redirecciones.

La prueba de navegador utiliza el CLI real de inicialización, el worker HTTP, FastAPI, SQLite y el build Vue, sin respuestas API inventadas. Carga las cinco trayectorias, comprueba las fases, reinicia el worker y verifica cero lecturas en la reserva física. PostgreSQL se verifica adicionalmente con la suite en un clúster temporal; el navegador no certifica un despliegue PostgreSQL remoto.

Resultados finales: **125 pruebas aprobadas en PostgreSQL 18.4** (58,51 s; 1.579 avisos de deprecación) y **118 aprobadas, 7 omitidas en SQLite** (27,07 s; 1.496 avisos). Build Vite correcto. El navegador verificó el historial completo de 288 puntos por 24 horas, las fases programadas de las cinco cubas según sus edades, reanudación y cero lecturas físicas, sin errores JavaScript ni respuestas API de error. El estado final contiene 5.266 mensajes canónicos simulados. Capturas y resultado JSON: `mosto-audit/simulation-*-live.png` y `simulation-browser-results.json`, en el directorio externo de la auditoría.

Docker/Compose no se ejecutaron; se corrigió el Dockerfile para incluir Alembic y sus revisiones, necesarios para inicializar y comprobar el esquema. No se modificó Supabase ni se ejecutó commit, merge o push. CSV, pickle y cambio previo del README de ML se verificaron intactos por SHA-256.

Pendiente: reglas cinéticas y seguimiento estructurado de intervenciones, dataset de trayectorias con partición por fermentación, validación de riesgo futuro y forecast, fallas de sensores y comunicaciones programables, calibración/hardware real, MQTT, reloj acelerado explícito y rediseño integral. Las cinco recetas de demostración no constituyen por sí solas un dataset de entrenamiento suficiente ni una validación externa.
