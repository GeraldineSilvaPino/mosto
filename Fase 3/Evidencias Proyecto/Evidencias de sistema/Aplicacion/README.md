# Aplicación MOSTO

La demo local reúne el frontend Vue 3 con Vite y Chart.js, la API FastAPI, PostgreSQL 16 y un simulador que envía lecturas de temperatura, Brix y pH mediante HTTP. El dashboard permite seguir cinco cubas y consultar curvas, alertas, perfiles y estimaciones experimentales de riesgo de parada.

## Iniciar

Instala Docker con el complemento Compose v2. En Windows, inicia Docker Desktop en modo de contenedores Linux. Los puertos locales 5173 y 8000 deben estar disponibles. Desde esta carpeta, donde se encuentra `docker-compose.yml`, ejecuta:

```sh
docker compose --profile demo up -d --build
docker compose --profile demo ps -a
```

Compose crea la base y ejecuta las migraciones. En una instalación nueva también crea los datos iniciales. Es normal que `init-demo` termine con código 0. Los servicios `mosto-demo-db`, `backend`, `frontend` y `simulator` siguen en ejecución. La demo trae su configuración local y se puede iniciar sin crear archivos `.env`.

## Comprobar la demo

1. Abre la [aplicación](http://localhost:5173). En el formulario de acceso, pulsa **Admin** y luego inicia sesión.
2. Abre una cuba desde el dashboard y comprueba su última lectura. El simulador envía un ciclo aproximadamente cada 20 segundos. Para ver las entregas de ambos nodos, ejecuta `docker compose logs --tail 10 simulator`.
3. Comprueba el [estado de la API](http://localhost:8000/api/ready) o consulta su [documentación interactiva](http://localhost:8000/docs).

En una base recién creada, el gráfico crece con las lecturas. La primera estimación de riesgo del flujo continuo necesita aproximadamente 45 minutos de datos. Los ejemplos de configuración del backend y del frontend se incluyen para el desarrollo fuera de Docker.

## Detener y reanudar

```sh
docker compose --profile demo down
docker compose --profile demo up -d
```

El proyecto Compose utiliza el nombre `mosto`. El volumen `mosto_mosto_demo_data` conserva el historial entre arranques, incluso después del traslado de la carpeta. El simulador retoma el proceso activo de cada cuba. Para reconstruir las imágenes después de actualizar el código, añade `--build` al comando de inicio.
