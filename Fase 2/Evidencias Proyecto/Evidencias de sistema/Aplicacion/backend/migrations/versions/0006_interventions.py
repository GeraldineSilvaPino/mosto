"""Structured human interventions, independent of measured alert recovery."""
from alembic import op
import sqlalchemy as sa

revision = "0006_interventions"
down_revision = "0005_profile_versions"
branch_labels = depends_on = None


def upgrade():
    key = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table("INTERVENCION_OPERATIVA",
        sa.Column("id", key, primary_key=True),
        sa.Column("fermentacion_id", sa.BigInteger(), sa.ForeignKey("PROCESO_FERMENTACION.id"), nullable=False),
        sa.Column("alerta_id", sa.BigInteger(), sa.ForeignKey("EVENTO_ALERTA.id")),
        sa.Column("responsable_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id"), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("solicitud", sa.JSON(), nullable=False),
        sa.UniqueConstraint("fermentacion_id", "request_id", name="uq_intervencion_solicitud"))
    op.create_table("EVENTO_INTERVENCION",
        sa.Column("id", key, primary_key=True),
        sa.Column("intervencion_id", sa.BigInteger(), sa.ForeignKey("INTERVENCION_OPERATIVA.id"), nullable=False),
        sa.Column("bitacora_id", sa.BigInteger(), sa.ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("respuesta", sa.String(30)),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("solicitud", sa.JSON(), nullable=False),
        sa.UniqueConstraint("intervencion_id", "request_id", name="uq_evento_intervencion_solicitud"),
        sa.UniqueConstraint("intervencion_id", "revision", name="uq_evento_intervencion_revision"))
    if op.get_bind().dialect.name == "postgresql":
        op.execute('''CREATE FUNCTION public.mosto_intervention_event_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $f$ BEGIN
          RAISE EXCEPTION 'Intervention history is immutable' USING ERRCODE='23514';
        END; $f$''')
        op.execute('CREATE TRIGGER immutable_intervention_event BEFORE UPDATE OR DELETE ON "EVENTO_INTERVENCION" FOR EACH ROW EXECUTE FUNCTION public.mosto_intervention_event_immutable()')


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute('DROP TRIGGER immutable_intervention_event ON "EVENTO_INTERVENCION"')
        op.execute('DROP FUNCTION public.mosto_intervention_event_immutable()')
    op.drop_table("EVENTO_INTERVENCION")
    op.drop_table("INTERVENCION_OPERATIVA")
