# Reloj acelerado: núcleo implementado, integración pendiente

## Estado tras retomar la sesión

Actualización de ajustes/cierre: la regla térmica convierte la hora observada a
hora real esperada antes de seleccionar el override. El cierre de cada episodio
usa el reloj del mensaje disparador para fin_condicion; fecha_real_fin permanece
real y la auditoría publica ambos dominios. Verificación con reloj inyectado y
regresiones: SQLite 29 aprobadas/3 omitidas; PostgreSQL 20 aprobadas. Aún falta
adaptar la selección temporal en ingesta y consultas y verificar HTTP real.

Actualización: reglas cinéticas y monitoreo ya resuelven el reloj histórico de
la calibración. La cinética combina corte simulado y corte de recepción real;
la frescura usa hora real esperada. Monitoreo expone `observation_clock`,
`simulation_clock` y `expected_delivery_age_seconds`; el watchdog compara tiempo
real. Pruebas específicas con reloj inyectado y regresiones aprobadas. La ingesta
sigue bloqueada hasta revisar overrides, cierre de procesos y consultas: aún no
hay validación acelerada de extremo a extremo.

Emisor/outbox adaptado y verificado: generación según hora simulada; disponibilidad,
reintentos y espera en hora real. Los retardos configurados en segundos siguen
siendo segundos reales; los cortes definidos por secuencia terminan en la fecha
real correspondiente a esa secuencia. Preflight compara el reloj completo.
Cambiarlo invalida la reutilización del archivo de estado; las recetas sin reloj
mantienen su identidad previa. Reinicios conservan sobres y secuencias.

Pruebas del bloque: 53 aprobadas en 10,04 s, incluidas simulación previa, fallas,
reinicio/reintento exacto, demora real, corte por secuencia y rechazo de preflight.
La fixture de formato antiguo excluye ahora simulation_clock, ausente en aquel
formato. No se cambió el algoritmo de identidad antiguo para satisfacer la prueba.

El emisor se verificó con transporte de prueba para el modo acelerado; la API
real todavía rechaza esas calibraciones. Las menciones inferiores al rechazo del
worker describen el paso anterior. NO hay todavía demo acelerada de extremo a extremo.

Siguiente integración obligatoria antes de retirar la guarda de ingesta:

1. Ingesta: validar reloj registrado, disponibilidad real esperada, proceso,
   asignación y calibración; conservar recepción del servidor y calcular retraso
   contra hora real esperada, nunca restando recepción real a observación simulada.
2. Episodios cinéticos: sustituir el corte común y la condición observed<=received
   por cortes explícitos y frescura real. Mantener persistencias en horas simuladas.
3. Monitoreo: separar silencio real de edad simulada; el filtro actual observado<=now
   excluiría datos válidos de una simulación adelantada. Revisar también vigencia
   de ajustes de perfil, cierre de proceso y comparación de curvas.
4. Exponer reloj y ambos tiempos en API/Vue; verificar HTTP real, reinicio, fallas
   y alertas antes de anunciar modo acelerado disponible.

Revisión del 18-11-2026. Implementado el núcleo puro en `app/simulation/clock.py`; todavía no habilita aceleración en API ni worker.

## Sección cerrada: conversión entre dominios temporales

`SimulationClock` conserva anclas UTC inmutables y factor finito entre 1 y 3600. Este límite es una decisión técnica inicial, no una certificación de carga. Convierte en ambos sentidos con resolución de microsegundos y calcula entrega con retraso en segundos reales. Rechaza fechas sin zona, factores fuera de rango y retardos negativos/no finitos. La serialización permite reconstruir exactamente la configuración al reiniciar; la persistencia del worker todavía no está integrada.

Validación: 15 pruebas aprobadas en SQLite aislado (1,99 s), incluyendo 1×/60×/180×/3600×, ida/vuelta, cambio de zona, serialización y errores. No se modificaron recetas actuales, identidades, telemetría, reglas ni ML. Esta sección cierra la primitiva, no el bloque completo del sprint 4.

## Contrato propuesto

Avance de integración: `CalibrationCreate.simulation_clock` permite registrar el
reloj únicamente con trayectoria sintética y ancla simulada igual al inicio del
proceso. La ruta exige demo/test y conserva la receta entre recalibraciones del
mismo dispositivo/proceso. Preflight devuelve `simulation_clock`; recetas antiguas
devuelven null. Hasta completar el flujo, el worker marca
`accelerated_clock_not_supported` y la ingesta rechaza estas calibraciones.
Esto evita procesar silenciosamente una receta acelerada con reglas 1x.
Validación parcial: 78 aprobadas/2 omitidas SQLite (registro, simulación, fallas y
telemetría). Falta PostgreSQL e integración completa; no es un cierre funcional.

Sección adicional cerrada el 18-11: extractor cinético y adaptador SQL aceptan
`received_as_of` para filtrar disponibilidad real independientemente de `as_of`
(observación). La salida muestra ambos. El valor predeterminado conserva el
comportamiento anterior. Verificación: 41 pruebas SQLite de cinética/episodios/
pipeline y 18 pruebas de cinética PostgreSQL aprobadas. La integración pública
del reloj sigue pendiente; esta opción interna no autoriza ingesta acelerada.

El reloj debe registrarse como parte de la receta inmutable de una simulación demo/test, con factor positivo finito, ancla UTC real y ancla UTC simulada. El modo predeterminado sigue siendo 1× y conserva las identidades de las recetas existentes. La conversión será `simulada = ancla_simulada + factor × (real - ancla_real)`; su inversa permitirá programar entregas sin alterar la recepción del servidor.

Cada observación conserva su fecha simulada y la recepción UTC real. El servidor debe validar el reloj registrado, el proceso, la secuencia y la fecha esperada antes de aceptar una observación que exceda la tolerancia futura física. La excepción solo aplica a trayectorias simuladas explícitas en demo/test; nunca a dispositivos físicos ni a una etiqueta enviada libremente por el emisor.

Los retrasos de transporte, reintentos, caducidad de credenciales y silencio se evalúan en tiempo real. La edad, pendientes y persistencia biológica se evalúan en horas simuladas. Una resta entre ambos dominios no representa latencia. Las consultas causales necesitan distinguir corte simulado de corte de disponibilidad real; no basta con relajar la guarda de fechas futuras.

## Integración y pruebas de cierre

- Registro y preflight: receta y reloj coincidentes, rechazo de factores inválidos y cambios tras inicio; compatibilidad de recetas 1× y estados antiguos.
- Worker/outbox: generación por reloj simulado, entrega por reloj real, identidad estable tras reinicio, sobres idénticos en reintentos, fallas y backlog sin pérdida accidental.
- Ingesta y reglas: recepción auténtica, aislamiento físico/simulado, asignación/calibración temporal coherente, cortes causales explícitos y ausencia de recuperación ficticia.
- API/Vue: factor, fechas y procedencia visibles; silencio real separado del progreso biológico. ML v2 permanece NO_VALIDADO.
- Verificación: pruebas unitarias de conversión y fronteras, integración HTTP con reinicio/fallas, SQLite/PostgreSQL y navegador. Hasta completar estas verificaciones el bloque permanece abierto.
