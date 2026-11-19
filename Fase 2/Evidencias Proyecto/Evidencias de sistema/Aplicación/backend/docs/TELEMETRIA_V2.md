# Telemetría v2: identidad, tiempo y calidad

Estado local del bloque, 15-11-2026. La API HTTP, el almacenamiento y la consulta desde Vue están conectados. Las pruebas usan bases desechables; no se ha migrado Supabase, desplegado producción ni conectado un ESP32 real. El bloque posterior ya implementa el [simulador continuo](SIMULADOR_ENOLOGICO.md); el nuevo modelo predictivo permanece pendiente.

## Identidad y aprovisionamiento

El dispositivo debe existir y tener una asignación a una cuba y un proceso que cubran el instante de medición. La ingesta no crea ninguno de esos recursos. El JWT de usuario sirve para administrar; cada dispositivo transmite con su propia credencial en `X-Mosto-Device-Key`.

| Operación | Endpoint | Acceso |
| --- | --- | --- |
| Emitir credencial | `POST /api/dispositivos/{id}/credenciales` | Administrador del ámbito autorizado |
| Listar metadatos de credenciales | `GET /api/dispositivos/{id}/credenciales` | Usuario con lectura del dispositivo |
| Revocar credencial | `DELETE /api/dispositivos/{id}/credenciales/{credential_id}` | Administrador del ámbito autorizado |
| Crear versión de calibración | `POST /api/dispositivos/{id}/calibraciones` | Administrador del ámbito autorizado |
| Consultar calibraciones | `GET /api/dispositivos/{id}/calibraciones` | Usuario con lectura del dispositivo |
| Revocar calibración | `DELETE /api/dispositivos/{id}/calibraciones/{calibration_id}` | Administrador del ámbito autorizado |
| Enviar medición | `POST /api/v2/telemetria` | Credencial del dispositivo |
| Consultar comprobante | `GET /api/v2/telemetria/{message_id}` | JWT con acceso al proceso histórico |

Crear una credencial requiere `{"source":"fisico","label":"Prototipo 01","expires_days":90}`. El origen admite `fisico` o `simulado`; queda fijado al aprovisionar y no puede cambiarse. El token se entrega una sola vez con `Cache-Control: no-store`; la base conserva únicamente su hash SHA-256. Las claves usan un secreto aleatorio de 32 bytes, caducan en 1–365 días y admiten revocación. Para rotar, emitir una nueva, configurarla en el emisor y revocar la anterior. Los listados nunca devuelven tokens ni hashes.

La API comprueba empresa y dispositivo activos, pertenencia de la credencial, vigencia y revocación. Aprovisionamiento, revocación e ingesta bloquean la misma fila de dispositivo en PostgreSQL; después de esperar, la ingesta vuelve a leer la credencial. Un JWT de administrador o la antigua clave compartida del simulador no sustituyen la clave v2. Los dispositivos sin asignación se administran según la política de administrador de toda la empresa, descrita en [Autorización](AUTORIZACION_EMPRESA_BODEGA.md).

## Calibración y significado enológico

`brix_apparent` representa una medida derivada de flotabilidad/inclinación. No certifica por sí misma azúcar residual durante la fermentación. La calibración real debe obtenerse y contrastarse con el prototipo; este bloque implementa su registro y aplicación, no demuestra su exactitud física.

Para origen físico, `tilt_polynomial` aplica:

```text
Brix_aparente = c0 + c1·ángulo + c2·ángulo² + c3·ángulo³
               + kT·(temperatura − temperatura_referencia)
```

Se admiten 2–4 coeficientes, un dominio angular explícito entre 0 y 180°, una vigencia `[valid_from, valid_until)` y una tolerancia de concordancia de 0–1 °Bx (por defecto 0,1). La conversión del servidor es autoritativa; el Brix reportado debe concordar dentro de esa tolerancia. Una calibración no se edita: se crea otra versión o se revoca. Si `kT` no es cero, una temperatura ausente o inválida impide validar Brix.

Ejemplo **exclusivamente para probar software**, sin validez para el hardware:

```json
{
  "version": "prueba-01",
  "method": "tilt_polynomial",
  "valid_from": "2026-11-14T00:00:00Z",
  "coefficients": [-10, 0.5],
  "tilt_min": 20,
  "tilt_max": 80,
  "temperature_coefficient": 0,
  "reference_temperature": 20,
  "tolerance": 0.1
}
```

Para origen simulado se exige `synthetic_identity`, sin coeficientes físicos ni límites angulares. Conserva explícitamente que el valor procede de una simulación. La procedencia no viene del mensaje, sino del dispositivo aprovisionado; esto no constituye atestación criptográfica de hardware.

## Mensaje y respuestas

Ejemplo de sobre; sustituir IDs y fechas por los del dispositivo, calibración y proceso existentes:

```json
{
  "schema_version": 2,
  "device_id": 1,
  "boot_id": "d46fda94-d2b6-4f4b-ae36-6c22bde25f65",
  "sequence": 1,
  "observed_at": "2026-11-15T15:00:00Z",
  "temperature_c": {"value": 22, "quality": "good"},
  "brix_apparent": {"value": 20, "quality": "good"},
  "tilt_degrees": 60,
  "calibration_id": 1
}
```

El ESP32 debe sincronizar su reloj, generar un UUID de arranque y asignar una secuencia a cada observación. Un reintento conserva el sobre completo y la secuencia. Un nuevo arranque utiliza otro UUID. La API no exige llegada secuencial: admite mensajes atrasados.

| Respuesta | Significado |
| --- | --- |
| 201 | Nuevo mensaje aceptado, con calidad evaluada por canal |
| 200 | Reintento idéntico; mismo comprobante y hora de recepción original |
| 401 | Clave ausente, inválida, revocada o caducada |
| 403 | Clave de otro dispositivo, dispositivo o empresa inactivos |
| 409 | Secuencia reutilizada con otro contenido, asignación/proceso ambiguos, calibración ajena o conflicto de integridad |
| 422 | Sobre inválido, campo extra, dato no finito, hora sin zona o medición demasiado futura |

La clave idempotente es `(dispositivo, boot_id, sequence)`. Se compara el hash del JSON validado y normalizado, no los bytes originales de HTTP. El orden de claves y una zona horaria equivalente no alteran el contenido canónico. La autenticación se comprueba incluso en los reintentos. Un reintento autorizado devuelve el comprobante original aunque el proceso se haya cerrado o la calibración se haya revocado después.

Se conserva la restricción heredada de una lectura por `(dispositivo, timestamp)`: enviar otra secuencia con exactamente la misma hora devuelve 409, sin escribir un mensaje parcial. Los clientes deben reintentar la observación original, no inventar otra secuencia para la misma muestra.

## Tiempo, calidad y persistencia

- `observed_at`: instante medido por el emisor, normalizado a UTC. `received_at`: hora del servidor al comenzar a procesar la petición, antes de esperar bloqueos. No es la hora de commit.
- Se rechazan más de dos minutos de adelanto. Se marca `delayed` si el retraso supera diez minutos. `out_of_order` compara la hora observada con la máxima hora previamente aceptada del dispositivo; no expresa continuidad de secuencias.
- La asignación y el proceso se resuelven por intervalos `[inicio, fin)`. Un paquete retrasado puede pertenecer a una cuba anterior o a un proceso cerrado; no se reasigna a la cuba actual por comodidad.
- Cada canal declara `good`, `missing`, `invalid` o `uncalibrated`. `missing` exige `value: null`; `good` exige un valor finito. Brix declarado válido exige referencia de calibración.
- Temperaturas fuera de −55 a 125 °C se invalidan según el rango del [DS18B20 del fabricante](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf). Ese rango valida el sensor; **no es un rango enológico seguro ni un umbral de alerta**.
- Calibración revocada/fuera de vigencia, inclinación ausente/fuera del dominio o compensación térmica imposible degradan Brix a `uncalibrated`. La discrepancia con la fórmula lo degrada a `invalid`. Se registra el motivo en `diagnostics`.
- Fallar un canal no elimina el otro. Los valores reportados quedan en el sobre canónico; la proyección para gráficos solo incluye valores utilizables y deja `NULL` en los demás. pH, temperatura ambiente y densidad no se inventan.
- Un 201 confirma persistencia, no que ambos sensores sean válidos. El emisor debe leer las calidades y diagnósticos del comprobante. Los sobres rechazados por validación/autorización no se guardan como mensajes aceptados.

`MENSAJE_TELEMETRIA` conserva identidad, sobre normalizado, hash, referencia de calibración, calidad, diagnóstico y enlaces históricos. `LECTURA_TELEMETRIA` mantiene una proyección compatible con las consultas actuales, con origen `v2_fisico` o `v2_simulado`. Ambas escrituras, los episodios térmicos y la última recepción del dispositivo se confirman en una transacción. El indicador global heredado `lectura_valida` requiere ambos canales válidos; consumidores futuros deben utilizar las calidades independientes.

## Migración, interfaz y límites

La revisión `0003_telemetry_v2` añade tres tablas (credenciales, calibraciones y mensajes) y origen/última recepción al dispositivo: 21 tablas de dominio más `alembic_version`. No modifica las revisiones anteriores. PostgreSQL añade guardas de referencias, origen y campos inmutables, e impide actualizar/borrar mensajes canónicos. SQLite no reproduce estos triggers; se usa para pruebas portables, no para certificar concurrencia.

Device Hub distingue Físico/Simulado/Sin aprovisionar y usa recepción del servidor para la conectividad v2 (ventana de diez minutos). Batería, señal e IP ausentes se muestran como no informadas; el contrato v2 todavía no incorpora esos canales. Una repetición idéntica no refresca la recepción original. La ventana es un valor inicial para cadencia nominal de cinco minutos, pendiente de configuración por perfil de dispositivo.

Un proceso con mensajes v2 devuelve `estado_ia: NO_VALIDADO`, `riesgo_pct: null` y `alerta_ia: false`. Vue muestra N/D y diagnóstico pendiente, elimina la inclinación inventada y describe el delta de Brix como diferencia entre muestras, sin fingir una tasa de 24 horas. El clasificador legacy no se aplica a ese proceso ni se generan alertas ML basadas en él. La ingesta v2 evalúa ahora [episodios térmicos](ALERTAS_V2_Y_EPISODIOS.md) por canal con persistencia, histéresis, auditoría, bitácora y MTTR. Usa reglas v2, separadas de las legacy; las recomendaciones y reglas cinéticas siguen pendientes. No debe interpretarse ausencia de alerta como fermentación sana.

Las inyecciones legacy de anomalía/restauración y los endpoints antiguos rechazan dispositivos aprovisionados y cubas con dispositivos v2 o procesos abiertos con historial canónico. Esto evita mezclar las muestras de demostración antigua con el canal nuevo; se conservan las muestras históricas previas al aprovisionamiento.

También quedan pendientes: adaptador MQTT, firmware y calibración del prototipo real, formularios de aprovisionamiento en Vue, reloj acelerado de simulación, pipeline ML validado, rediseño completo y adopción de datos remotos. El simulador continuo posterior usa tiempo UTC de pared y recetas congeladas en la calibración sintética; no admite acelerar enviando fechas futuras. Un despliegue externo requiere transporte HTTPS y validación operativa, todavía fuera de esta entrega local.

## Validación

- Suite completa en PostgreSQL 18.4 temporal: **98 aprobadas**, 46,35 s, 1.350 avisos de deprecación.
- Suite completa en SQLite temporal: **91 aprobadas, 7 omitidas** por depender de PostgreSQL, 26,83 s, 1.267 avisos de deprecación.
- Casos incluidos: dos empresas, permisos, emisión/revocación/caducidad, revocación concurrente, reintentos simultáneos, conflictos de secuencia/timestamp, cambio de asignación, cierre de proceso, zonas horarias equivalentes, canales fallidos y calibración.
- Build Vite correcto. Navegador Edge/Playwright contra FastAPI y SQLite aislada, sin respuestas API interceptadas: cuatro mediciones, cuatro reintentos idempotentes, curvas de temperatura/Brix, origen, campos ausentes y riesgo N/D. Sin errores JavaScript ni respuestas API de error. La prueba aprovisiona un dispositivo como físico para ejercitar el contrato; no interviene hardware real. Capturas y resultado JSON en el directorio externo `mosto-audit` de la auditoría, prefijo `v2-`.
- Verificados por SHA-256 contra el inventario original: CSV, pickle y cambio previo del usuario en README de ML permanecen intactos. No se ejecutó commit, merge, push ni modificación de Supabase.

Comandos desde la raíz del repositorio:

```powershell
backend/venv/Scripts/python.exe -m pytest -q --disable-warnings
backend/venv/Scripts/python.exe backend/scripts/test_postgres.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'
```

El runner crea, detiene y limpia exclusivamente su clúster temporal. Los resultados no acreditan un despliegue en Supabase ni la ejecución del workflow remoto.
