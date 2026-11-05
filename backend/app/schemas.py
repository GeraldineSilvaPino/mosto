"""
Esquemas Pydantic para validación y serialización de datos de la API MOSTO.
Capa DTO (Data Transfer Objects).
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


# ==========================================
# 1. DTOs DE INGESTA IOT (Microcontroladores)
# Compatible con tempsensmosto.ino y esp86xyz.ino
# ==========================================

class TelemetriaESP32In(BaseModel):
    """
    Carga útil esperada desde tempsensmosto.ino (ESP32 Nodo Cuba)
    Sensores: DS18B20 (vino), DHT22 (ambiente), PH-4502C (pH con divisor 2.0x)
    """
    mac_address: str = Field(..., example="C8:F0:9E:4B:82:10", description="MAC física del ESP32")
    cuba_id: Optional[int] = Field(None, example=1, description="ID de la cuba (opcional si ya está asignado en DB)")
    temperatura_vino: float = Field(..., example=18.45, description="Temperatura del mosto/vino en °C (DS18B20)")
    temperatura_ambiente: Optional[float] = Field(None, example=21.20, description="Temperatura ambiental en °C (DHT22)")
    humedad_ambiente: Optional[float] = Field(None, example=65.0, description="Humedad relativa en % (DHT22)")
    voltaje_ph: Optional[float] = Field(None, example=2.45, description="Voltaje PO de sonda PH-4502C para calibrar")
    ph: Optional[float] = Field(None, example=3.45, description="pH directo si el sensor ya viene calibrado")
    bateria_voltaje: Optional[float] = Field(None, example=3.92, description="Voltaje batería Li-Po (V)")
    rssi: Optional[int] = Field(None, example=-68, description="Intensidad de señal Wi-Fi en dBm")


class TelemetriaESP8266In(BaseModel):
    """
    Carga útil esperada desde esp86xyz.ino (ESP8266 Flotador Hidrómetro)
    Sensor: MPU-6050 (Acelerómetro I2C para inclinación / densidad / °Brix)
    """
    mac_address: str = Field(..., example="5C:CF:7F:12:34:56", description="MAC física del ESP8266")
    cuba_id: Optional[int] = Field(None, example=1, description="ID de la cuba (opcional si ya está asignado)")
    angulo_tilt: Optional[float] = Field(None, example=43.20, description="Ángulo de inclinación en grados respecto a Z")
    ax: Optional[float] = Field(None, example=0.045, description="Aceleración en X (g)")
    ay: Optional[float] = Field(None, example=0.680, description="Aceleración en Y (g)")
    az: Optional[float] = Field(None, example=0.730, description="Aceleración en Z (g)")
    temp_vino: Optional[float] = Field(None, example=18.30, description="Temperatura interna del flotador (°C)")
    brix: Optional[float] = Field(None, example=22.50, description="°Brix directo si el nodo ya lo calculó")
    densidad_sg: Optional[float] = Field(None, example=1.0940, description="Gravedad específica directa (SG)")
    bateria_voltaje: Optional[float] = Field(None, example=3.85, description="Voltaje batería Li-Po (V)")
    rssi: Optional[int] = Field(None, example=-72, description="Intensidad de señal Wi-Fi en dBm")


class TelemetriaProcesadaOut(BaseModel):
    temperatura_vino: Optional[float] = None
    temperatura_ambiente: Optional[float] = None
    humedad_ambiente: Optional[float] = None
    ph: Optional[float] = None
    angulo_tilt: Optional[float] = None
    brix: Optional[float] = None
    densidad_sg: Optional[float] = None
    bateria_pct: Optional[int] = None
    calidad_wifi: Optional[str] = None


class TelemetriaRespuestaOut(BaseModel):
    status: str = Field(..., example="ok")
    mensaje: str = Field(..., example="Telemetría registrada y calibrada con éxito")
    lectura_id: int
    cuba_id: Optional[int] = None
    proceso_id: Optional[int] = None
    timestamp: datetime
    valores_procesados: TelemetriaProcesadaOut


# ==========================================
# 2. DTOs PARA EL FRONTEND (Vistas Vue 3)
# ==========================================

class LecturaOut(BaseModel):
    id: int
    dispositivo_id: Optional[int] = None
    timestamp: datetime
    temp_mosto: Optional[float] = None
    temp_ambiente: Optional[float] = None
    densidad_sg: Optional[float] = None
    brix: Optional[float] = None
    ph: Optional[float] = None
    origen_dato: Optional[str] = "sensor_iot"

    class Config:
        from_attributes = True


class CubaOut(BaseModel):
    id: int
    codigo_cuba: str
    nombre: Optional[str] = None
    capacidad_lts: Optional[float] = None
    ubicacion_en_bodega: Optional[str] = None
    estado_operativo: str
    
    # Proceso de fermentación activo
    proceso_activo_id: Optional[int] = None
    variedad: Optional[str] = None
    lote: Optional[str] = None
    volumen_actual_lts: Optional[float] = None
    dia_fermentacion: Optional[int] = None
    dias_estimados: Optional[int] = 14
    temp_min_perfil: Optional[float] = None
    temp_max_perfil: Optional[float] = None
    
    # Métricas en tiempo real calculadas de la última lectura
    ultima_temperatura: Optional[float] = None
    ultimos_brix: Optional[float] = None
    ultimo_ph: Optional[float] = None
    ultima_lectura_timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


class HistoricoCubaOut(BaseModel):
    cuba_id: int
    nombre_cuba: str
    proceso_id: Optional[int] = None
    rango_horas: int
    total_muestras: int
    timestamps: List[str]
    temperaturas_vino: List[Optional[float]]
    grados_brix: List[Optional[float]]
    valores_ph: List[Optional[float]]
    # Compatibilidad directa con datasets de Chart.js (CubaDetailView.vue)
    labels: List[str] = []
    temp: List[Optional[float]] = []
    brix: List[Optional[float]] = []


# ==========================================
# 3. DTOs PARA GESTIÓN DE ALERTAS
# ==========================================

class AlertaAtenderIn(BaseModel):
    usuario_id: Optional[int] = Field(default=1, description="ID del usuario/operador que atiende la alerta")
    nota: Optional[str] = Field(None, description="Observaciones técnicas iniciales al atender la alerta")


class AlertaResolverIn(BaseModel):
    usuario_id: Optional[int] = Field(default=1, description="ID del operador o enólogo que resuelve la incidencia")
    nota_resolucion: Optional[str] = Field(None, description="Nota técnica o acción correctiva aplicada en terreno")


class AlertasMetricasOut(BaseModel):
    total_alertas: int = Field(..., description="Total histórico de incidencias registradas")
    alertas_activas: int = Field(..., description="Total de alertas actualmente en curso (pendientes + atendidas)")
    alertas_criticas: int = Field(..., description="Alertas críticas activas en curso")
    total_resueltas: int = Field(..., description="Total de alertas resueltas")
    mttr_promedio_minutos: float = Field(..., description="Tiempo medio de resolución en minutos (MTTR)")
    tasa_resolucion_pct: float = Field(..., description="Porcentaje de incidencias resueltas sobre el total")


class AlertaOut(BaseModel):
    id: int
    dispositivo_id: Optional[int] = None
    fermentacion_id: Optional[int] = None
    cuba_id: Optional[int] = None
    cuba_codigo: Optional[str] = None
    cuba_nombre: Optional[str] = None
    variedad: Optional[str] = None
    sensor_tipo: Optional[str] = None
    
    # Datos de la alerta y severidad
    tipo_alerta: str
    severidad: str
    estado: str
    met_dispar: Optional[str] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    
    # Fechas y auditoría (cumplimiento restricción ck_alerta_atencion)
    timestamp: datetime
    atendida_por: Optional[int] = None
    operador_nombre: Optional[str] = None
    fecha_atencion: Optional[datetime] = None
    fecha_resolucion: Optional[datetime] = None
    nota_atencion: Optional[str] = None
    nota_resolucion: Optional[str] = None

    class Config:
        from_attributes = True



# ==========================================
# 4. DTOs PARA CICLO DE VIDA DE PROCESOS
# ==========================================

class ProcesoIniciarIn(BaseModel):
    cuba_id: int
    volumen_litros: float
    perfil_id: Optional[int] = None
    cepa_id: Optional[int] = None
    brix_inicial: Optional[float] = 24.5
    brix_objetivo: Optional[float] = 1.0
    densidad_inicial_sg: Optional[float] = 1.1000
    dias_estimados: Optional[int] = 14


class ProcesoFinalizarIn(BaseModel):
    densidad_final_sg: Optional[float] = None
    brix_final: Optional[float] = None
    motivo: Optional[str] = None


class ProcesoOut(BaseModel):
    id: int
    cuba_id: int
    codigo_cuba: Optional[str] = None
    perfil_id: Optional[int] = None
    perfil_nombre: Optional[str] = None
    cepa_nombre: Optional[str] = None
    volumen_litros: Optional[float] = None
    brix_inicial: Optional[float] = None
    brix_objetivo: Optional[float] = None
    densidad_inicial_sg: Optional[float] = None
    densidad_final_sg: Optional[float] = None
    estado: str
    fecha_inicio: Optional[datetime] = None
    fecha_estimada_fin: Optional[datetime] = None
    fecha_real_fin: Optional[datetime] = None
    dia_fermentacion: Optional[int] = None

    class Config:
        from_attributes = True



# ==========================================
# 5. DTOs PARA DEVICE HUB E INVENTARIO IoT
# ==========================================

class DispositivoVincularIn(BaseModel):
    dispositivo_id: int
    cuba_id: int


class DispositivoDesvincularIn(BaseModel):
    dispositivo_id: int


class DispositivoOut(BaseModel):
    id: int
    code: str
    name: str
    mac: str
    model: str
    sensorType: str
    sensorLabel: str
    assignedCubaId: Optional[int] = None
    assignedCubaCode: Optional[str] = None
    assignedCubaName: Optional[str] = None
    status: str  # online | offline | maintenance
    statusLabel: str
    signalRssi: Optional[int] = None
    signalQuality: Optional[str] = None
    powerSource: Optional[str] = "mains"
    batteryLevel: Optional[int] = 100
    firmware: Optional[str] = "v2.4.1"
    lastTelemetry: Optional[str] = None
    ultima_conexion: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==========================================
# 6. DTOs PARA PERFILES DE FERMENTACIÓN (TASK-BE-06B)
# ==========================================

class PerfilCreateIn(BaseModel):
    """Payload de entrada para creación de un perfil de fermentación."""
    nomb_perfil: str = Field(..., min_length=2, max_length=100, example="Tinto Robusto & Guarda", description="Nombre descriptivo del perfil")
    temp_min: float = Field(..., example=18.0, description="Temperatura mínima óptima en °C")
    temp_max: float = Field(..., example=28.0, description="Temperatura máxima óptima en °C")
    ph_min: Optional[float] = Field(3.20, example=3.20, description="pH mínimo aceptable")
    ph_max: Optional[float] = Field(3.80, example=3.80, description="pH máximo aceptable")
    brix_caida_min_dia: Optional[float] = Field(1.50, example=1.50, description="Caída mínima diaria esperada en °Brix")
    cepa_id: int = Field(..., example=1, description="ID de la cepa vinífera asociada")
    bodega_id: int = Field(..., example=1, description="ID de la bodega")
    activo: Optional[bool] = Field(True, description="Indica si el perfil está habilitado para ser asignado")

    @model_validator(mode="after")
    def validar_rangos(self):
        if self.temp_min is not None and self.temp_max is not None and self.temp_min > self.temp_max:
            raise ValueError("temp_min no puede ser mayor que temp_max (ck_perfil_temp)")
        if self.ph_min is not None and self.ph_max is not None and self.ph_min > self.ph_max:
            raise ValueError("ph_min no puede ser mayor que ph_max (ck_perfil_ph)")
        return self


class PerfilUpdateIn(BaseModel):
    """Payload de entrada para modificación parcial o total de un perfil de fermentación."""
    nomb_perfil: Optional[str] = Field(None, min_length=2, max_length=100, example="Tinto Robusto & Guarda Modificado")
    temp_min: Optional[float] = Field(None, example=19.0, description="Temperatura mínima óptima en °C")
    temp_max: Optional[float] = Field(None, example=27.5, description="Temperatura máxima óptima en °C")
    ph_min: Optional[float] = Field(None, example=3.10, description="pH mínimo aceptable")
    ph_max: Optional[float] = Field(None, example=3.70, description="pH máximo aceptable")
    brix_caida_min_dia: Optional[float] = Field(None, example=1.80, description="Caída diaria esperada de azúcar")
    cepa_id: Optional[int] = Field(None, example=1)
    bodega_id: Optional[int] = Field(None, example=1)
    activo: Optional[bool] = Field(None, example=True)

    @model_validator(mode="after")
    def validar_rangos(self):
        if self.temp_min is not None and self.temp_max is not None and self.temp_min > self.temp_max:
            raise ValueError("temp_min no puede ser mayor que temp_max (ck_perfil_temp)")
        if self.ph_min is not None and self.ph_max is not None and self.ph_min > self.ph_max:
            raise ValueError("ph_min no puede ser mayor que ph_max (ck_perfil_ph)")
        return self


class PerfilOut(BaseModel):
    """DTO de salida para perfiles de fermentación con bandas térmicas y de acidez."""
    id: int
    nomb_perfil: str
    temp_min: float
    temp_max: float
    ph_min: Optional[float] = None
    ph_max: Optional[float] = None
    brix_caida_min_dia: Optional[float] = None
    activo: bool
    bodega_id: Optional[int] = None
    bodega_nombre: Optional[str] = None
    cepa_id: Optional[int] = None
    cepa_nombre: Optional[str] = None
    crit_min: Optional[float] = None
    crit_max: Optional[float] = None

    class Config:
        from_attributes = True


# ==========================================
# 7. DTOs PARA AUTENTICACIÓN Y SEGURIDAD (Módulo 1)
# ==========================================

class LoginIn(BaseModel):
    email: str = Field(..., example="enologo@mosto.cl")
    password: str = Field(..., min_length=4, example="vinacura2024")
    remember_me: Optional[bool] = False


class UserAuthPayload(BaseModel):
    id: int
    name: str
    email: str
    role: str
    winery: str
    avatarInitial: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserAuthPayload


class PasswordResetIn(BaseModel):
    email: str = Field(..., example="enologo@mosto.cl")


# ==========================================
# 8. DTOs PARA GESTIÓN DE USUARIOS Y ROLES (Módulo 5)
# ==========================================

class UsuarioOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    active: bool
    phone: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsuarioCreateIn(BaseModel):
    name: str = Field(..., min_length=2, example="Andrea Muñoz")
    email: str = Field(..., example="andrea.munoz@vinamosto.cl")
    role: str = Field(..., example="operador") # admin | enologo | operador | operario
    password: Optional[str] = Field("mosto2026", example="mosto2026")
    phone: Optional[str] = Field("+56912345678", example="+56912345678")
    bodega_id: Optional[int] = Field(None, example=5)


class UsuarioUpdateRolIn(BaseModel):
    role: str = Field(..., example="enologo")


class UsuarioUpdateEstadoIn(BaseModel):
    active: bool


# ==========================================
# 9. DTOs PARA CONFIGURACIÓN DE EMPRESA Y SAAS (Módulo 5)
# ==========================================

class SaasQuotaDTO(BaseModel):
    planName: str
    billingCycle: str
    status: str
    usedCubas: int
    maxCubas: int
    usedUsers: int
    maxUsers: int


class EmpresaOut(BaseModel):
    brandName: str
    facility: str
    valley: str
    logoUrl: Optional[str] = ""
    taxId: str
    legalName: str
    taxCategory: str
    address: str
    region: str
    contactEmail: str
    contactPhone: str
    dailyEnologyReport: bool
    smsCriticalAlerts: bool
    saasQuota: SaasQuotaDTO


class EmpresaUpdateIn(BaseModel):
    brandName: Optional[str] = None
    facility: Optional[str] = None
    valley: Optional[str] = None
    logoUrl: Optional[str] = None
    taxId: Optional[str] = None
    legalName: Optional[str] = None
    taxCategory: Optional[str] = None
    address: Optional[str] = None
    region: Optional[str] = None
    contactEmail: Optional[str] = None
    contactPhone: Optional[str] = None
    dailyEnologyReport: Optional[bool] = None
    smsCriticalAlerts: Optional[bool] = None


class AmpliacionCuotaIn(BaseModel):
    extra_cubas: int = Field(..., ge=1, le=100, example=6)


# ==========================================
# 10. DTOs PARA BITÁCORA ENOLÓGICA (Módulo 4)
# ==========================================

class BitacoraCreateIn(BaseModel):
    type: str = Field(..., example="nota") # nota | alerta | config | lectura
    cuba: Optional[str] = Field("general", example="cuba-01")
    message: str = Field(..., min_length=2, example="Remontaje realizado.")
    author: Optional[str] = Field("Sistema", example="María González")
    dosis: Optional[str] = Field(None, example="35 mg/L")


class BitacoraOut(BaseModel):
    id: int
    type: str
    timestamp: datetime
    cuba: str
    message: str
    author: str
    dosis: Optional[str] = None

    class Config:
        from_attributes = True


# ==========================================
# 11. DTOs PARA REGISTRO DE DISPOSITIVOS IOT (Módulo 4)
# ==========================================

class DispositivoCreateIn(BaseModel):
    code: str = Field(..., example="ESP32-CB05-TEMP")
    name: str = Field(..., example="Nodo Térmico Cuba 05")
    mac: str = Field(..., example="24:6F:28:AB:CD:EF")
    model: Optional[str] = Field("ESP32-WROOM-32D", example="ESP32-WROOM-32D")
    sensorType: str = Field(..., example="DS18B20") # DS18B20 | MPU-6050 | PH-4502C | DUAL
    cubaId: Optional[Any] = Field(None, example=1)
    powerSource: Optional[str] = Field("mains", example="mains")
    samplingInterval: Optional[str] = Field("1 min", example="1 min")
    notes: Optional[str] = Field(None, example="Instalado en vendimia 2026.")


# ==========================================
# 12. DTOs DE CATÁLOGOS MAESTROS
# ==========================================

class CepaOut(BaseModel):
    id: int
    name: str
    tipo_uva: Optional[str] = None

    class Config:
        from_attributes = True


class TipoMaterialCubaOut(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True
