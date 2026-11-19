# Prompts para las dos cuentas

## Inicial A — usuario actual

Estamos trabajando en paralelo. Comprueba que estás en codex/mosto-safe-foundation
y conserva cambios locales. Lee CONTINUAR_MOSTO.md, backend/docs/ESTADO_PLAN_MAESTRO.md,
backend/docs/paralelo/PLAN_PARALELO.md, CONTRATO_COORDINACION.md y RAMA_A_BACKEND.md.
Ejecuta A1–A5 dentro de la propiedad de archivos acordada; no modifiques frontend
ni archivos de B. Lee ESTADO_A.md y las solicitudes remotas de B para retomar el
primer trabajo pendiente. Continúa autónomamente entre secciones: no termines el
turno solo porque una prueba o subtarea pasó. Si algo requiere al compañero, datos
reales, hardware o autorización, registra la dependencia y sigue otro bloque
independiente. Actualiza ESTADO_A.md al cerrar cada sección con pruebas y límites,
haz commits cohesivos y push solo a tu rama. No habilites ML no validado, no uses
Supabase ni despliegues. Al terminar ambas ramas integra según el plan y verifica
compatibilidad real. No declares 100 % sin cumplir las puertas originales.

## Seguimiento A

Continúa la rama A desde ESTADO_A.md y el último commit; verifica qué se ejecutó,
no repitas cierres. Lee solicitudes B con fetch/git show. Completa el siguiente
bloque A pendiente y continúa los independientes, actualizando estado, pruebas,
commits y push. Respeta propiedad de archivos y límites del PLAN_PARALELO.
Solo detente si todo el alcance A ejecutable está terminado o todas las opciones
restantes dependen de información/autorización externa; explica entonces cada
dependencia y deja el punto exacto de reanudación. No mezcles B hasta su entrega.

## Inicial B — compañero

Trabaja en un clon separado en codex/mosto-ui-delivery, partiendo de la base común
publicada; fetch/pull --ff-only con árbol limpio, sin reset destructivo. Lee
CONTINUAR_MOSTO.md, backend/docs/ESTADO_PLAN_MAESTRO.md y los archivos de
backend/docs/paralelo: PLAN_PARALELO.md, CONTRATO_COORDINACION.md, RAMA_B_FRONTEND.md,
ESTADO_B.md. Ejecuta B1–B5 respetando propiedad exclusiva: frontend, tu workflow
opcional y docs B. No edites backend, estado maestro, continuidad ni archivos A.
Continúa entre secciones sin finalizar por una subtarea aprobada. Si falta una API,
anótala en SOLICITUDES_B.md, consulta contratos A con fetch/git show y sigue trabajo
independiente. Actualiza ESTADO_B.md con pruebas/evidencia/límites; commit y push
solo a B. No hagas merge a A/develop ni despliegues. Conserva NO_VALIDADO y no inventes
datos, recomendaciones o permisos. Entrega UI funcional, accesible y comprobada,
E2E portable y manual según tus puertas, con pendientes externos explícitos.

## Seguimiento B

Continúa B desde ESTADO_B.md y commits actuales. Revisa solicitudes/contratos A
remotos sin integrar su rama ni editar sus archivos. Completa el siguiente bloque
UI/E2E/manual pendiente y sigue los independientes; actualiza estado y evidencia,
commit y push solo B. No repitas trabajo cerrado ni pares tras cada componente.
Si todo lo ejecutable está terminado, entrega hash final, pruebas, contratos
consumidos y pendientes de integración; A hará el merge y pruebas conjuntas.

Estos prompts expresan continuidad deseada, pero ninguna instrucción evita límites
de sesión, contexto o cuota. Ante una interrupción, el estado versionado permite
reanudar sin confundir una interrupción con un cierre funcional.
