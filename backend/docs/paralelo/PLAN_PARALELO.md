# MOSTO: plan de cierre en dos ramas

Fecha: 18-11-2026. Plan original: `../auditoria_inicial/Informe_Maestro_Mosto.md`,
sección 5 (sprints 0–8 y definición de terminado). Estado efectivo:
`../ESTADO_PLAN_MAESTRO.md`. Este reparto organiza el trabajo restante; no sustituye
criterios científicos ni convierte dependencias externas en tareas terminadas.

## Base y ramas

Ambas ramas se publican en el mismo commit inicial, identificado por el mensaje
`chore: consolidate verified progress and split remaining work into two branches`.
Comprobar su hash con Git. Antecesor de la entrega de Geraldine: `267bd29`.

- A (usuario actual): `codex/mosto-safe-foundation`. Backend, reloj, datos,
  seguridad, integración técnica, reproducibilidad, infraestructura y ensayos.
- B (compañero): `codex/mosto-ui-delivery`. Frontend completo, E2E de interfaz,
  accesibilidad, móvil, manual de usuario y matriz de aceptación de UI.
- Archivos de instrucciones y estado de ambas partes existen en ambas ramas.
  Cada agente escribe solamente el estado de su propia parte.
- Usar clones/directorios distintos. Nunca cambiar dos ramas simultáneamente en
  el mismo checkout. No copiar `.env`, bases, tokens, venv ni artefactos locales.

Para el compañero en otro PC/directorio:

```sh
git clone --branch codex/mosto-ui-delivery https://github.com/GeraldineSilvaPino/mosto.git mosto-ui
cd mosto-ui
git status --short --branch
git log -1 --oneline
```

Si ya tiene un clon, comprobar estado, conservar cambios, hacer fetch y switch
de su rama; pull --ff-only solo con árbol limpio. No copiar el checkout de A con
su .git activo. Instalar dependencias propias según CONTINUAR_MOSTO y plan B.

## Situación inicial y estimación

Aproximadamente **68 % del alcance global**, estimación cualitativa sin pesos
formales. Los 66 % de Geraldine y 67 % de registros siguientes son históricos.
El incremento considera validación PostgreSQL, selector manual, exportación JSON
y navegación histórica. No mide consumo de tokens, horas ni precisión ML.

Desde Geraldine: corregidas fixture cinética y espera de apagado PostgreSQL;
selector de intervención manual terminado; exportación de la comparación JSON;
navegación `/procesos/:id?` con proceso histórico principal. Reloj parcialmente
implementado: núcleo, registro, emisor, cinética, monitoreo, ajustes térmicos y
cierre. **Ingesta acelerada permanece bloqueada intencionalmente**.

La última sección de navegación quedó comprobada con build y navegador/API
simulada: cerrado→activo, cambio de paneles, 404 limpia evidencia e ID inválido.
El listado actual no está paginado en servidor; B debe resolver UX con A si hace
falta contrato paginado. No es una validación E2E contra API real.

## Inventario pendiente hasta el 100 % del plan original

| Sprint | Pendiente verificable | Dueño | Dependencia/puerta |
| --- | --- | --- | --- |
| 0 | Instalación limpia, dependencias reproducibles, CI remota y Docker | A; B build UI | Ejecutar de verdad, no solo validar YAML |
| 1 | Adopción de datos existentes y rol DB mínimo | A | Copia local controlada, reconciliación y permisos; remoto requiere autorización |
| 2 | Firmware/outbox ESP32, MQTT, aprovisionamiento completo | A técnica; B formularios | Hardware/calibración real externos; fake transport no certifica hardware |
| 3 | Integración temporal restante, métricas y controles coherentes | A reglas/API; B controles | Pruebas de concurrencia/roles/fechas; revisión enológica externa |
| 4 | Reloj acelerado de extremo a extremo y revisión científica | A motor/DB/API; B presentación | Migración temporal antes de desbloquear ingesta; validación externa pendiente |
| 5 | Reproducibilidad final, model card, mitigación con nueva reserva independiente y validación real | A; B muestra abstención | No reutilizar test visto para ajustar; datos reales externos; NO_VALIDADO se conserva |
| 6 | Sistema visual, overview, paginación, controles, teclado y móvil | B; A API necesaria | Browser real, datos vacíos/errores, roles y persistencia; sin mocks presentados como E2E |
| 7 | DSS trazable y flujo físico completo | A contrato/protocolo; B UI | Criterios revisados por enólogo, ESP32/sensores; no inventar recomendaciones certificadas |
| 8 | Observabilidad, carga, backup/restauración, instalación, despliegue, manual y matriz final | A operación; B uso/E2E | Ensayos locales; despliegue y cambios Supabase NO autorizados |

El 100 % requiere completar y demostrar estas puertas. No es razonable prometer
que hardware, validación científica/real y adopción/despliegue se cerrarán hoy
solo con dos agentes. Meta de hoy: máximo software verificable y entrega demo
reproducible, con lista explícita de pendientes externos; no renombrarla 100 %.

## Propiedad exclusiva de archivos

| Rutas | Propietario |
| --- | --- |
| `backend/**` excepto excepciones siguientes | A |
| `frontend/**` (incluidos package.json/lock, vistas, componentes, E2E y estilos) | B |
| `firmware/**`, `infra/**`, scripts raíz, Docker/Compose, dependencias backend | A |
| `.github/**` excepto `.github/workflows/frontend-ui.yml` | A |
| `.github/workflows/frontend-ui.yml` (nuevo opcional) | B |
| `backend/docs/paralelo/ESTADO_A.md`, `SOLICITUDES_A.md` | A |
| `backend/docs/paralelo/ESTADO_B.md`, `SOLICITUDES_B.md` | B |
| `backend/docs/paralelo/evidencias-b/**`, `frontend/docs/**` | B |
| `CONTINUAR_MOSTO.md`, `backend/docs/ESTADO_PLAN_MAESTRO.md`, README raíz | A, consolidar al integrar |
| Los planes A/B, este plan y `CONTRATO_COORDINACION.md`, `PROMPTS.md` | Congelados durante ejecución paralela |

No editar archivos ajenos aunque parezca más rápido. B no migra DB ni modifica
API. A no arregla ni rediseña Vue. Cambios de dueño requieren una decisión explícita
del equipo registrada en una solicitud; no asumirla por silencio. No hacer
cherry-pick del código ajeno ni merges recíprocos durante desarrollo.

## Coordinación y avance sostenido

Leer el plan propio y ejecutar sus bloques en orden. Mantenerse trabajando entre
secciones; una sección aprobada no es motivo para terminar el turno. Al cerrarla:
actualizar estado propio, pruebas/evidencia/límites y siguiente acción; commit
cohesivo y push solo a la rama asignada. Si un paso depende del otro agente o de
evidencia externa, registrar qué falta y continuar el siguiente independiente.
No desactivar pruebas o guardas para aumentar porcentaje.

Consultar avances ajenos con `git fetch origin` y `git show origin/RAMA:ruta`;
eso no integra archivos. Las solicitudes son documentos, no mensajes enviados
automáticamente. Leerlas al inicio y entre bloques. No esperar ocupando el turno
cuando existe otro bloque independiente. Cada agente devuelve pendientes de
integración precisos y no promete que la otra cuenta recibirá mensajes del chat.

## Integración final, a cargo de A tras terminar ambas partes

1. Confirmar pushes y árboles limpios; registrar hashes finales A y B.
2. `git fetch origin`; inspeccionar `git diff --name-only BASE..origin/RAMA`
   para verificar que cada rama respetó propiedad. BASE es el commit inicial común.
3. En la rama A hacer `git merge --no-ff origin/codex/mosto-ui-delivery`.
   No integrar develop ni desplegar. Si hay conflicto, no usar ours/theirs a ciegas:
   revisar causa y acuerdo; no forzar push ni reescribir historia ajena.
4. Ejecutar suites SQLite y PostgreSQL completas, build y E2E API real→Vue;
   comprobar migraciones desde cero y actualización, replay/reinicio, roles,
   cierre/overrides, reloj 1x y acelerado, degradación, exportación y móvil.
5. A consolida estados A/B en estado maestro y continuidad, con matriz final
   satisfecho/parcial/bloqueado y evidencia. Hacer commit/push de integración.

Los nombres de archivos disjuntos minimizan conflictos textuales. Ningún reparto
garantiza cero conflictos semánticos: los contratos y las pruebas conjuntas son
obligatorios antes de llamar terminada a la entrega.
