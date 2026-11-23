"""
Modelos ORM de SQLAlchemy para MOSTO.
Baseline local de 18 tablas. Diferencias con Supabase documentadas en
docs/MIGRACIONES_Y_POSTGRESQL.md; no implica equivalencia con la base remota.
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String,
    Float, Numeric, Boolean, DateTime, ForeignKey, Text,
    CheckConstraint, UniqueConstraint, Index, func, text, Uuid, JSON
)
from sqlalchemy.orm import relationship
from .db_base import Base


# ==========================================
# 1. ENTIDADES MAESTRAS Y ORGANIZACIONALES
# ==========================================

class EmpresaCliente(Base):
    __tablename__ = "EMPRESA_CLIENTE"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    nomb_emp = Column(String(150), unique=True, nullable=False)
    email_emp = Column(String(120), nullable=True)
    direccion_emp = Column(String(200), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Configuración extendida SaaS y fiscal
    rut = Column(String(50), nullable=True)
    razon_social = Column(String(150), nullable=True)
    giro = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    logo_url = Column(Text, nullable=True)
    reporte_diario = Column(Boolean, default=True)
    alertas_sms = Column(Boolean, default=True)
    max_cubas = Column(Integer, default=24)
    max_usuarios = Column(Integer, default=15)
    plan_nombre = Column(String(100), default="Plan Bodega Industrial")
    ciclo_facturacion = Column(String(100), default="Anual (Renovación: Nov 2027)")

    bodegas = relationship("Bodega", back_populates="empresa")


class Bodega(Base):
    __tablename__ = "BODEGA"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nombre", name="uq_bodega_empresa_nombre"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    direccion = Column(String(200), nullable=True)
    empresa_id = Column(BigInteger, ForeignKey("EMPRESA_CLIENTE.id"), nullable=False)
    valle_vitivinicola = Column(String(100), nullable=True)
    comuna = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    empresa = relationship("EmpresaCliente", back_populates="bodegas")
    cubas = relationship("Cuba", back_populates="bodega")


# ==========================================
# 2. CUBAS, MATERIALES Y CEPAS
# ==========================================

class TipoMaterialCuba(Base):
    __tablename__ = "TIPO_MATERIAL_CUBA"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)


class Cepa(Base):
    __tablename__ = "CEPA"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    tipo_uva = Column(String(50), nullable=True)           # Tinto / Blanco
    nombre_variedad = Column(String(100), unique=True, nullable=False) # Cabernet Sauvignon, Carménère...


class Cuba(Base):
    __tablename__ = "CUBA"
    __table_args__ = (
        UniqueConstraint("bodega_id", "codigo", name="uq_cuba_bodega_codigo"),
        CheckConstraint("cap_litros IS NULL OR cap_litros > 0", name="ck_cuba_capacidad"),
        CheckConstraint("estado_operativo IN ('disponible', 'en_uso', 'mantencion', 'fuera_servicio')", name="ck_cuba_estado"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    codigo = Column(String(50), nullable=False, index=True) # Único dentro de cada bodega
    cap_litros = Column(Numeric(10, 2), nullable=True)
    sector_cuba = Column(String(50), nullable=True)
    estado_operativo = Column(String(50), default="disponible", nullable=False)
    fecha_cuba = Column(DateTime, nullable=True)
    bodega_id = Column(BigInteger, ForeignKey("BODEGA.id"), nullable=False)
    material_id = Column(BigInteger, ForeignKey("TIPO_MATERIAL_CUBA.id"), nullable=True)

    bodega = relationship("Bodega", back_populates="cubas")
    material = relationship("TipoMaterialCuba")
    procesos = relationship("ProcesoFermentacion", back_populates="cuba")


class PerfilFermentacion(Base):
    __tablename__ = "PERFIL_FERMENTACION"
    __table_args__ = (
        UniqueConstraint("bodega_id", "cepa_id", "nomb_perfil", name="uq_perfil_bodega_cepa_nombre"),
        CheckConstraint("temp_min <= temp_max", name="ck_perfil_temp"),
        CheckConstraint("ph_min <= ph_max", name="ck_perfil_ph"),
        CheckConstraint("ph_min BETWEEN 0 AND 14 AND ph_max BETWEEN 0 AND 14", name="ck_perfil_ph_rango"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    nomb_perfil = Column(String(100), nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    temp_min = Column(Numeric(5, 2), nullable=True)
    temp_max = Column(Numeric(5, 2), nullable=True)
    brix_caida_min_dia = Column(Numeric(5, 2), nullable=True)
    ph_min = Column(Numeric(4, 2), nullable=True)
    ph_max = Column(Numeric(4, 2), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    bodega_id = Column(BigInteger, ForeignKey("BODEGA.id"), nullable=False)
    cepa_id = Column(BigInteger, ForeignKey("CEPA.id"), nullable=False)

    cepa = relationship("Cepa")
    bodega = relationship("Bodega")


class VersionPerfil(Base):
    __tablename__ = "VERSION_PERFIL"
    __table_args__ = (UniqueConstraint("perfil_id", "revision", name="uq_version_perfil"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    perfil_id = Column(BigInteger, ForeignKey("PERFIL_FERMENTACION.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    configuracion = Column(JSON, nullable=False)
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=True)
    origen = Column(String(40), nullable=False)


class ProcesoFermentacion(Base):
    __tablename__ = "PROCESO_FERMENTACION"
    __table_args__ = (
        CheckConstraint("estado IN ('en_proceso', 'finalizada', 'detenida', 'cancelada')", name="ck_proceso_estado"),
        CheckConstraint("fecha_real_fin IS NULL OR fecha_real_fin > fecha_inicio", name="ck_proceso_fechas"),
        CheckConstraint("volumen_litros IS NULL OR volumen_litros > 0", name="ck_proceso_volumen"),
        Index("idx_cuba_proceso_activo_unico", "cuba_id", unique=True, postgresql_where=text("estado IN ('en_proceso', 'detenida')"), sqlite_where=text("estado IN ('en_proceso', 'detenida')")),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    cuba_id = Column(BigInteger, ForeignKey("CUBA.id", ondelete="RESTRICT"), nullable=False, index=True)
    perfil_id = Column(BigInteger, ForeignKey("PERFIL_FERMENTACION.id"), nullable=True)
    perfil_snapshot = Column(JSON, nullable=True)
    volumen_litros = Column(Numeric(10, 2), nullable=True)
    brix_inicial = Column(Numeric(5, 2), nullable=True)
    brix_objetivo = Column(Numeric(5, 2), nullable=True)
    densidad_inicial_sg = Column(Numeric(6, 4), nullable=True)
    estado = Column(String(50), default="en_proceso", nullable=False) # 'en_proceso', 'finalizada', 'detenida', 'cancelada'
    fecha_inicio = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_estimada_fin = Column(DateTime(timezone=True), nullable=True)
    fecha_real_fin = Column(DateTime(timezone=True), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    cuba = relationship("Cuba", back_populates="procesos")
    perfil = relationship("PerfilFermentacion")
    lecturas = relationship("LecturaTelemetria", back_populates="fermentacion")
    alertas = relationship("EventoAlerta", back_populates="fermentacion")


# ==========================================
# 3. HARDWARE IOT Y MODELOS
# ==========================================

class ModeloDispositivo(Base):
    __tablename__ = "MODELO_DISPOSITIVO"
    __table_args__ = (
        UniqueConstraint("marca", "modelo", "version_hardware", name="uq_modelo_dispositivo"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    marca = Column(String(100), nullable=True)
    modelo = Column(String(100), nullable=False)
    arquitectura = Column(String(100), nullable=True)
    version_hardware = Column(String(50), nullable=True)


class Dispositivo(Base):
    __tablename__ = "DISPOSITIVO"
    __table_args__ = (
        CheckConstraint("estado IN ('activo', 'inactivo', 'mantencion')", name="ck_dispositivo_estado"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    mac_address = Column(String(50), unique=True, nullable=False, index=True)
    tipo_dispositivo = Column(String(50), nullable=True) # Sonda DS18B20 / Flotador MPU-6050
    firmware_version = Column(String(50), nullable=True)
    estado = Column(String(50), default="activo", nullable=False)
    empresa_id = Column(BigInteger, ForeignKey("EMPRESA_CLIENTE.id"), nullable=False)
    modelo_id = Column(BigInteger, ForeignKey("MODELO_DISPOSITIVO.id"), nullable=False)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    origen = Column(String(16), nullable=True)  # Set explicitly once: fisico / simulado.
    ultima_recepcion = Column(DateTime(timezone=True), nullable=True)

    modelo = relationship("ModeloDispositivo")
    empresa = relationship("EmpresaCliente")
    asignaciones = relationship("AsignacionDispositivo", back_populates="dispositivo")
    lecturas = relationship("LecturaTelemetria", back_populates="dispositivo")
    estados_nodo = relationship("TelemetriaEstadoNodo", back_populates="dispositivo")


class AsignacionDispositivo(Base):
    __tablename__ = "ASIGNACION_DISPOSITIVO"
    __table_args__ = (
        CheckConstraint("activo = (desasignado_en IS NULL)", name="ck_asignacion_activo"),
        CheckConstraint("desasignado_en IS NULL OR desasignado_en > asignado_en", name="ck_asignacion_fechas"),
        Index("idx_dispositivo_activo_unico", "dispositivo_id", unique=True, postgresql_where=text("activo = true"), sqlite_where=text("activo = 1")),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=False)
    cuba_id = Column(BigInteger, ForeignKey("CUBA.id"), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    asignado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    desasignado_en = Column(DateTime(timezone=True), nullable=True)

    dispositivo = relationship("Dispositivo", back_populates="asignaciones")
    cuba = relationship("Cuba")


# ==========================================
# 4. TELEMETRÍA (Lecturas tempsensmosto.ino y esp86xyz.ino)
# ==========================================

class LecturaTelemetria(Base):
    __tablename__ = "LECTURA_TELEMETRIA"
    __table_args__ = (
        UniqueConstraint("dispositivo_id", "timestamp", name="uq_lectura_dispositivo_instante"),
        CheckConstraint("ph BETWEEN 0 AND 14", name="ck_lectura_ph"),
        Index("ix_lectura_fermentacion_tiempo", "fermentacion_id", "timestamp"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id", ondelete="RESTRICT"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    reloj_calibracion_id = Column(BigInteger, ForeignKey("CALIBRACION_DISPOSITIVO.id"), nullable=True)

    temp_mosto = Column(Numeric(5, 2), nullable=True)      # DS18B20 (tempsensmosto.ino)
    temp_ambiente = Column(Numeric(5, 2), nullable=True)   # DHT22 (tempsensmosto.ino)
    densidad_sg = Column(Numeric(6, 4), nullable=True)     # Calculado
    brix = Column(Numeric(5, 2), nullable=True)            # MPU-6050 (esp86xyz.ino)
    ph = Column(Numeric(4, 2), nullable=True)              # PH-4502C (tempsensmosto.ino)
    origen_dato = Column(String(50), default="sensor_iot") # sensor_iot / manual
    lectura_valida = Column(Boolean, default=True)

    dispositivo = relationship("Dispositivo", back_populates="lecturas")
    fermentacion = relationship("ProcesoFermentacion", back_populates="lecturas")


class TelemetriaEstadoNodo(Base):
    __tablename__ = "TELEMETRIA_ESTADO_NODO"
    __table_args__ = (
        UniqueConstraint("dispositivo_id", "timestamp", name="uq_estado_nodo_instante"),
        CheckConstraint("bateria_pct BETWEEN 0 AND 100", name="ck_nodo_bateria"),
        CheckConstraint("rssi_dbm <= 0", name="ck_nodo_rssi"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    bateria_pct = Column(SmallInteger, nullable=True)      # % batería Li-Po
    bateria_volt = Column(Numeric(4, 2), nullable=True)
    rssi_dbm = Column(SmallInteger, nullable=True)          # Señal Wi-Fi (dBm)
    estado_red = Column(String(50), default="conectado")

    dispositivo = relationship("Dispositivo", back_populates="estados_nodo")


# ==========================================
# 5. ALERTAS E INCIDENCIAS
# ==========================================

class EventoAlerta(Base):
    __tablename__ = "EVENTO_ALERTA"
    __table_args__ = (
        CheckConstraint("(atendida_por IS NULL) = (fecha_atencion IS NULL)", name="ck_alerta_atencion"),
        CheckConstraint("estado IN ('pendiente', 'atendida', 'resuelta')", name="ck_alerta_estado"),
        CheckConstraint("severidad IN ('baja', 'media', 'alta', 'critica')", name="ck_alerta_severidad"),
        Index("uq_episodio_condicion_abierta", "fermentacion_id", "tipo_alerta", unique=True,
              postgresql_where=text("version_regla IS NOT NULL AND fin_condicion IS NULL"),
              sqlite_where=text("version_regla IS NOT NULL AND fin_condicion IS NULL")),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id", ondelete="RESTRICT"), nullable=True, index=True)
    atendida_por = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=True)
    fecha_atencion = Column(DateTime(timezone=True), nullable=True)
    fecha_resolucion = Column(DateTime(timezone=True), nullable=True)
    nota_atencion = Column(Text, nullable=True)
    nota_resolucion = Column(Text, nullable=True)
    mensaje = Column(Text, nullable=True)
    valor_registrado = Column(Numeric(6, 2), nullable=True)
    valor_limite = Column(Numeric(6, 2), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    tipo_alerta = Column(String(50), nullable=False)
    severidad = Column(String(20), default="media")
    estado = Column(String(50), default="pendiente", nullable=False)
    met_dispar = Column(String(50), nullable=True)
    resuelta_por = Column(BigInteger, ForeignKey("USUARIO.id", name="fk_alerta_resuelta_por"), nullable=True)
    version_regla = Column(String(40), nullable=True)
    origen = Column(String(16), nullable=True)
    inicio_condicion = Column(DateTime(timezone=True), nullable=True)
    fin_condicion = Column(DateTime(timezone=True), nullable=True)
    ultima_observacion = Column(DateTime(timezone=True), nullable=True)
    estado_condicion = Column(String(32), nullable=True)
    evidencia = Column(JSON, nullable=True)

    fermentacion = relationship("ProcesoFermentacion", back_populates="alertas")
    dispositivo = relationship("Dispositivo")


# ==========================================
# 6. BITÁCORA ENOLÓGICA E INTERVENCIONES
# ==========================================

class BitacoraIntervencion(Base):
    __tablename__ = "BITACORA_INTERVENCION"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    fecha_registro = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    tipo_intervencion = Column(String(50), nullable=False) # 'nota', 'alerta', 'config', 'lectura'
    descripcion = Column(Text, nullable=False)
    dosis_aplicada = Column(String(100), nullable=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id", ondelete="RESTRICT"), nullable=True)
    cuba_id = Column(BigInteger, ForeignKey("CUBA.id"), nullable=True)
    alerta_id = Column(BigInteger, ForeignKey("EVENTO_ALERTA.id", name="fk_bitacora_alerta"), nullable=True)

    usuario = relationship("Usuario")
    fermentacion = relationship("ProcesoFermentacion")
    cuba = relationship("Cuba")


# ==========================================
# 7. USUARIOS Y ROLES (RBAC)
# ==========================================

class IntervencionOperativa(Base):
    __tablename__ = "INTERVENCION_OPERATIVA"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=False)
    alerta_id = Column(BigInteger, ForeignKey("EVENTO_ALERTA.id"))
    responsable_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    tipo = Column(String(40), nullable=False)
    accion = Column(Text, nullable=False)
    motivo = Column(Text, nullable=False)
    estado = Column(String(30), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    request_id = Column(String(36), nullable=False)
    solicitud = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("fermentacion_id", "request_id", name="uq_intervencion_solicitud"),)
    __mapper_args__ = {"version_id_col": revision}


class EventoIntervencion(Base):
    __tablename__ = "EVENTO_INTERVENCION"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    intervencion_id = Column(BigInteger, ForeignKey("INTERVENCION_OPERATIVA.id"), nullable=False)
    bitacora_id = Column(BigInteger, ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    estado = Column(String(30), nullable=False)
    descripcion = Column(Text, nullable=False)
    respuesta = Column(String(30))
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    request_id = Column(String(36), nullable=False)
    solicitud = Column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("intervencion_id", "request_id", name="uq_evento_intervencion_solicitud"),
        UniqueConstraint("intervencion_id", "revision", name="uq_evento_intervencion_revision"),
    )


class AjustePerfilProceso(Base):
    __tablename__ = "AJUSTE_PERFIL_PROCESO"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    bitacora_id = Column(BigInteger, ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True)
    vigente_desde = Column(DateTime(timezone=True), nullable=False)
    accion = Column(String(20), nullable=False)
    motivo = Column(Text, nullable=False)
    configuracion = Column(JSON, nullable=False)
    request_id = Column(String(36), nullable=False)
    solicitud = Column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("fermentacion_id", "revision", name="uq_ajuste_perfil_revision"),
        UniqueConstraint("fermentacion_id", "request_id", name="uq_ajuste_perfil_solicitud"),
    )


class MedicionManual(Base):
    __tablename__ = "MEDICION_MANUAL"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=False)
    alerta_id = Column(BigInteger, ForeignKey("EVENTO_ALERTA.id"))
    intervencion_id = Column(BigInteger, ForeignKey("INTERVENCION_OPERATIVA.id"))
    bitacora_id = Column(BigInteger, ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    variable = Column(String(40), nullable=False)
    valor = Column(Float, nullable=False)
    unidad = Column(String(20), nullable=False)
    metodo = Column(String(40), nullable=False)
    instrumento = Column(String(200), nullable=False)
    evidencia = Column(Text, nullable=False)
    observado_en = Column(DateTime(timezone=True), nullable=False)
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    request_id = Column(String(36), nullable=False)
    solicitud = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("fermentacion_id", "request_id", name="uq_medicion_manual_solicitud"),)


class AnulacionMedicion(Base):
    __tablename__ = "ANULACION_MEDICION"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    medicion_id = Column(BigInteger, ForeignKey("MEDICION_MANUAL.id"), nullable=False, unique=True)
    bitacora_id = Column(BigInteger, ForeignKey("BITACORA_INTERVENCION.id"), nullable=False, unique=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    motivo = Column(Text, nullable=False)
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    request_id = Column(String(36), nullable=False)
    solicitud = Column(JSON, nullable=False)


class Rol(Base):
    __tablename__ = "ROL"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False) # admin, enologo, operador
    descripcion = Column(String(200), nullable=True)


class Usuario(Base):
    __tablename__ = "USUARIO"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    nomb_compl = Column(String(100), nullable=False)
    correo_elec = Column(String(100), nullable=False)
    telefono = Column(String(50), nullable=True)
    empresa_id = Column(BigInteger, ForeignKey("EMPRESA_CLIENTE.id"), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    password_hash = Column(String(255), nullable=True)
    rol = Column(String(50), default="operador")
    auth_uid = Column(Uuid(as_uuid=False), unique=True, nullable=True)

    empresa = relationship("EmpresaCliente")
    bodega_asignaciones = relationship("UsuarioBodega", back_populates="usuario")

    @property
    def nombre(self):
        return self.nomb_compl

    @property
    def email(self):
        return self.correo_elec


class UsuarioBodega(Base):
    __tablename__ = "USUARIO_BODEGA"
    __table_args__ = (
        UniqueConstraint("usuario_id", "bodega_id", name="uq_usuario_bodega"),
    )


    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=False)
    bodega_id = Column(BigInteger, ForeignKey("BODEGA.id"), nullable=False)
    rol_id = Column(BigInteger, ForeignKey("ROL.id"), nullable=False)
    asignado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="bodega_asignaciones")
    bodega = relationship("Bodega")
    rol = relationship("Rol")


class UmbralFermentacion(Base):
    """Per-process thresholds retained from the audited schema; not exposed yet."""
    __tablename__ = "UMBRAL_FERMENTACION"
    __table_args__ = (
        UniqueConstraint("fermentacion_id", name="uq_umbral_fermentacion"),
        CheckConstraint("temp_min <= temp_max", name="ck_umbral_temp"),
        CheckConstraint("ph_min <= ph_max", name="ck_umbral_ph"),
        CheckConstraint("ph_min BETWEEN 0 AND 14 AND ph_max BETWEEN 0 AND 14", name="ck_umbral_ph_rango"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    temp_min = Column(Numeric(5, 2), nullable=True)
    temp_max = Column(Numeric(5, 2), nullable=True)
    brix_caida_min_dia = Column(Numeric(5, 2), nullable=True)
    ph_min = Column(Numeric(4, 2), nullable=True)
    ph_max = Column(Numeric(4, 2), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    establecido_por = Column(BigInteger, ForeignKey("USUARIO.id", ondelete="RESTRICT"), nullable=False)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id", ondelete="RESTRICT"), nullable=False)


Index("uq_usuario_correo", func.lower(Usuario.correo_elec), unique=True)


class CredencialDispositivo(Base):
    __tablename__ = "CREDENCIAL_DISPOSITIVO"
    id = Column(Uuid(as_uuid=False), primary_key=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id", ondelete="RESTRICT"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    etiqueta = Column(String(80), nullable=False)
    creada_en = Column(DateTime(timezone=True), nullable=False)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    revocada_en = Column(DateTime(timezone=True), nullable=True)
    creada_por = Column(BigInteger, ForeignKey("USUARIO.id", ondelete="RESTRICT"), nullable=False)


class RelojProceso(Base):
    __tablename__ = "RELOJ_PROCESO"
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"),
                             primary_key=True, autoincrement=False)
    clave = Column(Text, nullable=False)


class CalibracionDispositivo(Base):
    __tablename__ = "CALIBRACION_DISPOSITIVO"
    __table_args__ = (UniqueConstraint("dispositivo_id", "version", name="uq_calibracion_dispositivo_version"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id", ondelete="RESTRICT"), nullable=False)
    version = Column(String(80), nullable=False)
    metodo = Column(String(32), nullable=False)
    parametros = Column(JSON, nullable=False)
    valida_desde = Column(DateTime(timezone=True), nullable=False)
    valida_hasta = Column(DateTime(timezone=True), nullable=True)
    revocada_en = Column(DateTime(timezone=True), nullable=True)
    creada_en = Column(DateTime(timezone=True), nullable=False)
    creada_por = Column(BigInteger, ForeignKey("USUARIO.id", ondelete="RESTRICT"), nullable=False)


class MensajeTelemetria(Base):
    __tablename__ = "MENSAJE_TELEMETRIA"
    __table_args__ = (
        UniqueConstraint("dispositivo_id", "boot_id", "secuencia", name="uq_mensaje_dispositivo_boot_secuencia"),
        CheckConstraint("secuencia >= 0", name="ck_mensaje_secuencia"),
        CheckConstraint("origen IN ('fisico', 'simulado')", name="ck_mensaje_origen"),
        Index("ix_mensaje_proceso_observado", "fermentacion_id", "observado_en"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id", ondelete="RESTRICT"), nullable=False)
    credencial_id = Column(Uuid(as_uuid=False), ForeignKey("CREDENCIAL_DISPOSITIVO.id", ondelete="RESTRICT"), nullable=False)
    boot_id = Column(Uuid(as_uuid=False), nullable=False)
    secuencia = Column(BigInteger, nullable=False)
    observado_en = Column(DateTime(timezone=True), nullable=False)
    recibido_en = Column(DateTime(timezone=True), nullable=False)
    origen = Column(String(16), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    asignacion_id = Column(BigInteger, ForeignKey("ASIGNACION_DISPOSITIVO.id", ondelete="RESTRICT"), nullable=False)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id", ondelete="RESTRICT"), nullable=False)
    calibracion_id = Column(BigInteger, ForeignKey("CALIBRACION_DISPOSITIVO.id", ondelete="RESTRICT"), nullable=True)
    lectura_id = Column(BigInteger, ForeignKey("LECTURA_TELEMETRIA.id", ondelete="RESTRICT"), nullable=False, unique=True)
    calidad_temperatura = Column(String(20), nullable=False)
    calidad_brix = Column(String(20), nullable=False)
    temperatura = Column(Float, nullable=True)
    brix = Column(Float, nullable=True)
    diagnosticos = Column(JSON, nullable=False)
    fuera_de_orden = Column(Boolean, nullable=False)
    retrasado = Column(Boolean, nullable=False)


class EstadoRegla(Base):
    __tablename__ = "ESTADO_REGLA"
    __table_args__ = (UniqueConstraint("fermentacion_id", "codigo", name="uq_estado_regla_proceso_codigo"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    configuracion = Column(JSON, nullable=False)
    perfil_ajuste_revision = Column(Integer, nullable=False, default=0, server_default='0')
    ultima_observacion = Column(DateTime(timezone=True), nullable=False)
    inicio_candidato = Column(DateTime(timezone=True), nullable=True)
    inicio_recuperacion = Column(DateTime(timezone=True), nullable=True)
    episodio_id = Column(BigInteger, ForeignKey("EVENTO_ALERTA.id"), nullable=True)


class AuditoriaAlerta(Base):
    __tablename__ = "AUDITORIA_ALERTA"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    alerta_id = Column(BigInteger, ForeignKey("EVENTO_ALERTA.id"), nullable=False, index=True)
    accion = Column(String(40), nullable=False)
    registrado_en = Column(DateTime(timezone=True), nullable=False)
    observado_en = Column(DateTime(timezone=True), nullable=True)
    usuario_id = Column(BigInteger, ForeignKey("USUARIO.id"), nullable=True)
    mensaje_id = Column(BigInteger, ForeignKey("MENSAJE_TELEMETRIA.id"), nullable=True)
    detalle = Column(JSON, nullable=False)
