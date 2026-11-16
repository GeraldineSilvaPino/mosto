# Estado de ejecución del plan maestro

Actualizado el 15-11-2026, después de verificar episodios térmicos v2, bitácora y auditoría en navegador. Rama de trabajo: `codex/mosto-safe-foundation`. Entrega consolidada para publicación en esta rama; no se ha integrado develop ni migrado Supabase. Para continuar en otro equipo, leer [CONTINUAR_MOSTO](../../CONTINUAR_MOSTO.md). El hash y la disponibilidad remota se comprueban con Git.

**Avance global estimado: alrededor del 45 %.** Es una estimación de alcance y complejidad, no una medición de horas ni de líneas de código. La auditoría está entregada; la estimación considera principalmente lo que falta para cumplir la definición de terminado del proyecto. El ML validado, la integración de incidentes/DSS, la UI integral y el hardware real concentran todavía una parte importante del trabajo.

| Sprint del informe | Estado comprobable | Pendiente principal |
| --- | --- | --- |
| 0. Contención y reproducción | Configuración aislada, autenticación obligatoria, baseline offline, PostgreSQL temporal y CI preparada | Ejecución CI remota y cierre de reproducibilidad/despliegue entre entornos |
| 1. Identidad y esquema | Autorización por empresa/bodega, actores reales, migraciones locales y pruebas concurrentes | Adopción del esquema con datos existentes y rol de producción con privilegios mínimos |
| 2. Dispositivos e ingesta | Credenciales, calibración, timestamps, calidad, idempotencia, atribución histórica; outbox del simulador | Firmware/outbox del ESP32, MQTT y formularios completos de aprovisionamiento |
| 3. Procesos, incidentes y bitácora | Episodios térmicos v2 transaccionales, histéresis, perfil congelado por proceso, resolución idempotente, bitácora vinculada y MTTR con tiempos válidos | Reglas cinéticas, versionado completo de perfiles y seguimiento estructurado de intervenciones |
| 4. Simulación científica | Núcleo continuo por fases, cinco escenarios, persistencia, tiempo físico 1×, historial y panel de fases | Fallas programables de sensores/comunicaciones y reloj acelerado explícito |
| 5. ML y forecast | Auditoría, reproducción del baseline y abstención ante v2 | Dataset por trayectorias, evento/horizonte, features causales, splits, comparación, calibración y forecast |
| 6. UI operacional | Estados desconocidos, procedencia, fases simuladas y acciones de incidentes persistentes verificadas | Sistema visual completo, overview, paginación global, controles restantes, accesibilidad y móvil |
| 7. DSS e integración física | Canal físico reservado y contrato común listo | Hardware calibrado, recomendaciones trazables, intervención y seguimiento reales |
| 8. Entrega y validación | Suites locales, pruebas de navegador y documentación técnica por bloque | Carga objetivo, observabilidad, respaldo/restauración, despliegue, manual y matriz final de requisitos |

La implementación adelantó el núcleo del sprint 4 para disponer de telemetría continua con la que verificar el sprint 3. Esto no cierra todas las puertas del sprint 4 ni convierte un escenario sintético en evidencia de exactitud enológica.

## Registro de secciones cerradas

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

Construir la evaluación cinética causal y el contrato de dataset/modelo:

1. Definir el evento de parada, horizonte de predicción y casos donde el sistema debe abstenerse por cobertura o calibración insuficiente.
2. Extraer tasas suavizadas y pendientes en ventanas por proceso usando exclusivamente el pasado disponible; distinguir Brix aparente de azúcar residual real.
3. Separar reglas de desviación/observación de una probabilidad de parada aprendida y calibrada; añadir evidencia temporal reutilizando el contrato de episodios.
4. Generar trayectorias independientes y particiones por fermentación, con pruebas de fuga temporal y comparación contra baselines simples.
5. Evaluar riesgo futuro y proyección de Brix; mantener N/D mientras no exista evidencia suficiente para habilitar el modelo.

El origen de simulación, el nombre del escenario y los estados latentes se conservan como procedencia/evaluación: no se introducirán como features de inferencia de un dispositivo real. Siguen pendientes watchdog de silencio, diagnóstico de regla sin perfil, versionado completo de perfiles, seguimiento estructurado de intervenciones y el resto de sprints de la tabla.

## Última evidencia

- PostgreSQL 18.4: 139 pruebas aprobadas.
- SQLite: 131 aprobadas y 8 omitidas por depender de PostgreSQL.
- Evidencia previa del simulador (sección anterior): worker HTTP real, FastAPI, SQLite y Vue: cinco trayectorias al día, reinicio sin duplicación, reserva física sin lecturas y ventana de 24 horas con 288 puntos.
- Build Vite correcto; sin errores JavaScript en los flujos comprobados.
- La prueba local no acredita producción, exactitud física, generalización ML ni integración del prototipo.

Detalles: [Episodios y alertas v2](ALERTAS_V2_Y_EPISODIOS.md), [Telemetría v2](TELEMETRIA_V2.md), [Simulador](SIMULADOR_ENOLOGICO.md), [Autorización](AUTORIZACION_EMPRESA_BODEGA.md) y [Migraciones](MIGRACIONES_Y_POSTGRESQL.md).

## Traspaso a otro equipo

Informe original, adenda del notebook y cobertura preservados en `auditoria_inicial/`; resultados finales de pruebas y navegador en `evidencias/`. Estos documentos históricos no sustituyen este estado actualizado. Secretos, bases locales y artefactos de ejecución se regeneran siguiendo CONTINUAR_MOSTO.md.
