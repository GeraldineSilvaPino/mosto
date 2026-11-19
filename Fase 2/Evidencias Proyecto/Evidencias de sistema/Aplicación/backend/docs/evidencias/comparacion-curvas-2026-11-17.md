# Cierre local: comparación de curvas

17-11-2026 · Windows/Python 3.11.4 · rama `codex/mosto-safe-foundation`, árbol local sin commit/push. [Contrato](../COMPARACION_CURVAS.md).

- Suite focalizada: **16 aprobadas**, 86 warnings, 3,48 s. La prueba de horas duplicadas utiliza dos dispositivos del mismo proceso: la ingesta canónica ya rechaza duplicar la hora de un solo dispositivo.
- Suite completa: **273 aprobadas, 14 omitidas, 90 warnings**, 77,72 s. [Salida](curve-comparison-final.txt). Las omisiones requieren PostgreSQL; no se ejecutó ese motor.
- Build Vite correcto: **8,17 s**, con `VITE_API_BASE_URL=http://127.0.0.1:8878` en el proceso de compilación local, sin editar archivos de entorno. Recompilar con la API local adecuada antes de reutilizar ese build: el servidor desechable se detuvo al terminar.
- Navegador sobre Uvicorn, API y SQLite nuevos, con mensajes v2 ingresados mediante los contratos HTTP: dos procesos alineados en edad, 97 puntos visibles por proceso, una lectura manual por proceso a las siete horas, refractómetro y densímetro diferenciados. Consulta anterior a recepción/registro devuelve cero puntos; volver a ahora restaura las curvas y evidencia. Riesgo v2 permanece NO_VALIDADO/N/D.
- Captura local `backend/artifacts/curve-comparison-browser.jpg`; scaffold desechable `backend/artifacts/comparison_browser_demo.py`. No es una suite E2E portable ni evidencia de hardware, móvil, accesibilidad o carga.
- `git diff --check` sin errores. No requiere nueva migración: head `0007_manual_measurements`. No se modificó Supabase ni se desplegó producción.

SHA-256 del modelo experimental congelado, comprobado sin reentrenar ni recalibrar:

```text
3d6a1ef55ab7134fa7d5c99bc345401e9b2af26787ffb40662246b3f7497f6c3
```

Este cierre ofrece comparación descriptiva, no recomendaciones de tratamiento ni validación causal. Permanecen pendientes overrides explícitos de perfil, PostgreSQL, criterios DSS revisados por enología y evidencia real independiente.
