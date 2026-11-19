# Arquitectura y Convenciones del Backend (MOSTO)

Este documento define la estructura de capas, las reglas de codificacion y las convenciones de trabajo para el desarrollo del backend en FastAPI.

---

## 1. Arquitectura en Capas (Layered Architecture)

El backend de MOSTO implementa una arquitectura modular desacoplada en capas para garantizar alta cohesibilidad y bajo acoplamiento:

```
                    FLUJO UNIDIRECCIONAL DE PETICIONES
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 1. Capa de Presentacion / Controladores (routers/)                     │
 │    - Recibe peticiones HTTP (GET, POST, PUT, PATCH, DELETE)            │
 │    - Valida parametros con esquemas Pydantic                           │
 │    - Inyecta la sesion de base de datos con Depends(get_db)            │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 2. Capa de Transferencia y Validacion de Datos (schemas.py)            │
 │    - Define la estructura formal de entrada y salida (DTOs)            │
 │    - Aplica tipado estricto y validaciones de rango                    │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 3. Capa de Negocio / Servicios (services/)                             │
 │    - Contiene algoritmos, formulas de calibracion y reglas enologicas  │
 │    - Coordina inserciones, transacciones y manejo de consistencia      │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 4. Capa de Acceso a Datos / Modelos ORM (models.py + database.py)      │
 │    - Mapeo de tablas de PostgreSQL (Supabase) con SQLAlchemy           │
 │    - Administra pool de conexiones y transacciones con la base de datos│
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Estructura del Directorio app/

La carpeta `backend/app/` organiza los componentes tecnicos segun su proposito:

```
backend/
├── Dockerfile                  # Especificacion de imagen de contenedor Docker
├── requirements.txt            # Dependencias oficiales de Python
├── .env.example                # Plantilla de variables de entorno (sin credenciales)
├── .env                        # Credenciales reales de Supabase (ignorado en Git)
├── docs/                       # Documentacion tecnica del backend
└── app/
    ├── __init__.py
    ├── main.py                 # Instancia principal de FastAPI, CORS y registro de routers
    ├── database.py             # Configuracion del pool SQLAlchemy y funcion get_db
    ├── models.py               # Entidades ORM (tablas de Supabase)
    ├── schemas.py              # Esquemas Pydantic de entrada y salida
    ├── services/               # Logica de negocio pura y algoritmos
    │   ├── __init__.py
    │   ├── telemetry_service.py # Calibracion y persistencia de sensores
    │   ├── rules_engine.py      # Motor de evaluacion de anomalias
    │   └── cuba_service.py      # Orquestacion de procesos y cubas
    └── routers/                # Controladores que exponen endpoints HTTP REST
        ├── __init__.py
        ├── telemetry.py        # Endpoints de ingesta de hardware
        ├── cubas.py            # Endpoints de monitoreo y graficos
        ├── alerts.py           # Endpoints de gestion de alertas y MTTR
        └── devices.py          # Endpoints de administracion de dispositivos
```

---

## 3. Responsabilidad Estricta de Cada Modulo

1. **Routers (`routers/`):**
   * No deben contener calculos matematicos, formulas fisicas ni logica condicional compleja.
   * Su unica funcion es recibir el payload validado, llamar al servicio correspondiente pasandole la sesion `db: Session` y retornar la respuesta tipada.
2. **Servicios (`services/`):**
   * Encapsulan toda la logica de negocio.
   * Realizan conversiones de unidades (°Brix, densidad SG, pH, porcentaje de bateria).
   * Controlan las transacciones de base de datos (`db.commit()`, `db.rollback()`).
3. **Esquemas (`schemas.py`):**
   * Se definen como clases que heredan de `pydantic.BaseModel`.
   * Incluyen tipos de datos estrictos, valores por defecto opcionales y descripciones con `Field(...)` para documentacion OpenAPI automatica.
4. **Modelos (`models.py`):**
   * Representan las tablas reales de la base de datos PostgreSQL en Supabase.
   * Definen columnas, tipos SQL, llaves primarias, foraneas e indices.

---

## 4. Manejo de Errores y Codigos de Estado HTTP

El backend debe utilizar codigos de estado HTTP estandar:

* `200 OK`: Peticion exitosa con datos de retorno.
* `201 Created`: Recurso creado exitosamente (ej: nueva lectura o nuevo proceso).
* `400 Bad Request`: Peticion con parametros incoherentes con la logica del negocio.
* `404 Not Found`: Recurso solicitado no existe en la base de datos.
* `422 Unprocessable Entity`: Error de validacion de estructura o tipos JSON (manejado automaticamente por FastAPI).
* `500 Internal Server Error`: Excepcion no controlada en el servidor.

Para arrojar errores controlados al cliente:
```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Cuba con el identificador proporcionado no fue encontrada"
)
```

---

## 5. Convenciones de Codigo

* **Formato de Archivos:** Nombres en minusculas separados por guion bajo (`snake_case`).
* **Nombres de Clases:** Nombres en mayusculas/minusculas combinadas (`PascalCase`).
* **Nombres de Variables y Funciones:** `snake_case`.
* **Tipado Estricto:** Toda firma de funcion debe especificar tipos de parametros y retorno (`def calcular_promedio(valores: list[float]) -> float:`).
* **Nombres de Tablas de Base de Datos:** En Supabase estan creadas en mayusculas (ej: `"CUBA"`, `"DISPOSITIVO"`), por lo que en SQLAlchemy deben declararse exactamente igual con `__tablename__ = "NOMBRE_TABLA"`.

---

## 6. Flujo de Trabajo en Git

1. Cada tarea se desarrolla en una rama derivada de `develop` con el prefijo `feat/be-` o `fix/be-`.
2. Los mensajes de confirmacion (commits) siguen el estandar Conventional Commits:
   * `feat(backend): agregar calculo de grados brix desde inclinacion`
   * `fix(backend): corregir restriccion de estado operativo en tabla cuba`
   * `docs(backend): actualizar especificacion de endpoints`
3. Antes de solicitar integracion (merge) hacia `develop`, el codigo debe ser probado con el contenedor Docker local y verificado en `http://localhost:8000/docs`.
