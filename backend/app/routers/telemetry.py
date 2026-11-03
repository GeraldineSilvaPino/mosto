"""
Router de Ingesta de Telemetría IoT.
Recibe datos vía HTTP POST desde los microcontroladores programados por el equipo:
- ESP32: Sonda DS18B20 + DHT22 + pH (tempsensmosto.ino)
- ESP8266: Inclinómetro MPU-6050 para grados Brix (esp86xyz.ino)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/telemetria", tags=["Telemetría IoT"])


def convertir_inclinacion_a_brix(inclinacion_grados: float) -> float:
    """
    Fórmula de calibración del densímetro flotante (Tilt Hydrometer):
    A mayor densidad/azúcar, el flotador flota más vertical (menor ángulo).
    A menor densidad/azúcar (fermentación avanzada), el flotador se acuesta (mayor ángulo).
    Calibración lineal base: 10° ~ 25°Bx hasta 70° ~ 0°Bx.
    """
    # Mapeo lineal simple: Brix = 25 - ((inclinacion - 10) * (25 / 60))
    brix = 25.0 - ((inclinacion_grados - 10.0) * (25.0 / 60.0))
    return round(max(0.0, min(32.0, brix)), 2)


@router.post("/nodo-cuba", status_code=status.HTTP_201_CREATED)
def recibir_telemetria_esp32(payload: schemas.TelemetriaESP32In, db: Session = Depends(get_db)):
    """
    Recepción de telemetría de tempsensmosto.ino (ESP32).
    """
    # Verificar si la cuba existe
    cuba = db.query(models.Cuba).filter(models.Cuba.id == payload.cuba_id).first()
    if not cuba:
        # Si no existe, crearla automáticamente para facilitar pruebas
        cuba = models.Cuba(
            id=payload.cuba_id,
            codigo=f"CB-{payload.cuba_id:02d}",
            nombre=f"Cuba {payload.cuba_id:02d}",
            variedad="Cabernet Sauvignon",
            lote="Lote 2026-A"
        )
        db.add(cuba)
        db.commit()
        db.refresh(cuba)

    # Actualizar o registrar el dispositivo ESP32
    dispositivo = db.query(models.Dispositivo).filter(models.Dispositivo.mac == payload.device_mac).first()
    if not dispositivo:
        dispositivo = models.Dispositivo(
            codigo=f"ESP32-CB{payload.cuba_id:02d}-TEMP",
            nombre=f"Nodo Térmico Cuba {payload.cuba_id:02d}",
            mac=payload.device_mac,
            modelo="ESP32",
            tipo_sensor="DS18B20",
            cuba_id=cuba.id,
            estado="online",
            ultima_conexion=datetime.utcnow()
        )
        db.add(dispositivo)
    else:
        dispositivo.estado = "online"
        dispositivo.ultima_conexion = datetime.utcnow()

    # Guardar lectura
    nueva_lectura = models.LecturaTelemetria(
        cuba_id=cuba.id,
        dispositivo_id=dispositivo.id if dispositivo else None,
        temp_vino=payload.temp_vino,
        temp_ambiente=payload.temp_ambiente,
        humedad_ambiente=payload.humedad_ambiente,
        voltaje_ph=payload.voltaje_ph,
        timestamp=datetime.utcnow()
    )
    db.add(nueva_lectura)
    db.commit()

    return {
        "status": "ok",
        "mensaje": "Lectura de ESP32 guardada correctamente",
        "cuba_id": cuba.id,
        "temp_vino": payload.temp_vino
    }


@router.post("/flotador", status_code=status.HTTP_201_CREATED)
def recibir_telemetria_esp8266(payload: schemas.TelemetriaESP8266In, db: Session = Depends(get_db)):
    """
    Recepción de telemetría de esp86xyz.ino (ESP8266 con MPU-6050).
    """
    cuba = db.query(models.Cuba).filter(models.Cuba.id == payload.cuba_id).first()
    if not cuba:
        cuba = models.Cuba(
            id=payload.cuba_id,
            codigo=f"CB-{payload.cuba_id:02d}",
            nombre=f"Cuba {payload.cuba_id:02d}",
            variedad="Cabernet Sauvignon",
            lote="Lote 2026-A"
        )
        db.add(cuba)
        db.commit()
        db.refresh(cuba)

    # Calcular Brix a partir del ángulo medido
    brix_calculado = convertir_inclinacion_a_brix(payload.inclinacion)

    # Guardar lectura
    nueva_lectura = models.LecturaTelemetria(
        cuba_id=cuba.id,
        inclinacion=payload.inclinacion,
        brix_calculado=brix_calculado,
        ax=payload.ax,
        ay=payload.ay,
        az=payload.az,
        timestamp=datetime.utcnow()
    )
    db.add(nueva_lectura)
    db.commit()

    return {
        "status": "ok",
        "mensaje": "Lectura de inclinómetro guardada correctamente",
        "inclinacion_grados": payload.inclinacion,
        "brix_calculado": brix_calculado
    }

