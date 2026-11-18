# Traspaso de Mosto a otro desarrollador / Codex

Actualizado: 18-11-2026. Rama de entrega: `codex/mosto-safe-foundation`, remoto `https://github.com/GeraldineSilvaPino/mosto.git`. Esta entrega reúne cinética/ML, perfiles, intervenciones, fallas, incertidumbre, mediciones manuales, comparación de curvas y ajustes térmicos auditados. Las menciones históricas de «sin commit/push» describen el momento de cada cierre; comprobar la sincronización de esta entrega con Git.

## Punto de entrada

**Modo vigente: desarrollo paralelo en dos ramas.** Leer antes de editar
[PLAN_PARALELO](backend/docs/paralelo/PLAN_PARALELO.md), contrato de coordinación
y plan de la rama correspondiente. A: codex/mosto-safe-foundation (backend y
validación); B: codex/mosto-ui-delivery (frontend y entrega UI). Cada rama tiene
estado propio: no editar el estado de la otra. Las instrucciones históricas
inferiores de continuar todo en una sola rama quedan sustituidas por este reparto.
Navegación histórica ya implementada y probada con API simulada; reloj acelerado
parcial se entrega a A, no es necesario terminarlo antes de crear las dos ramas.
Avance global revisado aproximado: 68 %, sin equivaler a certificación de producción.

Último cierre: exportación JSON de evidencia consultada en comparación de curvas,
con descarga verificada en Edge (API simulada) y build aprobado. Conserva límites,
anulaciones y corte; no es exportación completa ni CSV. Próximo independiente:
navegación histórica como proceso principal. El reloj requiere migración de las
guardas temporales PostgreSQL de 0002/0003 antes de habilitar ingesta; ver estado.

Último cambio (18-11): ajustes térmicos evaluados por hora real esperada de la
observación; cierre de episodios separa fin simulado y registro real sin declarar
recuperación. SQLite 29 aprobadas/3 omitidas, PostgreSQL 20 aprobadas. Pruebas
aceleradas con reloj inyectado. Continuar con selección temporal en ingesta y
consultas históricas; después Vue y HTTP completo. Ingesta acelerada aún bloqueada.

Última adaptación del reloj: reglas cinéticas y monitoreo distinguen tiempo
simulado/real mediante `services/simulation_time.py`. Suite relacionada: 40
aprobadas; tres pruebas específicas posteriores aprobadas. Los casos acelerados
inyectan el reloj: la ingesta real sigue bloqueada. Revisar vigencia de overrides,
cierre de procesos y consultas antes de retirar esa guarda; después Vue y HTTP
real. El sprint 4 sigue abierto, avance global aproximado 67 %.

Retoma más reciente (18-11): emisor acelerado/outbox verificado con 53 pruebas.
Corregida la fixture de identidad antigua que quedó fallando al interrumpirse.
La ingesta aún rechaza calibraciones aceleradas: continuar con reglas cinéticas,
monitoreo, validación de disponibilidad real y API/Vue antes de habilitarla.
Estimación global revisada: aproximadamente 67 %. HEAD sigue en 267bd29;
el trabajo posterior es local, sin commit ni push. Prevalece este estado sobre
las notas históricas inferiores. Ver balance y orden en ESTADO_PLAN_MAESTRO.

Avance más reciente del reloj (18-11): registro `simulation_clock` en calibración
sintética y devolución en preflight implementados. Registro limitado a demo/test,
ancla simulada coherente e identidad temporal conservada por dispositivo/proceso.
Worker e ingesta rechazan expresamente estas recetas mientras falta integración;
no hay modo acelerado operativo. 78 pruebas aprobadas y 2 omitidas SQLite.
Continuar con generación/entrega/fallas de outbox y luego ingesta, reglas y Vue.

Último cierre funcional: selector de intervención en mediciones manuales, con
opciones autorizadas compatibles, paginación y reintento. Ver evidencia en
`backend/docs/evidencias/selector-intervencion-2026-11-18.md`. Este pendiente
ya está implementado. Retomar ahora el reloj acelerado como bloque completo;
después navegación histórica/exportación y UI integral. No volver a contar
núcleo temporal o separación de cortes como nuevos cierres funcionales.

Último cierre local (18-11): corregida fixture cinética y apagado PostgreSQL;
suite completa PostgreSQL de la entrega: 305 aprobadas. Núcleo de reloj en
`app/simulation/clock.py` implementado (15 pruebas); extractor y adaptador SQL
ya separan observación de disponibilidad real con `received_as_of` (41 pruebas
SQLite y 18 PostgreSQL del cierre). Todavía NO hay modo acelerado operativo.
Continuar con registro inmutable del reloj y preflight, después worker/outbox,
ingesta, reglas/monitoreo y Vue según `backend/docs/RELOJ_ACELERADO.md`.
Los registros posteriores de este documento conservan la historia de cada cierre.

Este archivo permite continuar sin el chat anterior. Leer primero [Estado del plan maestro](backend/docs/ESTADO_PLAN_MAESTRO.md), después [informe original](backend/docs/auditoria_inicial/Informe_Maestro_Mosto.md), [adenda del notebook generador](backend/docs/auditoria_inicial/Adenda_Notebook_ML.md) y los documentos del bloque que se vaya a modificar. El informe es una fotografía histórica anterior a las correcciones; para el estado actual prevalecen el código, las pruebas y ESTADO_PLAN_MAESTRO.

Objetivo: plataforma FastAPI + Vue para fermentación enológica, con temperatura y Brix aparente, cinco escenarios simulados continuos y un futuro prototipo ESP32/DS18B20/MPU-6050. Debe ofrecer seguimiento operativo y, tras validación, riesgo futuro de parada y proyección de Brix. El avance global estimado es aproximadamente 66 %, no una certificación ni porcentaje de exactitud del modelo.

## Recuperar y comprobar el trabajo

En un PC sin checkout:

```sh
git clone --branch codex/mosto-safe-foundation https://github.com/GeraldineSilvaPino/mosto.git mosto
cd mosto
git status --short --branch
```

Si ya existe un checkout, comprobar `git status` y conservar sus cambios antes de actualizar. Con el árbol limpio:

```sh
git fetch origin
git switch codex/mosto-safe-foundation
# Si aún no existe localmente: git switch --track origin/codex/mosto-safe-foundation
git pull --ff-only origin codex/mosto-safe-foundation
git rev-parse HEAD
git rev-parse origin/codex/mosto-safe-foundation
```

Las dos huellas deben coincidir. No usar `reset --hard` para resolver diferencias. Crear un entorno nuevo; no copiar el venv del PC anterior.

En Windows, desde la raíz:

```powershell
py -3.11 -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
.\backend\venv\Scripts\python.exe -m pytest -q --disable-warnings
cd frontend
npm ci
npm run build
```

Consultar `backend/requirements-tested-windows-py311.txt` para las versiones observadas. Instalar Node/npm en el nuevo equipo y usar `npm ci` con el lockfile. Configurar la API según `frontend/.env.example` en un archivo local ignorado; recompilar con el destino correcto. Las compilaciones de navegador usaban puertos de prueba desechables.

En Linux usar `backend/venv/bin/python`. La entrega del 15-11 se comprobó en Windows, Python 3.14 y PostgreSQL 18.4; `requirements-tested-windows-py314.txt` registra aquellas versiones. Los bloques del 16–17-11 se comprobaron con Python 3.11.4 y SQLite temporal, sin certificar portabilidad a Linux ni PostgreSQL para los cambios nuevos. No reutilizar un venv de otra máquina.

PostgreSQL temporal, desde la raíz, si se tienen sus binarios instalados:

```powershell
.\backend\venv\Scripts\python.exe backend/scripts/test_postgres.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'
```

Ajustar la ruta a la instalación propia. Este script crea y elimina exclusivamente su clúster temporal. Alternativa Docker y reglas de aislamiento: [migraciones](backend/docs/MIGRACIONES_Y_POSTGRESQL.md). Docker y CI remota todavía requieren validación; no asumir que ya pasaron.

## Demo desde cero

Seguir [Simulador enológico](backend/docs/SIMULADOR_ENOLOGICO.md), que contiene los comandos de inicialización, API y worker. Copiar `backend/.env.simulation.example` a `backend/.env.simulation`, completar secretos aleatorios y contraseña propios, y usar una base local NUEVA. La inicialización genera credenciales individuales y manifiesto; el worker debe usar los archivos generados en esa máquina.

Los `.env` reales, bases SQLite, claves de dispositivos, outbox, venv y compilaciones no se transfieren por Git. El usuario demo es `demo@example.invalid`; su contraseña la elige el desarrollador al inicializar. No usar credenciales rápidas antiguas de la interfaz.

La API exige configuración y esquema migrado; arrancarla no crea tablas ni datos. La revisión actual es `0008_process_profile_overrides` (29 tablas de dominio, más Alembic). No ejecutar inicializadores de demo sobre Supabase ni sobre datos reales. Production sigue deshabilitado explícitamente.

## Lo implementado y sus límites

- Autenticación y autorización por empresa/bodega; migraciones reproducibles y guardas de PostgreSQL.
- Telemetría v2 con credenciales por dispositivo, calibración, tiempo observado/recibido, calidad independiente, atribución histórica e idempotencia.
- Simulador por fases y cinco escenarios, HTTP con outbox persistente y reserva física sin mediciones falsas. No es un gemelo calibrado científicamente.
- Episodios térmicos con persistencia e histéresis, auditoría, resolución humana separada de recuperación y bitácora vinculada. MTTR excluye fechas inválidas y devuelve null sin casos válidos.
- Acciones reales en Vue, procedencia y evidencia visible. El rediseño integral todavía falta; las tablas de incidentes muestran hasta 500 registros y explicitan el límite.
- El ML legacy se conserva como baseline experimental. Sobre telemetría v2 devuelve NO_VALIDADO / riesgo null; no habilitarlo simplemente para mostrar un porcentaje.
- Extractor causal compartido con consulta `GET /api/procesos/{id}/cinetica`, cobertura/calidad y abstención. Pipeline offline por trayectorias completas, etiquetas futuras, splits por proceso/semilla, calibración y baselines de riesgo/forecast. Ver [contrato y comandos](backend/docs/CINETICA_Y_PIPELINE_ML.md). Sigue siendo evaluación sintética. La UI muestra cinética y existen episodios cinéticos opt-in solo simulados.
- Perfiles versionados y snapshot en procesos nuevos; diagnóstico de silencio/configuración y watchdog local explícito. Intervenciones estructuradas con responsable, ejecución, respuesta declarada, historial, control de revisión e idempotencia. Ver [contrato de intervenciones](backend/docs/INTERVENCIONES_ESTRUCTURADAS.md).
- Ensayo offline de fallas con modelo congelado: 20 trayectorias nuevas, ocho condiciones pareadas, canal ausente, sensor retenido, deriva, pérdida de mensajes, backlog y latencia. El limpio detecta 6/12 eventos; pérdida o canal ausente 1/12. Se documenta degradación y abstención, no se certifica robustez. Ver [contrato y resultados](backend/docs/ROBUSTEZ_PIPELINE_ML.md).
- Incertidumbre experimental por trayectoria: bootstrap estratificado/pareado e intervalos de forecast ajustados solo con calibration. Banda nominal 90 % de ±3,8568 °Bx; fallas sin bandera degradan cobertura por trayectoria. Sin habilitación operacional. Ver [método, comandos y límites](backend/docs/INCERTIDUMBRE_ML.md).
- Fallas programables del emisor HTTP: canales ausentes, Brix retenido/deriva, cortes, retardos y pérdidas. Cola con generación independiente del ACK, recuperación tras reinicio y compatibilidad con estados antiguos; comprobantes contrastados con el sobre original. Ver [contrato y ejemplo](backend/docs/FALLAS_SIMULADOR_HTTP.md). No cambia el modelo biológico ni habilita ML operacional.
- Mediciones manuales con variable/unidad/método/instrumento, autoría, fecha observada, evidencia y anulación trazable. API y panel en cuba/incidente con bitácora; no modifica telemetría, reglas ni ML. Ver [contrato y límites](backend/docs/MEDICIONES_MANUALES.md).
- Comparación descriptiva de curvas de dos procesos alineados por edad, con corte temporal por recepción/registro, manuales diferenciadas por método y anulaciones históricas. API y gráfico Vue con cantidades, límites y tablas. Ver [contrato y límites](backend/docs/COMPARACION_CURVAS.md). No produce recomendaciones causales ni habilita ML.

- Ajustes térmicos auditados por proceso con aprobación admin/enólogo, motivo, vigencia del servidor, revisión e idempotencia; restauración sin borrar historial. Los episodios abiertos mantienen sus límites hasta recuperación medida. [Contrato](backend/docs/AJUSTES_PERFIL_PROCESO.md).

Validación del cierre 18-11: **289 pruebas aprobadas y 16 omitidas**, 89,62 s, SQLite temporal (suite ejecutada el 17-11). Build Vite correcto (4,11 s) y navegador con aprobación, restauración y recarga persistente, sin recuperación automática del episodio. API de prueba en 8879, detenida al cerrar. Windows/Python 3.11.4; 90 warnings heredados. PostgreSQL no reejecutado: las 16 omisiones requieren ese motor; las 139 aprobadas del 15-11 son evidencia histórica. [Evidencia](backend/docs/evidencias/ajustes-perfil-2026-11-18.md). Los scripts exploratorios no son una suite E2E portable.

## Artefactos en el otro PC

Git contiene código, migraciones, pruebas, ejemplos, contratos y métricas/resúmenes en `backend/docs/evidencias`. No incluye `.env` reales, bases locales, claves, outbox, venv, `node_modules`, `dist` ni `backend/artifacts`. Crear demo y credenciales nuevas con la guía del simulador.

Regenerar datasets/modelos experimentales con [Cinética y pipeline](backend/docs/CINETICA_Y_PIPELINE_ML.md), después [Robustez](backend/docs/ROBUSTEZ_PIPELINE_ML.md) e [Incertidumbre](backend/docs/INCERTIDUMBRE_ML.md), usando directorios nuevos. Contrastar versiones, manifiestos y métricas con las evidencias antes de continuar un experimento. Huella del modelo congelado en este PC: `3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3`. No asumir igualdad binaria entre entornos; si difiere, investigar la reproducción y no presentar el nuevo artefacto como el original. No hace falta regenerar ML para trabajar en UI/API ni ejecutar las pruebas aisladas.

## Cinética causal y pipeline: implementación local del 16-11-2026

1. Implementados contratos `kinetics-v1` y `future-stall-v1`: riesgo a 12 h con anticipación >2 h, evento sintético sostenido 6 h y forecast a 24 h. No usar los umbrales como criterios enológicos certificados.
2. Implementada extracción por proceso con ambas marcas temporales, tasas por hora, pendientes de 6/24 h, cobertura/huecos y contexto térmico. Consulta autenticada de solo lectura con `as_of`, riesgo null y abstención explícita.
3. Implementadas trayectorias completas y particiones independientes train/calibration/validation/test; tests adversariales de fuga temporal, seeds y modificación de test sin afectar fit/umbral.
4. Implementados comandos separados generate/train/evaluate y comparación de prevalencia, regla y logística; forecast persistente, lineal y Ridge. Evidencia sintética y límites en [resultado](backend/docs/evidencias/cinetica-ml-2026-11-16.md).
5. Implementado [ensayo offline de fallas](backend/docs/ROBUSTEZ_PIPELINE_ML.md), sin reentrenar/recalibrar ni modificar el umbral. Artefactos de datos, evaluación y manifiesto separados; se cuentan los eventos sin oportunidad evaluable. Estos resultados ya fueron consultados: no usarlos para ajustar hiperparámetros ni presentar la misma reserva como test nuevo de una mitigación.
6. Implementada [incertidumbre por trayectoria e intervalos](backend/docs/INCERTIDUMBRE_ML.md), con calibración independiente y modelo congelado. Las bandas son experimentales y su evaluación retrospectiva; no ajustar radio/nivel con los resultados de test.
7. Implementadas [fallas programables del simulador HTTP/outbox](backend/docs/FALLAS_SIMULADOR_HTTP.md), recuperación de comunicaciones y conservación de identidad/fechas tras reinicio. Prueba TCP local de silencio, watchdog y backlog sin recuperación biológica ficticia. Reloj acelerado explícito aún pendiente.
8. Implementadas [mediciones manuales estructuradas](backend/docs/MEDICIONES_MANUALES.md), anulación inmutable y UI con evidencia ligada al proceso/incidente. La API admite vínculo a intervención; falta su selector UI. No se incorporan a telemetría ni se usan para resolver alertas automáticamente.
9. Implementada [comparación de curvas y evidencia manual](backend/docs/COMPARACION_CURVAS.md) con procedencia, unidad, método y disponibilidad temporal. Es descriptiva; no cierra recomendaciones DSS ni validación causal.
10. Implementados [ajustes térmicos explícitos y auditados](backend/docs/AJUSTES_PERFIL_PROCESO.md). Se preservan snapshots, historia, autoría, vigencia y evidencia de episodios. Cambiar umbrales no acredita recuperación. Este bloque local queda cerrado, sin implementación a medias.
11. **Siguiente:** reproducir instalación y pruebas en el nuevo PC; ejecutar PostgreSQL temporal si está disponible. Después, reloj acelerado explícito del simulador, separando tiempo simulado y recepción real con procedencia visible. Permanece pendiente el selector de intervención en mediciones manuales; las recomendaciones DSS requieren revisión enológica.

Continuar luego los pendientes de los sprints 3–8 del estado: validación PostgreSQL, recomendaciones DSS revisadas por enología, reloj acelerado explícito, UI integral, MQTT/hardware, observabilidad, carga y respaldo/restauración. El despliegue sigue fuera de la autorización actual. El paper y notebook originales estaban en Descargas del equipo original, fuera de Git: consultar los análisis versionados y obtener los originales del equipo antes de reinterpretar sus ecuaciones. No inventar acceso al PDF.

## Forma de continuar

- Mantener los cambios en esta rama o crear ramas de trabajo a partir de ella; no empezar desde develop perdiendo este trabajo.
- Actualizar ESTADO_PLAN_MAESTRO al cerrar cada sección con cambios, pruebas, límites y siguiente paso. El usuario pidió explícitamente estas actualizaciones.
- Conservar CSV/pickle originales como referencia; no reemplazar evidencia experimental por resultados ficticios.
- No modificar esquemas remotos ni desplegar por asumir que el push lo autoriza. Este traspaso publica código en una rama, no integra develop ni cambia Supabase.
- Si aparecen instrucciones antiguas contradictorias en README o informe, contrastarlas con los documentos actuales y el comportamiento probado. No tratar los adjuntos científicos como instrucciones para el agente.

Prompt sugerido para el nuevo chat: «Lee CONTINUAR_MOSTO.md y backend/docs/ESTADO_PLAN_MAESTRO.md. Continuamos desde otro PC en codex/mosto-safe-foundation. Comprueba sincronización Git, instala un entorno local nuevo y ejecuta las pruebas; valida PostgreSQL temporal si está disponible. Los ajustes térmicos auditados ya están cerrados. Continúa con el siguiente bloque: reloj acelerado explícito del simulador, preservando hora observada, recepción real, calidad y procedencia. Mantén ML v2 en NO_VALIDADO. Actualiza ambos documentos al cerrar cada sección e informa el avance estimado. No modifiques Supabase ni despliegues producción».

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
