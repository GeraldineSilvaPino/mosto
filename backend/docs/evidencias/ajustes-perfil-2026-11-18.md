# Cierre: ajustes térmicos por proceso

18-11-2026 · Windows/Python 3.11.4 · rama `codex/mosto-safe-foundation`. [Contrato](../AJUSTES_PERFIL_PROCESO.md).

- Suite completa ejecutada al terminar el código el 17-11: **289 aprobadas, 16 omitidas, 90 warnings**, 89,62 s. [Salida](profile-overrides-final.txt). Las omisiones requieren PostgreSQL; no se reejecutó ese motor. Corrección durante la prueba focalizada: comparar instantes UTC, equivalentes con sufijos `Z` y `+00:00`, en lugar de comparar su representación textual.
- Migraciones SQLite desde cero, downgrade/upgrade y concordancia ORM comprobadas por la suite. Head `0008_process_profile_overrides`: 29 tablas de dominio y Alembic. La generación SQL PostgreSQL fue comprobada; no sustituye la ejecución de triggers/concurrencia.
- Build Vite: **4,11 s**, con `VITE_API_BASE_URL=http://127.0.0.1:8879` solo en el proceso de compilación. Regenerar el build con el destino correcto en otro equipo. No se publicó el build.
- Navegador contra API y SQLite nuevas: aprobación de 5–10 a 5–30 °C, motivo y autor en historial; restauración como revisión 2 y recarga el 18-11 conservando ambas revisiones y el episodio abierto con banda original. No se envían nuevas mediciones durante esa comprobación; las pruebas de backend verifican la recuperación medida posterior.
- Captura local `backend/artifacts/profile-overrides-browser.jpg` y scaffold `backend/artifacts/profile_override_browser_demo.py`, ambos desechables e ignorados por Git. No constituyen suite E2E portable, prueba móvil ni validación enológica. Servidor local detenido al cerrar.
- Huella del modelo experimental conservada: `3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3`. No se reentrenó ni recalibró.
- No se modificó Supabase ni se desplegó producción. Se prepara la entrega Git de los bloques acumulados y las guías para continuar desde otro PC.
