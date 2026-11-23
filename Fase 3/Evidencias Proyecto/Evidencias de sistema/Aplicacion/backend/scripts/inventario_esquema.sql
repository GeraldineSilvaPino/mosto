-- Ejecutar con psql -X -qAt -v ON_ERROR_STOP=1 -f inventario_esquema.sql
-- Objetos del esquema de la aplicación. Las definiciones no incluyen filas.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path = pg_catalog;
WITH objetos (clase, tabla, nombre, definicion) AS (
    SELECT 'tabla', c.relname, '', jsonb_build_array(c.relrowsecurity, c.relforcerowsecurity)
      FROM pg_class c
     WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r','p')
    UNION ALL
    SELECT 'columna', c.relname, a.attname,
           jsonb_build_array(format_type(a.atttypid, a.atttypmod), a.attnotnull,
                             a.attidentity, a.attgenerated, pg_get_expr(d.adbin, d.adrelid))
      FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
      LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
     WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r','p')
       AND a.attnum > 0 AND NOT a.attisdropped
    UNION ALL
    SELECT 'restriccion', c.relname, k.conname,
           jsonb_build_array(pg_get_constraintdef(k.oid), k.convalidated)
      FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
     WHERE c.relnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 'indice', c.relname, i.relname, to_jsonb(pg_get_indexdef(i.oid))
      FROM pg_index x JOIN pg_class c ON c.oid = x.indrelid
      JOIN pg_class i ON i.oid = x.indexrelid
     WHERE c.relnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 'trigger', c.relname, t.tgname,
           jsonb_build_array(pg_get_triggerdef(t.oid), t.tgenabled)
      FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
     WHERE c.relnamespace = 'public'::regnamespace AND NOT t.tgisinternal
    UNION ALL
    SELECT 'funcion', '', p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')',
           to_jsonb(pg_get_functiondef(p.oid))
      FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.prokind = 'f'
    UNION ALL
    SELECT 'politica', tablename, policyname,
           jsonb_build_array(permissive, roles, cmd, qual, with_check)
      FROM pg_policies WHERE schemaname = 'public'
)
SELECT jsonb_build_object('clase', clase, 'tabla', tabla, 'nombre', nombre, 'definicion', definicion)
  FROM objetos ORDER BY clase, tabla, nombre;
COMMIT;
