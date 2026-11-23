# Migraciones y validación PostgreSQL

Estado del bloque, 15-11-2026: migraciones locales versionadas y probadas, sin modificar Supabase. Se conserva `MOSTO_ENV=production` deshabilitado. Esta entrega no constituye una migración aplicada sobre los datos existentes.

## Revisiones

- `0001_schema`: definición congelada de las 18 tablas, independiente de futuras modificaciones del ORM. Solo acepta bases vacías. Incluye la tabla antes ausente `UMBRAL_FERMENTACION`, UUID de identidad externa, claves foráneas, checks e índices.
- `0002_guards`: funciones y triggers PostgreSQL de integridad entre empresas, bodegas, procesos y sensores, incluidos intervalos de asignación. En SQLite se omite esta revisión de triggers; ese motor solo comprueba las restricciones portables.
- `0003_telemetry_v2`: credenciales individuales, calibraciones versionadas y mensajes canónicos; origen y última recepción del dispositivo. Añade guardas de identidad, referencias e inmutabilidad en PostgreSQL. Esta revisión llega a 21 tablas de dominio.
- `0004_alert_episodes`: estados de regla, auditoría inmutable en PostgreSQL, condiciones separadas de gestión, autor de resolución y bitácora vinculada.
- `0005_profile_versions`: historial de perfiles y snapshot de parámetros al iniciar procesos nuevos. No reconstruye configuraciones iniciales históricas. Detalles: [Perfiles versionados](PERFILES_VERSIONADOS.md).
- `0006_interventions`: intervenciones estructuradas y eventos vinculados a bitácora, solicitudes/revisiones únicas y auditoría inmutable en PostgreSQL. Esta revisión llega a 26 tablas de dominio. Detalles: [Intervenciones](INTERVENCIONES_ESTRUCTURADAS.md).
- `0007_manual_measurements`: mediciones manuales y anulaciones con autoría, evidencia, unicidad, vínculo a bitácora y triggers de inmutabilidad PostgreSQL. Esta revisión llega a 28 tablas de dominio. Detalles: [Mediciones manuales](MEDICIONES_MANUALES.md).
- `0008_process_profile_overrides`: ajustes térmicos inmutables por proceso, revisión/UUID únicos, autor, vigencia, configuración y bitácora; añade la revisión aplicada a la persistencia de reglas sin cambiar su configuración base. Head actual: 29 tablas de dominio + Alembic. [Contrato](AJUSTES_PERFIL_PROCESO.md). Validación SQLite: 289 aprobadas/16 omitidas; PostgreSQL pendiente para los bloques nuevos.

Las pruebas y la inicialización demo utilizan Alembic. El arranque del servidor no ejecuta DDL. `/api/ready` exige que la revisión aplicada coincida con la del código; una base antigua o sin versionar devuelve 503, sin modificarla.

`migrations/env.py` utiliza exclusivamente `MOSTO_MIGRATION_DATABASE_URL`, o una conexión explícita del código de pruebas. Nunca carga `backend/.env` ni usa implícitamente `DATABASE_URL`. Solo permite destinos locales denominados `mosto_test` o `mosto_demo` para PostgreSQL y archivos SQLite con esos prefijos. Se rechazan parámetros libpq que puedan sustituir el host o la base aparentemente indicados en la URL.

## Reglas cubiertas

- Código de cuba único dentro de su bodega, sin impedir el mismo código en otra.
- Correo de usuario único sin distinguir mayúsculas/minúsculas.
- Una asignación de rol por usuario y bodega.
- Un proceso que ocupa la cuba, tanto `en_proceso` como `detenida`. Finalizar un proceso detenido está permitido; iniciar otro encima no.
- Una asignación activa por dispositivo. Los intervalos históricos tampoco pueden solaparse en PostgreSQL.
- Rangos de pH, coherencia de fechas, volumen positivo cuando está informado, estados válidos, batería y señal.
- Perfil y cuba de la misma bodega; volumen que no supera la capacidad al crear/modificar el proceso.
- Membresías, asignaciones, autores de bitácora y actores de alertas coherentes con su empresa.
- Propiedad histórica no trasladable cambiando las referencias principales de una entidad.
- Una lectura debe pertenecer al intervalo del proceso y a un intervalo de asignación del dispositivo. Se admiten lecturas retrasadas correspondientes a un intervalo anterior válido; la mera existencia de una asignación histórica no autoriza cualquier timestamp.

La [ingesta v2](TELEMETRIA_V2.md) ya resuelve credenciales, calibración, idempotencia por secuencia y mensajes fuera de orden. Sus validaciones de aplicación complementan los triggers.

## Concurrencia y transacciones

Iniciar/finalizar procesos bloquea la cuba. Reasignar un sensor bloquea el dispositivo y guarda el cierre del vínculo previo antes de insertar el siguiente. Administrar usuarios bloquea la empresa y vuelve a comprobar los permisos del actor tras obtener el bloqueo. Los índices y triggers siguen actuando si una escritura omite el controlador HTTP.

Las migraciones PostgreSQL utilizan un advisory lock transaccional y límites de espera. Las violaciones de integridad que llegan a la API producen un 409 genérico; no se muestran SQL ni parámetros de otras empresas. El ejecutor de pruebas crea un usuario `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`. Este usuario es propietario de su base temporal y puede ejecutar DDL: **no es todavía el rol de producción con privilegios mínimos**.

## Cómo reproducir las pruebas

Desde `C:/mosto`, con las dependencias instaladas en el entorno virtual:

```powershell
backend/venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
backend/venv/Scripts/python.exe backend/scripts/test_postgres.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'
```

El segundo comando inicializa un clúster nuevo en `backend/artifacts/mosto-pg-*`, con contraseña aleatoria, puerto libre y escucha exclusiva en `127.0.0.1`. Crea la base `mosto_test`, ejecuta las pruebas, detiene su propio servidor y comprueba el directorio antes de limpiarlo. No conecta con el servicio PostgreSQL instalado ni con Supabase. En Windows, el lanzador redirige la salida a archivo para evitar que un proceso separado mantenga abiertos los pipes del padre.

También se puede proporcionar `MOSTO_TEST_DATABASE_URL` a pytest para un PostgreSQL de pruebas propio, por ejemplo el servicio Compose. **La suite trunca las tablas de ese destino** entre casos: debe ser una base local desechable. El runner temporal es la opción que evita reutilizar accidentalmente una base valiosa.

## Preparar una demo nueva

Desde `C:/mosto/backend`, configurar `MOSTO_ENV=demo`, `DATABASE_URL` apuntando a una base local **vacía**, `JWT_SECRET_KEY`, `MOSTO_SIMULATOR_KEY` y `MOSTO_DEMO_PASSWORD`; ejecutar:

```powershell
python -m scripts.init_demo
```

Este comando aplica las migraciones antes de sembrar los datos explícitos. Una demo antigua creada mediante `create_all` se conserva y se rechaza como destino del baseline. Para una demo nueva se puede usar otro archivo, por ejemplo `artifacts/mosto_demo_v2.db`, manteniendo intacto el anterior. No utilizar `stamp head` para saltarse la comprobación.

Para generar SQL revisable sin conectarse, desde el directorio backend:

```powershell
$env:MOSTO_ENV = 'test'
$env:MOSTO_MIGRATION_DATABASE_URL = 'postgresql+psycopg2://localhost/mosto_test'
python -m alembic upgrade head --sql
```

La generación offline se prueba impidiendo expresamente abrir conexiones. Ese SQL tampoco debe aplicarse directamente a una base Supabase existente.

## Diferencias con Supabase y adopción pendiente

El snapshot de esquema de la auditoría se conserva en `migrations/reference/supabase_audit_20261114.json`, sin filas, contraseñas ni identidad del rol de conexión. Contiene hash de procedencia. El [contraste de nulabilidad](DIFERENCIAS_SCHEMA_AUDITADO.md) registra **64 diferencias** entre el esquema auditado y el baseline local. No se ocultan como una supuesta equivalencia entre entornos.

Decisiones deliberadas del baseline:

- Temperatura ambiente, pH y otros canales no medidos admiten NULL; no se inventan mediciones para satisfacer `NOT NULL`.
- Brix aparente no impone la antigua restricción de azúcar residual no negativo. Es una medida derivada cuya interpretación depende de la calibración; no representa directamente azúcar residual durante toda la fermentación.
- `auth_uid` conserva tipo UUID y unicidad, pero no crea una tabla ficticia `auth.users` ni importa el servicio de autenticación de Supabase. La relación externa debe decidirse en el procedimiento de adopción.
- Un proceso detenido conserva la reserva de la cuba; el índice remoto auditado solo cubría `en_proceso`.
- Los triggers comprueban intervalos temporales; el trigger auditado de lecturas aceptaba cualquier asignación histórica.
- Se conservan varios campos opcionales heredados de procesos y configuración. No es todavía una normalización final de todos los datos del dominio.

Antes de adoptar una base existente: obtener un dump de esquema completo y una copia local controlada, reconciliar tipos/defaults/nulabilidad/identidades/FKs externas/políticas, detectar y resolver datos incompatibles, crear una revisión específica de transición y ensayar respaldo/restauración. El snapshot actual no incluye toda esa información. Ningún `stamp`, downgrade ni cambio de tablas se ha ejecutado sobre Supabase.

## Resultados

Los siguientes resultados corresponden al cierre del bloque de migraciones anterior a v2. Los resultados actuales se registran en [Telemetría v2](TELEMETRIA_V2.md#validación).

- PostgreSQL **18.4** local: **69 pruebas aprobadas**, 26,71 s.
- SQLite aislado: **64 aprobadas y 5 omitidas** por requerir PostgreSQL, 15,33 s.
- Comprobados upgrade → downgrade → upgrade, repetición sin cambios, concordancia ORM/esquema, SQL offline, rechazo de bases sin versionar y restricciones de destino.
- Comprobados casos negativos entre empresas, lecturas retrasadas y conflictos simultáneos de inicio de procesos, reasignación de sensores y cambio de administradores.
- Persisten avisos de deprecación: 1.050 en PostgreSQL y 987 en SQLite en esa ejecución.
- Se agregó un job de CI con PostgreSQL 16 y un rol no superusuario. Su YAML y el Compose se validaron localmente; no se ha ejecutado ese job en GitHub ni se ha probado Docker en este equipo. Los resultados anteriores corresponden al PostgreSQL 18.4 nativo.

La documentación de [Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) exige revisar las migraciones generadas; por eso los triggers y sus pruebas se escribieron explícitamente. Los bloqueos utilizados corresponden a los mecanismos descritos por [PostgreSQL](https://www.postgresql.org/docs/18/explicit-locking.html).
