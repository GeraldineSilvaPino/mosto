"""Append-only manual measurements and explicit annulment evidence."""
from alembic import op
import sqlalchemy as sa

revision = "0007_manual_measurements"
down_revision = "0006_interventions"
branch_labels = depends_on = None


def upgrade():
    key = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table("MEDICION_MANUAL",
        sa.Column("id", key, primary_key=True),
        sa.Column("fermentacion_id", sa.BigInteger(), sa.ForeignKey("PROCESO_FERMENTACION.id"), nullable=False),
        sa.Column("alerta_id", sa.BigInteger(), sa.ForeignKey("EVENTO_ALERTA.id")),
        sa.Column("intervencion_id", sa.BigInteger(), sa.ForeignKey("INTERVENCION_OPERATIVA.id")),
        sa.Column("bitacora_id", sa.BigInteger(), sa.ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id"), nullable=False),
        sa.Column("variable", sa.String(40), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("metodo", sa.String(40), nullable=False),
        sa.Column("instrumento", sa.String(200), nullable=False),
        sa.Column("evidencia", sa.Text(), nullable=False),
        sa.Column("observado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("solicitud", sa.JSON(), nullable=False),
        sa.UniqueConstraint("fermentacion_id", "request_id", name="uq_medicion_manual_solicitud"))
    op.create_table("ANULACION_MEDICION",
        sa.Column("id", key, primary_key=True),
        sa.Column("medicion_id", sa.BigInteger(), sa.ForeignKey("MEDICION_MANUAL.id"), nullable=False, unique=True),
        sa.Column("bitacora_id", sa.BigInteger(), sa.ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True),
        sa.Column("usuario_id", sa.BigInteger(), sa.ForeignKey("USUARIO.id"), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("solicitud", sa.JSON(), nullable=False))
    if op.get_bind().dialect.name == "postgresql":
        op.execute('''CREATE FUNCTION public.mosto_manual_measurement_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $f$ BEGIN
          RAISE EXCEPTION 'Manual measurement evidence is immutable' USING ERRCODE='23514';
        END; $f$''')
        for table in ("MEDICION_MANUAL", "ANULACION_MEDICION"):
            op.execute(f'CREATE TRIGGER immutable_manual_evidence BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION public.mosto_manual_measurement_immutable()')


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in ("ANULACION_MEDICION", "MEDICION_MANUAL"):
            op.execute(f'DROP TRIGGER immutable_manual_evidence ON "{table}"')
        op.execute('DROP FUNCTION public.mosto_manual_measurement_immutable()')
    op.drop_table("ANULACION_MEDICION")
    op.drop_table("MEDICION_MANUAL")
