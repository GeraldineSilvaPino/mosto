# Aplicación MOSTO

La instalación principal ejecuta el frontend Vue, la API FastAPI, el monitor de sensores y cinco emisores virtuales en Docker. La API persiste las lecturas en Supabase. La demo local usa su propio PostgreSQL en Docker.

## Arranque con Supabase

La instalación actual ya tiene su configuración. Ejecutar los comandos desde `C:\mosto\Fase 3\Evidencias Proyecto\Evidencias de sistema\Aplicacion`. En una instalación nueva, copiar `.env.operacion.example` a `.env.operacion`. Configurar la URL de la cuenta SQL dedicada a FastAPI y una clave JWT aleatoria (por ejemplo, generar 32 bytes con `python -c "import secrets; print(secrets.token_hex(32))"`). La cuenta necesita permisos y políticas sobre las tablas de MOSTO. La conexión usa el certificado público de Supabase incluido en `supabase-ca.crt` para verificar el servidor. Para usar otro certificado del proyecto, asignar su ruta a `MOSTO_CA_FILE` antes de ejecutar Compose. [Certificado distribuido por Supabase](https://github.com/supabase/cli/blob/v2.50.0/internal/gen/types/templates/prod-ca-2021.crt) · [Configuración TLS de Supabase](https://supabase.com/docs/guides/platform/ssl-enforcement)

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8080/api/ready
```

Abrir [MOSTO](http://localhost:8080). El frontend sirve las peticiones `/api` desde el mismo origen. El monitor comprueba el silencio de sensores cada 60 segundos. El sistema requiere una base preparada y usuarios con membresía en la bodega. Las migraciones y el alta de usuarios son operaciones independientes del arranque. Para detener esta instalación, usar `docker compose down`.

## Inventario de la instalación principal

Las cubas `SIM-01` a `SIM-05` tienen el mismo perfil Cabernet Sauvignon, 10.000 L de capacidad y lotes de 8.000 L en distintas fases. El [emisor v2](backend/scripts/simulate_v2.py) envía una muestra cada cinco minutos por dispositivo. Recupera la última hora inicial y continúa a tiempo real. El volumen `simulator_state` guarda el avance y los reintentos entre arranques. La ingesta deduplica por dispositivo, arranque y secuencia.

El modelo relaciona el consumo de °Brix aparente con la temperatura, la fase y la actividad fermentativa. El pH sigue una tendencia sintética suave con ruido reproducible. Dos lotes siguen la evolución normal y los otros representan enfriamiento, agotamiento de nutrientes y fermentación lenta. Cada trayectoria termina al alcanzar 30 días desde el inicio de su lote. Los registros se identifican como simulados. La sexta cuba, `REAL-06`, está disponible para asignar un proceso y hardware físico.

En este equipo ya están instalados `.env.operacion`, `backend/artifacts/flota-operacion/fleet.json` y `device-keys.env` en la misma carpeta del manifiesto. Para trasladar la instalación hay que transferir estos archivos privados y el estado del emisor. El manifiesto contiene los identificadores de los dispositivos y las calibraciones creados en Supabase. Para consultar el avance de cada emisor, ejecutar `docker compose logs --tail 2 simulator`.

Para aprovisionar una instalación vacía con un catálogo existente, ejecutar `python -m scripts.preparar_flota --help` desde `backend`. El comando utiliza `MOSTO_PROVISION_DATABASE_URL`, el certificado en `PGSSLROOTCERT` y una carpeta privada nueva para las claves. La cuenta de la API requiere políticas de lectura y escritura para los dispositivos y procesos del nuevo manifiesto. El arranque ordinario reutiliza la flota ya registrada.

## Demo local con PostgreSQL en Docker

Instala Docker con el complemento Compose v2. En Windows, inicia Docker Desktop en modo de contenedores Linux. Los puertos locales 5173 y 8000 deben estar disponibles. Desde esta carpeta, donde se encuentra `docker-compose.yml`, ejecuta:

```sh
docker compose -f compose.demo.yml up --build -d
docker compose -f compose.demo.yml ps -a
```

Compose crea la base y ejecuta las migraciones. En una instalación nueva también crea los datos iniciales. Es normal que `init-demo` termine con código 0. Los servicios `mosto-demo-db`, `backend`, `frontend` y `simulator` siguen en ejecución. La demo trae su configuración local y se puede iniciar sin crear archivos `.env`.

## Comprobar la demo

1. Abre la [aplicación](http://localhost:5173). En el formulario de acceso, pulsa **Admin** y luego inicia sesión.
2. Abre una cuba desde el dashboard y comprueba su última lectura. El simulador envía un ciclo aproximadamente cada 20 segundos. Para ver las entregas de ambos nodos, ejecuta `docker compose -f compose.demo.yml logs --tail 10 simulator`.
3. Comprueba el [estado de la API](http://localhost:8000/api/ready) o consulta su [documentación interactiva](http://localhost:8000/docs).

En una base recién creada, el gráfico crece con las lecturas. La primera estimación de riesgo del flujo continuo necesita aproximadamente 45 minutos de datos. Los ejemplos de configuración del backend y del frontend se incluyen para el desarrollo fuera de Docker.

## Detener y reanudar

```sh
docker compose -f compose.demo.yml down
docker compose -f compose.demo.yml up -d
```

El proyecto Compose utiliza el nombre `mosto`. El volumen `mosto_mosto_demo_data` conserva el historial entre arranques, incluso después del traslado de la carpeta. El simulador retoma el proceso activo de cada cuba. Para reconstruir las imágenes después de actualizar el código, añade `--build` al comando de inicio.
