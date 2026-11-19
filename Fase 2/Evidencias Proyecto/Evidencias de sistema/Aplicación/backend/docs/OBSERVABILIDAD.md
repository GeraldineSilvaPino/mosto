# Observabilidad local

Identificador UUID generado por servidor en cada petición HTTP. Respuestas
manejadas incluyen X-Request-ID, visible por CORS. El log `mosto.requests` incluye
ID, método, plantilla de ruta, código y duración. No registra query, cuerpo,
Authorization, claves de dispositivo ni ruta literal desconocida. El ID entrante
no se acepta como correlación confiable.

Desde backend, con configuración demo/test local y esquema migrado:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config logging.json --no-access-log
```

Usar este archivo explícito para activar INFO y evitar access logs con URL/query.
No es una política global de redacción para excepciones de bibliotecas ni proxy;
no habilitar echo SQL ni registrar secretos en aplicación. Las excepciones no
manejadas conservan su propagación; se registra status=500, pero la respuesta
generada por el manejador externo puede carecer de X-Request-ID.

GET /api/health comprueba vida del proceso; GET /api/ready comprueba conexión,
tabla inicial y revisión de migración. Salud no certifica ML ni calidad física.
Pendientes: métricas agregadas, retención de logs, alertas de operación y ensayo de
carga con objetivo explícito. No hay despliegue asociado a esta configuración.
