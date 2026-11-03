"""
Router de Ingesta de Telemetría IoT (Controlador FastAPI).
Equivalente a @RestController en Spring Boot.

Expone los endpoints HTTP consumidos por los microcontroladores:
- ESP32: Sonda DS18B20 + DHT22 + PH-4502C (tempsensmosto.ino)
- ESP8266: Inclinómetro MPU-6050 para densidad / °Brix (esp86xyz.ino)

Delega toda la lógica de negocio al servicio: app.services.telemetry_service
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    TelemetriaESP32In,
    TelemetriaESP8266In,
    TelemetriaRespuestaOut
)
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/api/telemetria", tags=["Telemetría IoT (Hardware)"])


@router.post(
    "/nodo-cuba",
    response_model=TelemetriaRespuestaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingesta de telemetría desde ESP32 (tempsensmosto.ino)",
    description=(
        "Recibe temperatura de vino (DS18B20), temperatura y humedad ambiental (DHT22), "
        "voltaje de la sonda pH (PH-4502C) y estado de batería/Wi-Fi. "
        "Aplica calibración física automática del pH y persiste en Supabase."
    )
)
def recibir_telemetria_esp32(
    payload: TelemetriaESP32In,
    db: Session = Depends(get_db)
):
    """
    Equivalente a un método POST en un @RestController de Spring Boot.
    """
    return telemetry_service.procesar_telemetria_esp32(db=db, payload=payload)


@router.post(
    "/flotador",
    response_model=TelemetriaRespuestaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingesta de telemetría desde ESP8266 (esp86xyz.ino)",
    description=(
        "Recibe ángulo de inclinación de acelerómetro MPU-6050 o componentes raw (ax, ay, az). "
        "Aplica la curva de flotación para calcular densidad (SG) y grados Brix enológicos."
    )
)
def recibir_telemetria_esp8266(
    payload: TelemetriaESP8266In,
    db: Session = Depends(get_db)
):
    """
    Equivalente a un método POST en un @RestController de Spring Boot.
    """
    return telemetry_service.procesar_telemetria_esp8266(db=db, payload=payload)
