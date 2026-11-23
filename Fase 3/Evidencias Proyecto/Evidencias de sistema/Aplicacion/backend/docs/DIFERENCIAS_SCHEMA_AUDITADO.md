# Diferencias de nulabilidad respecto del esquema auditado

Generado desde el snapshot de solo lectura del 14-11-2026 y el ORM de esta entrega. No consulta Supabase ni propone cambios automáticos. YES significa que permite NULL.

El snapshot no contiene longitudes/precisiones, identidad de secuencias ni la lista completa de triggers y políticas. Por eso no basta para certificar equivalencia ni para marcar una base existente con `alembic stamp`.

| Columna | Supabase auditado | Baseline local |
| --- | --- | --- |
| `ASIGNACION_DISPOSITIVO.asignado_en` | NO | YES |
| `BITACORA_INTERVENCION.fecha_registro` | NO | YES |
| `BODEGA.direccion` | NO | YES |
| `BODEGA.valle_vitivinicola` | NO | YES |
| `BODEGA.creado_en` | NO | YES |
| `BODEGA.comuna` | NO | YES |
| `BODEGA.region` | NO | YES |
| `CEPA.tipo_uva` | NO | YES |
| `CUBA.cap_litros` | NO | YES |
| `CUBA.sector_cuba` | NO | YES |
| `CUBA.fecha_cuba` | NO | YES |
| `CUBA.material_id` | NO | YES |
| `DISPOSITIVO.tipo_dispositivo` | NO | YES |
| `DISPOSITIVO.firmware_version` | NO | YES |
| `DISPOSITIVO.creado_en` | NO | YES |
| `EMPRESA_CLIENTE.email_emp` | NO | YES |
| `EMPRESA_CLIENTE.creado_en` | NO | YES |
| `EVENTO_ALERTA.timestamp` | NO | YES |
| `EVENTO_ALERTA.severidad` | NO | YES |
| `EVENTO_ALERTA.met_dispar` | NO | YES |
| `EVENTO_ALERTA.mensaje` | NO | YES |
| `EVENTO_ALERTA.dispositivo_id` | NO | YES |
| `EVENTO_ALERTA.fermentacion_id` | NO | YES |
| `LECTURA_TELEMETRIA.timestamp` | NO | YES |
| `LECTURA_TELEMETRIA.temp_mosto` | NO | YES |
| `LECTURA_TELEMETRIA.temp_ambiente` | NO | YES |
| `LECTURA_TELEMETRIA.densidad_sg` | NO | YES |
| `LECTURA_TELEMETRIA.brix` | NO | YES |
| `LECTURA_TELEMETRIA.ph` | NO | YES |
| `LECTURA_TELEMETRIA.origen_dato` | NO | YES |
| `LECTURA_TELEMETRIA.dispositivo_id` | NO | YES |
| `LECTURA_TELEMETRIA.lectura_valida` | NO | YES |
| `LECTURA_TELEMETRIA.fermentacion_id` | NO | YES |
| `MODELO_DISPOSITIVO.marca` | NO | YES |
| `MODELO_DISPOSITIVO.arquitectura` | NO | YES |
| `MODELO_DISPOSITIVO.version_hardware` | NO | YES |
| `PERFIL_FERMENTACION.temp_min` | NO | YES |
| `PERFIL_FERMENTACION.temp_max` | NO | YES |
| `PERFIL_FERMENTACION.brix_caida_min_dia` | NO | YES |
| `PERFIL_FERMENTACION.ph_min` | NO | YES |
| `PERFIL_FERMENTACION.ph_max` | NO | YES |
| `PROCESO_FERMENTACION.volumen_litros` | NO | YES |
| `PROCESO_FERMENTACION.brix_inicial` | NO | YES |
| `PROCESO_FERMENTACION.brix_objetivo` | NO | YES |
| `PROCESO_FERMENTACION.densidad_inicial_sg` | NO | YES |
| `PROCESO_FERMENTACION.fecha_inicio` | NO | YES |
| `PROCESO_FERMENTACION.fecha_estimada_fin` | NO | YES |
| `PROCESO_FERMENTACION.creado_en` | NO | YES |
| `PROCESO_FERMENTACION.perfil_id` | NO | YES |
| `TELEMETRIA_ESTADO_NODO.timestamp` | NO | YES |
| `TELEMETRIA_ESTADO_NODO.bateria_pct` | NO | YES |
| `TELEMETRIA_ESTADO_NODO.bateria_volt` | NO | YES |
| `TELEMETRIA_ESTADO_NODO.rssi_dbm` | NO | YES |
| `TELEMETRIA_ESTADO_NODO.estado_red` | NO | YES |
| `UMBRAL_FERMENTACION.temp_min` | NO | YES |
| `UMBRAL_FERMENTACION.temp_max` | NO | YES |
| `UMBRAL_FERMENTACION.brix_caida_min_dia` | NO | YES |
| `UMBRAL_FERMENTACION.ph_min` | NO | YES |
| `UMBRAL_FERMENTACION.ph_max` | NO | YES |
| `UMBRAL_FERMENTACION.actualizado_en` | NO | YES |
| `USUARIO.telefono` | NO | YES |
| `USUARIO.creado_en` | NO | YES |
| `USUARIO.empresa_id` | NO | YES |
| `USUARIO_BODEGA.asignado_en` | NO | YES |

Estas diferencias requieren reconciliación antes de migrar datos existentes. En particular, los canales no medidos se conservan como ausentes, en lugar de insertar pH o temperatura ambiente ficticios. Los campos de procesos que aún admiten NULL son compatibilidad heredada; no significan que la API permita iniciar una fermentación sin volumen. Véase MIGRACIONES_Y_POSTGRESQL.md para las otras diferencias de índices, relaciones y reglas.
