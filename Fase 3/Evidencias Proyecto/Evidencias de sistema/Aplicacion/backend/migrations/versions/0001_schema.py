"""Portable Mosto schema, frozen baseline for EMPTY local databases.

This is an intentional adaptation, not a stamp for existing Supabase schemas.
Nullable unmeasured channels and UUID auth_uid are deliberate; see migration docs.
"""
from alembic import op, context
import sqlalchemy as sa

revision = "0001_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        existing = set(sa.inspect(op.get_bind()).get_table_names()) - {"alembic_version"}
        if existing:
            raise RuntimeError("Baseline requires an empty database; do not stamp an existing schema")
    # Frozen schema operations; reviewed against the audit snapshot.
    op.create_table('CEPA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('tipo_uva', sa.String(length=50), nullable=True),
    sa.Column('nombre_variedad', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nombre_variedad')
    )
    op.create_index(op.f('ix_CEPA_id'), 'CEPA', ['id'], unique=False)
    op.create_table('EMPRESA_CLIENTE',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('nomb_emp', sa.String(length=150), nullable=False),
    sa.Column('email_emp', sa.String(length=120), nullable=True),
    sa.Column('direccion_emp', sa.String(length=200), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rut', sa.String(length=50), nullable=True),
    sa.Column('razon_social', sa.String(length=150), nullable=True),
    sa.Column('giro', sa.String(length=150), nullable=True),
    sa.Column('telefono', sa.String(length=50), nullable=True),
    sa.Column('logo_url', sa.Text(), nullable=True),
    sa.Column('reporte_diario', sa.Boolean(), nullable=True),
    sa.Column('alertas_sms', sa.Boolean(), nullable=True),
    sa.Column('max_cubas', sa.Integer(), nullable=True),
    sa.Column('max_usuarios', sa.Integer(), nullable=True),
    sa.Column('plan_nombre', sa.String(length=100), nullable=True),
    sa.Column('ciclo_facturacion', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nomb_emp')
    )
    op.create_index(op.f('ix_EMPRESA_CLIENTE_id'), 'EMPRESA_CLIENTE', ['id'], unique=False)
    op.create_table('MODELO_DISPOSITIVO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('marca', sa.String(length=100), nullable=True),
    sa.Column('modelo', sa.String(length=100), nullable=False),
    sa.Column('arquitectura', sa.String(length=100), nullable=True),
    sa.Column('version_hardware', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('marca', 'modelo', 'version_hardware', name='uq_modelo_dispositivo')
    )
    op.create_index(op.f('ix_MODELO_DISPOSITIVO_id'), 'MODELO_DISPOSITIVO', ['id'], unique=False)
    op.create_table('ROL',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('codigo', sa.String(length=50), nullable=False),
    sa.Column('descripcion', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_index(op.f('ix_ROL_id'), 'ROL', ['id'], unique=False)
    op.create_table('TIPO_MATERIAL_CUBA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_TIPO_MATERIAL_CUBA_id'), 'TIPO_MATERIAL_CUBA', ['id'], unique=False)
    op.create_table('BODEGA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('direccion', sa.String(length=200), nullable=True),
    sa.Column('empresa_id', sa.BigInteger(), nullable=False),
    sa.Column('valle_vitivinicola', sa.String(length=100), nullable=True),
    sa.Column('comuna', sa.String(length=100), nullable=True),
    sa.Column('region', sa.String(length=100), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['empresa_id'], ['EMPRESA_CLIENTE.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('empresa_id', 'nombre', name='uq_bodega_empresa_nombre')
    )
    op.create_index(op.f('ix_BODEGA_id'), 'BODEGA', ['id'], unique=False)
    op.create_table('DISPOSITIVO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('mac_address', sa.String(length=50), nullable=False),
    sa.Column('tipo_dispositivo', sa.String(length=50), nullable=True),
    sa.Column('firmware_version', sa.String(length=50), nullable=True),
    sa.Column('estado', sa.String(length=50), nullable=False),
    sa.Column('empresa_id', sa.BigInteger(), nullable=False),
    sa.Column('modelo_id', sa.BigInteger(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("estado IN ('activo', 'inactivo', 'mantencion')", name='ck_dispositivo_estado'),
    sa.ForeignKeyConstraint(['empresa_id'], ['EMPRESA_CLIENTE.id'], ),
    sa.ForeignKeyConstraint(['modelo_id'], ['MODELO_DISPOSITIVO.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_DISPOSITIVO_id'), 'DISPOSITIVO', ['id'], unique=False)
    op.create_index(op.f('ix_DISPOSITIVO_mac_address'), 'DISPOSITIVO', ['mac_address'], unique=True)
    op.create_table('USUARIO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('nomb_compl', sa.String(length=100), nullable=False),
    sa.Column('correo_elec', sa.String(length=100), nullable=False),
    sa.Column('telefono', sa.String(length=50), nullable=True),
    sa.Column('empresa_id', sa.BigInteger(), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('rol', sa.String(length=50), nullable=True),
    sa.Column('auth_uid', sa.Uuid(as_uuid=False), nullable=True),
    sa.ForeignKeyConstraint(['empresa_id'], ['EMPRESA_CLIENTE.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('auth_uid')
    )
    op.create_index(op.f('ix_USUARIO_id'), 'USUARIO', ['id'], unique=False)
    op.create_table('CUBA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('codigo', sa.String(length=50), nullable=False),
    sa.Column('cap_litros', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('sector_cuba', sa.String(length=50), nullable=True),
    sa.Column('estado_operativo', sa.String(length=50), nullable=False),
    sa.Column('fecha_cuba', sa.DateTime(), nullable=True),
    sa.Column('bodega_id', sa.BigInteger(), nullable=False),
    sa.Column('material_id', sa.BigInteger(), nullable=True),
    sa.CheckConstraint("estado_operativo IN ('disponible', 'en_uso', 'mantencion', 'fuera_servicio')", name='ck_cuba_estado'),
    sa.CheckConstraint('cap_litros IS NULL OR cap_litros > 0', name='ck_cuba_capacidad'),
    sa.ForeignKeyConstraint(['bodega_id'], ['BODEGA.id'], ),
    sa.ForeignKeyConstraint(['material_id'], ['TIPO_MATERIAL_CUBA.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('bodega_id', 'codigo', name='uq_cuba_bodega_codigo')
    )
    op.create_index(op.f('ix_CUBA_codigo'), 'CUBA', ['codigo'], unique=False)
    op.create_index(op.f('ix_CUBA_id'), 'CUBA', ['id'], unique=False)
    op.create_table('PERFIL_FERMENTACION',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('nomb_perfil', sa.String(length=100), nullable=False),
    sa.Column('temp_min', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('temp_max', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('brix_caida_min_dia', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('ph_min', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('ph_max', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('bodega_id', sa.BigInteger(), nullable=False),
    sa.Column('cepa_id', sa.BigInteger(), nullable=False),
    sa.CheckConstraint('ph_min <= ph_max', name='ck_perfil_ph'),
    sa.CheckConstraint('ph_min BETWEEN 0 AND 14 AND ph_max BETWEEN 0 AND 14', name='ck_perfil_ph_rango'),
    sa.CheckConstraint('temp_min <= temp_max', name='ck_perfil_temp'),
    sa.ForeignKeyConstraint(['bodega_id'], ['BODEGA.id'], ),
    sa.ForeignKeyConstraint(['cepa_id'], ['CEPA.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('bodega_id', 'cepa_id', 'nomb_perfil', name='uq_perfil_bodega_cepa_nombre')
    )
    op.create_index(op.f('ix_PERFIL_FERMENTACION_id'), 'PERFIL_FERMENTACION', ['id'], unique=False)
    op.create_table('TELEMETRIA_ESTADO_NODO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('bateria_pct', sa.SmallInteger(), nullable=True),
    sa.Column('bateria_volt', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('rssi_dbm', sa.SmallInteger(), nullable=True),
    sa.Column('estado_red', sa.String(length=50), nullable=True),
    sa.CheckConstraint('bateria_pct BETWEEN 0 AND 100', name='ck_nodo_bateria'),
    sa.CheckConstraint('rssi_dbm <= 0', name='ck_nodo_rssi'),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispositivo_id', 'timestamp', name='uq_estado_nodo_instante')
    )
    op.create_index(op.f('ix_TELEMETRIA_ESTADO_NODO_id'), 'TELEMETRIA_ESTADO_NODO', ['id'], unique=False)
    op.create_index(op.f('ix_TELEMETRIA_ESTADO_NODO_timestamp'), 'TELEMETRIA_ESTADO_NODO', ['timestamp'], unique=False)
    op.create_table('USUARIO_BODEGA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('bodega_id', sa.BigInteger(), nullable=False),
    sa.Column('rol_id', sa.BigInteger(), nullable=False),
    sa.Column('asignado_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['bodega_id'], ['BODEGA.id'], ),
    sa.ForeignKeyConstraint(['rol_id'], ['ROL.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['USUARIO.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'bodega_id', name='uq_usuario_bodega')
    )
    op.create_index(op.f('ix_USUARIO_BODEGA_id'), 'USUARIO_BODEGA', ['id'], unique=False)
    op.create_table('ASIGNACION_DISPOSITIVO',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=False),
    sa.Column('cuba_id', sa.BigInteger(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('asignado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('desasignado_en', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('activo = (desasignado_en IS NULL)', name='ck_asignacion_activo'),
    sa.CheckConstraint('desasignado_en IS NULL OR desasignado_en > asignado_en', name='ck_asignacion_fechas'),
    sa.ForeignKeyConstraint(['cuba_id'], ['CUBA.id'], ),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_dispositivo_activo_unico', 'ASIGNACION_DISPOSITIVO', ['dispositivo_id'], unique=True, postgresql_where=sa.text('activo = true'), sqlite_where=sa.text('activo = 1'))
    op.create_index(op.f('ix_ASIGNACION_DISPOSITIVO_id'), 'ASIGNACION_DISPOSITIVO', ['id'], unique=False)
    op.create_table('PROCESO_FERMENTACION',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('cuba_id', sa.BigInteger(), nullable=False),
    sa.Column('perfil_id', sa.BigInteger(), nullable=True),
    sa.Column('volumen_litros', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('brix_inicial', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('brix_objetivo', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('densidad_inicial_sg', sa.Numeric(precision=6, scale=4), nullable=True),
    sa.Column('estado', sa.String(length=50), nullable=False),
    sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_estimada_fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_real_fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("estado IN ('en_proceso', 'finalizada', 'detenida', 'cancelada')", name='ck_proceso_estado'),
    sa.CheckConstraint('fecha_real_fin IS NULL OR fecha_real_fin > fecha_inicio', name='ck_proceso_fechas'),
    sa.CheckConstraint('volumen_litros IS NULL OR volumen_litros > 0', name='ck_proceso_volumen'),
    sa.ForeignKeyConstraint(['cuba_id'], ['CUBA.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['perfil_id'], ['PERFIL_FERMENTACION.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cuba_proceso_activo_unico', 'PROCESO_FERMENTACION', ['cuba_id'], unique=True, postgresql_where=sa.text("estado IN ('en_proceso', 'detenida')"), sqlite_where=sa.text("estado IN ('en_proceso', 'detenida')"))
    op.create_index(op.f('ix_PROCESO_FERMENTACION_cuba_id'), 'PROCESO_FERMENTACION', ['cuba_id'], unique=False)
    op.create_index(op.f('ix_PROCESO_FERMENTACION_id'), 'PROCESO_FERMENTACION', ['id'], unique=False)
    op.create_table('BITACORA_INTERVENCION',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('fecha_registro', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tipo_intervencion', sa.String(length=50), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('dosis_aplicada', sa.String(length=100), nullable=True),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('fermentacion_id', sa.BigInteger(), nullable=True),
    sa.Column('cuba_id', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['cuba_id'], ['CUBA.id'], ),
    sa.ForeignKeyConstraint(['fermentacion_id'], ['PROCESO_FERMENTACION.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['USUARIO.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_BITACORA_INTERVENCION_fecha_registro'), 'BITACORA_INTERVENCION', ['fecha_registro'], unique=False)
    op.create_index(op.f('ix_BITACORA_INTERVENCION_id'), 'BITACORA_INTERVENCION', ['id'], unique=False)
    op.create_table('EVENTO_ALERTA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=True),
    sa.Column('fermentacion_id', sa.BigInteger(), nullable=True),
    sa.Column('atendida_por', sa.BigInteger(), nullable=True),
    sa.Column('fecha_atencion', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fecha_resolucion', sa.DateTime(timezone=True), nullable=True),
    sa.Column('nota_atencion', sa.Text(), nullable=True),
    sa.Column('nota_resolucion', sa.Text(), nullable=True),
    sa.Column('mensaje', sa.Text(), nullable=True),
    sa.Column('valor_registrado', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('valor_limite', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tipo_alerta', sa.String(length=50), nullable=False),
    sa.Column('severidad', sa.String(length=20), nullable=True),
    sa.Column('estado', sa.String(length=50), nullable=False),
    sa.Column('met_dispar', sa.String(length=50), nullable=True),
    sa.CheckConstraint("estado IN ('pendiente', 'atendida', 'resuelta')", name='ck_alerta_estado'),
    sa.CheckConstraint("severidad IN ('baja', 'media', 'alta', 'critica')", name='ck_alerta_severidad'),
    sa.CheckConstraint('(atendida_por IS NULL) = (fecha_atencion IS NULL)', name='ck_alerta_atencion'),
    sa.ForeignKeyConstraint(['atendida_por'], ['USUARIO.id'], ),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ),
    sa.ForeignKeyConstraint(['fermentacion_id'], ['PROCESO_FERMENTACION.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_EVENTO_ALERTA_fermentacion_id'), 'EVENTO_ALERTA', ['fermentacion_id'], unique=False)
    op.create_index(op.f('ix_EVENTO_ALERTA_id'), 'EVENTO_ALERTA', ['id'], unique=False)
    op.create_index(op.f('ix_EVENTO_ALERTA_timestamp'), 'EVENTO_ALERTA', ['timestamp'], unique=False)
    op.create_table('LECTURA_TELEMETRIA',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('dispositivo_id', sa.BigInteger(), nullable=True),
    sa.Column('fermentacion_id', sa.BigInteger(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('temp_mosto', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('temp_ambiente', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('densidad_sg', sa.Numeric(precision=6, scale=4), nullable=True),
    sa.Column('brix', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('ph', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('origen_dato', sa.String(length=50), nullable=True),
    sa.Column('lectura_valida', sa.Boolean(), nullable=True),
    sa.CheckConstraint('ph BETWEEN 0 AND 14', name='ck_lectura_ph'),
    sa.ForeignKeyConstraint(['dispositivo_id'], ['DISPOSITIVO.id'], ),
    sa.ForeignKeyConstraint(['fermentacion_id'], ['PROCESO_FERMENTACION.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dispositivo_id', 'timestamp', name='uq_lectura_dispositivo_instante')
    )
    op.create_index(op.f('ix_LECTURA_TELEMETRIA_fermentacion_id'), 'LECTURA_TELEMETRIA', ['fermentacion_id'], unique=False)
    op.create_index(op.f('ix_LECTURA_TELEMETRIA_id'), 'LECTURA_TELEMETRIA', ['id'], unique=False)
    op.create_index(op.f('ix_LECTURA_TELEMETRIA_timestamp'), 'LECTURA_TELEMETRIA', ['timestamp'], unique=False)
    op.create_index('ix_lectura_fermentacion_tiempo', 'LECTURA_TELEMETRIA', ['fermentacion_id', 'timestamp'], unique=False)
    op.create_table('UMBRAL_FERMENTACION',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('temp_min', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('temp_max', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('brix_caida_min_dia', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('ph_min', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('ph_max', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('establecido_por', sa.BigInteger(), nullable=False),
    sa.Column('fermentacion_id', sa.BigInteger(), nullable=False),
    sa.CheckConstraint('ph_min <= ph_max', name='ck_umbral_ph'),
    sa.CheckConstraint('ph_min BETWEEN 0 AND 14 AND ph_max BETWEEN 0 AND 14', name='ck_umbral_ph_rango'),
    sa.CheckConstraint('temp_min <= temp_max', name='ck_umbral_temp'),
    sa.ForeignKeyConstraint(['establecido_por'], ['USUARIO.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['fermentacion_id'], ['PROCESO_FERMENTACION.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fermentacion_id', name='uq_umbral_fermentacion')
    )
    op.create_index(op.f('ix_UMBRAL_FERMENTACION_id'), 'UMBRAL_FERMENTACION', ['id'], unique=False)

    op.create_index("uq_usuario_correo", "USUARIO", [sa.text("lower(correo_elec)")], unique=True)


def downgrade():
    op.drop_index("uq_usuario_correo", table_name="USUARIO")
    # Frozen schema operations; reviewed against the audit snapshot.
    op.drop_index(op.f('ix_UMBRAL_FERMENTACION_id'), table_name='UMBRAL_FERMENTACION')
    op.drop_table('UMBRAL_FERMENTACION')
    op.drop_index('ix_lectura_fermentacion_tiempo', table_name='LECTURA_TELEMETRIA')
    op.drop_index(op.f('ix_LECTURA_TELEMETRIA_timestamp'), table_name='LECTURA_TELEMETRIA')
    op.drop_index(op.f('ix_LECTURA_TELEMETRIA_id'), table_name='LECTURA_TELEMETRIA')
    op.drop_index(op.f('ix_LECTURA_TELEMETRIA_fermentacion_id'), table_name='LECTURA_TELEMETRIA')
    op.drop_table('LECTURA_TELEMETRIA')
    op.drop_index(op.f('ix_EVENTO_ALERTA_timestamp'), table_name='EVENTO_ALERTA')
    op.drop_index(op.f('ix_EVENTO_ALERTA_id'), table_name='EVENTO_ALERTA')
    op.drop_index(op.f('ix_EVENTO_ALERTA_fermentacion_id'), table_name='EVENTO_ALERTA')
    op.drop_table('EVENTO_ALERTA')
    op.drop_index(op.f('ix_BITACORA_INTERVENCION_id'), table_name='BITACORA_INTERVENCION')
    op.drop_index(op.f('ix_BITACORA_INTERVENCION_fecha_registro'), table_name='BITACORA_INTERVENCION')
    op.drop_table('BITACORA_INTERVENCION')
    op.drop_index(op.f('ix_PROCESO_FERMENTACION_id'), table_name='PROCESO_FERMENTACION')
    op.drop_index(op.f('ix_PROCESO_FERMENTACION_cuba_id'), table_name='PROCESO_FERMENTACION')
    op.drop_index('idx_cuba_proceso_activo_unico', table_name='PROCESO_FERMENTACION', postgresql_where=sa.text("estado IN ('en_proceso', 'detenida')"), sqlite_where=sa.text("estado IN ('en_proceso', 'detenida')"))
    op.drop_table('PROCESO_FERMENTACION')
    op.drop_index(op.f('ix_ASIGNACION_DISPOSITIVO_id'), table_name='ASIGNACION_DISPOSITIVO')
    op.drop_index('idx_dispositivo_activo_unico', table_name='ASIGNACION_DISPOSITIVO', postgresql_where=sa.text('activo = true'), sqlite_where=sa.text('activo = 1'))
    op.drop_table('ASIGNACION_DISPOSITIVO')
    op.drop_index(op.f('ix_USUARIO_BODEGA_id'), table_name='USUARIO_BODEGA')
    op.drop_table('USUARIO_BODEGA')
    op.drop_index(op.f('ix_TELEMETRIA_ESTADO_NODO_timestamp'), table_name='TELEMETRIA_ESTADO_NODO')
    op.drop_index(op.f('ix_TELEMETRIA_ESTADO_NODO_id'), table_name='TELEMETRIA_ESTADO_NODO')
    op.drop_table('TELEMETRIA_ESTADO_NODO')
    op.drop_index(op.f('ix_PERFIL_FERMENTACION_id'), table_name='PERFIL_FERMENTACION')
    op.drop_table('PERFIL_FERMENTACION')
    op.drop_index(op.f('ix_CUBA_id'), table_name='CUBA')
    op.drop_index(op.f('ix_CUBA_codigo'), table_name='CUBA')
    op.drop_table('CUBA')
    op.drop_index(op.f('ix_USUARIO_id'), table_name='USUARIO')
    op.drop_table('USUARIO')
    op.drop_index(op.f('ix_DISPOSITIVO_mac_address'), table_name='DISPOSITIVO')
    op.drop_index(op.f('ix_DISPOSITIVO_id'), table_name='DISPOSITIVO')
    op.drop_table('DISPOSITIVO')
    op.drop_index(op.f('ix_BODEGA_id'), table_name='BODEGA')
    op.drop_table('BODEGA')
    op.drop_index(op.f('ix_TIPO_MATERIAL_CUBA_id'), table_name='TIPO_MATERIAL_CUBA')
    op.drop_table('TIPO_MATERIAL_CUBA')
    op.drop_index(op.f('ix_ROL_id'), table_name='ROL')
    op.drop_table('ROL')
    op.drop_index(op.f('ix_MODELO_DISPOSITIVO_id'), table_name='MODELO_DISPOSITIVO')
    op.drop_table('MODELO_DISPOSITIVO')
    op.drop_index(op.f('ix_EMPRESA_CLIENTE_id'), table_name='EMPRESA_CLIENTE')
    op.drop_table('EMPRESA_CLIENTE')
    op.drop_index(op.f('ix_CEPA_id'), table_name='CEPA')
    op.drop_table('CEPA')

