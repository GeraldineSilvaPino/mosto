# Rama A — backend, simulación y entrega técnica

Rama exclusiva: `codex/mosto-safe-foundation`. Leer PLAN_PARALELO y CONTRATO_COORDINACION.
Estado editable: ESTADO_A; necesidades para B: SOLICITUDES_A. No tocar frontend.

## A1. Terminar integración temporal (prioridad)

Leer RELOJ_ACELERADO y todos los servicios simulation_time, telemetry_v2,
episodes, kinetic_episodes, monitoring, kinetics_query, curve_comparison y
profile_overrides. Revisar rutas procesos, cubas, comparaciones, simulaciones y
aprovisionamiento. Núcleo y emisor no son un flujo operativo completo.

- Diseñar nueva migración posterior a 0008: no editar migraciones aplicadas para
  cambiar historia. Guardas de 0002/0003 comparan observación con asignación/cierre
  reales: separar dominios sin relajar las restricciones físicas o entre empresas.
- Acordar invariantes explícitas de inicio, asignación, calibración, cierre,
  cambio de dispositivo/receta, revocación y backlog. Verificar reloj único por
  proceso cuando intervienen varios dispositivos; registro actual congela por
  dispositivo/proceso. Evitar mezcla silenciosa de relojes o bypass sin receta.
- Conservar recepción real, validación de secuencia, calidad e idempotencia.
  El reloj debe proceder de calibración autorizada, nunca del payload libre.
- Adaptar consultas de cinética, histórico de cuba y comparación para usar corte
  real de disponibilidad y corte simulado de observación. Resolver semántica de
  mediciones manuales y cierres sin inventar conversiones físicas.
- Exponer metadatos explícitos para B. Solo retirar guarda acelerada tras pruebas
  HTTP y PostgreSQL de escenarios adversariales y propagación correcta de reloj.
- Entregar comandos demo reproducibles y datos de prueba no secretos; 1x intacto.

Puerta A1: suite SQLite/PostgreSQL, migración up/down/up aislada, proceso cerrado,
asignación histórica, mezcla de fuentes, preflight discrepante, replay exacto,
reinicio/outage/delay/loss, override/backlog y silencio sin falsa recuperación.
Publicar contrato final y fixture JSON en SOLICITUDES_A; B implementa presentación.

## A2. Completar soporte backend de UI y operación

Revisar peticiones B. Añadir paginación/filtros con compatibilidad para listas
antiguas (nuevo endpoint o parámetro opt-in); totales y orden estable. Contrastar
KPI, listas y exportaciones por misma empresa, origen y período. Revisar controles
no persistentes detectados por B. Documentar solicitudes de interfaz sin editar Vue.
Revisar aprovisionamiento, calibración y tratamiento de errores. Probar permisos
negativos, concurrencia y entradas inválidas de toda API nueva.

## A3. Reproducibilidad y operación (independiente de A1)

Instalación limpia backend; lock/versiones y CI existente; PostgreSQL con rol
limitado. Ensayar Docker si disponible; registrar limitación si no lo está.
Observabilidad mínima: salud/readiness, logs correlacionados sin secretos y errores
operativos distinguibles. Definir carga objetivo explícita y medir latencia,
errores y saturación. Herramientas de backup/restore exclusivamente sobre bases
locales desechables, restauración y comprobación de filas/integridad/migraciones.
Manual técnico en backend/docs; no certificar pruebas que no se ejecutaron.

## A4. ML, DSS y hardware

Reproducir resultados y completar model card/limitaciones, sin reentrenar con test
ya visto ni activar ML v2. Si se mitiga robustez, reservar nuevas trayectorias antes
de evaluar y comparar baselines/abstención/intervalos. Preparar protocolo de
etiquetas reales y revisión enológica; no inventar aprobación ni datos.
Auditar lo disponible de ESP32/MQTT. Preparar firmware/contrato/outbox y tests
con transporte controlado donde sea posible; ensayos físicos solo con hardware
disponible. DSS: contratos trazables de hipótesis/evidencia y revisión humana;
tratamientos/umbrales no revisados permanecen deshabilitados y documentados.

## A5. Integración final

Seguir merge y puertas del PLAN_PARALELO solo cuando ambas partes terminen.
Reconciliar matriz original sprint por sprint y reportar software entregado versus
validación externa pendiente. Nunca declarar 100 % por agotamiento del tiempo.
