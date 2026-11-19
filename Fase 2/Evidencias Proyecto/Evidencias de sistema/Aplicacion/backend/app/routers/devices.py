"""
Router de Inventario de Hardware y Device Hub IoT.
Gestiona el estado en vivo de microcontroladores (ESP32/ESP8266), registro y vinculación con cubas.
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from app.services.access import business_db
from app.models import (
    Dispositivo,
    ModeloDispositivo,
    AsignacionDispositivo,
    Cuba,
    TelemetriaEstadoNodo,
    LecturaTelemetria,
    EmpresaCliente
)
from app.schemas import (
    DispositivoOut,
    DispositivoVincularIn,
    DispositivoDesvincularIn,
    DispositivoCreateIn
)

router = APIRouter(prefix="/api/dispositivos", tags=["Device Hub e Inventario IoT"])


def _formatear_tiempo_relativo(delta_segundos: float) -> str:
    """Retorna una cadena legible en español para la última telemetría."""
    if delta_segundos < 60:
        return f"Hace {max(1, int(delta_segundos))} seg"
    elif delta_segundos < 3600:
        return f"Hace {int(delta_segundos // 60)} min"
    elif delta_segundos < 86400:
        return f"Hace {int(delta_segundos // 3600)} h"
    else:
        return f"Hace {int(delta_segundos // 86400)} d"


def _evaluar_calidad_senal(rssi: Optional[int]) -> str:
    """Determina la calidad de enlace Wi-Fi en función del valor RSSI en dBm."""
    if rssi is None or rssi == 0:
        return "none"
    if rssi >= -60:
        return "excellent"
    elif rssi >= -72:
        return "good"
    elif rssi >= -85:
        return "weak"
    else:
        return "none"


def _mapear_dispositivo_out(d: Dispositivo, db: Session) -> DispositivoOut:
    """Helper que mapea la entidad Dispositivo y su telemetría reciente al DTO DispositivoOut."""
    # 1. Buscar asignación activa respetando ck_asignacion_activo (activo = True y desasignado_en es None)
    asignacion_activa = (
        db.query(AsignacionDispositivo)
        .filter(
            AsignacionDispositivo.dispositivo_id == d.id,
            AsignacionDispositivo.activo == True,
            AsignacionDispositivo.desasignado_en == None
        )
        .order_by(desc(AsignacionDispositivo.id))
        .first()
    )

    cuba_asignada = asignacion_activa.cuba if asignacion_activa else None

    # 2. Obtener última telemetría del nodo (batería y RSSI)
    ultimo_estado_nodo = (
        db.query(TelemetriaEstadoNodo)
        .filter(TelemetriaEstadoNodo.dispositivo_id == d.id)
        .order_by(desc(TelemetriaEstadoNodo.timestamp))
        .first()
    )

    # 3. Obtener última lectura de sensores
    ultima_lectura = (
        db.query(LecturaTelemetria)
        .filter(LecturaTelemetria.dispositivo_id == d.id)
        .order_by(desc(LecturaTelemetria.timestamp))
        .first()
    )

    # Determinar la marca temporal más reciente de conexión
    timestamps_conexion = [d.ultima_recepcion] if d.ultima_recepcion else []
    if ultimo_estado_nodo and ultimo_estado_nodo.timestamp:
        timestamps_conexion.append(ultimo_estado_nodo.timestamp)
    if ultima_lectura and ultima_lectura.timestamp:
        timestamps_conexion.append(ultima_lectura.timestamp)

    ultima_conexion = d.ultima_recepcion or (max(timestamps_conexion) if timestamps_conexion else None)

    # 4. Cálculo dinámico de estado en línea: si now() - ultima_conexion > 120s -> 'offline'
    ahora_utc = datetime.now(timezone.utc)
    status = "offline"
    status_label = "Desconectado"
    last_telemetry_str = "Sin transmisiones"

    if ultima_conexion:
        if ultima_conexion.tzinfo is None:
            ts_aware = ultima_conexion.replace(tzinfo=timezone.utc)
        else:
            ts_aware = ultima_conexion

        delta_seg = (ahora_utc - ts_aware).total_seconds()
        last_telemetry_str = _formatear_tiempo_relativo(delta_seg)

        if delta_seg <= (600 if d.origen else 120):
            status = "online"
            status_label = "En Línea"
        else:
            status = "offline"
            status_label = "Desconectado"

    # Si el estado administrativo de la BD es mantención, prevalece
    if d.estado == "mantencion":
        status = "maintenance"
        status_label = "En Mantención"

    # 5. Sensor y Fuente de Energía
    tipo_str = (d.tipo_dispositivo or "").upper()
    if "FLOTADOR" in tipo_str or "MPU" in tipo_str or "TILT" in tipo_str or "INCLINOMETRO" in tipo_str:
        sensor_type = "MPU-6050"
        sensor_label = "Inclinómetro Giroscopio MPU-6050"
        power_source = "battery"
    elif "PH" in tipo_str:
        sensor_type = "PH-4502C"
        sensor_label = "Sonda de pH Analógica PH-4502C"
        power_source = "mains"
    elif "DUAL" in tipo_str:
        sensor_type = "DUAL"
        sensor_label = "Combo Dual (DS18B20 + MPU-6050)"
        power_source = "battery"
    else:
        sensor_type = "DS18B20"
        sensor_label = "Sonda Térmica Estanco DS18B20"
        power_source = "mains"

    bateria_val = int(ultimo_estado_nodo.bateria_pct) if (ultimo_estado_nodo and ultimo_estado_nodo.bateria_pct is not None) else None
    rssi_val = int(ultimo_estado_nodo.rssi_dbm) if (ultimo_estado_nodo and ultimo_estado_nodo.rssi_dbm is not None) else None
    qual_val = _evaluar_calidad_senal(rssi_val)

    modelo_nombre = d.modelo.modelo if d.modelo else "Sin modelo"
    values = []
    if ultima_lectura is not None:
        if ultima_lectura.temp_mosto is not None:
            values.append(f"{float(ultima_lectura.temp_mosto):.2f} °C")
        if ultima_lectura.brix is not None:
            values.append(f"{float(ultima_lectura.brix):.2f} °Bx aparente")


    return DispositivoOut(
        id=d.id,
        code=f"{'ESP8266' if 'ESP8266' in tipo_str else 'ESP32'}-DEV-{d.id:02d}",
        name=f"Nodo {sensor_type} ({cuba_asignada.codigo if cuba_asignada else 'Sin Asignar'})",
        mac=d.mac_address,
        model=modelo_nombre,
        sensorType=sensor_type,
        sensorLabel=sensor_label,
        assignedCubaId=cuba_asignada.id if cuba_asignada else None,
        assignedCubaCode=cuba_asignada.codigo if cuba_asignada else None,
        assignedCubaName=f"Cuba {cuba_asignada.codigo}" if cuba_asignada else None,
        status=status,
        statusLabel=status_label,
        signalRssi=rssi_val,
        signalQuality=qual_val,
        powerSource="battery" if bateria_val is not None else "unknown",
        batteryLevel=bateria_val,
        firmware=d.firmware_version,
        lastTelemetry=last_telemetry_str,
        ultima_conexion=ultima_conexion,
        source=d.origen,
        lastReadingValue=" / ".join(values) if values else "Sin medición válida"
    )


@router.get("", response_model=List[DispositivoOut], summary="Listar inventario de dispositivos IoT")
def listar_dispositivos(
    cuba_id: Optional[int] = Query(None, description="Filtrar por cuba asignada"),
    status: Optional[str] = Query(None, description="Filtrar por estado: 'online', 'offline', 'maintenance'"),
    db: Session = Depends(business_db("devices"))
):
    """
    Lista todos los dispositivos microcontroladores registrados con su estado telemétrico
    dinámico (online si transmitió en los últimos 120s, de lo contrario offline).
    """
    dispositivos = db.query(Dispositivo).order_by(Dispositivo.id.asc()).all()
    resultado = [_mapear_dispositivo_out(d, db) for d in dispositivos]

    if cuba_id is not None:
        resultado = [r for r in resultado if r.assignedCubaId == cuba_id]

    if status is not None:
        resultado = [r for r in resultado if r.status == status]

    return resultado


@router.post("", response_model=DispositivoOut, status_code=status.HTTP_201_CREATED, summary="Registrar nuevo dispositivo IoT")
def crear_dispositivo(payload: DispositivoCreateIn, db: Session = Depends(business_db("devices"))):
    """
    Registra un nuevo microcontrolador ESP32/ESP8266 en la base de datos
    y opcionalmente lo vincula a una cuba de fermentación.
    """
    mac_clean = payload.mac.strip().upper()
    existente = db.query(Dispositivo).filter(func.upper(Dispositivo.mac_address) == mac_clean).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un dispositivo registrado con la dirección MAC '{mac_clean}'."
        )

    # Models are shared catalogs, provisioned outside tenant CRUD.
    nombre_modelo = payload.model or "ESP32-WROOM-32D"
    modelo = db.query(ModeloDispositivo).filter(func.lower(ModeloDispositivo.modelo) == nombre_modelo.lower()).first()
    if modelo is None:
        raise HTTPException(409, "Modelo no aprovisionado en el catálogo")
    cuba = None
    if payload.cubaId:
        try:
            cuba_id = int(payload.cubaId)
        except (TypeError, ValueError):
            raise HTTPException(422, "Identificador de cuba inválido")
        cuba = db.query(Cuba).filter_by(id=cuba_id).first()
        if cuba is None:
            raise HTTPException(404, "Cuba no encontrada")
    nuevo_dispositivo = Dispositivo(
        mac_address=mac_clean, tipo_dispositivo=payload.sensorType,
        firmware_version=None, estado="activo",
        empresa_id=db.info["access"].company_id, modelo_id=modelo.id)
    try:
        db.add(nuevo_dispositivo)
        db.flush()
        if cuba is not None:
            db.add(AsignacionDispositivo(dispositivo_id=nuevo_dispositivo.id,
                                        cuba_id=cuba.id, activo=True))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "No se pudo registrar el dispositivo con los datos proporcionados")
    db.refresh(nuevo_dispositivo)
    return _mapear_dispositivo_out(nuevo_dispositivo, db)


@router.get("/{dispositivo_id}", response_model=DispositivoOut, summary="Obtener detalle de un dispositivo")
def obtener_dispositivo(dispositivo_id: int, db: Session = Depends(business_db("devices"))):
    """Retorna el estado detallado y última telemetría de un dispositivo IoT."""
    d = db.query(Dispositivo).filter(Dispositivo.id == dispositivo_id).first()
    if not d:
        raise HTTPException(status_code=404, detail=f"Dispositivo con ID {dispositivo_id} no encontrado")
    return _mapear_dispositivo_out(d, db)


@router.post("/vincular", response_model=DispositivoOut, summary="Vincular dispositivo a una cuba")
def vincular_dispositivo(payload: DispositivoVincularIn, db: Session = Depends(business_db("devices"))):
    """Vincula un dispositivo a una cuba."""
    d = db.query(Dispositivo).filter(Dispositivo.id == payload.dispositivo_id).with_for_update().first()
    if not d:
        raise HTTPException(status_code=404, detail=f"Dispositivo con ID {payload.dispositivo_id} no encontrado")

    c = db.query(Cuba).filter(Cuba.id == payload.cuba_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cuba con ID {payload.cuba_id} no encontrada")

    if c.bodega and c.bodega.empresa_id != d.empresa_id:
        raise HTTPException(
            status_code=400,
            detail=f"Inconsistencia de empresa: la cuba pertenece a la bodega {c.bodega_id} (empresa {c.bodega.empresa_id}), mientras que el dispositivo pertenece a la empresa {d.empresa_id}."
        )

    ahora = datetime.utcnow()

    asignaciones_previas = (
        db.query(AsignacionDispositivo)
        .filter(
            AsignacionDispositivo.dispositivo_id == d.id,
            AsignacionDispositivo.activo == True
        )
        .all()
    )
    for a in asignaciones_previas:
        a.activo = False
        a.desasignado_en = ahora

    # Close the old interval before INSERT; the partial unique index is immediate.
    db.flush()
    nueva_asignacion = AsignacionDispositivo(
        dispositivo_id=d.id,
        cuba_id=c.id,
        activo=True,
        asignado_en=ahora,
        desasignado_en=None
    )
    db.add(nueva_asignacion)
    db.commit()
    db.refresh(d)

    return _mapear_dispositivo_out(d, db)


@router.post("/desvincular", response_model=DispositivoOut, summary="Desvincular dispositivo de su cuba actual")
def desvincular_dispositivo(payload: DispositivoDesvincularIn, db: Session = Depends(business_db("devices"))):
    """Libera un dispositivo cerrando su asignación activa."""
    d = db.query(Dispositivo).filter(Dispositivo.id == payload.dispositivo_id).with_for_update().first()
    if not d:
        raise HTTPException(status_code=404, detail=f"Dispositivo con ID {payload.dispositivo_id} no encontrado")

    ahora = datetime.utcnow()

    asignaciones_activas = (
        db.query(AsignacionDispositivo)
        .filter(
            AsignacionDispositivo.dispositivo_id == d.id,
            AsignacionDispositivo.activo == True
        )
        .all()
    )

    for a in asignaciones_activas:
        a.activo = False
        a.desasignado_en = ahora

    db.commit()
    db.refresh(d)

    return _mapear_dispositivo_out(d, db)
