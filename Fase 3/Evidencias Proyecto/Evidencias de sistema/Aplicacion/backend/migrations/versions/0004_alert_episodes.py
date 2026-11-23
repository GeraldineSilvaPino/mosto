"""Thermal episodes, immutable action history and linked interventions."""
from alembic import op
import sqlalchemy as sa

revision = "0004_alert_episodes"
down_revision = "0003_telemetry_v2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("EVENTO_ALERTA") as batch:
        batch.add_column(sa.Column("resuelta_por", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_alerta_resuelta_por", "USUARIO", ["resuelta_por"], ["id"])
        for name, kind in (
            ("version_regla", sa.String(40)), ("origen", sa.String(16)),
            ("inicio_condicion", sa.DateTime(timezone=True)), ("fin_condicion", sa.DateTime(timezone=True)),
            ("ultima_observacion", sa.DateTime(timezone=True)), ("estado_condicion", sa.String(32)),
            ("evidencia", sa.JSON()),
        ):
            batch.add_column(sa.Column(name, kind, nullable=True))
        batch.create_index("uq_episodio_condicion_abierta", ["fermentacion_id", "tipo_alerta"], unique=True,
                           postgresql_where=sa.text("version_regla IS NOT NULL AND fin_condicion IS NULL"),
                           sqlite_where=sa.text("version_regla IS NOT NULL AND fin_condicion IS NULL"))
    with op.batch_alter_table("BITACORA_INTERVENCION") as batch:
        batch.add_column(sa.Column("alerta_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_bitacora_alerta", "EVENTO_ALERTA", ["alerta_id"], ["id"])
    op.create_table("ESTADO_REGLA",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("fermentacion_id", sa.BigInteger(), sa.ForeignKey("PROCESO_FERMENTACION.id"), nullable=False),
        sa.Column("codigo", sa.String(50), nullable=False),
        sa.Column("configuracion", sa.JSON(), nullable=False),
        sa.Column("ultima_observacion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inicio_candidato", sa.DateTime(timezone=True)),
        sa.Column("inicio_recuperacion", sa.DateTime(timezone=True)),
        sa.Column("episodio_id", sa.BigInteger(), sa.ForeignKey("EVENTO_ALERTA.id")),
        sa.UniqueConstraint("fermentacion_id", "codigo", name="uq_estado_regla_proceso_codigo"))
    op.create_table("AUDITORIA_ALERTA",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("alerta_id", sa.BigInteger(), sa.ForeignKey("EVENTO_ALERTA.id"), nullable=False),
        sa.Column("accion", sa.String(40), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observado_en", sa.DateTime(timezone=True)),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id")),
        sa.Column("mensaje_id", sa.BigInteger(), sa.ForeignKey("MENSAJE_TELEMETRIA.id")),
        sa.Column("detalle", sa.JSON(), nullable=False))
    op.create_index("ix_AUDITORIA_ALERTA_alerta_id", "AUDITORIA_ALERTA", ["alerta_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('''CREATE FUNCTION public.mosto_episode_references() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $f$
        DECLARE target_process bigint; target_company bigint; actor_company bigint; message_process bigint;
        BEGIN
          IF TG_TABLE_NAME = 'ESTADO_REGLA' THEN
            IF TG_OP = 'UPDATE' AND (NEW.fermentacion_id IS DISTINCT FROM OLD.fermentacion_id OR
                NEW.codigo IS DISTINCT FROM OLD.codigo OR NEW.configuracion::jsonb IS DISTINCT FROM OLD.configuracion::jsonb) THEN
              RAISE EXCEPTION 'Rule ownership and snapshot are immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.episodio_id IS NOT NULL THEN
              SELECT fermentacion_id INTO target_process FROM public."EVENTO_ALERTA" WHERE id=NEW.episodio_id;
              IF target_process IS DISTINCT FROM NEW.fermentacion_id THEN
                RAISE EXCEPTION 'Rule episode belongs to another process' USING ERRCODE='23514';
              END IF;
            END IF;
          ELSIF TG_TABLE_NAME = 'BITACORA_INTERVENCION' THEN
            IF NEW.alerta_id IS NOT NULL THEN
              SELECT fermentacion_id INTO target_process FROM public."EVENTO_ALERTA" WHERE id=NEW.alerta_id;
              IF target_process IS NULL OR target_process IS DISTINCT FROM NEW.fermentacion_id THEN
                RAISE EXCEPTION 'Intervention and episode disagree' USING ERRCODE='23514';
              END IF;
            END IF;
          ELSE
            IF TG_TABLE_NAME = 'AUDITORIA_ALERTA' THEN
              IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Alert audit is append only' USING ERRCODE='23514';
              END IF;
              SELECT fermentacion_id INTO target_process FROM public."EVENTO_ALERTA" WHERE id=NEW.alerta_id;
              actor_company := NULL;
              SELECT empresa_id INTO actor_company FROM public."USUARIO" WHERE id=NEW.usuario_id;
              IF NEW.mensaje_id IS NOT NULL THEN
                SELECT fermentacion_id INTO message_process FROM public."MENSAJE_TELEMETRIA" WHERE id=NEW.mensaje_id;
                IF message_process IS DISTINCT FROM target_process THEN
                  RAISE EXCEPTION 'Audit evidence belongs to another process' USING ERRCODE='23514';
                END IF;
              END IF;
            ELSE
              target_process := NEW.fermentacion_id;
              SELECT empresa_id INTO actor_company FROM public."USUARIO" WHERE id=NEW.resuelta_por;
            END IF;
            SELECT b.empresa_id INTO target_company FROM public."PROCESO_FERMENTACION" p
              JOIN public."CUBA" c ON c.id=p.cuba_id JOIN public."BODEGA" b ON b.id=c.bodega_id WHERE p.id=target_process;
            IF target_company IS NULL THEN
              IF TG_TABLE_NAME = 'AUDITORIA_ALERTA' THEN
                SELECT d.empresa_id INTO target_company FROM public."EVENTO_ALERTA" a
                  JOIN public."DISPOSITIVO" d ON d.id=a.dispositivo_id WHERE a.id=NEW.alerta_id;
              ELSE
                SELECT empresa_id INTO target_company FROM public."DISPOSITIVO" WHERE id=NEW.dispositivo_id;
              END IF;
            END IF;
            IF actor_company IS NOT NULL AND actor_company IS DISTINCT FROM target_company THEN
              RAISE EXCEPTION 'Episode actor belongs to another company' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END; $f$''')
        for table in ("ESTADO_REGLA", "BITACORA_INTERVENCION", "EVENTO_ALERTA", "AUDITORIA_ALERTA"):
            actions = "INSERT OR UPDATE OR DELETE" if table == "AUDITORIA_ALERTA" else "INSERT OR UPDATE"
            op.execute(f'CREATE TRIGGER mosto_episode_guard BEFORE {actions} ON public."{table}" FOR EACH ROW EXECUTE FUNCTION public.mosto_episode_references()')


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in ("ESTADO_REGLA", "BITACORA_INTERVENCION", "EVENTO_ALERTA", "AUDITORIA_ALERTA"):
            op.execute(f'DROP TRIGGER mosto_episode_guard ON public."{table}"')
        op.execute("DROP FUNCTION public.mosto_episode_references()")
    op.drop_table("AUDITORIA_ALERTA")
    op.drop_table("ESTADO_REGLA")
    with op.batch_alter_table("BITACORA_INTERVENCION") as batch:
        batch.drop_constraint("fk_bitacora_alerta", type_="foreignkey")
        batch.drop_column("alerta_id")
    with op.batch_alter_table("EVENTO_ALERTA") as batch:
        batch.drop_index("uq_episodio_condicion_abierta")
        batch.drop_constraint("fk_alerta_resuelta_por", type_="foreignkey")
        for name in ("resuelta_por", "version_regla", "origen", "inicio_condicion", "fin_condicion", "ultima_observacion", "estado_condicion", "evidencia"):
            batch.drop_column(name)
