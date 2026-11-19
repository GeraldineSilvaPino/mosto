# Autorización por empresa y bodega

Actualización del bloque posterior: las migraciones locales y estas pruebas de autorización también se ejecutaron satisfactoriamente en PostgreSQL 18.4. La validación concurrente incluye protección del último administrador. Véanse los [resultados y límites de adopción](MIGRACIONES_Y_POSTGRESQL.md); las referencias a PostgreSQL pendiente más abajo describen el estado de la entrega anterior.

La consulta `/api/simulaciones/procesos/{id}` aplica el mismo ámbito histórico de procesos. El nuevo [simulador continuo](SIMULADOR_ENOLOGICO.md) usa claves individuales; el origen y la receta se comprueban antes de emitir, sin otorgarle un JWT administrativo ni acceso de escritura a la base del backend.

Implementación local en `codex/mosto-safe-foundation`, posterior a la base segura. No se aplicaron migraciones ni escrituras a Supabase. `production` continúa deshabilitado.

## Política efectiva

El JWT identifica al usuario. Los permisos se consultan en `USUARIO_BODEGA` y `ROL` en cada petición; `USUARIO.rol` y los claims de rol no autorizan operaciones. La empresa debe estar activa y la asignación debe pertenecer a esa empresa. Asignaciones duplicadas o roles desconocidos provocan rechazo, sin escoger arbitrariamente el permiso mayor. `operario` se normaliza a `operador`.

| Acción | Permiso requerido en la bodega |
| --- | --- |
| Consultar cubas, procesos, históricos, predicción, perfiles, alertas y bitácora | admin, enologo, operador o lector |
| Iniciar/finalizar procesos, atender/resolver alertas, registrar intervenciones | admin, enologo u operador |
| Crear/modificar/desactivar perfiles | admin o enologo |
| Registrar/vincular/desvincular dispositivos | admin u operador |
| Emitir/revocar credenciales y crear/revocar calibraciones v2 | admin; política `provision` |
| Consultar metadatos de credenciales y calibraciones | admin, enologo, operador o lector con acceso al dispositivo |
| Inyectar/restaurar escenarios demo | admin, además de entorno demo/test |
| Administrar usuarios y configuración de empresa | admin en **todas** las bodegas de la empresa |

La última regla es conservadora: un administrador de una sola bodega no puede suspender una cuenta que también trabaja en otras bodegas. La administración delegada de personal por bodega requiere separar operaciones sobre la cuenta de operaciones sobre sus asignaciones; no se implementa implícitamente.

Un usuario operador en A y lector en B puede consultar ambas, pero sus escrituras se limitan a A. La existencia de un rol de escritura en alguna bodega no lo extiende a las demás. Las referencias a entidades fuera del ámbito retornan 404; carecer del permiso para la operación retorna 403.

## Mecanismo y límites

`services/access.py` crea una sesión SQLAlchemy independiente de la sesión de autenticación. Instala criterios de lectura mediante `do_orm_execute` y `with_loader_criteria`, incluidos alias, relaciones y agregados. La sesión comienza sin objetos previamente cargados. Los subqueries de ámbito utilizan tablas Core y no vuelven a inyectar recursivamente los criterios ORM.

La sesión de negocio rechaza SQL directo y mutaciones masivas; las mutaciones ORM pasan por `before_flush`, con lista de entidades permitidas, comprobación de referencias y prohibición de trasladar registros históricos entre empresas, bodegas, cubas o procesos. Los catálogos compartidos son de lectura. Las consultas operativas, exportaciones y métricas usan el mismo ámbito. El código de autenticación, aprovisionamiento y simulador legacy conserva sesiones específicas; no debe reutilizarse como dependencia de un router de negocio.

Esto es autorización de aplicación, no RLS ni aislamiento de un administrador de base de datos. Las futuras tablas deben incorporarse explícitamente a la política. No se habilita producción hasta contrastar migraciones, restricciones, concurrencia y permisos del rol PostgreSQL.

Los dispositivos sin asignación activa forman un inventario común de su empresa. Una asignación activa fuera del ámbito excluye el dispositivo; un vínculo histórico no da acceso al estado actual. Las lecturas históricas se filtran por el proceso autorizado, no por la ubicación actual del dispositivo. La telemetría sin proceso queda fuera de estas consultas de negocio.

Las notas generales todavía no tienen `bodega_id`: son visibles al autor y a administradores de toda la empresa. Las notas vinculadas a cubas siguen el ámbito de estas. Añadir un ámbito explícito a notas generales forma parte de la migración pendiente.

## Cambios de integridad y contrato

- Crear un usuario exige contraseña explícita de 12 a 256 caracteres. No hay contraseña ni teléfono inventados. Usuario y asignación se guardan en una transacción.
- Se exige `bodega_id` al crear usuarios cuando hay varias bodegas; el cambio de rol también debe indicar la bodega cuando el usuario tiene varias asignaciones.
- Solo se aceptan roles aprovisionados. El inicializador demo incorpora los roles y el modelo de hardware básico de manera explícita e idempotente, sin reemplazar usuarios ni contraseñas.
- Se impide la autosuspensión y dejar una bodega sin administrador activo. En PostgreSQL, las modificaciones administrativas toman un bloqueo de fila de empresa para serializar esta comprobación. Su comportamiento concurrente aún debe probarse en PostgreSQL; SQLite no valida ese bloqueo.
- Los DTO de usuarios y `/api/auth/me` incluyen `memberships`; la identidad autenticada incluye `company_admin`. El rol mostrado se deriva de las asignaciones. Las etiquetas generales no sustituyen los permisos por bodega.
- Crear dispositivos valida previamente la cuba y el modelo de catálogo; dispositivo y asignación se guardan juntos. Los conflictos de unicidad no devuelven detalles de otra empresa.
- Iniciar un proceso requiere un perfil activo existente y perteneciente a la bodega. Si la selección es ambigua, requiere identificador explícito; ya no inventa perfiles desde una operación de inicio.
- Bitácora y atención de alertas toman el autor de la sesión. Los campos de autor heredados del cliente no suplantan esa identidad. `atendida_por` representa a quien atendió; el esquema aún no tiene un campo independiente para quien resuelve.
- El resolver de cubas en bitácora deja de buscar coincidencias parciales entre dígitos de códigos.
- Vue incorpora selección de bodega, contraseña inicial explícita, rol de solo lectura y estados visibles de carga, error y éxito. Crear una cuenta no afirma enviar una invitación por correo.

## Evidencia y trabajo pendiente

Validación local del bloque: **54 pruebas aprobadas en 33,45 s** (1.048 avisos de deprecación pendientes); build Vite correcto; flujos de creación y cambio de rol comprobados en navegador sin errores JavaScript. El inicializador actualizó los catálogos de la demo local preservando credenciales. Los hashes del CSV, pickle y README de ML previo del usuario permanecen intactos.

Las pruebas HTTP adversariales en `tests/test_access.py` utilizan dos empresas y dos bodegas con permisos distintos dentro de una empresa. Cubren separación de listados/detalles/históricos/predicción, métricas y CSV; referencias ajenas y atomicidad; rol manipulado en JWT y rol legacy; autoría; revocación de asignaciones; empresa inactiva; último administrador; alias, carga de relaciones, `Session.get` y rechazo de SQL directo/bulk.

La suite previa también sigue ejecutándose en una base SQLite temporal. No hay conexión de pruebas a Supabase. La verificación de Vue usa el build real y respuestas interceptadas: comprueba creación en la bodega seleccionada, contraseña mínima y cambio del rol de esa bodega. No equivale a una prueba de navegador contra PostgreSQL.

La revisión visual móvil evidencia el problema previo de la barra lateral fija del layout global. Este bloque no certifica adaptación móvil ni constituye el rediseño UI/UX solicitado. La siguiente fase conserva ese trabajo pendiente.

Actualización: migraciones locales, restricciones y concurrencia se validaron en PostgreSQL; el aprovisionamiento y la [ingesta v2](TELEMETRIA_V2.md) también están implementados. Los comprobantes se consultan por el proceso histórico autorizado. Permanecen pendientes la adopción del esquema remoto, asignación y revocación de membresías desde UI, selección de bodega en configuración, navegación según permisos, simulador continuo, nuevo pipeline ML y rediseño general. La recuperación de contraseña todavía requiere implementar el envío y flujo real.
