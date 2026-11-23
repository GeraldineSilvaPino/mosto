# Cierre local: mediciones manuales

17-11-2026 · Windows/Python 3.11.4 · `codex/mosto-safe-foundation`. Cambios locales, sin commit/push. [Contrato](../MEDICIONES_MANUALES.md).

- Suite completa: **257 aprobadas, 14 omitidas, 90 warnings**, 93,28 s, SQLite temporal. [Salida](manual-measurements-final.txt). Las omisiones requieren PostgreSQL; tres nuevas cubren inmutabilidad SQL y concurrencia de alta/anulación.
- Primer pase focalizado de mediciones/migraciones: 26 aprobadas, 6 omitidas; después se añadieron rechazo de booleanos, rollback de anulación y concurrencia. El resultado consolidado anterior corresponde al código backend final.
- Migración `0007_manual_measurements`: 28 tablas de dominio + Alembic, concordancia ORM, ciclo downgrade/upgrade y generación SQL PostgreSQL offline. No se aplicó sobre Supabase ni bases existentes del usuario.
- Build Vue final correcto: **6,11 s**, con `VITE_API_BASE_URL=http://127.0.0.1:8877` únicamente en el proceso de compilación para esta demo. No se cambiaron archivos de entorno. El build local generado apunta a la demo detenida; recompilar con el destino local apropiado antes de reutilizarlo.
- Navegador con build final, Uvicorn y SQLite nuevos: login de prueba, alta manual, anulación, recarga; formulario del incidente cambia de Brix a temperatura ajustando método/unidad, guarda 24,2 °C y muestra enlace al incidente #1001. Tras recarga conserva autor, fechas, instrumento, evidencia y bitácora. El incidente sigue pendiente.
- Captura local de la comprobación: `backend/artifacts/manual-measurements-browser.jpg`. El script desechable `backend/artifacts/manual_browser_demo.py` y su base temporal no forman parte del código de producción. La primera apertura detectó un build que apuntaba al puerto predeterminado 8000; se recompiló para el 8877 antes del flujo exitoso. No hubo cambio de autenticación ni redirección a servicios remotos.

Las pruebas comprueban calidad del contrato, intervalos históricos, tenant/roles, referencias cruzadas, autoría no falsificable, idempotencia, atomicidad, inmutabilidad de sesión y ausencia de efectos sobre alertas, telemetría y estado de reglas. PostgreSQL no se ejecutó. No es una suite E2E portable ni certificación móvil/enológica. Comparación de curvas, selector UI de intervención y DSS siguen pendientes. No se desplegó producción ni se habilitó ML.
