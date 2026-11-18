# Estado de ejecución del plan maestro

## Ejecución vigente en paralelo (18-11-2026)

Leer [reparto completo](paralelo/PLAN_PARALELO.md) y planes A/B antes de editar.
**Estimación vigente: aproximadamente 68 %**; porcentajes inferiores históricos
no se deben sumar. A es dueña del backend/validación y B del frontend/manual/UI.
Los estados operativos durante el paralelo son [A](paralelo/ESTADO_A.md) y
[B](paralelo/ESTADO_B.md); A consolidará aquí después del merge final.

Navegación histórica cerrada en frontend: ruta protegida `/procesos/:id?`, entrada
de menú, selección de activos/cerrados, comparación y exportación con proceso
principal elegido, mediciones e intervenciones por ID. Errores/IDs inválidos
retiran evidencia anterior; selección cambia todos los paneles. Build aprobado;
Edge con API simulada verificó proceso cerrado, cambio al activo, 404 e ID inválido.
No es E2E contra API real ni lista paginada servidor. Esos límites pertenecen a B.

Sección a medias: reloj acelerado. Ingesta aún rechaza recetas con reloj; triggers
temporales requieren migración, consultas y pruebas integrales pendientes. A lo
retoma; B puede avanzar independientemente. No bloquear reparto por este bloque.
Plan original, inventario de faltantes, dependencias externas, criterios de cierre,
propiedad de archivos y protocolo de merge se encuentran en el reparto completo.

Actualizado el 18-11-2026, con ajustes térmicos auditados por proceso cerrados en API y Vue y entrega consolidada para continuar desde otro PC en `codex/mosto-safe-foundation`. No se ha integrado develop ni migrado Supabase. Leer [CONTINUAR_MOSTO](../../CONTINUAR_MOSTO.md) para clonar/actualizar, instalar y regenerar artefactos locales. El hash y la disponibilidad remota se comprueban con Git; las menciones históricas de «sin commit/push» corresponden al momento de cada cierre.

**Avance global estimado: aproximadamente 68 %.** Estimación de alcance revisada tras cerrar los ajustes térmicos auditados, su aplicación temporal y el flujo Vue de aprobación/restauración. No existe una ponderación formal que permita calcular un porcentaje exacto; no mide horas ni precisión del modelo. El ML validado, recomendaciones DSS, UI integral, hardware real y validación operativa concentran todavía una parte importante del trabajo. Este cierre no certifica un sprint completo ni producción.

| Sprint del informe | Estado comprobable | Pendiente principal |
| --- | --- | --- |
| 0. Contención y reproducción | Configuración aislada, autenticación obligatoria, baseline offline, PostgreSQL temporal y CI preparada | Ejecución CI remota y cierre de reproducibilidad/despliegue entre entornos |
| 1. Identidad y esquema | Autorización por empresa/bodega, actores reales, migraciones locales y pruebas concurrentes | Adopción del esquema con datos existentes y rol de producción con privilegios mínimos |
| 2. Dispositivos e ingesta | Credenciales, calibración, timestamps, calidad, idempotencia, atribución histórica; outbox del simulador | Firmware/outbox del ESP32, MQTT y formularios completos de aprovisionamiento |
| 3. Procesos, incidentes y bitácora | Episodios térmicos y cinéticos simulados opt-in, perfiles versionados/snapshots, ajustes térmicos auditados por proceso, resolución idempotente, bitácora, intervenciones y mediciones manuales con anulación trazable | Criterios enológicos revisados y validación operativa |
| 4. Simulación científica | Núcleo continuo por fases, cinco escenarios, tiempo físico 1×, historial/panel, fallas programables de sensores/comunicaciones y recuperación persistente HTTP/outbox | Integrar reloj acelerado (núcleo y cortes causales probados); validación científica externa |
| 5. ML y forecast | Extractor causal/API, splits independientes, baselines, calibración, forecast, fallas pareadas, bootstrap por trayectoria e intervalos experimentales con modelo congelado; abstención operacional v2 | Mitigar límites de sensores con evidencia independiente, validar utilidad/cobertura de bandas, cambios de dominio y validación real antes de habilitar |
| 6. UI operacional | Estados desconocidos, procedencia, fases simuladas y acciones de incidentes persistentes verificadas | Sistema visual completo, overview, paginación global, controles restantes, accesibilidad y móvil |
| 7. DSS e integración física | Canal físico reservado, contrato común, intervenciones/respuesta humana, mediciones manuales y comparación descriptiva de dos procesos al corte temporal | Hardware calibrado, recomendaciones trazables y validación de mediciones/seguimiento reales |
| 8. Entrega y validación | Suites locales, pruebas de navegador y documentación técnica por bloque | Carga objetivo, observabilidad, respaldo/restauración, despliegue, manual y matriz final de requisitos |

La implementación adelantó el núcleo del sprint 4 para disponer de telemetría continua con la que verificar el sprint 3. Esto no cierra todas las puertas del sprint 4 ni convierte un escenario sintético en evidencia de exactitud enológica.

## Registro de secciones cerradas

### Exportación de evidencia consultada y dependencia del reloj (18-11-2026)

- Cerrada exportación JSON en comparación de curvas (sprints 6–7): resultado
  consultado con corte, procedencia, unidades, métodos, anulaciones, límites y
  advertencias. No exporta historial completo ni muestras excluidas del gráfico.
  Se exporta la respuesta cargada, no filtros editados aún sin consultar.
- Build Vite aprobado (4,04 s). Edge headless con API simulada descargó y comparó
  exactamente el JSON, incluidos truncamiento, anulaciones y texto multilínea;
  sin errores JavaScript. Script exploratorio ignorado: artifacts/browser-check/export.cjs.
- Dependencia concreta del sprint 4: triggers de 0002_relational_guards y
  0003_telemetry_v2 comparan timestamp/observado_en con asignado_en, desasignado_en
  y fecha_real_fin. Habilitar solo API produciría semántica distinta en PostgreSQL.
  Requiere una nueva migración local y pruebas de intervalos/concurrencia/replay;
  conservar guarda de ingesta. No es un bloqueo de permisos ni exige acción del usuario.
- Siguiente sección independiente: navegación de procesos históricos como principal.
  Retomar reloj con migración temporal explícita, consultas, UI y ensayo completo.
  Avance global conservador: 67 %; exportación CSV e historial completo no implementados.

### Reloj: vigencia térmica y cierre administrativo (18-11-2026)

- Regla térmica selecciona ajustes por hora real esperada de la observación,
  conservando sus intervalos de persistencia en tiempo simulado. Una muestra
  atrasada no toma ajustes aprobados después de su instante esperado.
- Cierre administrativo mantiene fecha_real_fin real; fin_condicion y hora de
  observación auditada usan el reloj del mensaje que originó el episodio. Auditoría
  conserva hora real, reloj y motivo; cierre no declara recuperación ni resolución.
- SQLite: 29 aprobadas/3 omitidas (7,94 s); PostgreSQL 18.4: 20 aprobadas
  (11,38 s), incluyendo ajustes auditados y los dos casos nuevos. Casos acelerados
  con reloj inyectado; todavía no certifican el flujo acelerado HTTP real.
- Sigue abierto sprint 4, 67 % global estimado. Próximo: coherencia de selección
  de procesos/asignaciones y cierre en ingesta, consultas históricas/comparación,
  luego API/Vue y ensayo completo. La guarda de ingesta permanece activa.

### Reloj: adaptación de reglas y monitoreo, integración abierta (18-11-2026)

- Resolvedor de reloj histórico desde calibración, con control de dispositivo y
  proceso. Revocar una calibración no reinterpreta el tiempo de mensajes antiguos.
- Regla cinética usa corte simulado y disponibilidad real separados; frescura por
  hora real esperada de entrega, persistencia por hora observada.
- Monitoreo publica reloj, edad de observación y edad real esperada de entrega.
  El watchdog transforma su marca temporal antes de comprobar silencio real.
- Verificación: 40 pruebas de monitoreo/cinética/episodios aprobadas en 12,55 s;
  después, tres pruebas específicas aprobadas en 1,20 s, incluida transmisión
  de ambos cortes a la regla. Casos acelerados usan reloj inyectado: no acreditan
  todavía ingesta acelerada real ni PostgreSQL de este bloque.
- Sigue abierto sprint 4. Próximo: resolver vigencia de ajustes térmicos y cierre
  de procesos respecto del reloj; validar ingesta y consultas, luego UI y HTTP
  real. La guarda de ingesta sigue activa. Estimación conservada: 67 %.

### Retoma: emisor acelerado y balance desde 267bd29 (18-11-2026)

- Sección activa: sprint 4, reloj acelerado. Emisor/outbox genera por tiempo
  simulado y entrega/reintenta por tiempo real; conserva identidad 1x y sobres
  al reiniciar, comprueba reloj remoto y rechaza cambios de receta en el estado.
  Corregida fixture que reconstruía formato antiguo incluyendo un campo nuevo.
  Suite específica: 53 aprobadas en 10,04 s. Integración de ingesta aún bloqueada.
- Desde Geraldine: reproducción de la entrega; corrección de fixture cinética;
  validación completa PostgreSQL (305 aprobadas en aquel cierre) y apagado robusto;
  selector manual de intervención terminado; núcleo, registro, cortes causales
  y emisor del reloj implementados. No hay commits posteriores a 267bd29: son
  modificaciones locales, incluidos archivos nuevos todavía sin seguimiento.
- Estimación revisada: aproximadamente 67 %, por cierres verificados y avance
  parcial; no existe ponderación matemática. Las cifras 66 % previas son históricas.
- Siguiente: integrar ingesta + episodios cinéticos + monitoreo de ambos relojes;
  revisar ajustes temporales y cierres; después API/Vue y ensayo HTTP real completo.
  No retirar el rechazo de ingesta antes de estas garantías. Detalle en
  [Reloj acelerado](RELOJ_ACELERADO.md).
- Después del reloj: navegación histórica/exportación (sprints 6–7), UI integral
  y accesibilidad/móvil (6), observabilidad/carga/respaldo-restauración (8).
  Revisión enológica, validación ML real y hardware/MQTT siguen pendientes externos
  y de integración (4–5–7–2). Despliegue no autorizado por este trabajo.

### Reloj acelerado: avance de integración, bloque todavía abierto (18-11-2026)

- Registro de calibración sintética acepta `simulation_clock` con ancla simulada
  igual al inicio de proceso. Solo demo/test; exige trayectoria y conserva
  autorización de aprovisionamiento. Una nueva calibración del mismo dispositivo
  y proceso no puede cambiar ni retirar el reloj de la receta registrada.
- Preflight devuelve el reloj. El worker 1x se bloquea explícitamente ante esa
  configuración; la ingesta también la rechaza hasta completar la integración.
  Las recetas existentes sin reloj mantienen su comportamiento.
- Pruebas de registro, simulación, fallas y telemetría: **78 aprobadas, 2 omitidas**
  en SQLite, 14,28 s. PostgreSQL de estos cambios aún pendiente. Sin cambios Vue.
- Próximo trabajo concreto: conversión de generación/entrega y fallas del outbox;
  después validación temporal en ingesta, reglas/monitoreo y presentación. Esta
  entrada documenta trabajo parcial, no un cierre funcional ni incremento del
  porcentaje global. El selector manual completado permanece cerrado.

### Selector de intervención en mediciones manuales (18-11-2026)

- Cerrado el pendiente funcional de sprints 6–7: selector opcional en el panel
  compartido, opciones compatibles por proceso/incidente, paginación, errores y
  reintento. Guardado y consulta conservan el vínculo sin cambiar la intervención
  ni el estado de la alerta. Nuevo endpoint de opciones con autorización vigente.
- Verificación: 19 aprobadas/3 omitidas SQLite; 22 aprobadas PostgreSQL; build
  correcto; navegador con API interceptada verifica selección, envío, recarga y
  reintento. [Evidencia y límites](evidencias/selector-intervencion-2026-11-18.md).
- Orden de continuación: (1) reloj acelerado completo, (2) navegación principal
  de procesos históricos y exportación, (3) UI integral/accesibilidad/móvil,
  (4) observabilidad, carga y respaldo/restauración. En paralelo al desarrollo,
  permanecen pendientes revisión enológica, datos reales y hardware; no se
  sustituyen con resultados sintéticos. Despliegue fuera del alcance autorizado.
- El reloj constituye un único bloque abierto: núcleo y cortes implementados no
  equivalen a modo operativo. Avance global conservador: aproximadamente 66 %;
  los cierres concretos anteriores son la medida verificable del progreso.

### Disponibilidad real separada de observación simulada (18-11-2026)

- Extractor y adaptador SQL incorporan `received_as_of` opcional; la salida conserva ambos cortes. La omisión mantiene el corte común anterior. Edad, cobertura y pendientes siguen expresadas en tiempo de observación; mensajes recibidos después del corte real quedan excluidos.
- SQLite: 41 pruebas aprobadas en 18,01 s (cinética, episodios y pipeline). PostgreSQL 18.4: 18 pruebas cinéticas aprobadas en 7,77 s. Casos adversariales con reloj real anterior y posterior al simulado, fronteras de microsegundos, mensajes futuros y retrasados, conversión de zona y compatibilidad del modo anterior.
- Esta sección es infraestructura interna del reloj acelerado. No habilita ingesta futura, no cambia los parámetros públicos de consulta ni activa ML. Pendientes: registro inmutable del reloj, preflight, worker/outbox, reglas, monitoreo y presentación Vue. No se cierra el sprint 4; se conserva 66 % global estimado.
- La validación PostgreSQL de la entrega previa ya se cerró con 305 pruebas aprobadas y se corrigió la espera de apagado del ejecutor. Las referencias a ese pendiente en registros anteriores son históricas.

### Ajustes térmicos auditados y traspaso de equipo (18-11-2026)

- Migración local 0008: historial inmutable, revisión/UUID únicos, autor autenticado, vigencia del servidor y bitácora atómica. Admin/enólogo aprueba banda completa o restaura la inicial como otra revisión. Sin doble firma ni cambios de Brix/pH, calibraciones o modelo biológico. Head: 29 tablas de dominio + Alembic.
- Selección por hora observada, preservación de backlog y reinicio de persistencia al cambiar revisión. Los episodios abiertos conservan sus umbrales y exigen recuperación medida; aprobar no altera evidencia, resolución ni MTTR. Snapshot del proceso y configuración base de reglas permanecen inmutables.
- Panel Vue con bandas inicial/vigente, umbrales conservados por episodios, motivo, aprobación/restauración e historial. Navegador/API/SQLite nuevos: dos revisiones persistentes después de recargar y episodio abierto sin recuperación automática.
- Suite completa: **289 aprobadas, 16 omitidas**, 89,62 s, 90 warnings, SQLite temporal/Python 3.11.4; ejecutada el 17-11 y navegador concluido el 18-11. Dieciséis nuevas aprobadas y dos casos PostgreSQL pendientes. Build Vite correcto, 4,11 s. Migraciones desde cero, downgrade/upgrade y concordancia ORM comprobadas. Modelo ML congelado intacto.
- [Contrato](AJUSTES_PERFIL_PROCESO.md), [evidencia](evidencias/ajustes-perfil-2026-11-18.md), [salida de pruebas](evidencias/profile-overrides-final.txt). Guías actualizadas para entregar los bloques acumulados y continuar en otro PC. Sin implementación pendiente dentro de esta sección; quedan validaciones externas explícitas. Sin Supabase ni despliegue.
- Siguiente: reproducir instalación/pruebas en el nuevo equipo, validar PostgreSQL temporal si está disponible y continuar con reloj acelerado explícito del simulador. Las recomendaciones DSS requieren revisión enológica.

### Comparación de curvas y evidencia manual al corte (17-11-2026)

- Contrato `curve-comparison-v1`, API de solo lectura con principal/referencia autorizados, alineación por horas de proceso, corte temporal y ventanas de hasta 168 h. Telemetría disponible por recepción, manuales por registro y anulaciones según lo conocido al corte; metadatos actuales del proceso separados.
- Segmentos independientes ante calidad insuficiente, horas ambiguas, huecos >15 minutos y cambios de dispositivo/calibración/origen. Manuales diferenciadas por método/instrumento; anuladas visibles en tabla y fuera del gráfico. Límites de 3.000/300 registros por proceso con total/truncamiento explícitos. Sin mezcla de métodos, inferencia causal ni recomendaciones automáticas.
- Panel Vue con dos curvas, puntos manuales, tablas de evidencia, procedencia y corte seleccionable. Navegador/API/SQLite nuevos: 97 puntos visibles y un contraste manual por proceso, alineados pese a distintas fechas de calendario; un corte anterior a recepción/registro retira toda esa evidencia y volver a ahora la restaura.
- Suite final: **273 aprobadas, 14 omitidas**, 77,72 s, 90 warnings, SQLite temporal/Python 3.11.4. Dieciséis pruebas nuevas. Build Vite correcto, 8,17 s. PostgreSQL pendiente, sin migración nueva ni cambios del modelo ML congelado.
- [Contrato y límites](COMPARACION_CURVAS.md), [evidencia](evidencias/comparacion-curvas-2026-11-17.md), `evidencias/curve-comparison-final.txt`. Siguiente bloque técnico: overrides de perfiles explícitos y auditados, conservando historia y configuración aplicada. Recomendaciones DSS requieren criterios enológicos y validación adicional. Supabase y producción intactos.

### Mediciones manuales estructuradas e interfaz (17-11-2026)

- Migración local 0007: observaciones manuales y anulaciones inmutables, UUID de reintento, autor autenticado, variable/unidad/método/instrumento, evidencia y horas observada/registrada. Vínculos autorizados al proceso, alerta e intervención opcionales; bitácora en la misma transacción. Sin reconstruir notas antiguas ni alterar telemetría, reglas, ML o resolución de episodios.
- API con catálogo, intervalos históricos, permisos por bodega, paginación y anulación motivada que conserva el original. UI compartida en detalle de cuba e incidente; reemplaza el antiguo ingreso libre «Registrar Muestra». Selector de intervención aún pendiente en UI; el vínculo existe en API.
- Suite completa: **257 aprobadas, 14 omitidas**, 93,28 s, 90 warnings, SQLite temporal/Python 3.11.4. Dieciocho nuevas aprobadas y tres casos PostgreSQL pendientes (inmutabilidad SQL y concurrencia). Migración desde cero, downgrade/upgrade y concordancia ORM comprobados; esquema actual 28 tablas de dominio + Alembic.
- Build final Vite correcto, 6,11 s. Navegador contra API/SQLite nuevos: alta de Brix, anulación con motivo y recarga persistente; contraste térmico vinculado al incidente #1001, bitácora actualizada y alerta todavía pendiente tras recarga. Sin certificación móvil, carga ni validación enológica.
- [Contrato y límites](MEDICIONES_MANUALES.md), [evidencia](evidencias/mediciones-manuales-2026-11-17.md), `evidencias/manual-measurements-final.txt`. Siguiente sección: comparación de curvas y evidencia manual para DSS, conservando métodos, unidades, origen y tiempo disponible. Supabase y producción intactos; ML operacional sin habilitar.

### Fallas programables HTTP/outbox y recuperación (17-11-2026)

- Contrato `emitter-faults-v1` congelado en calibración sintética/manifiesto: canales ausentes, Brix retenido/deriva, cortes, retardos y pérdidas. Inicializador con `--fault-plan`, ejemplo versionado y procedencia consultable. Sin modificación de la trayectoria biológica ni de los artefactos ML congelados.
- Generación independiente de entrega, dos cursores persistentes, FIFO, evidencia de pérdida sin ACK y conservación de sobres tras reinicio. Actualización compatible de estados SQLite antiguos del emisor, sin migración de aplicación. Cambios de receta rechazados por identidad/preflight; validación de valores, calidad y timestamp de los comprobantes.
- **22 pruebas nuevas**: cortes y recuperación, aislamiento de otros dispositivos, canales independientes, fallas transitorias/respuesta perdida, compatibilidad, CLI y confirmaciones falsas. TCP local real con Uvicorn/LocalHTTP comprueba episodio térmico, silencio/watchdog y backlog sin declarar recuperación ni resolución humana; reserva física sin lecturas.
- Suite completa: **239 aprobadas, 11 omitidas**, 180,34 s, 90 warnings, SQLite temporal y Python 3.11.4. Sin cambios frontend ni nueva comprobación de build/navegador; PostgreSQL pendiente. SHA-256 del modelo congelado preservado. Evidencia: [cierre](evidencias/fallas-emisor-2026-11-17.md), `evidencias/emitter-faults-tests-final.txt`.
- [Contrato, ejemplo, comandos y límites](FALLAS_SIMULADOR_HTTP.md). El corte programado afecta POST; el preflight sigue disponible. Reloj 1×, sin reordenación ni aceleración nueva. Próximo bloque: mediciones manuales estructuradas y su vínculo con procesos/incidentes. Supabase, producción y ML operacional sin cambios.

### Incertidumbre por trayectoria e intervalos de forecast (17-11-2026)

- Contrato `trajectory-uncertainty-v1`, CLI offline de calibración/evaluación con artefacto separado del modelo. Score máximo de error por proceso, solo partición calibration; rango finito sin recorte. Datos insuficientes dejan radio null; reconstrucción de calibración comprueba integridad. Modelo y umbral preservados.
- Bootstrap de 2.000 réplicas por procesos completos, estratificado por escenario y pareado entre condiciones. Multiplicidad de procesos conservada, métricas no definidas sin límites ficticios y rangos degenerados identificados. Se separa cobertura de bandas emitidas y servicio de todas las ventanas con target.
- Quince trayectorias de calibración producen radio **±3,8568 °Bx** al 90 % nominal. Test original y stress limpio quedan cubiertos, pero con sensor retenido solo **8/20 trayectorias** completas y con deriva **0/20**, aunque la cobertura por ventana sea 96,08/90,31 %. Banda amplia, evaluación retrospectiva y sin garantía real; no habilita forecast operacional.
- Suite completa: **217 aprobadas, 11 omitidas**, 178,91 s, 90 warnings, SQLite temporal. Doce pruebas nuevas, contaminación de splits ajenos sin efecto en el radio, bootstrap y repetición de evaluación con hashes idénticos. Sin cambios frontend/build/navegador; PostgreSQL pendiente.
- [Contrato, referencias y comandos](INCERTIDUMBRE_ML.md), [resultados y huellas](evidencias/incertidumbre-ml-2026-11-17.md), `evidencias/uncertainty-tests-final.txt`. Siguiente bloque local: fallas programables del simulador HTTP/outbox y recuperación de comunicaciones. No se modificó Supabase ni se desplegó.

### Ensayo offline de fallas de sensores y comunicaciones (17-11-2026)

- Contrato `sensor-stress-v1`: 20 trayectorias nuevas con semillas separadas de las 100 originales, ocho condiciones pareadas y 11.680 ventanas. Incluye canal ausente, sensor retenido, deriva, pérdida de mensajes, entrega acumulada y latencia. Etiquetas/targets originales conservados; modelo, calibración y umbral congelados.
- Informes de cobertura/abstención, riesgo condicional, detección sobre todos los eventos, forecast, pares comunes y desgloses por escenario/proceso. Hashes, recetas y predicciones reproducibles; sin importaciones de base de datos ni HTTP.
- Hallazgos: limpio detecta **6/12 eventos**; canal ausente o pérdida detectan **1/12**; entrega acumulada **4/12**; latencia de dos horas fuerza abstención total. Sensor retenido/deriva siguen elegibles y elevan MAE de 0,306 a 0,750/1,310 °Bx, y falsas ventanas de 16 a 40/31. Se cierra el ensayo, no se certifica robustez ni se habilita el modelo.
- Suite completa: **205 aprobadas, 11 omitidas**, 161,34 s, SQLite temporal, 90 warnings. Ocho pruebas nuevas, incluida repetición determinista y prohibición de fit en evaluación. Sin cambios frontend; no se repitió build/navegador. PostgreSQL pendiente.
- [Contrato y reproducción](ROBUSTEZ_PIPELINE_ML.md), [resultados y huellas](evidencias/robustez-ml-2026-11-17.md), `evidencias/robustness-tests-final.txt`. Siguiente sección: incertidumbre de métricas por trayectoria e intervalos de forecast, calibrados sin consultar test para ajustarlos. Supabase y producción intactos.

### Intervenciones estructuradas y respuesta declarada (17-11-2026)

- Migración local 0006: propuestas con responsable autorizado, proceso/alerta coherentes, ejecución, seguimiento, cierre o cancelación. UUID de reintento, control de revisión, historial inmutable y bitácora en una transacción. El cierre humano no modifica alertas, recuperación, MTTR ni ML.
- Panel Vue en detalle de cuba y ficha de incidente: responsables, acciones según permisos, formularios, historial y paginación. Se conserva el UUID ante fallos de comunicación dentro del componente.
- Validación final completa: **197 aprobadas, 11 omitidas**, 120,57 s, SQLite temporal; build Vite correcto (12,30 s). Las omisiones incluyen tres pruebas nuevas PostgreSQL de trigger/concurrencia, pendientes de ejecución en ese motor. Se mantienen 90 warnings heredados. Evidencia: `evidencias/interventions-final.txt`.
- Navegador contra API/SQLite nueva desechable: propuesta, ejecución declarada, seguimiento no evaluable y cierre; recarga conserva los cuatro eventos. Episodio cinético sigue en seguimiento y ML en NO_VALIDADO. No se afirma validación móvil ni enológica.
- Contrato y límites: [Intervenciones estructuradas](INTERVENCIONES_ESTRUCTURADAS.md). Pendientes mediciones manuales con unidad/método, comparación de curvas y DSS. Siguiente sección: fallas de sensores, cortes y retardos en evaluación offline con modelo congelado. Sin Supabase ni despliegue.

### Versionado de perfiles y configuración aplicada (16-11-2026)

- Migración local 0005, historial inmutable con autor/fecha/origen, revisiones y edición optimista desde Vue; no-op y archivo idempotentes. Límites ausentes permanecen null.
- Nuevos procesos iniciados por API y nueva flota simulada conservan parámetros completos. Las reglas térmicas, diagnóstico y consulta de cuba usan el snapshot, incluso si se edita el perfil antes de la primera lectura. Procesos históricos quedan explícitamente sin snapshot; no se inventa su configuración inicial.
- Historial consultable en API y Vue; preservación de parámetros y permisos verificados. Detalles y límites en [Perfiles versionados](PERFILES_VERSIONADOS.md). Sin migración remota ni despliegue.
- Validación final: **185 aprobadas, 8 omitidas**, 47,17 s, SQLite temporal; build Vite correcto (4,66 s). Migración desde cero, downgrade/upgrade y preservación de datos previos comprobados. PostgreSQL no reejecutado; UI verificada por compilación, sin nueva sesión de navegador. Evidencia: `evidencias/profiles-final.txt`.
- Siguiente bloque: intervenciones estructuradas y seguimiento de respuesta. Quedan overrides explícitos, validación PostgreSQL y revisión integral de controles heredados.

### Diagnóstico de reglas y silencio: implementación local (16-11-2026)

- `current_monitoring` distingue ausencia de mensajes, falta de recepción, mediciones atrasadas y datos recientes; diagnostica límites térmicos ausentes/configuración congelada y regla cinética sin configurar. Vue muestra el estado sin convertir frescura en salud.
- Watchdog explícito demo/test, sin arranque automático ni escrituras en GET: reinicia persistencia, marca episodios abiertos como desconocidos y audita una sola transición. No inventa observaciones ni declara recuperación/resolución. No requiere migración nueva.
- Validación final: **177 aprobadas, 8 omitidas**, 45,76 s, SQLite temporal; build Vite correcto. Incluye frontera temporal, retorno de datos, candidatos y guarda de entorno. PostgreSQL no reejecutado; diagnóstico Vue verificado por compilación, sin nueva sesión de navegador. Evidencia: `evidencias/monitoring-final.txt`.
- Contrato, ejecución y límites: [Seguimiento y silencio](SEGUIMIENTO_Y_SILENCIO.md). Próximo bloque: perfiles versionados completos; después intervenciones estructuradas y robustez ML. Sin Supabase ni despliegue.

### UI de cinética y evidencia de episodios (16-11-2026)

- Panel de tasas por hora, cobertura/huecos por canal, motivos de abstención, procedencia, actualización manual y automática. Errores de consulta retiran los valores actuales; riesgo/forecast permanecen N/D.
- Evidencia cinética en fichas de incidentes, con pendientes, umbrales, persistencia y actor de configuración. Corregidos sensor/canal y unidades en la lista de alertas para el nuevo tipo.
- Suite final local: **169 aprobadas, 8 omitidas**, 65,79 s, SQLite temporal. PostgreSQL no reejecutado. Build Vue comprobado.
- Navegador contra API/SQLite nueva desechable: login, curva sintética de 25 h, panel con pendientes/cobertura, actualización manual y ficha del episodio persistido con configuración. Captura local `backend/artifacts/kinetic-panel.jpg`. Sin certificación móvil, carga ni validación enológica.
- Próximo bloque: perfiles versionados completos, watchdog de silencio, intervenciones estructuradas y ensayos de fallas/retardos. La regla cinética física sigue sin habilitarse. No se modificó Supabase ni se desplegó.

### Episodios cinéticos experimentales persistentes (16-11-2026)

- Regla `kinetic-episodes-v1` opt-in por proceso, exclusivamente simulada y en demo/test; sin habilitación automática ni umbrales para dispositivos físicos. Activación por administrador/enólogo con identidad, fecha y configuración congelada en `ESTADO_REGLA`, sin migración nueva.
- Confirmación y recuperación sostenidas, histéresis, control de calidad Brix independiente de temperatura, huecos y recepción tardía. Auditoría/ingesta en una transacción, reintentos sin duplicación y cierre de proceso separado de recuperación y gestión humana.
- Primer cierre: 11 pruebas del bloque aprobadas, incluyendo replay HTTP de 25 h con extractor real. Se amplía la matriz de permisos y se registrará la suite consolidada al cerrar UI. Se corrigió la ubicación de un paso de aprovisionamiento en la prueba de operador, que la ejecución ampliada había detectado.
- Siguiente sección: presentación de tasas/cobertura/abstención y evidencia cinética en Vue; comprobar con API/SQLite local desechable. No se habilita riesgo ML ni forecast operacional.

### Contrato causal y objetivo ML experimental (16-11-2026)

- Contratos `kinetics-v1` y `future-stall-v1` documentados en [Cinética y pipeline](CINETICA_Y_PIPELINE_ML.md): disponibilidad por observación/recepción, calidad independiente y calibración homogénea.
- Riesgo de inicio futuro en 12 h, anticipación mínima de 2 h, persistencia de 6 h y forecast de Brix aparente a 24 h. Objetivo sintético latente separado de reglas descriptivas y de una futura etiqueta enológica real.
- Particiones por proceso/semilla para entrenamiento, calibración, validación y test; los escenarios no son features. Umbrales y presupuesto de falsas alarmas son decisiones experimentales, pendientes de aprobación enológica antes de uso real.
- Comprobación de partida: rama `codex/mosto-safe-foundation`, commit `8bda568`, árbol inicialmente limpio. Este equipo dispone de Python 3.11.4, no del 3.14 de la entrega; se instalaron las dependencias de pruebas faltantes. No se consultó ni modificó Supabase.
- Siguiente cierre: verificar extractor/API con pruebas de fuga temporal, cobertura, cadencia y autorización, y después ejecutar la comparación sintética offline.

### Extractor causal y consulta por proceso (16-11-2026)

- Extractor compartido en `app/services/kinetics.py`, con tasas suavizadas, pendientes de 6/24 h, dispersión residual, contexto térmico y motivos de abstención. Filtra tanto observación como recepción; no mezcla procesos ni usa valores futuros.
- `GET /api/procesos/{id}/cinetica?as_of=...`: consulta autenticada dentro del ámbito de empresa/bodega, sin escrituras, con evidencia descriptiva y riesgo/forecast null. No crea episodios cinéticos persistentes ni habilita el modelo legacy.
- Primera suite de este equipo: **144 aprobadas, 8 omitidas**, 112,29 s, en SQLite temporal. Incluye invariancia de cadencia, timestamps, huecos, calibraciones, canales independientes y acceso entre empresas. Posteriormente se refuerzan pruebas de calidad actual y recepción tardía; el resultado final se registra al cerrar el pipeline.
- Siguiente paso: comparación offline de riesgo/forecast sobre trayectorias completas, con artefactos separados de los modelos operacionales.

### Pipeline ML y forecast sintético offline (16-11-2026)

- Comandos separados `ml.causal_pipeline generate/train/evaluate`, artefactos sin sobrescritura y sin importar base de datos/configuración. Manifiestos con recetas completas, semillas, contratos, versiones y hashes; CSV/pickle originales intactos.
- 100 trayectorias de 240 h y 7.300 ventanas; splits de 55/15/15/15 procesos para train/calibration/validation/test, sin semillas compartidas. Pruebas adversariales verifican que contaminar test no cambia fit, escalado, calibración ni umbral.
- Test sintético: logística calibrada Brier 0,04021 frente a prevalencia 0,05195; detecta **4/9 eventos**, anticipación mediana entre detectados 5,5 h, dos ventanas falsas positivas. Falla los tres eventos de agotamiento simulado; calibración no mejora claramente respecto del modelo sin calibrar. Forecast Ridge MAE 0,32089 °Bx frente a persistencia 1,47784 y extrapolación lineal 0,62213.
- Suite final: **157 aprobadas y 8 omitidas** en SQLite temporal, 103,60 s; build Vite correcto. PostgreSQL no reejecutado en este equipo por falta de binarios disponibles; las 139 aprobadas anteriores siguen siendo evidencia histórica.
- Evidencia y límites: [informe](evidencias/cinetica-ml-2026-11-16.md), [métricas/huellas](evidencias/cinetica-ml-evaluation.json), [contrato/comandos](CINETICA_Y_PIPELINE_ML.md). Repetida generación con código final: mismo dataset y métricas.
- Cierre del **pipeline experimental**, no del sprint 5 completo: el modelo no se habilita en v2, riesgo/forecast siguen null. Pendientes episodios cinéticos persistentes, UI de tasas/cobertura, fallas/retardos y validación externa/real. Sin Supabase, despliegue, commit ni push.

### Backend de episodios térmicos (15-11-2026)

- Confirmación y recuperación tras diez minutos, histéresis, calidad por canal y tolerancia explícita de huecos.
- Condición medida independiente de la gestión humana; concurrencia, reintentos, escalamiento y cierre de proceso comprobados.
- Migración 0004, auditoría de eventos, enlace a bitácora y MTTR sin convertir tiempos ausentes o negativos en cero.
- Primer cierre: PostgreSQL 137 aprobadas; SQLite 129 aprobadas y 8 omitidas. Después se añadieron comprobaciones de aislamiento de historia/intervenciones y rechazo de fuentes mezcladas por proceso.

### Interfaz de incidentes y auditoría (15-11-2026)

- Corregida la omisión de llamadas al servidor para IDs ≥1000; eliminadas las alertas inventadas y el falso aislamiento remoto del sensor.
- Notas, contraste manual, atención y resolución persistidos; autores/fechas del servidor. La resolución no declara recuperación física.
- Panel compartido con evidencia, umbrales congelados, procedencia, condición/gestión y bitácora vinculada.
- Prueba real HTTP → FastAPI → SQLite → Vue: episodio #1001, tres entradas de bitácora, recarga persistente y ficha de auditoría coherente. También comprobada resolución desde Auditoría y rechazo visual de una nota insuficiente.
- Sin errores JavaScript ni respuestas API fallidas en ese flujo. Tablas limitadas explícitamente a 500 registros; las métricas de Auditoría corresponden al historial completo de la cuba seleccionada.

### Consolidación y documentación (15-11-2026)

- Suite completa final: PostgreSQL 139 aprobadas; SQLite 131 aprobadas y 8 omitidas.
- Build Vite aprobado; documentos de alertas, simulador, telemetría, migraciones y este estado sincronizados.
- Evidencias locales: `backend/artifacts/episodes-sqlite-final.txt`, `backend/artifacts/episodes-postgres-final.txt`; capturas `episodes-resolution-live.png`, `episodes-audit-live.png` y `episodes-browser-results.json` en el directorio de auditoría.
- Persisten advertencias de deprecación del código heredado. El resultado no equivale a certificación de producción ni a una validación enológica.

## Siguiente bloque de ejecución

Continuar desde la cinética causal y evaluación sintética implementadas:

1. Acordar con enología umbrales/perfiles y etiquetas reales: el objetivo actual es solo un sustituto sintético de parada.
2. **Siguiente bloque técnico:** reloj acelerado explícito del simulador, con hora simulada/observada y recepción real diferenciadas, procedencia visible y pruebas de persistencia, fallas y reinicio. Antes, reproducir instalación y suite en el nuevo PC; validar PostgreSQL temporal cuando esté disponible. Perfiles versionados, snapshots y ajustes térmicos auditados ya implementados.
3. Comparación descriptiva de curvas y evidencia manual ya implementada. Completar recomendaciones DSS trazables con criterios revisados por enología y validación de utilidad; sin equiparar refractometría con azúcar residual ni convertir correlación en recomendación causal. Quedan selector UI de intervención para mediciones, navegación de procesos históricos como principal, exportación y rediseño integral.
4. Incertidumbre por trayectoria, intervalos experimentales y fallas programables HTTP/outbox ya implementados. Quedan reloj acelerado explícito, mecanismos biológicos externos y mitigaciones evaluadas sobre otra reserva independiente; no reutilizar los test vistos para ajustar hiperparámetros ni estrechar bandas.
5. Validar con datos reales independientes antes de cualquier modo de observación operacional ML; mantener N/D mientras no exista evidencia suficiente.

El origen de simulación, el nombre del escenario y los estados latentes se conservan como procedencia/evaluación: no se introducirán como features de inferencia de un dispositivo real. Watchdog explícito, diagnóstico de regla sin perfil, perfiles versionados e intervenciones con respuesta declarada ya tienen implementación local; sus límites y el resto de pendientes figuran en las secciones y tabla anteriores.

## Última evidencia

- SQLite, suite ejecutada el 17-11-2026 para el cierre del 18-11: **289 aprobadas y 16 omitidas** por depender de PostgreSQL; Python 3.11.4, 89,62 s, 90 warnings. Evidencia: `evidencias/profile-overrides-final.txt`.
- PostgreSQL 18.4, evidencia anterior del 15-11-2026: 139 pruebas aprobadas. No reejecutado para este bloque.
- Pipeline sintético sobre 100 trayectorias, ensayo sobre 20 nuevas con ocho condiciones pareadas e incertidumbre posterior con calibración separada/bootstrap por proceso; fallos y límites documentados, sin habilitación operacional.
- Evidencia previa del simulador (sección anterior): worker HTTP real, FastAPI, SQLite y Vue: cinco trayectorias al día, reinicio sin duplicación, reserva física sin lecturas y ventana de 24 horas con 288 puntos.
- Nuevo ensayo HTTP del emisor: Uvicorn TCP local, silencio durante corte y replay de datos atrasados sin recuperación ni resolución ficticias. Las 22 pruebas del bloque incluyen reinicio, sobres exactos y actualización de estado antiguo.
- Último build Vite: ajustes térmicos (4,11 s), con navegador concluido el 18-11 en detalle de cuba: aprobación, restauración y recarga conservan ambas revisiones y el episodio abierto. API local de prueba explícita en 8879, detenida al cerrar. No existe una suite E2E portable.
- La prueba local no acredita producción, exactitud física, generalización ML ni integración del prototipo.

Detalles: [Episodios y alertas v2](ALERTAS_V2_Y_EPISODIOS.md), [Telemetría v2](TELEMETRIA_V2.md), [Simulador](SIMULADOR_ENOLOGICO.md), [Autorización](AUTORIZACION_EMPRESA_BODEGA.md) y [Migraciones](MIGRACIONES_Y_POSTGRESQL.md).

## Traspaso a otro equipo

Informe original, adenda del notebook y cobertura preservados en `auditoria_inicial/`; resultados finales de pruebas y navegador en `evidencias/`. Estos documentos históricos no sustituyen este estado actualizado. Secretos, bases locales y artefactos de ejecución se regeneran siguiendo CONTINUAR_MOSTO.md.

## Verificación del traspaso en equipo original (18-11-2026)

- Historial comprobado: 8bda568 (carcartes) declaraba 45 %; 267bd29 (Geraldine Silva) declara aproximadamente 66 %. Git no identifica cuentas de Codex. HEAD y rama remota consultada con ls-remote coinciden en 267bd297de611e49237e4a040a521a2811d3131a; árbol inicialmente limpio.
- Reproducción local con entorno existente Python 3.14: SQLite 289 aprobadas, 16 omitidas, 3497 warnings, 114,50 s. Build Vite aprobado en 4,36 s. No se acredita instalación limpia.
- PostgreSQL 18.4 temporal: 295 aprobadas y 10 errores, 3666 warnings, 200,13 s. Los diez errores ocurren en la fixture kinetic_stream (backend/tests/test_kinetic_episodes.py:23): intenta actualizar asignado_en de una asignación histórica y el trigger mosto_immutable_scope lo rechaza. Validación PostgreSQL ABIERTA; corregir preparación temporal de la fixture sin debilitar la inmutabilidad y repetir pruebas antes del reloj acelerado.
- El apagado temporal excedió 60 s por checkpoint; comprobación posterior pg_ctl status: no server running, y log confirma database system is shut down. Directorio diagnóstico conservado en backend/artifacts/mosto-pg-b5l2ni10 (ignorado por Git).
- Se cierra la comprobación documental/Git y reproducción SQLite/build; no se cierra PostgreSQL. Se mantiene la estimación 66 %. Reloj acelerado todavía no implementado en esta revisión. Sin despliegue ni cambios en Supabase.

## Cierre de validación PostgreSQL (18-11-2026)

Se corrigió la fixture kinetic_stream para avanzar desde la fecha actual con reloj controlado, sin actualizar asignado_en de una asignación histórica. Los triggers de inmutabilidad permanecen intactos. Resultado: PostgreSQL 18.4, suite completa, 305 aprobadas, 3668 warnings, 193,54 s; SQLite, 12 pruebas cinéticas aprobadas, 232 warnings, 10,06 s. Entorno Python 3.14.6 existente. La suite SQLite completa y build anteriores siguen vigentes; no hubo cambios de producto/frontend.

Queda cerrado el defecto de preparación de pruebas y validación funcional PostgreSQL local de la entrega. Esto no valida CI remota, instalación limpia, producción ni datos reales. Avance estimado conservado en 66 %. Próximo bloque: implementar el contrato propuesto en backend/docs/RELOJ_ACELERADO.md; documento de diseño, todavía sin aceleración habilitada.
Nota del ejecutor: pytest pasó, pero el comando global salió con código 1 por timeout de apagado a 60 s. El checkpoint tardó 91,964 s; pg_ctl status posterior confirmó no server running y el log confirmó apagado completo. Clúster diagnóstico conservado en backend/artifacts/mosto-pg-ggkv8x3o. Pendiente robustecer la espera de apagado del script antes de considerar cerrado el ejecutor completo.

## Cierre del ejecutor PostgreSQL y núcleo temporal (18-11-2026)

- Corregido scripts/test_postgres.py: solicitud única de apagado sin espera bloqueante de pg_ctl, comprobaciones de estado cada cinco segundos y plazo total de 180 s. Solo el estado explícito de servidor detenido autoriza eliminar el clúster temporal; errores o plazo vencido conservan el directorio y hacen fallar el comando.
- Validación: dos pruebas del ejecutor aprobadas (checkpoint lento, estado desconocido y plazo agotado); ejecución real PostgreSQL 18.4 con las 12 pruebas cinéticas aprobadas en 12,72 s, apagado confirmado y comando final con código 0. Esto cierra el defecto del ejecutor registrado anteriormente. La suite completa previa mantiene 305 aprobadas; no se afirma haber repetido toda la suite en este cierre.
- Implementado app/simulation/clock.py: anclas UTC y factor inmutables, conversiones real/simulada e inversa, retraso de transporte en segundos reales y validación estricta de rango/fechas. Quince pruebas aprobadas en 1,99 s. Contrato y límites: backend/docs/RELOJ_ACELERADO.md.
- Cierre parcial del sprint 4: núcleo temporal probado; pendiente integración con receta/preflight, worker/outbox, ingesta, reglas, cortes causales y API/Vue. El modo acelerado no está habilitado. Próxima sección: registrar el reloj de forma inmutable y separar disponibilidad real de observación simulada sin alterar el modo 1x.
- Avance global conservado en aproximadamente 66 % hasta cerrar la integración. Sin cambios remotos, despliegue ni habilitación ML. Los registros anteriores quedan como evidencia histórica.

Validación consolidada tras la retoma (18-11): SQLite, 315 aprobadas y 16 omitidas por PostgreSQL, 3782 warnings, 101,97 s. Las pruebas específicas del emisor suman 53 aprobadas. No se reejecutó toda la suite PostgreSQL para los cambios nuevos del reloj; la evidencia de 305 aprobadas corresponde al cierre anterior.
