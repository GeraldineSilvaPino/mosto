"""
Esquemas Pydantic para validación y serialización de datos de la API.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ==========================================
# ESQUEMAS DE INGESTA IOT (Desde los .ino)
# ==========================================

class TelemetriaESP32In(BaseModel):
    """
    Carga útil esperada desde tempsensmosto.ino (ESP32 con DS18B20 + DHT22 + pH)
    """
    device_mac: str = Field(..., description="Dirección MAC física del ESP32")
    cuba_id: int = Field(..., description="ID numérico de la cuba")
    temp_vino: float = Field(..., description="Temperatura del vino en °C (DS18B20)")
    temp_ambiente: Optional[float] = Field(None, description="Temperatura ambiente en °C (DHT22)")
    humedad_ambiente: Optional[float] = Field(None, description="Humedad ambiente en % (DHT22)")
    voltaje_ph: Optional[float] = Field(None, description="Voltaje analógico PO de sonda pH")


class TelemetriaESP8266In(BaseModel):
    """
    Carga útil esperada desde esp86xyz.ino (ESP8266 con MPU-6050 cápsula flotante)
    """
    device_mac: str = Field(..., description="Dirección MAC física del ESP8266")
    cuba_id: int = Field(..., description="ID numérico de la cuba")
    inclinacion: float = Field(..., description="Ángulo de inclinación en grados (MPU-6050)")
    ax: Optional[float] = Field(None, description="Aceleración en eje X (g)")
    ay: Optional[float] = Field(None, description="Aceleración en eje Y (g)")
    az: Optional[float] = Field(None, description="Aceleración en eje Z (g)")


# ==========================================
# ESQUEMAS DE CONSULTA PARA EL FRONTEND
# ==========================================

class LecturaOut(BaseModel):
    id: int
    cuba_id: int
    timestamp: datetime
    temp_vino: Optional[float] = None
    temp_ambiente: Optional[float] = None
    humedad_ambiente: Optional[float] = None
    voltaje_ph: Optional[float] = None
    inclinacion: Optional[float] = None
    brix_calculado: Optional[float] = None

    class Config:
        from_attributes = True


class CubaOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    variedad: str
    lote: Optional[str] = None
    capacidad_litros: int
    volumen_actual: int
    dia_fermentacion: int
    dias_estimados: int
    estado: str
    # Últimas lecturas resumidas
    ultima_temperatura: Optional[float] = None
    ultimos_brix: Optional[float] = None

    class Config:
        from_attributes = True


class AlertaOut(BaseModel):
    id: int
    cuba_id: int
    sensor_tipo: str
    severidad: str
    titulo: str
    descripcion: str
    valor_detectado: Optional[str] = None
    regla_infringida: Optional[str] = None
    estado: str
    atendido_por: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DispositivoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    mac: str
    modelo: str
    tipo_sensor: str
    cuba_id: Optional[int] = None
    estado: str
    fuente_energia: str
    nivel_bateria: int
    ultima_conexion: datetime

    class Config:
        from_attributes = True

