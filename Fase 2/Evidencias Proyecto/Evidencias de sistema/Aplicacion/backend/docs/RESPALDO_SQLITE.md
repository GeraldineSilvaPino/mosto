# Respaldo y restauración SQLite local

Herramienta independiente de `.env`: `scripts/sqlite_backup.py`. Solo fuente de
respaldo o destino restaurado con nombre mosto_demo*.db / mosto_test*.db (también
.sqlite3). No conecta PostgreSQL ni Supabase. No migra ni reemplaza bases existentes.

Desde raíz, con rutas locales explícitas y directorios ya existentes:

```powershell
.\backend\venv\Scripts\python.exe backend/scripts/sqlite_backup.py backup backend/artifacts/mosto_demo.db backend/artifacts/demo-snapshot.db
.\backend\venv\Scripts\python.exe backend/scripts/sqlite_backup.py restore backend/artifacts/demo-snapshot.db backend/artifacts/mosto_demo_restored.db
```

Usa SQLite backup API (incluye snapshot coherente de WAL), no copia cruda del
archivo abierto. Produce archivo y manifiesto .json con SHA-256, revisión Alembic
y cantidades de filas. Verifica integrity_check y foreign_key_check. Restaurar
comprueba hash/manifiesto antes de crear el destino y verifica su integridad.
El destino se crea exclusivamente; nunca se sobrescribe. Si falla la copia elimina
solo el archivo recién creado tras cerrar conexiones. Manifest y archivo deben
guardarse juntos. Una interrupción puede dejar un archivo incompleto: usar otro
nombre, no tratarlo como respaldo válido sin manifiesto y verificación.

El hash detecta corrupción, no autentica un archivo de un atacante que también
pueda reemplazar el manifiesto. Guardar en almacenamiento controlado. El respaldo
contiene todos los datos de la base, incluidos hashes/credenciales: no subirlo a
Git ni compartirlo como evidencia. Usar artifacts ignorado para ensayos locales.

Pruebas del 18-11: cuatro aprobadas, 1,30 s. Snapshot anterior preservado tras
cambiar fuente, destino existente rechazado, alteración de archivo rechazada,
base sin metadatos rechazada y restauración del esquema actual con datos demo.
No acredita PostgreSQL, cifrado, retención, recuperación de desastre, RPO/RTO
de producción ni compatibilidad entre distintas versiones del esquema.
