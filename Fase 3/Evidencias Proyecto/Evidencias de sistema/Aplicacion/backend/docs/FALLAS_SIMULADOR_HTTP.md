# Fallas programables del emisor HTTP

Implementación local del 17-11-2026. Contrato `emitter-faults-v1`, exclusivo de trayectorias sintéticas. Complementa el [ensayo ML offline](ROBUSTEZ_PIPELINE_ML.md): permite comprobar la ingesta real, la cola persistente y la recuperación de comunicaciones. No cambia el modelo biológico `mosto-phases-1`, sus semillas ni los artefactos ML congelados. El riesgo y forecast operacionales continúan N/D.

## Receta y reloj

Cada calibración sintética puede guardar `parametros.emitter_faults`, también presente en el manifiesto del emisor. Requiere `synthetic_identity` y una receta `simulation`; se rechaza en calibraciones físicas. Los endpoints de configuración del dispositivo y procedencia del proceso exponen el plan dentro de sus permisos existentes. No hay formulario nuevo en Vue.

Un plan contiene de 1 a 100 eventos, con `start_sequence` inclusivo y `end_sequence` exclusivo. La secuencia cero corresponde al inicio del proceso y cada paso son cinco minutos físicos. Se valida el horizonte y se rechazan intervalos vacíos y superposiciones en un mismo canal o transporte. Brix, temperatura y transporte pueden fallar simultáneamente. Los eventos se ordenan canónicamente para estabilizar la identidad del emisor.

| `kind` | Efecto observable |
| --- | --- |
| `brix_missing` | Brix null y calidad `missing`; temperatura independiente |
| `temperature_missing` | Temperatura null y calidad `missing`; Brix independiente |
| `brix_frozen_unflagged` | Repite el Brix de la trayectoria limpia en `start_sequence - 1`; mantiene `good` para ejercitar un sensor que no declara su falla |
| `brix_drift_unflagged` | Suma `(sequence - start_sequence) / 12 * drift_brix_per_hour`; mantiene `good` |
| `communication_outage` | Suprime los POST del dispositivo durante el intervalo y conserva los sobres pendientes |
| `delivery_delay` | Retiene cada sobre hasta `observed_at + delay_seconds` |
| `message_loss` | Marca la muestra como perdida, sin POST ni comprobante ficticio |

La retención requiere inicio mayor que cero y toma la muestra limpia anterior, aunque otro evento haya alterado la emisión anterior. La deriva acepta tasas finitas entre −0,25 y 0,25 °Bx/h. El retardo acepta de 1 a 86.400 segundos. Solo cada tipo correspondiente admite estos parámetros. Al acabar una falla de sensor se vuelve a la curva limpia; esto no representa una recuperación biológica ni una reparación física validada.

El reloj sigue en **1× UTC**, sin observaciones futuras. Un corte activo detiene todos los POST pendientes de ese dispositivo, incluido su historial anterior. El GET de verificación de receta permanece disponible: el corte programado simula el canal de entrega de telemetría, no toda la red ni una caída del servidor. Una caída real de red usa los reintentos existentes. El emisor necesita verificar la receta al iniciar o reiniciar antes de generar muestras; tras verificarla, los errores transitorios de POST no detienen la generación.

## Persistencia y entrega

El SQLite privado del emisor conserva dos cursores: `generated_sequence`, próximo índice por generar, y `next_sequence`, próximo índice por entregar o descartar según el plan. La generación del sobre exacto y el avance de su cursor ocurren en una transacción. La entrega es FIFO: un mensaje retrasado también retiene los posteriores. No se simula reordenación de paquetes en este contrato.

`outbox` registra `available_at`, `disposition` (`pending`, `delivered`, `lost`), cuerpo exacto, estado sintético de referencia y comprobante. `truth.emitter_faults` documenta qué alteraciones se aplicaron; esa verdad latente no viaja como feature de inferencia. Las pérdidas deliberadas conservan evidencia local, dejan huecos en el servidor y avanzan sin inventar un ACK. El contador `lost` incluye todas las pérdidas ya generadas, aunque el cursor de entrega todavía esté retenido antes de ellas. No hay purga automática de esta evidencia; la generación está acotada por el horizonte de la receta.

Un éxito HTTP solo confirma la muestra si el comprobante coincide en dispositivo, proceso, origen, hora observada, valores y calidades de ambos canales, con identificador positivo. Se aceptan canales ausentes válidos. Respuestas malformadas bloquean el dispositivo y conservan la muestra pendiente. Si el servidor guarda pero se pierde la respuesta, se reenvía el mismo sobre y la idempotencia devuelve el comprobante original.

Al reabrir estados antiguos se agregan las columnas locales y se reconstruye el cursor a partir de la cola y los ACK anteriores. No cambia el UUID de recetas sin fallas ni se regeneran sus sobres pendientes. Un cambio de plan requiere una nueva calibración/receta y un estado nuevo: el estado anterior y el preflight rechazan las discrepancias. Esto no migra el esquema de la aplicación, que sigue en `0006_interventions`.

`statuses()` y la salida JSON del CLI muestran ambos cursores, pendientes, pérdidas, `waiting_until` y errores. `--drain` genera todo lo vencido y entrega lo disponible; termina cuando no puede avanzar, incluso si solo hubo pérdidas. No espera a que termine un corte futuro. Códigos de salida de `--once`/`--drain`: **0** sin errores ni sobres generados pendientes, **1** ante bloqueo/error de transporte, **2** con sobres pendientes por corte/retardo o lote acotado. Un cero con `--once` no certifica que se haya generado todo el historial. El modo continuo sigue esperando y reintenta cuando corresponde.

## Reproducción local

Desde `backend`, preparar una configuración aislada siguiendo [Simulador enológico](SIMULADOR_ENOLOGICO.md). Sobre una base NUEVA y un directorio NUEVO:

```powershell
python -m scripts.init_simulation_demo --env-file .env.simulation --output artifacts/fault-fleet --base-url http://127.0.0.1:8000 --fault-plan examples/simulation-faults.json
python -m uvicorn app.main:app --env-file .env.simulation --host 127.0.0.1 --port 8000
```

En otra terminal, con esa API en ejecución:

```powershell
python -m scripts.simulate_v2 --manifest artifacts/fault-fleet/fleet.json --env-file artifacts/fault-fleet/device-keys.env --state artifacts/fault-fleet/emitter.db --batch 100
```

El ejemplo programa alteraciones diez minutos después de la creación de la demo según las edades iniciales de cada proceso. Si se inicia más tarde, esos eventos ya serán históricos; el corte no vuelve a empezar al abrir el worker. El dispositivo 1 acumula mensajes entre los minutos 10 y 40. Detener el worker y repetir su comando conserva la identidad y la cola. La reserva física 6 permanece inactiva, sin credenciales ni lecturas. Ningún comando requiere Supabase ni despliegue.

## Verificación y límites

`tests/test_simulation_faults.py` cubre validación, determinismo, canales independientes, corte y reinicio, pérdida de respuestas, ACK inválidos, aislamiento entre dispositivos, actualización de estados antiguos y CLI. Una prueba abre un puerto TCP local con Uvicorn y el cliente `LocalHTTP` real: confirma un episodio térmico, provoca silencio, ejecuta el watchdog y entrega backlog. Las observaciones atrasadas siguen identificadas como tales; no declaran recuperación ni resolución humana. La recepción de backlog no prueba que la medición esté al día.

Las pruebas usan SQLite temporal y un reloj de prueba controlado; no validan tiempos de corte físicos en hardware, PostgreSQL, carga sostenida ni portabilidad de un despliegue. El reloj acelerado explícito sigue pendiente. El plan de fallas es procedencia programada, no un diagnóstico causal del proceso ni una certificación de robustez ML. Véanse las [pruebas del emisor](evidencias/fallas-emisor-2026-11-17.md).
