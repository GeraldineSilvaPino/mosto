# Base de Datos Supabase (PostgreSQL) - Guia Tecnica

Este documento describe la arquitectura, entidades, restricciones CHECK y disparadores (triggers) activos en la base de datos de produccion Supabase del proyecto MOSTO.

---

## 1. Topologia de Conexion y Pooling

* **Proveedor de Infraestructura:** Supabase (PostgreSQL en region AWS `us-west-2` Oregon).
* **Identificador de Proyecto:** `bbzhnfoyasvgxwftuked`
* **Mecanismo de Conexion:** **Supavisor Transaction Pooler** (Puerto `6543`).
  * **Motivo Tecnico:** El endpoint directo `db.bbzhnfoyasvgxwftuked.supabase.co:5432` resuelve exclusivamente mediante direcciones IPv6, lo que genera fallos de tiempo de espera (timeout) en redes con proveedores de internet basados en IPv4.
  * El servicio de **Pooler** (`aws-0-us-west-2.pooler.supabase.com:6543`) cuenta con soporte dual IPv4/IPv6 y gestiona eficientemente el ciclo de vida de conexiones concurrentes.
* **Cadena de Conexion en `.env`:**
  ```env
  DATABASE_URL="postgresql+psycopg2://postgres.bbzhnfoyasvgxwftuked:12345Mosto54321%21@aws-0-us-west-2.pooler.supabase.com:6543/postgres"
  ```
  *(Nota: El signo de exclamacion `!` debe codificarse en formato URL como `%21` para evitar interpretaciones erroneas del analizador sintactico).*

---

## 2. Estructura de Tablas Relacionales (Esquema Fase 2)

Las tablas en la base de datos estan creadas con nombres en **MAYUSCULAS**:

```
                       ESQUEMA RELACIONAL PRINCIPAL
 ┌───────────────────┐        ┌─────────────┐        ┌──────────────────────┐
 │  EMPRESA_CLIENTE  │◄───────┤   BODEGA    │◄───────┤         CUBA         │
 └─────────▲─────────┘        └──────▲──────┘        └──────────▲───────────┘
           │                         │                          │
           │                         ▼                          ▼
 ┌─────────┴─────────┐     ┌─────────────────────┐   ┌──────────────────────┐
 │    DISPOSITIVO    │     │ PERFIL_FERMENTACION │   │ PROCESO_FERMENTACION │
 └─────────▲─────────┘     └─────────────────────┘   └──────────▲───────────┘
           │                                                    │
           └──────────────────────────┬─────────────────────────┘
                                      ▼
                           ┌─────────────────────┐
                           │  LECTURA_TELEMETRIA │
                           └─────────────────────┘
```

### Catalogo de Tablas:
1. `EMPRESA_CLIENTE`: Empresa vitivinicola titular de las instalaciones.
2. `BODEGA`: Recinto fisico que alberga las cubas e instalaciones.
3. `USUARIO` / `ROL` / `USUARIO_BODEGA`: Control de acceso y roles operativos.
4. `TIPO_MATERIAL_CUBA`: Clasificacion del material del estanque (Acero Inoxidable, Roble, Hormigon).
5. `CEPA`: Variedad de uva vinifera (Cabernet Sauvignon, Carmenere, Sauvignon Blanc).
6. `CUBA`: Estanque fisico de fermentacion con capacidad y ubicacion.
7. `PERFIL_FERMENTACION`: Parametros optimos y criticos de fermentacion por cepa.
8. `UMBRAL_FERMENTACION`: Tabla auxiliar de bandas termicas y limites.
9. `PROCESO_FERMENTACION`: Lote especifico en fermentacion activa dentro de una cuba.
10. `MODELO_DISPOSITIVO`: Especificaciones tecnicas del hardware (ESP32-WROOM-32, ESP8266-12F).
11. `DISPOSITIVO`: Microcontrolador individual identificado por direccion MAC.
12. `ASIGNACION_DISPOSITIVO`: Registro de asociacion fisica entre sensores y cubas.
13. `LECTURA_TELEMETRIA`: Serie temporal con registros de temperatura, densidad, grados Brix y pH.
14. `TELEMETRIA_ESTADO_NODO`: Serie temporal de telemetria de hardware (bateria y nivel de senal Wi-Fi).
15. `EVENTO_ALERTA`: Registro de incidencias y violaciones de umbral.
16. `BITACORA_INTERVENCION`: Registro de acciones correctivas tomadas por el personal tecnico.

---

## 3. Restricciones CHECK de Integridad

PostgreSQL valida estrictamente los valores permitidos para las siguientes columnas. Cualquier valor no contemplado provocara un fallo de integridad:

| Tabla | Restriccion (CHECK) | Valores Permitidos / Regla |
|---|---|---|
| `CUBA` | `ck_cuba_estado` | `'disponible'`, `'en_uso'`, `'mantencion'`, `'fuera_servicio'` |
| `PROCESO_FERMENTACION` | `ck_proceso_estado` | `'en_proceso'`, `'finalizada'`, `'detenida'`, `'cancelada'` |
| `EVENTO_ALERTA` | `ck_alerta_estado` | `'pendiente'`, `'atendida'`, `'resuelta'` |
| `EVENTO_ALERTA` | `ck_alerta_severidad` | `'baja'`, `'media'`, `'alta'`, `'critica'` |
| `DISPOSITIVO` | `ck_dispositivo_estado` | `'activo'`, `'inactivo'`, `'mantencion'` |
| `ASIGNACION_DISPOSITIVO` | `ck_asignacion_activo` | `activo = (desasignado_en IS NULL)` (si activo es True, fecha de desasignacion debe ser nula) |
| `LECTURA_TELEMETRIA` | `ck_lectura_ph` | `ph >= 0.0 AND ph <= 14.0` |
| `LECTURA_TELEMETRIA` | `ck_lectura_brix` | `brix >= 0.0` |
| `TELEMETRIA_ESTADO_NODO` | `ck_nodo_bateria` | `bateria_pct >= 0 AND bateria_pct <= 100` |
| `TELEMETRIA_ESTADO_NODO` | `ck_nodo_rssi` | `rssi_dbm <= 0` |

---

## 4. Disparadores (Triggers PL/pgSQL)

La base de datos cuenta con tres funciones disparadoras que aseguran la consistencia relacional y enologica:

### 1. `trg_validar_asignacion_empresa` (`fn_validar_asignacion_empresa`)
* **Tabla:** `ASIGNACION_DISPOSITIVO`
* **Regla:** Un dispositivo solo puede asignarse a una cuba que pertenezca a la misma empresa cliente. Si las empresas difieren, la base de datos rechaza la operacion.

### 2. `trg_validar_lectura` (`fn_validar_lectura`)
* **Tabla:** `LECTURA_TELEMETRIA`
* **Regla:** Solo se permite insertar una lectura si el `dispositivo_id` se encuentra actualmente asignado en `ASIGNACION_DISPOSITIVO` a la cuba donde se ejecuta el `PROCESO_FERMENTACION`.

### 3. `trg_validar_proceso` (`fn_validar_proceso`)
* **Tabla:** `PROCESO_FERMENTACION`
* **Reglas:**
  1. El `PERFIL_FERMENTACION` debe pertenecer a la misma bodega que la `CUBA`.
  2. El `volumen_litros` no puede superar la capacidad de la cuba (`cap_litros`).

---

## 5. Buenas Practicas de Consumo desde SQLAlchemy

1. **Campos Requeridos (NOT NULL):** Entidades como `DISPOSITIVO` exigen `empresa_id` y `modelo_id`. `CUBA` exige `material_id` y `bodega_id`.
2. **Inyeccion de Sesion:** Usar siempre la dependencia inyectada `db: Session = Depends(get_db)`. La sesion gestiona automaticamente la apertura y cierre de conexiones, evitando saturar el pool de Supabase.
3. **Flujo de Asignacion Previa:** Para registrar una lectura de telemetria, el backend garantiza previamente que el dispositivo exista y tenga asignacion activa a la cuba correspondiente.
