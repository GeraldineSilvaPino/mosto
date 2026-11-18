# Cierre local: fallas del emisor HTTP

Fecha: 17-11-2026. Windows, Python 3.11.4, rama `codex/mosto-safe-foundation`. Implementación en árbol local, sin commit/push. Contrato y reproducción: [Fallas del simulador](../FALLAS_SIMULADOR_HTTP.md).

## Comprobaciones

- Suite focalizada `tests/test_simulation_faults.py`: **22 aprobadas**, 86 warnings, 8,38 s.
- Suite completa desde la raíz: `backend/venv/Scripts/python.exe -m pytest -q --disable-warnings --tb=short`: **239 aprobadas, 11 omitidas, 90 warnings**, 180,34 s. [Salida preservada](emitter-faults-tests-final.txt).
- Las omisiones requieren PostgreSQL. La suite utiliza SQLite temporal y migraciones locales hasta `0006_interventions`; no se añade migración de aplicación.
- Prueba TCP real: servidor Uvicorn en `127.0.0.1` y puerto efímero, cliente `LocalHTTP`, autenticación y persistencia reales de la API. Tres observaciones confirman un episodio térmico; el corte retiene cinco mensajes; el watchdog marca condición desconocida. Al entregar dos observaciones atrasadas, el monitoreo informa `mediciones_atrasadas` y el episodio sigue sin recuperación ni resolución humana. Reserva física sin lecturas. Se controla el reloj de prueba; no es una espera física de cuarenta minutos.
- Reinicio con pendientes conserva los sobres exactos y sus horas observadas; recepción posterior usa la hora de entrega. Pérdida de respuesta tras guardar en servidor se recupera sin duplicación. Los otros dispositivos continúan ante un corte programado individual.
- Estados antiguos del emisor mantienen UUID y sobre pendiente al agregar columnas. Plan incompatible y ACK alterados se rechazan. CLI distingue pendientes de éxito y drena pérdidas deliberadas sin inventar recepción.
- Ejemplo JSON validado: cinco dispositivos sintéticos y siete eventos dentro del horizonte. `git diff --check` sin errores.

## Integridad y límites

SHA-256 de `backend/artifacts/causal-v1-final-model/experimental.joblib` después del bloque:

```text
3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3
```

Coincide con el cierre anterior. No se reentrena, recalibra ni habilita el modelo. Telemetría v2 conserva riesgo/forecast N/D. No se modificó Supabase ni se desplegó producción. No hubo cambios frontend, nuevo build ni navegador; PostgreSQL no se reejecutó. Quedan reloj acelerado explícito, validación científica, carga, hardware y demás pendientes del plan. Este bloque verifica recuperación del transporte, no salud biológica ni robustez predictiva.
