"""
Esquemas Pydantic para validación y serialización de datos de la API MOSTO.
Capa DTO (Data Transfer Objects).
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


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

class AlertaOut(BaseModel):
    id: int
    dispositivo_id: Optional[int] = None
    fermentacion_id: Optional[int] = None
    timestamp: datetime
    tipo_alerta: str
    severidad: str
    met_dispar: Optional[str] = None

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
