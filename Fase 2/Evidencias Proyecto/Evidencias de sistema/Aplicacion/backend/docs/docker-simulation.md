# Simulación de demostración en Docker

El CMD inicia Uvicorn y, después de `/api/ready`, un emisor local de la cuba
`DEMO-LIVE`. El Dockerfile de este despliegue habilita `MOSTO_SIMULATION_ENABLED=1`
y selecciona `MOSTO_SIMULATION_DEVICE_ID=12`. Para desactivarlo, establecer
`MOSTO_SIMULATION_ENABLED=0` en Render. No configurar un Docker Command que
sustituya el CMD si se desea este arranque conjunto.

El dispositivo, proceso, asignación y calibración deben existir previamente y
estar registrados como simulados. El arranque no crea cubas, procesos ni tablas,
no ejecuta migraciones y no modifica lecturas de sensores físicos.

Se emite por HTTP a la API del mismo contenedor, usando el puerto `PORT` de Render
o 8000. Se genera una credencial exclusiva del dispositivo a partir de un HMAC
del secreto del backend; solo su hash se almacena en PostgreSQL. La credencial
vence con la trayectoria (14 días en la configuración actual) y no se renueva
automáticamente. Revocarla bloquea ese emisor. No introducir secretos en Git.

El SQLite temporal es una cola de trabajo, no la fuente de recuperación. Las
secuencias confirmadas en `MENSAJE_TELEMETRIA` permiten recuperar el prefijo
continuo después de un reinicio. Los huecos se reenvían con identificadores
deterministas y la API verifica su idempotencia. Un bloqueo transaccional de
PostgreSQL coordina emisores de Docker durante despliegues superpuestos y es
compatible con el pooler transaccional. Desactivar emisores externos tras el
traspaso a Docker.

Render Free puede suspender el servicio por inactividad: durante la suspensión
no se emite; al despertar se entregan las muestras sintéticas pendientes con
sus fechas de observación y recepción diferenciadas. No garantiza ejecución 24/7.
El supervisor mantiene la API si el emisor falla y reintenta el emisor cada 30 s.
SIGTERM detiene ambos procesos. Para una trayectoria terminada se requiere una
nueva configuración explícita, no se reinician procesos ni se inventa continuidad.

Validación: `python -m unittest discover -s tests -p test_container_checkpoint.py`.
