# Seguimiento actual y watchdog de silencio

Entrega local del 16-11-2026. No requiere migración nueva ni modifica Supabase.
El contrato `silence-v1` utiliza un límite inicial de 15 minutos para cadencia
nominal de cinco minutos; no es un umbral enológico ni acredita salud del sensor.

## Diagnóstico de lectura

`GET /api/procesos/{id}/cinetica` incluye `current_monitoring`. Es diagnóstico
**actual**, incluso si `as_of` pide features históricas. La respuesta distingue:

- `sin_telemetria_v2`: no hay mensajes canónicos recibidos del proceso.
- `sin_recepcion_reciente`: la última recepción tiene más de 15 minutos.
- `mediciones_atrasadas`: hay recepción reciente, pero no una observación de
  los últimos 15 minutos. Recibir un backlog no rejuvenece la medición.
- `datos_recientes`: ambos relojes son recientes. No implica calidad válida,
  cobertura suficiente ni fermentación sana.
- `proceso_cerrado`: seguimiento histórico, sin vigilancia activa.

La frescura usa solo mensajes recibidos hasta el momento de consulta y excluye
observaciones futuras. Publica edades y fechas de recepción/observación por
separado. La configuración térmica distingue snapshot congelado, límites de
perfil ausentes y primera evaluación pendiente. Una configuración congelada
prevalece sobre modificaciones posteriores del perfil. La cinética informa su
activación experimental o ausencia de configuración.

Las consultas son de solo lectura. El panel Vue presenta ese diagnóstico junto
a cobertura y calidad. La falta de configuración no se representa como normal.

## Barrido persistente local

`app.services.monitoring.sweep_silence` se ejecuta explícitamente mediante:

```powershell
# Desde backend, con MOSTO_ENV=demo, DATABASE_URL local validada y secretos
# propios del entorno demo ya configurados; esquema inicializado previamente.
.\venv\Scripts\python.exe -m scripts.watchdog --once
.\venv\Scripts\python.exe -m scripts.watchdog --interval-seconds 60
```

El worker rechaza development y bases que no cumplan el aislamiento demo/test
**antes de abrir conexiones**. No se inicia al importar FastAPI, no se instala
como servicio ni queda programado automáticamente. Una instancia debe ejecutarse
durante la demo para que el silencio cambie el estado persistido sin nuevas
mediciones. Sin worker, la consulta/UI sigue mostrando la frescura actual.

Cuando detecta silencio o mediciones atrasadas, reinicia candidatos de entrada y
recuperación. Marca episodios abiertos como `desconocida` y añade una auditoría
`silencio_detectado` con tiempo del servidor, sin fecha observada inventada.
Conserva la última observación real, gestión humana, evidencia original y fecha
de fin vacía. No declara recuperación, no resuelve la alerta y no crea un episodio
de fermentación por el solo hecho de faltar datos. Barridos repetidos no duplican
la transición mientras la condición siga desconocida.

Usa bloqueo de cuba, estado y episodio en el mismo orden que la ingesta; el caller
confirma una transacción por barrido. Un fallo de auditoría revierte sus cambios.
Los procesos cerrados se excluyen. Al volver los datos, las reglas existentes
requieren nuevamente su persistencia de recuperación; el silencio no cuenta.

## Límites y pruebas

Probado en SQLite temporal: ausencia de datos/límites, backlog, frontera exacta
de 15 min, idempotencia, GET sin mutación, rollback, cierre de proceso, reinicio
de candidato, retorno de datos y rechazo de entorno no aislado. La matriz previa
de permisos cubre la consulta por proceso entre empresas.

No se ha certificado concurrencia PostgreSQL de este barrido ni carga con muchas
cubas. No genera todavía un incidente independiente de comunicaciones para un
dispositivo que nunca transmitió. Quedan pendientes configuración de cadencia por
dispositivo, despliegue/supervisión del worker y paginación del barrido. Próximo
bloque del plan: perfiles versionados completos y después intervenciones.
