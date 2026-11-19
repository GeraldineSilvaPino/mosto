"""Audited thermal overrides without rewriting initial rule or process snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0008_process_profile_overrides'
down_revision = '0007_manual_measurements'
branch_labels = depends_on = None


def upgrade():
    op.add_column('ESTADO_REGLA', sa.Column('perfil_ajuste_revision', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('AJUSTE_PERFIL_PROCESO',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True),
        sa.Column('fermentacion_id', sa.BigInteger(), sa.ForeignKey('PROCESO_FERMENTACION.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.BigInteger(), sa.ForeignKey('USUARIO.id'), nullable=False),
        sa.Column('bitacora_id', sa.BigInteger(), sa.ForeignKey('BITACORA_INTERVENCION.id'), nullable=False, unique=True),
        sa.Column('vigente_desde', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accion', sa.String(20), nullable=False),
        sa.Column('motivo', sa.Text(), nullable=False),
        sa.Column('configuracion', sa.JSON(), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('solicitud', sa.JSON(), nullable=False),
        sa.UniqueConstraint('fermentacion_id', 'revision', name='uq_ajuste_perfil_revision'),
        sa.UniqueConstraint('fermentacion_id', 'request_id', name='uq_ajuste_perfil_solicitud'))
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('''CREATE FUNCTION public.mosto_process_override_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $f$ BEGIN
          RAISE EXCEPTION 'Process override history is immutable' USING ERRCODE='23514';
        END; $f$''')
        op.execute('CREATE TRIGGER immutable_process_override BEFORE UPDATE OR DELETE ON "AJUSTE_PERFIL_PROCESO" FOR EACH ROW EXECUTE FUNCTION public.mosto_process_override_immutable()')


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP TRIGGER immutable_process_override ON "AJUSTE_PERFIL_PROCESO"')
        op.execute('DROP FUNCTION public.mosto_process_override_immutable()')
    op.drop_table('AJUSTE_PERFIL_PROCESO')
    op.drop_column('ESTADO_REGLA', 'perfil_ajuste_revision')
