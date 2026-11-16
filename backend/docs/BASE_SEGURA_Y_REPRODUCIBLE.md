# Primera entrega: aislamiento y baseline reproducible

Esta entrega conserva el clasificador existente como experimento. No convierte su score en una predicción enológica validada ni habilita un SaaS multiempresa en producción.

## Cambios operativos

- La API no crea tablas ni siembra registros durante importación, startup o consultas de bitácora/catálogos/empresa.
- `DATABASE_URL` y `JWT_SECRET_KEY` son obligatorias. Se eliminó la clave JWT pública de respaldo. El secreto debe tener al menos 32 bytes; generarlo aleatoriamente.
- Todas las rutas de negocio requieren Bearer. La autorización por rol/bodega/empresa se implementó en el bloque siguiente: [política, pruebas y límites](AUTORIZACION_EMPRESA_BODEGA.md). PostgreSQL y concurrencia ya se validaron en las entregas posteriores.
- `MOSTO_ENV` admite development, demo y test. Production se rechaza explícitamente hasta completar la validación de aislamiento y migraciones.
- Los endpoints de telemetría antiguos son exclusivamente demo/test y requieren `X-Mosto-Simulator-Key`. Los botones de inyectar/restaurar también están restringidos a esos entornos. No son el canal futuro del ESP32 real.
- Las lecturas del simulador antiguo se marcan `simulado_legacy`. Ese simulador todavía completa campos y usa cinética simplificada: solo se admite sobre la base demo aislada.
- `/api/health` indica que el proceso responde. `/api/ready` verifica acceso al esquema y la revisión Alembic actual; devuelve 503 sin detalles sensibles si falla. No acredita el estado del modelo.
- Las pantallas de auditoría y dispositivos ya no añaden incidentes/sensores ficticios cuando falta información. Ping/reinicio informan que el comando no está implementado, sin fingir éxito.

## Ejecución local disponible

En este checkout se preparó `backend/.env.demo` (ignorado por Git) con secretos aleatorios y `backend/artifacts/mosto_demo.db`. La base remota y `backend/.env` no se modificaron. La demo contiene tres cubas/procesos virtuales y un usuario, sin historial inventado de intervenciones ni lecturas.

Desde `C:/mosto/backend`:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env.demo --host 127.0.0.1 --port 8000
```

Desde `C:/mosto/frontend`, ejecutar `npm run dev`. Iniciar sesión con `demo@example.invalid`; la contraseña se encuentra en `MOSTO_DEMO_PASSWORD` dentro de `.env.demo`. Los botones antiguos de credenciales rápidas de la pantalla de login no representan este usuario.

Para preparar otra demo: copiar `.env.demo.example` a `.env.demo`, completar secretos/contraseña, y cargar ese archivo explícitamente antes de ejecutar `python -m scripts.init_demo`. Este comando exige una base local con nombre `mosto_demo`; aplica Alembic y crea los fixtures. Una segunda ejecución conserva los datos y contraseña existentes de una demo versionada reconocida. Rechaza bases no versionadas y no vacías, incluidas demos antiguas creadas mediante ORM: preparar otra base y preservar la anterior. No usarlo como herramienta de migración de Supabase.

Para arrancar el simulador desde otra terminal, cargar `MOSTO_SIMULATOR_KEY` del mismo `.env.demo` en el entorno y ejecutar `python scripts/simulate_esp.py --cuba 1,2,3`. La clave no es una credencial del futuro hardware real.

## Docker y PostgreSQL aislados

Compose ya no lee `backend/.env`. La demo usa exclusivamente `mosto_demo` en su servicio PostgreSQL local y un volumen nuevo. Definir `MOSTO_DEMO_JWT_KEY`, `MOSTO_SIMULATOR_KEY` y `MOSTO_DEMO_PASSWORD` en el entorno de Compose.

```powershell
docker compose --profile demo up --build
# Simulador opcional, en otra terminal:
docker compose --profile demo --profile simulator up --build simulator
```

La dependencia DB → inicialización → backend → simulador espera health/readiness. No se publica el puerto PostgreSQL demo; la API solo publica en loopback. Las contraseñas de PostgreSQL incluidas son exclusivamente del entorno local demo/test y no sirven para despliegue externo.

Para una base de pruebas PostgreSQL desechable:

```powershell
docker compose --profile test up -d mosto-test-db
$env:MOSTO_TEST_DATABASE_URL='postgresql+psycopg2://mosto_test:local-test-only@127.0.0.1:55433/mosto_test'
```

La suite aplica migraciones y vacía los datos entre pruebas únicamente en el destino validado. Nunca asignar una base con información valiosa aunque su nombre sea `mosto_test`. PostgreSQL 18.4 ya se ejecutó en un clúster nativo desechable; véase [Migraciones](MIGRACIONES_Y_POSTGRESQL.md). Docker/Compose siguen pendientes de ejecución. El esquema local no se presenta como equivalente exacto al remoto.

## Pruebas y entorno

Desde `C:/mosto`:

```powershell
.\backend\venv\Scripts\python.exe -m pytest -q --disable-warnings
```

Sin `MOSTO_TEST_DATABASE_URL`, conftest crea una SQLite temporal con claves foráneas habilitadas, reemplaza explícitamente el destino del proceso de pruebas antes de importar la app y crea fixtures por prueba. Ni el `.env` de desarrollo ni `DATABASE_URL` del shell se usan como destino de pruebas. Una URL remota o de nombre incorrecto en `MOSTO_TEST_DATABASE_URL` se rechaza antes de conectar. Cada prueba arranca con datos propios, sin depender de que otra prueba se haya ejecutado.

`requirements-tested-windows-py314.txt` registra exactamente el entorno Windows/Python 3.14 usado. No es un lock de Linux validado; el Dockerfile actual usa su propio entorno y debe validarse antes de presentar equivalencia. Se conservan warnings heredados de Pydantic/datetime para una migración posterior.

## Reproducción ML offline

Desde `C:/mosto/backend`:

```powershell
python -m ml.baseline generate --output artifacts/baseline/windows.csv
python -m ml.baseline train --dataset artifacts/baseline/windows.csv --output-dir artifacts/baseline/run-001
```

El generador conserva la distribución del notebook proporcionado y produce exactamente las 4.000 filas del CSV existente con semilla 42. La etiqueta representa un régimen sintético asignado de antemano; no un evento futuro observado. Los pasos representan 0,25 horas físicas. El código no afirma modelar las cuatro fases ni reproduce un fuzzy autoencoder.

La ejecución guarda hash del notebook/dataset/modelo, esquema de features, parámetros, versiones y los índices train/test. No reemplaza el pickle servido por la API. Las rutas de salida existentes se rechazan para evitar sobrescrituras. El resultado sobre el test reconstruido del artefacto original fue 93,375 % / AUC 0,9801875; el reentrenamiento local de esta entrega obtuvo 93,25 % / AUC 0,9805626. No se promete identidad binaria entre entornos.

## Contrato temporal v2 conectado

`app/telemetry_contract.py` define y valida un sobre con versión, dispositivo, boot UUID, secuencia, observed_at con zona horaria, temperatura y Brix aparente con calidad independiente y referencia de calibración. Rechaza NaN, horas sin zona, valores para canales ausentes y Brix válido sin calibración. Normaliza UTC y prohíbe campos extra.

El cliente no puede proporcionar empresa, origen físico/simulado ni received_at: provienen de la identidad y del servidor. El contrato ya está conectado a HTTP y almacenamiento con credenciales individuales, calibración versionada, idempotencia y asignación temporal. Véanse contrato, evidencias y límites en [Telemetría v2](TELEMETRIA_V2.md). El reloj acelerado de simulación permanece pendiente.

## Pendientes inmediatos

1. Adoptar los datos existentes mediante una transición específica. Las migraciones locales y la concurrencia ya están probadas en PostgreSQL 18.4; véase [Migraciones y PostgreSQL](MIGRACIONES_Y_POSTGRESQL.md). No se ha migrado Supabase.
2. Integrar las pantallas de aprovisionamiento y el prototipo real con el canal v2 ya implementado; añadir MQTT cuando corresponda.
3. El [simulador continuo por fases](SIMULADOR_ENOLOGICO.md) ya es el flujo nuevo de demostración, con tiempo físico 1× y carga histórica. Quedan el reloj acelerado y escenarios de fallas de sensores/comunicaciones.
4. Features por tiempo real, riesgo futuro, forecast y evaluación independiente; después rediseño visual completo.

No se hizo commit, merge, despliegue, rotación externa de secretos ni modificación de la base remota. La contraseña antigua se retiró del texto actual de la documentación; revocación y limpieza histórica requieren un procedimiento separado. El cambio previo del usuario en `app/ml/README.md` permanece intacto.

## Validación de esta entrega

Esta sección conserva la evidencia del primer bloque. Las suites actuales y los resultados posteriores están en [Migraciones](MIGRACIONES_Y_POSTGRESQL.md) y [Telemetría v2](TELEMETRIA_V2.md).

- 44 pruebas aprobadas en SQLite aislado; 668 warnings heredados de deprecación que permanecen visibles.
- Build Vite correcto; nueve pantallas y móvil inspeccionados con fixtures interceptados, sin errores JavaScript. Auditoría vacía y Device Hub vacío ya no contienen filas inventadas.
- Inicialización demo local y segunda ejecución verificadas; CSV/pickle originales y cambio local previo del README conservados por hash.
- Workflow de GitHub preparado para el mismo entorno Windows/Python 3.14 y build Node 26. No se ha ejecutado en GitHub ni se hizo push.
- Compose validado como YAML; ejecución Docker/PostgreSQL pendiente por falta de runtime local.
