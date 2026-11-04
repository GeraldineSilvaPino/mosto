"""
Controlador REST para Gestión y Reconocimiento de Alertas e Incidencias (MOSTO).
TASK-BE-04A: API de Consulta y Reconocimiento de Alertas (AlertsView.vue).
Rama: feat/be-alerts-read-ack

Endpoints expuestos:
- GET /api/alertas: Listado paginado con filtros de estado, severidad y cuba_id.
- GET /api/alertas/{id}: Detalle individual de alerta.
- PATCH /api/alertas/{id}/atender: Cambia estado a 'atendida' y registra operador y timestamp,
  asegurando el cumplimiento estricto de la restricción CHECK `ck_alerta_atencion`.
"""
from typing import List, Optional, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import EventoAlerta, ProcesoFermentacion, Cuba, Usuario, Dispositivo
from app.schemas import AlertaOut, AlertaAtenderIn

router = APIRouter(prefix="/api/alertas", tags=["Alertas e Incidencias"])


def _construir_titulo_descripcion(alerta: EventoAlerta) -> Tuple[str, str]:
    """Genera título y descripción descriptiva en base al tipo de alerta y severidad."""
    tipo = alerta.tipo_alerta or "desconocida"
    
    if tipo == "temp_alta":
        return (
            "Sobrecalentamiento en fermentación",
            "La temperatura del mosto superó el límite crítico superior definido en el perfil enológico."
        )
    elif tipo == "temp_baja":
        return (
            "Caída térmica brusca",
            "La temperatura del mosto descendió bajo el umbral mínimo óptimo, con riesgo de parada de fermentación."
        )
    elif tipo == "ph_alto":
        return (
            "Desviación de Acidez (pH Alto)",
            "El nivel de pH excede el rango máximo recomendado, generando riesgo de contaminación microbiológica."
        )
    elif tipo == "ph_bajo":
        return (
            "Acidez excesiva (pH Bajo)",
            "El nivel de pH descendió por debajo del rango de tolerancia enológica, inhibiendo las levaduras."
        )
    elif tipo == "bateria_baja":
        return (
            "Batería Crítica de Nodo IoT",
            "El microcontrolador presenta un nivel de carga bajo el umbral seguro de funcionamiento."
        )
    elif tipo == "wifi_debil":
        return (
            "Señal Wi-Fi Inestable",
            "La intensidad de señal RSSI del nodo IoT cayó bajo el nivel mínimo para garantizar la telemetría continua."
        )
    
    tipo_legible = tipo.replace("_", " ").capitalize()
    return (
        f"Alerta: {tipo_legible}",
        f"Incidencia registrada con severidad {alerta.severidad} detectada mediante {alerta.met_dispar or 'sensor_iot'}."
    )


def _mapear_alerta_out(alerta: EventoAlerta, db: Optional[Session] = None) -> AlertaOut:
    """Helper para transformar la entidad EventoAlerta al DTO enriquecido AlertaOut."""
    cuba_id = None
    cuba_codigo = None
    cuba_nombre = None
    variedad = None
    sensor_tipo = None
    operador_nombre = None

    # Extraer información de la cuba y el proceso de fermentación
    if alerta.fermentacion:
        if alerta.fermentacion.cuba:
            cuba_id = alerta.fermentacion.cuba.id
            cuba_codigo = alerta.fermentacion.cuba.codigo
            cuba_nombre = f"Cuba {alerta.fermentacion.cuba.codigo}"
            if alerta.fermentacion.cuba.sector_cuba:
                cuba_nombre += f" · {alerta.fermentacion.cuba.sector_cuba}"
        
        if alerta.fermentacion.perfil and alerta.fermentacion.perfil.cepa:
            variedad = alerta.fermentacion.perfil.cepa.nombre_variedad

    # Determinar tipo de sensor involucrado
    if alerta.dispositivo and alerta.dispositivo.tipo_dispositivo:
        sensor_tipo = alerta.dispositivo.tipo_dispositivo
    elif "temp" in alerta.tipo_alerta:
        sensor_tipo = "DS18B20"
    elif "ph" in alerta.tipo_alerta:
        sensor_tipo = "PH-4502C"
    elif "brix" in alerta.tipo_alerta or "tilt" in alerta.tipo_alerta:
        sensor_tipo = "MPU-6050"
    else:
        sensor_tipo = "Sensor IoT"

    # Determinar nombre del operador que atendió la alerta
    if alerta.atendida_por and db:
        usuario = db.query(Usuario).filter(Usuario.id == alerta.atendida_por).first()
        if usuario:
            operador_nombre = usuario.nombre
        else:
            operador_nombre = f"Operador #{alerta.atendida_por}"
    elif alerta.atendida_por:
        operador_nombre = f"Operador #{alerta.atendida_por}"

    titulo, descripcion = _construir_titulo_descripcion(alerta)

    return AlertaOut(
        id=alerta.id,
        dispositivo_id=alerta.dispositivo_id,
        fermentacion_id=alerta.fermentacion_id,
        cuba_id=cuba_id,
        cuba_codigo=cuba_codigo,
        cuba_nombre=cuba_nombre,
        variedad=variedad,
        sensor_tipo=sensor_tipo,
        tipo_alerta=alerta.tipo_alerta,
        severidad=alerta.severidad,
        estado=alerta.estado,
        met_dispar=alerta.met_dispar,
        titulo=titulo,
        descripcion=descripcion,
        timestamp=alerta.timestamp,
        atendida_por=alerta.atendida_por,
        operador_nombre=operador_nombre,
        fecha_atencion=alerta.fecha_atencion,
        fecha_resolucion=alerta.fecha_resolucion,
        nota_atencion=alerta.nota_atencion,
        nota_resolucion=alerta.nota_resolucion
    )


@router.get("", response_model=List[AlertaOut], summary="Listar alertas con filtros y paginación")
def listar_alertas(
    estado: Optional[str] = Query(None, description="Filtrar por estado: 'pendiente', 'atendida', 'resuelta'"),
    severidad: Optional[str] = Query(None, description="Filtrar por severidad: 'baja', 'media', 'alta', 'critica'"),
    cuba_id: Optional[int] = Query(None, description="Filtrar por ID de la cuba asociada"),
    tipo_alerta: Optional[str] = Query(None, description="Filtrar por código de anomalía (ej: 'temp_alta', 'ph_bajo')"),
    limit: int = Query(50, ge=1, le=500, description="Límite máximo de alertas a retornar (paginación)"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir para paginación"),
    db: Session = Depends(get_db)
):
    """
    Retorna la lista de alertas generadas en la bodega para consumo en `AlertsView.vue`.
    Permite filtrar dinámicamente por estado, severidad o cuba y cuenta con paginación parametrizable.
    """
    query = db.query(EventoAlerta)

    # 1. Filtro por estado ('pendiente', 'atendida', 'resuelta')
    if isinstance(estado, str) and estado.strip():
        query = query.filter(EventoAlerta.estado == estado.strip().lower())

    # 2. Filtro por severidad ('baja', 'media', 'alta', 'critica')
    if isinstance(severidad, str) and severidad.strip():
        query = query.filter(EventoAlerta.severidad == severidad.strip().lower())

    # 3. Filtro por tipo de alerta
    if isinstance(tipo_alerta, str) and tipo_alerta.strip():
        query = query.filter(EventoAlerta.tipo_alerta == tipo_alerta.strip().lower())

    # 4. Filtro por cuba específica (mediante join al proceso activo o asociado)
    if isinstance(cuba_id, int):
        query = (
            query.join(ProcesoFermentacion, EventoAlerta.fermentacion_id == ProcesoFermentacion.id)
            .filter(ProcesoFermentacion.cuba_id == cuba_id)
        )

    # Orden cronológico descendente: las alertas más recientes primero
    query = query.order_by(desc(EventoAlerta.timestamp))

    # Paginación segura
    lim = limit if isinstance(limit, int) else 50
    off = offset if isinstance(offset, int) else 0

    alertas = query.offset(off).limit(lim).all()

    return [_mapear_alerta_out(a, db) for a in alertas]


@router.get("/{id}", response_model=AlertaOut, summary="Obtener detalle de una alerta")
def obtener_alerta(id: int, db: Session = Depends(get_db)):
    """Retorna el detalle completo de una alerta individual por su identificador primario."""
    alerta = db.query(EventoAlerta).filter(EventoAlerta.id == id).first()
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta con ID {id} no encontrada."
        )
    return _mapear_alerta_out(alerta, db)


@router.patch("/{id}/atender", response_model=AlertaOut, summary="Atender alerta y registrar operador")
def atender_alerta(
    id: int,
    payload: Optional[AlertaAtenderIn] = None,
    db: Session = Depends(get_db)
):
    """
    Registra el inicio de atención/protocolo de una alerta por parte de un operador o enólogo:
    - Cambia el estado a `'atendida'`.
    - Cumple estrictamente la restricción de base de datos `ck_alerta_atencion`:
      al poblar `atendida_por`, es mandatorio registrar `fecha_atencion` con el timestamp actual.
    """
    alerta = db.query(EventoAlerta).filter(EventoAlerta.id == id).first()
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta con ID {id} no encontrada."
        )

    # Validar coherencia del flujo de estado
    if alerta.estado == "resuelta":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La alerta #{id} ya se encuentra resuelta y no puede volver a estado 'atendida'."
        )

    # Obtener ID del operador responsable (default = 1 si no se envía)
    operador_id = payload.usuario_id if (payload and payload.usuario_id) else (alerta.atendida_por or 1)

    # Actualización atómica garantizando la restricción CHECK ck_alerta_atencion
    alerta.estado = "atendida"
    alerta.fecha_atencion = datetime.utcnow()
    alerta.atendida_por = operador_id

    if payload and payload.nota:
        alerta.nota_atencion = payload.nota.strip()

    db.commit()
    db.refresh(alerta)

    return _mapear_alerta_out(alerta, db)
