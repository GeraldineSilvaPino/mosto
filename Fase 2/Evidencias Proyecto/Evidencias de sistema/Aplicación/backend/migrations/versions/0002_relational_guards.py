"""PostgreSQL relational and temporal guards. SQLite has only portable checks."""
from alembic import op

revision = "0002_guards"
down_revision = "0001_schema"
branch_labels = None
depends_on = None

# Frozen SQL: do not import the changing application implementation here.
FUNCTIONS = {
    "mosto_immutable_scope": """
DECLARE field text;
BEGIN
  FOREACH field IN ARRAY TG_ARGV LOOP
    IF (to_jsonb(OLD)->field) IS DISTINCT FROM (to_jsonb(NEW)->field) THEN
      RAISE EXCEPTION 'Historical ownership cannot change' USING ERRCODE='23514';
    END IF;
  END LOOP;
  RETURN NEW;
END;
""",
    "mosto_validate_process": """
DECLARE warehouse bigint; capacity numeric; profile_warehouse bigint;
BEGIN
  SELECT bodega_id, cap_litros INTO warehouse, capacity
    FROM public."CUBA" WHERE id=NEW.cuba_id FOR SHARE;
  IF NEW.perfil_id IS NOT NULL THEN
    SELECT bodega_id INTO profile_warehouse FROM public."PERFIL_FERMENTACION" WHERE id=NEW.perfil_id;
    IF warehouse IS DISTINCT FROM profile_warehouse THEN
      RAISE EXCEPTION 'Process profile and tank must share a warehouse' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.volumen_litros > capacity THEN
    RAISE EXCEPTION 'Process volume exceeds tank capacity' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_assignment": """
DECLARE device_company bigint; tank_company bigint;
BEGIN
  SELECT empresa_id INTO device_company FROM public."DISPOSITIVO"
    WHERE id=NEW.dispositivo_id FOR UPDATE;
  SELECT b.empresa_id INTO tank_company FROM public."CUBA" c
    JOIN public."BODEGA" b ON b.id=c.bodega_id WHERE c.id=NEW.cuba_id;
  IF device_company IS DISTINCT FROM tank_company THEN
    RAISE EXCEPTION 'Device and tank must share a company' USING ERRCODE='23514';
  END IF;
  IF NEW.asignado_en IS NULL OR EXISTS (
    SELECT 1 FROM public."ASIGNACION_DISPOSITIVO" a
    WHERE a.dispositivo_id=NEW.dispositivo_id AND a.id IS DISTINCT FROM NEW.id
      AND tstzrange(a.asignado_en, a.desasignado_en, '[)') &&
          tstzrange(NEW.asignado_en, NEW.desasignado_en, '[)')
  ) THEN
    RAISE EXCEPTION 'Device assignment intervals overlap or lack a start' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_membership": """
DECLARE user_company bigint; warehouse_company bigint;
BEGIN
  SELECT empresa_id INTO user_company FROM public."USUARIO" WHERE id=NEW.usuario_id;
  SELECT empresa_id INTO warehouse_company FROM public."BODEGA" WHERE id=NEW.bodega_id;
  IF user_company IS NULL OR user_company IS DISTINCT FROM warehouse_company THEN
    RAISE EXCEPTION 'Membership must stay within a company' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_reading": """
BEGIN
  IF NEW.dispositivo_id IS NULL OR NEW.fermentacion_id IS NULL OR NEW.timestamp IS NULL OR NOT EXISTS (
    SELECT 1 FROM public."PROCESO_FERMENTACION" p
      JOIN public."ASIGNACION_DISPOSITIVO" a ON a.cuba_id=p.cuba_id
    WHERE p.id=NEW.fermentacion_id AND a.dispositivo_id=NEW.dispositivo_id
      AND NEW.timestamp >= a.asignado_en
      AND (a.desasignado_en IS NULL OR NEW.timestamp < a.desasignado_en)
      AND NEW.timestamp >= p.fecha_inicio
      AND (p.fecha_real_fin IS NULL OR NEW.timestamp <= p.fecha_real_fin)
  ) THEN
    RAISE EXCEPTION 'Reading is outside its process or device assignment interval' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_note": """
DECLARE author_company bigint; tank_company bigint; process_tank bigint;
BEGIN
  SELECT empresa_id INTO author_company FROM public."USUARIO" WHERE id=NEW.usuario_id;
  IF NEW.fermentacion_id IS NOT NULL THEN
    SELECT cuba_id INTO process_tank FROM public."PROCESO_FERMENTACION" WHERE id=NEW.fermentacion_id;
    IF NEW.cuba_id IS NOT NULL AND NEW.cuba_id IS DISTINCT FROM process_tank THEN
      RAISE EXCEPTION 'Note tank and process disagree' USING ERRCODE='23514';
    END IF;
  END IF;
  IF COALESCE(NEW.cuba_id, process_tank) IS NOT NULL THEN
    SELECT b.empresa_id INTO tank_company FROM public."CUBA" c
      JOIN public."BODEGA" b ON b.id=c.bodega_id WHERE c.id=COALESCE(NEW.cuba_id, process_tank);
    IF author_company IS NULL OR author_company IS DISTINCT FROM tank_company THEN
      RAISE EXCEPTION 'Note author must belong to the process company' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_alert": """
DECLARE process_company bigint; device_company bigint; actor_company bigint; target_company bigint;
BEGIN
  IF NEW.fermentacion_id IS NOT NULL THEN
    SELECT b.empresa_id INTO process_company FROM public."PROCESO_FERMENTACION" p
      JOIN public."CUBA" c ON c.id=p.cuba_id JOIN public."BODEGA" b ON b.id=c.bodega_id
      WHERE p.id=NEW.fermentacion_id;
  END IF;
  IF NEW.dispositivo_id IS NOT NULL THEN
    SELECT empresa_id INTO device_company FROM public."DISPOSITIVO" WHERE id=NEW.dispositivo_id;
  END IF;
  IF process_company IS NOT NULL AND device_company IS NOT NULL AND process_company <> device_company THEN
    RAISE EXCEPTION 'Alert device and process must share a company' USING ERRCODE='23514';
  END IF;
  target_company := COALESCE(process_company, device_company);
  IF target_company IS NULL THEN
    RAISE EXCEPTION 'Alert must have an attributable company' USING ERRCODE='23514';
  END IF;
  IF NEW.atendida_por IS NOT NULL THEN
    SELECT empresa_id INTO actor_company FROM public."USUARIO" WHERE id=NEW.atendida_por;
    IF actor_company IS DISTINCT FROM target_company THEN
      RAISE EXCEPTION 'Alert actor must belong to the company' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END;
""",
}

TRIGGERS = [
    ("CUBA", "scope", "UPDATE", "mosto_immutable_scope", "'bodega_id'"),
    ("BODEGA", "scope", "UPDATE", "mosto_immutable_scope", "'empresa_id'"),
    ("DISPOSITIVO", "scope", "UPDATE", "mosto_immutable_scope", "'empresa_id'"),
    ("USUARIO", "scope", "UPDATE", "mosto_immutable_scope", "'empresa_id'"),
    ("PERFIL_FERMENTACION", "scope", "UPDATE", "mosto_immutable_scope", "'bodega_id'"),
    ("PROCESO_FERMENTACION", "scope", "UPDATE", "mosto_immutable_scope", "'cuba_id'"),
    ("ASIGNACION_DISPOSITIVO", "scope", "UPDATE", "mosto_immutable_scope", "'dispositivo_id', 'cuba_id', 'asignado_en'"),
    ("PROCESO_FERMENTACION", "validate", "INSERT OR UPDATE", "mosto_validate_process", ""),
    ("ASIGNACION_DISPOSITIVO", "validate", "INSERT OR UPDATE", "mosto_validate_assignment", ""),
    ("USUARIO_BODEGA", "validate", "INSERT OR UPDATE", "mosto_validate_membership", ""),
    ("LECTURA_TELEMETRIA", "validate", "INSERT OR UPDATE", "mosto_validate_reading", ""),
    ("BITACORA_INTERVENCION", "validate", "INSERT OR UPDATE", "mosto_validate_note", ""),
    ("EVENTO_ALERTA", "validate", "INSERT OR UPDATE", "mosto_validate_alert", ""),
]


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, body in FUNCTIONS.items():
        op.execute(f'CREATE FUNCTION public.{name}() RETURNS trigger LANGUAGE plpgsql '
                   f'SET search_path = pg_catalog, public AS $mosto${body}$mosto$')
    for table, suffix, actions, function, args in TRIGGERS:
        op.execute(f'CREATE TRIGGER mosto_{suffix} BEFORE {actions} ON public."{table}" '
                   f'FOR EACH ROW EXECUTE FUNCTION public.{function}({args})')


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, suffix, *_ in reversed(TRIGGERS):
        op.execute(f'DROP TRIGGER mosto_{suffix} ON public."{table}"')
    for name in reversed(FUNCTIONS):
        op.execute(f'DROP FUNCTION public.{name}()')
