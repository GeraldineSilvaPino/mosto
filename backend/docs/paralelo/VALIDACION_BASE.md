# Validación de la base común — 18-11-2026

Entorno existente Windows, Python 3.14.6 y PostgreSQL 18.4. No se afirma
instalación limpia ni ejecución CI remota.

- Suite completa SQLite: **320 passed, 16 skipped**, 3834 warnings, 100,84 s.
- Suite completa PostgreSQL temporal: **336 passed**, 4005 warnings, 210,25 s.
- Build frontend Vite: aprobado, 4,19 s.
- `git diff --check`: sin errores de whitespace.
- Navegador Edge de la nueva vista de historial, componente/router reales y API
  interceptada: proceso cerrado como principal, cambio a activo actualiza paneles,
  404 retira evidencia, ID inválido rechazado. Sin excepción JavaScript; advertencias
  del servidor de desarrollo HMR y ruta de cuba no incluida en harness aislado.
- Navegador previo: selector manual y exportación JSON comprobados con API simulada;
  persistencia/permisos del backend cubiertos por suites HTTP/base aislada.

Comandos desde raíz:

```powershell
.\backend\venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short
.\backend\venv\Scripts\python.exe backend/scripts/test_postgres.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin' -- -q --disable-warnings --tb=short
```

Desde frontend: `npm ci` en equipo nuevo y `npm run build`.
Ninguno de estos resultados valida ingesta acelerada completa, hardware real,
criterios enológicos, producción o compatibilidad posterior entre las ramas.
