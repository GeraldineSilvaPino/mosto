"""Freeze one clock per process across all registered synthetic recipes."""
from alembic import op
import sqlalchemy as sa

revision = "0009_process_clock_registry"
down_revision = "0008_process_profile_overrides"
branch_labels = depends_on = None
depends_on = None


def upgrade():
    pg = op.get_context().dialect.name == "postgresql"
    if pg:
        # Keep historical backfill and installation of the insert trigger atomic.
        op.execute('LOCK TABLE "CALIBRACION_DISPOSITIVO", "LECTURA_TELEMETRIA" IN SHARE ROW EXCLUSIVE MODE')
        process = "(parametros->'simulation'->>'process_id')::bigint"
        clock = """jsonb_build_array(parametros->'simulation_clock'->>'real_anchor',
            parametros->'simulation_clock'->>'simulated_anchor',
            (parametros->'simulation_clock'->>'factor')::double precision)::text"""
    else:
        # Enter a write transaction before DDL with sqlite3 legacy transaction mode.
        op.execute('UPDATE "CALIBRACION_DISPOSITIVO" SET id=id WHERE 0')
        process = "json_extract(parametros, '$.simulation.process_id')"
        clock = """json_array(json_extract(parametros, '$.simulation_clock.real_anchor'),
            json_extract(parametros, '$.simulation_clock.simulated_anchor'),
            CAST(json_extract(parametros, '$.simulation_clock.factor') AS REAL))"""
    op.create_table("RELOJ_PROCESO",
                    sa.Column("fermentacion_id", sa.BigInteger(),
                              sa.ForeignKey("PROCESO_FERMENTACION.id"), primary_key=True,
                              autoincrement=False),
                    sa.Column("clave", sa.Text(), nullable=False))
    # A legacy process with conflicting clocks must fail migration, even if one
    # recipe has already been revoked. Never pick a winner by insertion order.
    wall = "jsonb_build_array(NULL, NULL, NULL)::text" if pg else "json_array(NULL, NULL, NULL)"
    op.execute(f'''INSERT INTO "RELOJ_PROCESO" (fermentacion_id, clave)
        SELECT {process}, {clock} FROM "CALIBRACION_DISPOSITIVO" WHERE {process} IS NOT NULL
        UNION SELECT fermentacion_id, {wall} FROM "LECTURA_TELEMETRIA" WHERE fermentacion_id IS NOT NULL''')
    process = process.replace("parametros", "NEW.parametros")
    clock = clock.replace("parametros", "NEW.parametros")
    register_trigger(pg, "CALIBRACION_DISPOSITIVO", "register_process_clock", process, clock)
    # All currently supported projections (physical, synthetic 1x and legacy)
    # use wall UTC. Until dual-domain projections exist this closes every writer.
    register_trigger(pg, "LECTURA_TELEMETRIA", "register_reading_clock", "NEW.fermentacion_id", wall)


def register_trigger(pg, table, name, process, clock):
    if pg:
        op.execute(f'''CREATE FUNCTION public.mosto_{name}() RETURNS trigger
            LANGUAGE plpgsql AS $f$ BEGIN
            IF {process} IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM public."RELOJ_PROCESO" WHERE fermentacion_id={process} AND clave={clock}
            ) THEN
              INSERT INTO public."RELOJ_PROCESO" AS r (fermentacion_id, clave)
              VALUES ({process}, {clock}) ON CONFLICT (fermentacion_id) DO UPDATE
                SET clave = excluded.clave WHERE r.clave = excluded.clave;
              IF NOT FOUND THEN
                RAISE EXCEPTION 'Conflicting process clock' USING ERRCODE='23514';
              END IF;
            END IF;
            RETURN NEW;
            END; $f$''')
        op.execute(f'''CREATE TRIGGER {name} AFTER INSERT ON "{table}"
            FOR EACH ROW EXECUTE FUNCTION public.mosto_{name}()''')
    else:
        op.execute(f'''CREATE TRIGGER {name} AFTER INSERT ON "{table}"
            WHEN {process} IS NOT NULL BEGIN
            INSERT INTO "RELOJ_PROCESO" (fermentacion_id, clave) VALUES ({process}, {clock})
                ON CONFLICT(fermentacion_id) DO NOTHING;
            SELECT RAISE(ABORT, 'Conflicting process clock')
                WHERE EXISTS (SELECT 1 FROM "RELOJ_PROCESO"
                              WHERE fermentacion_id = {process} AND clave <> {clock});
            END''')


def downgrade():
    for table, name in (("LECTURA_TELEMETRIA", "register_reading_clock"),
                        ("CALIBRACION_DISPOSITIVO", "register_process_clock")):
        if op.get_context().dialect.name == "postgresql":
            op.execute(f'DROP TRIGGER {name} ON "{table}"')
            op.execute(f"DROP FUNCTION public.mosto_{name}()")
        else:
            op.execute(f"DROP TRIGGER {name}")
    op.drop_table("RELOJ_PROCESO")
