# Contrato entre las ramas (congelado)

1. Backend A es fuente de verdad; frontend B no replica permisos/decisiones.
2. A preserva endpoints, tipos y campos actuales. Nuevos datos aditivos y opcionales;
   no cambiar lista en objeto paginado sin endpoint/opt-in compatible. Datos ausentes
   siguen null, no cero. Errores conservan detail legible y códigos HTTP adecuados.
3. Timestamps de API con zona UTC; la UI localiza visualización, no modifica evidencia.
   `as_of` público actual representa corte real de disponibilidad. Cualquier corte
   simulado debe nombrarse explícitamente. Nunca redefinir silenciosamente `as_of`.
4. Campos internos existentes del reloj: real_anchor, simulated_anchor, factor.
   Monitoreo expone simulation_clock (null o configuración), observation_clock,
   expected_delivery_age_seconds, receipt_age_seconds, observation_age_seconds.
   Esos campos están en desarrollo; B puede representarlos defensivamente, pero
   no afirmar soporte acelerado operativo hasta A documentarlo con pruebas.
5. Propuesta de adiciones públicas A debe registrarse en SOLICITUDES_A con endpoint,
   request/response ejemplos, errores, permisos, defaults, compatibilidad y prueba.
   B registra aceptación/consumo en SOLICITUDES_B. No modificar este contrato común.
6. B solicita backend en SOLICITUDES_B con usuario/flujo y contrato mínimo. A decide
   implementación y registra respuesta en su archivo; cada cual escribe solo el suyo.
7. Para leer remoto: fetch + git show. No actualizar directorio de trabajo ajeno.
   Ningún agente conoce automáticamente los mensajes del chat de la otra cuenta.
8. Ejecución local aislada, production deshabilitado, ML NO_VALIDADO. Push de código
   no autoriza deploy, Supabase, credenciales, operaciones sobre datos reales o merge
   a develop. Ambos pueden commit/push solo su rama; A integra B al final según plan.
