"""Canonical telemetry v2, device credentials and versioned calibration."""
from alembic import op
import sqlalchemy as sa

revision = "0003_telemetry_v2"
down_revision = "0002_guards"
branch_labels = None
depends_on = None


def upgrade():
    # Frozen schema operations.
    op.create_table('CALIBRACION_DISPOSITIVO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=False),
    sa.Column('version', sa.String(length=80), nullable=False),
    sa.Column('metodo', sa.String(length=32), nullable=False),
    sa.Column('parametros', sa.JSON(), nullable=False),
    sa.Column('valida_desde', sa.DateTime(timezone=True), nullable=False),
    sa.Column('valida_hasta', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revocada_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('creada_por', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['creada_por'], ['USUARIO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispositivo_id', 'version', name='uq_calibracion_dispositivo_version')
    )
    op.create_table('CREDENCIAL_DISPOSITIVO',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('etiqueta', sa.String(length=80), nullable=False),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expira_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revocada_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creada_por', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['creada_por'], ['USUARIO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_CREDENCIAL_DISPOSITIVO_dispositivo_id'), 'CREDENCIAL_DISPOSITIVO', ['dispositivo_id'], unique=False)
    op.create_table('MENSAJE_TELEMETRIA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=False),
    sa.Column('credencial_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('boot_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('secuencia', sa.BigInteger(), nullable=False),
    sa.Column('observado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recibido_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('origen', sa.String(length=16), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('asignacion_id', sa.BigInteger(), nullable=False),
    sa.Column('fermentacion_id', sa.BigInteger(), nullable=False),
    sa.Column('calibracion_id', sa.BigInteger(), nullable=True),
    sa.Column('lectura_id', sa.BigInteger(), nullable=False),
    sa.Column('calidad_temperatura', sa.String(length=20), nullable=False),
    sa.Column('calidad_brix', sa.String(length=20), nullable=False),
    sa.Column('temperatura', sa.Float(), nullable=True),
    sa.Column('brix', sa.Float(), nullable=True),
    sa.Column('diagnosticos', sa.JSON(), nullable=False),
    sa.Column('fuera_de_orden', sa.Boolean(), nullable=False),
    sa.Column('retrasado', sa.Boolean(), nullable=False),
    sa.CheckConstraint("origen IN ('fisico', 'simulado')", name='ck_mensaje_origen'),
    sa.CheckConstraint('secuencia >= 0', name='ck_mensaje_secuencia'),
    sa.ForeignKeyConstraint(['asignacion_id'], ['ASIGNACION_DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['calibracion_id'], ['CALIBRACION_DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['credencial_id'], ['CREDENCIAL_DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['fermentacion_id'], ['PROCESO_FERMENTACION.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['lectura_id'], ['LECTURA_TELEMETRIA.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispositivo_id', 'boot_id', 'secuencia', name='uq_mensaje_dispositivo_boot_secuencia'),
    sa.UniqueConstraint('lectura_id')
    )
    op.create_index('ix_mensaje_proceso_observado', 'MENSAJE_TELEMETRIA', ['fermentacion_id', 'observado_en'], unique=False)
    op.add_column('DISPOSITIVO', sa.Column('origen', sa.String(length=16), nullable=True))
    op.add_column('DISPOSITIVO', sa.Column('ultima_recepcion', sa.DateTime(timezone=True), nullable=True))

    _install_guards()


def downgrade():
    _remove_guards()
    # Frozen schema operations.
    op.drop_column('DISPOSITIVO', 'ultima_recepcion')
    op.drop_column('DISPOSITIVO', 'origen')
    op.drop_index('ix_mensaje_proceso_observado', table_name='MENSAJE_TELEMETRIA')
    op.drop_table('MENSAJE_TELEMETRIA')
    op.drop_index(op.f('ix_CREDENCIAL_DISPOSITIVO_dispositivo_id'), table_name='CREDENCIAL_DISPOSITIVO')
    op.drop_table('CREDENCIAL_DISPOSITIVO')
    op.drop_table('CALIBRACION_DISPOSITIVO')



FUNCTIONS = {
    "mosto_validate_device_source": """
BEGIN
  IF NEW.origen IS NOT NULL AND NEW.origen NOT IN ('fisico', 'simulado') THEN
    RAISE EXCEPTION 'Unknown device source' USING ERRCODE='23514';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.origen IS NOT NULL AND OLD.origen IS DISTINCT FROM NEW.origen THEN
    RAISE EXCEPTION 'Provisioned device source is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_provisioning": """
DECLARE owner_company bigint; actor_company bigint; source text;
BEGIN
  SELECT empresa_id, origen INTO owner_company, source FROM public."DISPOSITIVO" WHERE id=NEW.dispositivo_id;
  SELECT empresa_id INTO actor_company FROM public."USUARIO" WHERE id=NEW.creada_por;
  IF source IS NULL OR owner_company IS DISTINCT FROM actor_company THEN
    RAISE EXCEPTION 'Invalid device provisioning scope' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME = 'CALIBRACION_DISPOSITIVO' THEN
    IF (source='fisico' AND NEW.metodo <> 'tilt_polynomial') OR
       (source='simulado' AND NEW.metodo <> 'synthetic_identity') THEN
      RAISE EXCEPTION 'Calibration method does not match device source' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END;
""",
    "mosto_validate_v2_message": """
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public."DISPOSITIVO" d
    JOIN public."CREDENCIAL_DISPOSITIVO" k ON k.dispositivo_id=d.id
    JOIN public."LECTURA_TELEMETRIA" l ON l.dispositivo_id=d.id
    JOIN public."PROCESO_FERMENTACION" p ON p.id=l.fermentacion_id
    JOIN public."ASIGNACION_DISPOSITIVO" a ON a.dispositivo_id=d.id AND a.cuba_id=p.cuba_id
    WHERE d.id=NEW.dispositivo_id AND d.origen=NEW.origen
      AND k.id=NEW.credencial_id AND l.id=NEW.lectura_id AND p.id=NEW.fermentacion_id
      AND l.timestamp=NEW.observado_en AND a.id=NEW.asignacion_id
      AND NEW.observado_en >= a.asignado_en
      AND (a.desasignado_en IS NULL OR NEW.observado_en < a.desasignado_en)
  ) THEN
    RAISE EXCEPTION 'Message references disagree' USING ERRCODE='23514';
  END IF;
  IF NEW.calibracion_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public."CALIBRACION_DISPOSITIVO" c WHERE c.id=NEW.calibracion_id AND c.dispositivo_id=NEW.dispositivo_id
  ) THEN
    RAISE EXCEPTION 'Calibration belongs to another device' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
""",
    "mosto_reject_message_change": """
BEGIN
  RAISE EXCEPTION 'Accepted telemetry envelopes are immutable' USING ERRCODE='23514';
END;
""",
}
TRIGGERS = [
    ('DISPOSITIVO', 'v2_source', 'INSERT OR UPDATE', 'mosto_validate_device_source', ''),
    ('CREDENCIAL_DISPOSITIVO', 'v2_provision', 'INSERT OR UPDATE', 'mosto_validate_provisioning', ''),
    ('CALIBRACION_DISPOSITIVO', 'v2_provision', 'INSERT OR UPDATE', 'mosto_validate_provisioning', ''),
    ('CALIBRACION_DISPOSITIVO', 'v2_immutable', 'UPDATE', 'mosto_immutable_scope', "'dispositivo_id','version','metodo','parametros','valida_desde','valida_hasta','creada_por','creada_en'"),
    ('CREDENCIAL_DISPOSITIVO', 'v2_immutable', 'UPDATE', 'mosto_immutable_scope', "'dispositivo_id','token_hash','creada_en','expira_en','creada_por'"),
    ('MENSAJE_TELEMETRIA', 'v2_validate', 'INSERT', 'mosto_validate_v2_message', ''),
    ('MENSAJE_TELEMETRIA', 'v2_immutable', 'UPDATE OR DELETE', 'mosto_reject_message_change', ''),
]


def _install_guards():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for name, body in FUNCTIONS.items():
        op.execute(f'CREATE FUNCTION public.{name}() RETURNS trigger LANGUAGE plpgsql '
                   f'SET search_path=pg_catalog, public AS $mosto${body}$mosto$')
    for table, suffix, actions, function, args in TRIGGERS:
        op.execute(f'CREATE TRIGGER mosto_{suffix} BEFORE {actions} ON public."{table}" '
                   f'FOR EACH ROW EXECUTE FUNCTION public.{function}({args})')


def _remove_guards():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for table, suffix, *_ in reversed(TRIGGERS):
        op.execute(f'DROP TRIGGER mosto_{suffix} ON public."{table}"')
    for name in reversed(FUNCTIONS):
        op.execute(f'DROP FUNCTION public.{name}()')
