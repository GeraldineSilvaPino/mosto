"""
Modelos ORM de SQLAlchemy para MOSTO.
Estructura alineada exactamente a las 19 tablas de Supabase (esquema oficial Fase 2).
Equivalente a la capa @Entity en Spring Boot.
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String,
    Float, Numeric, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from .database import Base


# ==========================================
# 1. ENTIDADES MAESTRAS Y ORGANIZACIONALES
# ==========================================

class EmpresaCliente(Base):
    __tablename__ = "EMPRESA_CLIENTE"

    id = Column(BigInteger, primary_key=True, index=True)
    nomb_emp = Column(String(100), unique=True, nullable=False)
    email_emp = Column(String(100), nullable=True)
    direccion_emp = Column(String(200), nullable=True)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    bodegas = relationship("Bodega", back_populates="empresa")


class Bodega(Base):
    __tablename__ = "BODEGA"

    id = Column(BigInteger, primary_key=True, index=True)
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

    id = Column(BigInteger, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)


class Cepa(Base):
    __tablename__ = "CEPA"

    id = Column(BigInteger, primary_key=True, index=True)
    tipo_uva = Column(String(50), nullable=True)           # Tinto / Blanco
    nombre_variedad = Column(String(100), unique=True, nullable=False) # Cabernet, Carménère...


class Cuba(Base):
    __tablename__ = "CUBA"

    id = Column(BigInteger, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True) # Ej: CB-01
    cap_litros = Column(Numeric(10, 2), nullable=True)
    sector_cuba = Column(String(50), nullable=True)
    estado_operativo = Column(String(50), default="disponible")
    fecha_cuba = Column(DateTime, nullable=True)
    bodega_id = Column(BigInteger, ForeignKey("BODEGA.id"), nullable=True)
    material_id = Column(BigInteger, ForeignKey("TIPO_MATERIAL_CUBA.id"), nullable=True)

    bodega = relationship("Bodega", back_populates="cubas")
    procesos = relationship("ProcesoFermentacion", back_populates="cuba")


class PerfilFermentacion(Base):
    __tablename__ = "PERFIL_FERMENTACION"

    id = Column(BigInteger, primary_key=True, index=True)
    nomb_perfil = Column(String(100), nullable=False)
    temp_min = Column(Numeric(5, 2), nullable=True)
    temp_max = Column(Numeric(5, 2), nullable=True)
    brix_caida_min_dia = Column(Numeric(5, 2), nullable=True)
    ph_min = Column(Numeric(4, 2), nullable=True)
    ph_max = Column(Numeric(4, 2), nullable=True)
    activo = Column(Boolean, default=True)
    bodega_id = Column(BigInteger, ForeignKey("BODEGA.id"), nullable=True)
    cepa_id = Column(BigInteger, ForeignKey("CEPA.id"), nullable=True)

    cepa = relationship("Cepa")
    bodega = relationship("Bodega")


class ProcesoFermentacion(Base):
    __tablename__ = "PROCESO_FERMENTACION"

    id = Column(BigInteger, primary_key=True, index=True)
    cuba_id = Column(BigInteger, ForeignKey("CUBA.id"), nullable=False, index=True)
    perfil_id = Column(BigInteger, ForeignKey("PERFIL_FERMENTACION.id"), nullable=True)
    volumen_litros = Column(Numeric(10, 2), nullable=True)
    brix_inicial = Column(Numeric(5, 2), nullable=True)
    brix_objetivo = Column(Numeric(5, 2), nullable=True)
    densidad_inicial_sg = Column(Numeric(6, 4), nullable=True)
    estado = Column(String(50), default="en_proceso") # 'en_proceso', 'finalizada', 'detenida', 'cancelada'
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

    id = Column(BigInteger, primary_key=True, index=True)
    marca = Column(String(100), nullable=True)
    modelo = Column(String(100), nullable=False)
    arquitectura = Column(String(100), nullable=True)
    version_hardware = Column(String(50), nullable=True)


class Dispositivo(Base):
    __tablename__ = "DISPOSITIVO"

    id = Column(BigInteger, primary_key=True, index=True)
    mac_address = Column(String(50), unique=True, nullable=False, index=True)
    tipo_dispositivo = Column(String(50), nullable=True) # Sonda DS18B20 / Flotador MPU-6050
    firmware_version = Column(String(50), nullable=True)
    estado = Column(String(50), default="activo")
    empresa_id = Column(BigInteger, ForeignKey("EMPRESA_CLIENTE.id"), nullable=False)
    modelo_id = Column(BigInteger, ForeignKey("MODELO_DISPOSITIVO.id"), nullable=False)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    modelo = relationship("ModeloDispositivo")
    empresa = relationship("EmpresaCliente")
    asignaciones = relationship("AsignacionDispositivo", back_populates="dispositivo")
    lecturas = relationship("LecturaTelemetria", back_populates="dispositivo")
    estados_nodo = relationship("TelemetriaEstadoNodo", back_populates="dispositivo")


class AsignacionDispositivo(Base):
    __tablename__ = "ASIGNACION_DISPOSITIVO"

    id = Column(BigInteger, primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=False)
    cuba_id = Column(BigInteger, ForeignKey("CUBA.id"), nullable=False)
    activo = Column(Boolean, default=True)
    asignado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    desasignado_en = Column(DateTime(timezone=True), nullable=True)

    dispositivo = relationship("Dispositivo", back_populates="asignaciones")
    cuba = relationship("Cuba")


# ==========================================
# 4. TELEMETRÍA (Lecturas tempsensmosto.ino y esp86xyz.ino)
# ==========================================

class LecturaTelemetria(Base):
    __tablename__ = "LECTURA_TELEMETRIA"

    id = Column(BigInteger, primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

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

    id = Column(BigInteger, primary_key=True, index=True)
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

    id = Column(BigInteger, primary_key=True, index=True)
    dispositivo_id = Column(BigInteger, ForeignKey("DISPOSITIVO.id"), nullable=True)
    fermentacion_id = Column(BigInteger, ForeignKey("PROCESO_FERMENTACION.id"), nullable=True, index=True)
    atendida_por = Column(BigInteger, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    tipo_alerta = Column(String(50), nullable=False)
    severidad = Column(String(20), default="warning")
    met_dispar = Column(String(50), nullable=True)

    fermentacion = relationship("ProcesoFermentacion", back_populates="alertas")


# ==========================================
# 6. USUARIOS Y ROLES (RBAC)
# ==========================================

class Rol(Base):
    __tablename__ = "ROL"

    id = Column(BigInteger, primary_key=True, index=True)
    nomb_rol = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(200), nullable=True)


class Usuario(Base):
    __tablename__ = "USUARIO"

    id = Column(BigInteger, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol_id = Column(BigInteger, ForeignKey("ROL.id"), nullable=False)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
