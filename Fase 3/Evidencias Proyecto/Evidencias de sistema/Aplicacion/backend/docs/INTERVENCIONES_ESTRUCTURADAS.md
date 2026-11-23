# Intervenciones y respuesta declarada

Implementación local del 17-11-2026. No modifica Supabase, no activa producción y no habilita ML v2.

## Contrato

Una propuesta identifica proceso, alerta opcional del mismo proceso, tipo de acción, acción concreta, motivo, autor autenticado y responsable activo con permisos operativos en la bodega. El responsable puede ser administrador, enólogo u operador; el rol lector solo consulta. Cualquier usuario con permiso operativo en esa bodega puede registrar avances; cada avance conserva su propio autor. No se ejecutan órdenes de hardware ni se recomiendan adiciones.

Estados admitidos:

- `propuesta` → `ejecutada` o `cancelada`.
- `ejecutada` → `en_seguimiento` o `cerrada`.
- `en_seguimiento` → otro seguimiento o `cerrada`.
- `cerrada` y `cancelada` son terminales. No hay borrado, reapertura ni reasignación; la propuesta original es inmutable.

Seguimiento y cierre requieren descripción y respuesta declarada: `sin_cambio`, `mejora_declarada`, `empeora_declarado` o `no_evaluable`. Son declaraciones humanas, no observaciones automáticas de recuperación. Las fechas corresponden al registro UTC en el servidor; no se aceptan fechas retroactivas ni se presume que coincidan con la hora física de ejecución.

Los procesos finalizados no admiten nuevas propuestas ni ejecución. Admiten cancelar propuestas pendientes y seguir/cerrar acciones cuya ejecución ya estaba registrada. Ninguna transición modifica la condición, gestión o resolución del episodio, el MTTR, la telemetría ni el resultado ML.

## API y persistencia

- `GET /api/intervenciones`: filtros `fermentacion_id`/`alerta_id`, `limit` 1–100 y `offset`; devuelve `items` y `total`, orden descendente de ID.
- `GET /api/intervenciones/contexto/{process_id}`: responsables de la bodega, permisos del usuario y estado activo/finalizado.
- `POST /api/intervenciones`: `request_id` UUID, proceso, alerta/responsable opcionales, `tipo`, `accion`, `motivo`. Responsable omitido: usuario autenticado.
- `GET /api/intervenciones/{id}/eventos`: paginado, revisiones más recientes primero.
- `POST /api/intervenciones/{id}/eventos`: UUID nuevo, `expected_revision`, estado, descripción y respuesta cuando corresponda.

La misma clave con el mismo contenido y actor no duplica la operación; contenido/actor diferente devuelve 409. Reintentar creación devuelve el estado actual de la intervención original; reintentar un avance devuelve su evento original. El control optimista rechaza revisiones obsoletas. PostgreSQL serializa escrituras mediante bloqueo de cuba, en el mismo orden que el cierre del proceso; SQLite conserva el control optimista, sin prometer equivalencia de bloqueos concurrentes.

La migración `0006_interventions` añade `INTERVENCION_OPERATIVA` y `EVENTO_INTERVENCION`. Cada transición crea una nota vinculada y un evento en la misma transacción. Claves únicas protegen solicitudes y revisiones. Las sesiones de negocio aíslan por proceso/empresa/bodega y prohíben reescribir auditoría. PostgreSQL añade un trigger de inmutabilidad de eventos; no se ha ejecutado en este equipo. Los controles de transición/responsable se aplican en la API; no se presenta la nueva tabla como protegida mediante RLS frente a acceso SQL privilegiado.

Vue integra el panel en detalle de cuba y ficha de incidente. Permite proponer, asignar responsable, registrar ejecución/seguimiento/cierre/cancelación y consultar historial paginado. El permiso lector oculta las acciones. Los reintentos dentro del componente conservan el UUID mientras el contenido no cambia; recargar o abandonar la pantalla pierde esa clave local, por lo que hay que consultar el historial antes de volver a presentar una operación de resultado incierto.

## Validación y límites

Pruebas HTTP de estados, idempotencia, autor, responsable, aislamiento, permisos mixtos, cierre de proceso, historial, paginación, rollback al fallar auditoría y conflictos de revisión. Migración desde cero, downgrade/upgrade y comparación con ORM. Pruebas PostgreSQL preparadas para trigger y concurrencia, omitidas en SQLite.

Navegador con API real y SQLite nueva desechable: propuesta → ejecución declarada → seguimiento `no_evaluable` → cierre; recarga y cuatro eventos persistentes. El episodio cinético sintético permanece en seguimiento y ML v2 en `NO_VALIDADO`. Se comprobó el flujo en detalle de cuba; la integración del panel en ficha de alerta se compila y sus enlaces/API tienen pruebas, sin una segunda prueba completa de navegador allí.

Pendientes del DSS: mediciones manuales con unidad/método/calibración, comparación causal de curvas antes/después, evaluación enológica, recomendaciones trazables, reasignación auditada y seguimiento real. Este bloque cierra el registro estructurado de acciones y respuesta declarada, no esos requisitos ni el sprint 7 completo. Siguiente bloque: evaluación offline de fallas de sensores, cortes y retardos con semillas reservadas y modelo congelado.
