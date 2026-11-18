"""Version history and explicit process snapshots; no fabricated historical backfill."""
from alembic import op
import sqlalchemy as sa

revision = "0005_profile_versions"
down_revision = "0004_alert_episodes"
branch_labels = depends_on = None


def upgrade():
    op.add_column("PERFIL_FERMENTACION", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("PROCESO_FERMENTACION", sa.Column("perfil_snapshot", sa.JSON(), nullable=True))
    op.create_table("VERSION_PERFIL",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("perfil_id", sa.BigInteger(), sa.ForeignKey("PERFIL_FERMENTACION.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuracion", sa.JSON(), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id")),
        sa.Column("origen", sa.String(40), nullable=False),
        sa.UniqueConstraint("perfil_id", "revision", name="uq_version_perfil"))
    if op.get_bind().dialect.name == "postgresql":
        op.execute('''CREATE FUNCTION public.mosto_profile_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $f$ BEGIN
          IF TG_TABLE_NAME = 'VERSION_PERFIL' THEN
            RAISE EXCEPTION 'Profile history is immutable' USING ERRCODE='23514';
          END IF;
          IF OLD.perfil_snapshot IS NOT NULL AND
             (NEW.perfil_snapshot::jsonb IS DISTINCT FROM OLD.perfil_snapshot::jsonb OR
              NEW.perfil_id IS DISTINCT FROM OLD.perfil_id) THEN
            RAISE EXCEPTION 'Process profile snapshot is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $f$''')
        op.execute('CREATE TRIGGER immutable_profile_version BEFORE UPDATE OR DELETE ON "VERSION_PERFIL" FOR EACH ROW EXECUTE FUNCTION public.mosto_profile_immutable()')
        op.execute('CREATE TRIGGER immutable_process_profile BEFORE UPDATE ON "PROCESO_FERMENTACION" FOR EACH ROW EXECUTE FUNCTION public.mosto_profile_immutable()')


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute('DROP TRIGGER immutable_process_profile ON "PROCESO_FERMENTACION"')
        op.execute('DROP TRIGGER immutable_profile_version ON "VERSION_PERFIL"')
        op.execute('DROP FUNCTION public.mosto_profile_immutable()')
    op.drop_table("VERSION_PERFIL")
    op.drop_column("PROCESO_FERMENTACION", "perfil_snapshot")
    op.drop_column("PERFIL_FERMENTACION", "revision")
