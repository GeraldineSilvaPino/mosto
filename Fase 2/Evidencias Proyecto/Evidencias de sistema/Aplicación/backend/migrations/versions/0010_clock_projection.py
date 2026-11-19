"""Bind a scheduled reading's real acquisition to its canonical simulation envelope."""
from importlib import import_module

from alembic import op

revision = "0010_clock_projection"
down_revision = "0009_process_clock_registry"
branch_labels = depends_on = None
depends_on = None

registry = import_module("migrations.versions.0009_process_clock_registry")
legacy = import_module("migrations.versions.0003_telemetry_v2")


def micros(value, pg):
    if pg:
        return f"(extract(epoch from ({value})::timestamptz) * 1000000)::bigint"
    # ORM timestamps and JSON clock anchors are normalized to UTC. Parse whole
    # seconds separately because SQLite's date functions round fractions to ms.
    return (f"(unixepoch(substr({value},1,19))*1000000 + "
            f"CAST(substr(substr(rtrim({value},'Z'),21,6)||'000000',1,6) AS INTEGER))")


def parameter(section, name, pg):
    if pg:
        return f"(c.parametros->'{section}'->>'{name}')"
    return f"json_extract(c.parametros,'$.{section}.{name}')"


def upgrade():
    pg = op.get_context().dialect.name == "postgresql"
    if not pg:
        op.execute('UPDATE "LECTURA_TELEMETRIA" SET id=id WHERE 0')
    op.execute('ALTER TABLE "LECTURA_TELEMETRIA" ADD COLUMN reloj_calibracion_id BIGINT '
               'REFERENCES "CALIBRACION_DISPOSITIVO"(id)')
    op.execute('DROP TRIGGER register_reading_clock' + (' ON "LECTURA_TELEMETRIA"' if pg else ''))
    # Preserve 0009's ordinary clock binding on every unmarked reading.
    if pg:
        op.execute('''CREATE TRIGGER register_reading_clock AFTER INSERT ON "LECTURA_TELEMETRIA"
            FOR EACH ROW WHEN (NEW.reloj_calibracion_id IS NULL)
            EXECUTE FUNCTION public.mosto_register_reading_clock()''')
    else:
        op.execute('''CREATE TRIGGER register_reading_clock AFTER INSERT ON "LECTURA_TELEMETRIA"
            WHEN NEW.fermentacion_id IS NOT NULL AND NEW.reloj_calibracion_id IS NULL BEGIN
            INSERT INTO "RELOJ_PROCESO" (fermentacion_id, clave)
              VALUES (NEW.fermentacion_id,json_array(NULL,NULL,NULL)) ON CONFLICT DO NOTHING;
            SELECT RAISE(ABORT,'Conflicting process clock') WHERE EXISTS
              (SELECT 1 FROM "RELOJ_PROCESO" WHERE fermentacion_id=NEW.fermentacion_id
               AND clave<>json_array(NULL,NULL,NULL)); END''')

    real = parameter("simulation_clock", "real_anchor", pg)
    simulated = parameter("simulation_clock", "simulated_anchor", pg)
    factor = parameter("simulation_clock", "factor", pg)
    process_id = parameter("simulation", "process_id", pg)
    key = (f"jsonb_build_array({real},{simulated},({factor})::double precision)::text" if pg else
           f"json_array({real},{simulated},CAST({factor} AS REAL))")
    valid_reading = f'''SELECT 1 FROM "CALIBRACION_DISPOSITIVO" c
        JOIN "DISPOSITIVO" d ON d.id=c.dispositivo_id
        JOIN "PROCESO_FERMENTACION" p ON p.id=CAST({process_id} AS BIGINT)
        JOIN "CUBA" t ON t.id=p.cuba_id JOIN "BODEGA" b ON b.id=t.bodega_id AND b.empresa_id=d.empresa_id
        JOIN "RELOJ_PROCESO" r ON r.fermentacion_id=p.id AND r.clave={key}
        JOIN "ASIGNACION_DISPOSITIVO" a ON a.dispositivo_id=d.id AND a.cuba_id=t.id
        WHERE c.id=NEW.reloj_calibracion_id AND c.metodo='synthetic_identity' AND c.revocada_en IS NULL
          AND d.id=NEW.dispositivo_id AND d.origen='simulado' AND NEW.origen_dato='v2_simulado'
          AND p.id=NEW.fermentacion_id AND CAST({factor} AS DOUBLE PRECISION) BETWEEN 1 AND 3600
          AND {micros(simulated, pg)}={micros("p.fecha_inicio", pg)}
          AND {micros("NEW.timestamp", pg)}>={micros(real, pg)}
          AND NEW.timestamp>=p.fecha_inicio AND (p.fecha_real_fin IS NULL OR NEW.timestamp<p.fecha_real_fin)
          AND NEW.timestamp>=c.valida_desde AND (c.valida_hasta IS NULL OR NEW.timestamp<c.valida_hasta)
          AND NEW.timestamp>=a.asignado_en AND (a.desasignado_en IS NULL OR NEW.timestamp<a.desasignado_en)'''
    cadence = parameter("simulation", "cadence_seconds", pg)
    duration = parameter("simulation", "duration_hours", pg)
    elapsed = f"(NEW.secuencia * CAST({cadence} AS BIGINT) * 1000000)"
    valid_message = f'''SELECT 1 FROM "LECTURA_TELEMETRIA" l
        JOIN "CALIBRACION_DISPOSITIVO" c ON c.id=l.reloj_calibracion_id AND c.id=NEW.calibracion_id
        JOIN "CREDENCIAL_DISPOSITIVO" k ON k.id=NEW.credencial_id AND k.dispositivo_id=l.dispositivo_id
        JOIN "PROCESO_FERMENTACION" p ON p.id=l.fermentacion_id
        JOIN "ASIGNACION_DISPOSITIVO" a ON a.id=NEW.asignacion_id AND a.cuba_id=p.cuba_id
        WHERE l.id=NEW.lectura_id AND l.dispositivo_id=NEW.dispositivo_id AND NEW.origen='simulado'
          AND l.fermentacion_id=NEW.fermentacion_id AND a.dispositivo_id=l.dispositivo_id
          AND l.timestamp>=a.asignado_en AND (a.desasignado_en IS NULL OR l.timestamp<a.desasignado_en)
          AND l.timestamp<=NEW.recibido_en AND c.revocada_en IS NULL
          AND (p.fecha_real_fin IS NULL OR l.timestamp<p.fecha_real_fin)
          AND NEW.secuencia BETWEEN 0 AND CAST({duration} AS BIGINT)*3600/CAST({cadence} AS BIGINT)
          AND {micros("NEW.observado_en", pg)}-{micros(simulated, pg)}={elapsed}
          AND abs(({micros("l.timestamp", pg)}-{micros(real, pg)})-
                  {elapsed}/CAST({factor} AS DOUBLE PRECISION))<=0.500001'''
    timed = '''EXISTS (SELECT 1 FROM "LECTURA_TELEMETRIA" WHERE id=NEW.lectura_id
                       AND reloj_calibracion_id IS NOT NULL)'''
    timed_recipe = f'''EXISTS (SELECT 1 FROM "CALIBRACION_DISPOSITIVO" c
                       WHERE c.id=NEW.calibracion_id AND {factor} IS NOT NULL)'''
    if pg:
        op.execute(f'''CREATE FUNCTION public.mosto_clock_reading() RETURNS trigger LANGUAGE plpgsql AS $f$
            BEGIN IF NOT EXISTS ({valid_reading}) THEN RAISE EXCEPTION 'Invalid scheduled reading'
            USING ERRCODE='23514'; END IF; RETURN NEW; END; $f$''')
        op.execute('''CREATE TRIGGER clock_reading BEFORE INSERT ON "LECTURA_TELEMETRIA"
            FOR EACH ROW WHEN (NEW.reloj_calibracion_id IS NOT NULL)
            EXECUTE FUNCTION public.mosto_clock_reading()''')
        op.execute('''CREATE TRIGGER clock_reading_locked BEFORE UPDATE ON "LECTURA_TELEMETRIA"
            FOR EACH ROW WHEN (OLD.reloj_calibracion_id IS NOT NULL OR NEW.reloj_calibracion_id IS NOT NULL)
            EXECUTE FUNCTION public.mosto_reject_message_change()''')
        body = legacy.FUNCTIONS["mosto_validate_v2_message"].replace("BEGIN", f"""BEGIN
            IF {timed} OR {timed_recipe} THEN
                IF NOT EXISTS ({valid_message}) THEN RAISE EXCEPTION 'Invalid scheduled envelope'
                USING ERRCODE='23514'; END IF; RETURN NEW;
            END IF;""", 1)
        replace_message_guard(body)
    else:
        op.execute(f'''CREATE TRIGGER clock_reading BEFORE INSERT ON "LECTURA_TELEMETRIA"
            WHEN NEW.reloj_calibracion_id IS NOT NULL AND NOT EXISTS ({valid_reading})
            BEGIN SELECT RAISE(ABORT,'Invalid scheduled reading'); END''')
        op.execute('''CREATE TRIGGER clock_reading_locked BEFORE UPDATE ON "LECTURA_TELEMETRIA"
            WHEN OLD.reloj_calibracion_id IS NOT NULL OR NEW.reloj_calibracion_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT,'Immutable scheduled reading'); END''')
        op.execute(f'''CREATE TRIGGER clock_envelope BEFORE INSERT ON "MENSAJE_TELEMETRIA"
            WHEN ({timed} OR {timed_recipe}) AND NOT EXISTS ({valid_message})
            BEGIN SELECT RAISE(ABORT,'Invalid scheduled envelope'); END''')
        op.execute(f'''CREATE TRIGGER clock_envelope_locked BEFORE UPDATE ON "MENSAJE_TELEMETRIA"
            WHEN {timed} OR {timed.replace("NEW.", "OLD.")} OR {timed_recipe}
            BEGIN SELECT RAISE(ABORT,'Immutable scheduled envelope'); END''')


def replace_message_guard(body):
    op.execute(f'''CREATE OR REPLACE FUNCTION public.mosto_validate_v2_message() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $f$ {body} $f$''')


def downgrade():
    pg = op.get_context().dialect.name == "postgresql"
    if not pg:
        op.execute('UPDATE "LECTURA_TELEMETRIA" SET id=id WHERE 0')
    # Refuse lossy rollback if this database has real/simulated pairs.
    op.execute('CREATE TEMP TABLE mosto_rollback_clock_check (n INTEGER CHECK(n=0))')
    op.execute('INSERT INTO mosto_rollback_clock_check SELECT 1 FROM "LECTURA_TELEMETRIA" '
               'WHERE reloj_calibracion_id IS NOT NULL LIMIT 1')
    op.execute('DROP TABLE mosto_rollback_clock_check')
    for name in ("clock_reading", "clock_reading_locked", "register_reading_clock"):
        op.execute(f'DROP TRIGGER {name}' + (' ON "LECTURA_TELEMETRIA"' if pg else ''))
    if pg:
        replace_message_guard(legacy.FUNCTIONS["mosto_validate_v2_message"])
        op.execute("DROP FUNCTION public.mosto_clock_reading()")
        op.execute("DROP FUNCTION public.mosto_register_reading_clock()")
    else:
        op.execute("DROP TRIGGER clock_envelope_locked")
        op.execute("DROP TRIGGER clock_envelope")
    op.execute('ALTER TABLE "LECTURA_TELEMETRIA" DROP COLUMN reloj_calibracion_id')
    wall = "jsonb_build_array(NULL,NULL,NULL)::text" if pg else "json_array(NULL,NULL,NULL)"
    registry.register_trigger(pg, "LECTURA_TELEMETRIA", "register_reading_clock", "NEW.fermentacion_id", wall)
