# Adopción de Supabase · 23 de noviembre de 2026

La consulta de solo lectura al PostgreSQL 17.6 de MOSTO encontró la revisión `0010_clock_projection`, la misma que en Fase 3. El arranque de Docker puede usar el esquema existente. La autorización de la API, las membresías y las diferencias de integridad requieren trabajo antes de operar sobre la base compartida.

## Respaldo y restauración

Se usó la conexión del proyecto documentado en Fase 2, con verificación TLS del servidor y pooler en modo sesión. Un snapshot PostgreSQL de lectura repetible dio origen al inventario de filas, al volcado de los esquemas `public` y `auth` y a la exportación SQL de la estructura de `public`. El archivo de datos y las credenciales de ensayo se guardaron en el perfil local de Windows, fuera del repositorio. El respaldo cubre estos dos esquemas. La configuración de la plataforma y los objetos de Storage quedan fuera de su alcance.

| Evidencia | Resultado |
| --- | --- |
| Archivo `esquemas.dump`, SHA-256 | `299244af4dacce09c2732d8d0605102c7211676360b5e45ffa6b9f5a83474c51` |
| Restauración | PostgreSQL 18.4 aislado, en una transacción, con roles locales para los propietarios y permisos del volcado |
| Recuentos de `public` | Coincidencia en las 31 tablas y sus 8.651 filas, incluida la revisión de Alembic |
| Datos de operación | 7 cubas, 8 procesos, 4.273 lecturas y 1.810 mensajes de telemetría |
| Acceso | 12 cuentas MOSTO, 8 activas. Tres tienen membresía de bodega y solo una de esas tres está activa. Las 12 tienen hash con el formato actual. Hay cero usuarios en `auth.users`. |
| Políticas | RLS habilitado en las 31 tablas de `public`, con 32 políticas |

## Diferencias frente a la instalación limpia

Se creó otra base local vacía con Alembic hasta `0010`. Se ejecutó el mismo [inventario de objetos](../../scripts/inventario_esquema.sql) sobre ambas bases usando el mismo servidor PostgreSQL para comparar las definiciones. Las columnas compartidas coinciden en nulabilidad. En 98 columnas difiere algún otro atributo, incluidos tipo o precisión, valor por defecto y mecanismo de identidad. Algunas diferencias reflejan decisiones de Supabase que conviene conservar, como el vínculo con `auth.users`.

El respaldo tiene una columna adicional, `EVENTO_ALERTA.resolucion_nota`. Hay índices únicos y restricciones con nombres o representaciones diferentes. Por ejemplo, el par bodega y código de cuba ya es único mediante un índice. Las claves foráneas de membresías también difieren en su comportamiento de borrado.

Una diferencia de integridad verificable es la ausencia de la clave foránea de `BITACORA_INTERVENCION.cuba_id` hacia `CUBA.id`. El respaldo tiene cero referencias huérfanas. En la copia se añadió la restricción con `NOT VALID`, se ejecutó `VALIDATE CONSTRAINT` con éxito y se revirtió la transacción. La corrección sigue pendiente en Supabase.

## Prueba del arranque sin perfil

Sobre una base derivada de la restauración se creó una cuenta SQL de ensayo sin permisos administrativos, con políticas para las operaciones probadas. Se asignaron contraseñas temporales únicamente en esa copia. Docker ejecutó el frontend compilado, FastAPI en modo `production` y el monitor. Se verificó el certificado del PostgreSQL de ensayo.

- `GET /api/ready` respondió 200 a través del proxy del frontend. Se sirvió el HTML de la aplicación.
- Firefox completó el login de la cuenta activa con bodega y abrió el dashboard. La respuesta HTTP fue 200. Una cuenta activa sin bodega obtuvo 403.
- Se verificaron el perfil de sesión y los listados de cubas, procesos, alertas, bitácora, usuarios, dispositivos y perfiles.
- Un alta en bitácora devolvió 201. Tras detener y recrear los contenedores, la misma sesión pudo consultar el registro.
- Se verificó al menos una ejecución del monitor de silencio. Los datos usados para esta prueba pertenecen a la copia.
- Suite en un PostgreSQL desechable independiente del respaldo: 370 pruebas aprobadas y una omitida por ser exclusiva de SQLite. Las cuatro pruebas del módulo de respaldo SQLite pasaron al ejecutarlo con ese motor. Se separó la configuración de pruebas (un administrador y tres cubas) de los cinco estanques y perfiles rápidos de la demo, y se ajustó el inicio del dispositivo de prueba para cubrir toda la ventana histórica de 24 horas.

## Pendientes de producción

1. Provisionar un rol SQL dedicado a la API con permisos por operación y políticas RLS dirigidas a ese rol. Los permisos de ensayo cubrieron las rutas enumeradas. Revisar también el acceso efectivo de los roles de la Data API de Supabase. La API de MOSTO emite su propio JWT.
2. Confirmar cuáles de las siete cuentas activas sin bodega deben operar y con qué rol. Conservar el rechazo 403 para las cuentas sin acceso asignado.
3. Revisar las diferencias de restricciones, autorizar la corrección de bitácora y verificar la telemetría v2 con el dispositivo destinado a la instalación. Completar el envío y canje de enlaces de recuperación de contraseña.
4. Preparar el respaldo del momento de despliegue y validar los flujos con el rol definitivo antes de habilitar el monitor sobre datos compartidos.
