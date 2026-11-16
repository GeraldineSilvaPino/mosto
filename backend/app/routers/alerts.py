"""
Controlador REST para Gestión, Reconocimiento y Auditoría de Alertas e Incidencias (MOSTO).
TASK-BE-04A: API de Consulta y Reconocimiento de Alertas (AlertsView.vue).
TASK-BE-04B: Resolución de Incidencias, Métricas MTTR y Exportación CSV (AlertsAuditView.vue).
Rama: feat/be-alerts-resolve-mttr

Endpoints expuestos:
- GET /api/alertas: Listado paginado con filtros de estado, severidad y cuba_id.
- GET /api/alertas/metricas: KPIs globales, total activas, críticas y fórmula MTTR.
- GET /api/alertas/exportar: Retorna bitácora histórica descargable en formato text/csv.
- GET /api/alertas/{id}: Detalle individual de alerta.
- PATCH /api/alertas/{id}/atender: Cambia estado a 'atendida' y registra operador y timestamp (ck_alerta_atencion).
- PATCH /api/alertas/{id}/resolver: Cambia estado a 'resuelta' y almacena nota de acción correctiva.
"""
import csv
import io
from typing import List, Optional, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.services.access import business_db, actor_id
from app.models import EventoAlerta, ProcesoFermentacion, Cuba, Usuario, Dispositivo, AuditoriaAlerta, BitacoraIntervencion
from app.services.telemetry_v2 import aware, utc_now
from app.services.episodes import record_action
from app.schemas import AlertaOut, AlertaAtenderIn, AlertaResolverIn, AlertasMetricasOut

router = APIRouter(prefix="/api/alertas", tags=["Alertas e Incidencias"])


def _extra_filters(query, estado=None, severidad=None, tipo_alerta=None, origen=None):
    for value, column in ((estado, EventoAlerta.estado), (severidad, EventoAlerta.severidad),
                          (tipo_alerta, EventoAlerta.tipo_alerta), (origen, EventoAlerta.origen)):
        if isinstance(value, str) and value.strip():
            query = query.filter(column == value.strip().lower())
    return query


def _construir_titulo_descripcion(alerta: EventoAlerta) -> Tuple[str, str]:
    """Genera título y descripción descriptiva en base al tipo de alerta y severidad."""
    tipo = alerta.tipo_alerta or "desconocida"
    if alerta.version_regla:
        return ("Temperatura sobre el perfil" if tipo == "temperatura_alta" else "Temperatura bajo el perfil",
                alerta.mensaje or "Desviación térmica observada; revisar la evidencia del episodio.")
    
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
    elif tipo in ("parada_fermentacion", "parada_fermentacion_ia", "parada"):
        return (
            "Predicción IA: Riesgo de Parada de Fermentación",
            alerta.mensaje or "El modelo de Inteligencia Artificial detectó estancamiento crítico en la curva de degradación de azúcares."
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
    elif "parada" in alerta.tipo_alerta or "ia" in alerta.tipo_alerta:
        sensor_tipo = "Modelo IA (ML)"
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
    resolvedor = db.query(Usuario).filter_by(id=alerta.resuelta_por).first() if db and alerta.resuelta_por else None

    return AlertaOut(
        id=alerta.id,
        resuelta_por=alerta.resuelta_por,
        resolvedor_nombre=resolvedor.nomb_compl if resolvedor else None,
        version_regla=alerta.version_regla, origen=alerta.origen,
        inicio_condicion=aware(alerta.inicio_condicion) if alerta.inicio_condicion else None,
        fin_condicion=aware(alerta.fin_condicion) if alerta.fin_condicion else None,
        ultima_observacion=aware(alerta.ultima_observacion) if alerta.ultima_observacion else None,
        estado_condicion=alerta.estado_condicion, evidencia=alerta.evidencia,
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
        timestamp=aware(alerta.timestamp) if alerta.timestamp else None,
        atendida_por=alerta.atendida_por,
        operador_nombre=operador_nombre,
        fecha_atencion=aware(alerta.fecha_atencion) if alerta.fecha_atencion else None,
        fecha_resolucion=aware(alerta.fecha_resolucion) if alerta.fecha_resolucion else None,
        nota_atencion=alerta.nota_atencion,
        nota_resolucion=alerta.nota_resolucion
    )


@router.get("", response_model=List[AlertaOut], summary="Listar alertas con filtros y paginación")
def listar_alertas(
    estado: Optional[str] = Query(None, description="Filtrar por estado: 'pendiente', 'atendida', 'resuelta'"),
    severidad: Optional[str] = Query(None, description="Filtrar por severidad: 'baja', 'media', 'alta', 'critica'"),
    cuba_id: Optional[int] = Query(None, description="Filtrar por ID de la cuba asociada"),
    tipo_alerta: Optional[str] = Query(None, description="Filtrar por código de anomalía (ej: 'temp_alta', 'ph_bajo')"),
    origen: Optional[str] = Query(None, description="fisico o simulado; omitir incluye legacy"),
    limit: int = Query(50, ge=1, le=500, description="Límite máximo de alertas a retornar (paginación)"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir para paginación"),
    db: Session = Depends(business_db("operations"))
):
    """
    Retorna la lista de alertas generadas en la bodega para consumo en `AlertsView.vue`.
    Permite filtrar dinámicamente por estado, severidad o cuba y cuenta con paginación parametrizable.
    """
    query = _extra_filters(db.query(EventoAlerta), origen=origen)

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


@router.get("/metricas", response_model=AlertasMetricasOut, summary="Obtener KPIs de auditoría y cálculo MTTR")
def obtener_metricas_alertas(
    cuba_id: Optional[int] = Query(None, description="Filtrar métricas por ID de cuba específica"),
    estado: Optional[str] = Query(None), severidad: Optional[str] = Query(None),
    tipo_alerta: Optional[str] = Query(None), origen: Optional[str] = Query(None),
    db: Session = Depends(business_db("operations"))
):
    """
    Calcula los KPIs de auditoría para la vista `AlertsAuditView.vue`:
    - Total de alertas registradas.
    - Total de alertas activas (en estado 'pendiente' o 'atendida').
    - Alertas críticas activas.
    - Total de incidencias resueltas.
    - Fórmula MTTR (Mean Time to Resolution) calculada estrictamente sobre alertas con estado 'resuelta':
        MTTR = sum(fecha_resolucion - fecha_generacion) / Total Resueltas (en minutos)
    - Tasa de resolución porcentual.
    """
    query = _extra_filters(db.query(EventoAlerta), estado, severidad, tipo_alerta, origen)
    if isinstance(cuba_id, int):
        query = (
            query.join(ProcesoFermentacion, EventoAlerta.fermentacion_id == ProcesoFermentacion.id)
            .filter(ProcesoFermentacion.cuba_id == cuba_id)
        )

    todas_alertas = query.all()
    total_alertas = len(todas_alertas)

    alertas_activas_list = [a for a in todas_alertas if a.estado in ("pendiente", "atendida")]
    total_activas = len(alertas_activas_list)
    total_criticas = len([a for a in alertas_activas_list if a.severidad == "critica"])

    alertas_resueltas = [a for a in todas_alertas if a.estado == "resuelta"]
    total_resueltas = len(alertas_resueltas)

    # ==========================================
    # CÁLCULO MTTR (Mean Time To Resolution)
    # MTTR = sum(fecha_resolucion - fecha_generacion) / Total Resueltas
    # ==========================================
    suma_minutos = 0.0
    muestras_mttr = 0
    for a in alertas_resueltas:
        f_generacion = a.timestamp
        f_resolucion = a.fecha_resolucion
        if f_generacion and f_resolucion:
            segundos = (aware(f_resolucion) - aware(f_generacion)).total_seconds()
            if segundos >= 0:
                suma_minutos += segundos / 60.0
                muestras_mttr += 1

    mttr_promedio = round(suma_minutos / muestras_mttr, 2) if muestras_mttr else None
    tasa_resolucion = round((total_resueltas / total_alertas) * 100.0, 1) if total_alertas > 0 else 0.0

    return AlertasMetricasOut(
        total_alertas=total_alertas,
        alertas_activas=total_activas,
        alertas_criticas=total_criticas,
        total_resueltas=total_resueltas,
        mttr_promedio_minutos=mttr_promedio,
        muestras_mttr=muestras_mttr,
        resueltas_sin_tiempos_validos=total_resueltas - muestras_mttr,
        condiciones_sin_recuperacion=sum(1 for a in todas_alertas if a.version_regla and a.fin_condicion is None),
        tasa_resolucion_pct=tasa_resolucion
    )


@router.get("/exportar", summary="Exportar bitácora histórica en formato CSV para descarga directa")
def exportar_bitacora_alertas_csv(
    estado: Optional[str] = Query(None, description="Filtrar por estado ('pendiente', 'atendida', 'resuelta')"),
    severidad: Optional[str] = Query(None, description="Filtrar por severidad ('baja', 'media', 'alta', 'critica')"),
    cuba_id: Optional[int] = Query(None, description="Filtrar por ID de cuba"),
    tipo_alerta: Optional[str] = Query(None), origen: Optional[str] = Query(None),
    db: Session = Depends(business_db("operations"))
):
    """
    Retorna la bitácora histórica completa en formato `text/csv` con descarga directa en el navegador.
    Cumple con el criterio de cabecera `Content-Type: text/csv` y `Content-Disposition: attachment`.
    """
    query = _extra_filters(db.query(EventoAlerta), tipo_alerta=tipo_alerta, origen=origen)

    if isinstance(estado, str) and estado.strip():
        query = query.filter(EventoAlerta.estado == estado.strip().lower())

    if isinstance(severidad, str) and severidad.strip():
        query = query.filter(EventoAlerta.severidad == severidad.strip().lower())

    if isinstance(cuba_id, int):
        query = (
            query.join(ProcesoFermentacion, EventoAlerta.fermentacion_id == ProcesoFermentacion.id)
            .filter(ProcesoFermentacion.cuba_id == cuba_id)
        )

    alertas = query.order_by(desc(EventoAlerta.timestamp)).all()

    # Generación de CSV en memoria con BOM utf-8 para compatibilidad nativa con Excel
    buffer = io.StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=',', quoting=csv.QUOTE_MINIMAL)

    # Cabeceras formales
    writer.writerow([
        "ID Incidencia",
        "Cuba",
        "Variedad",
        "Sensor",
        "Tipo Alerta",
        "Severidad",
        "Estado",
        "Fecha Deteccion (UTC)",
        "Fecha Atencion (UTC)",
        "Fecha Resolucion (UTC)",
        "Tiempo Resolucion (min)",
        "Operador",
        "Nota Atencion",
        "Accion Correctiva / Nota Resolucion", "Origen", "Estado Condicion", "Resuelto Por"
    ])

    for a in alertas:
        dto = _mapear_alerta_out(a, db)

        # Cálculo de tiempo de resolución si está disponible
        tiempo_res_str = ""
        if a.timestamp and a.fecha_resolucion:
            minutos = (aware(a.fecha_resolucion) - aware(a.timestamp)).total_seconds() / 60.0
            tiempo_res_str = f"{round(minutos, 1)}" if minutos >= 0 else ""

        writer.writerow([
            dto.id,
            dto.cuba_codigo or "N/A",
            dto.variedad or "N/A",
            dto.sensor_tipo or "N/A",
            dto.tipo_alerta,
            dto.severidad,
            dto.estado,
            dto.timestamp.strftime("%Y-%m-%d %H:%M:%S") if dto.timestamp else "",
            dto.fecha_atencion.strftime("%Y-%m-%d %H:%M:%S") if dto.fecha_atencion else "",
            dto.fecha_resolucion.strftime("%Y-%m-%d %H:%M:%S") if dto.fecha_resolucion else "",
            tiempo_res_str,
            dto.operador_nombre or "N/A",
            dto.nota_atencion or "",
            dto.nota_resolucion or "", dto.origen or "legacy", dto.estado_condicion or "", dto.resolvedor_nombre or ""
        ])

    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"bitacora_alertas_{timestamp_str}.csv"

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{nombre_archivo}"'
        }
    )


@router.get("/{id}", response_model=AlertaOut, summary="Obtener detalle de una alerta")
def obtener_alerta(id: int, db: Session = Depends(business_db("operations"))):
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
    db: Session = Depends(business_db("operations"))
):
    """
    Registra el inicio de atención/protocolo de una alerta por parte de un operador o enólogo:
    - Cambia el estado a `'atendida'`.
    - Cumple estrictamente la restricción de base de datos `ck_alerta_atencion`:
      al poblar `atendida_por`, es mandatorio registrar `fecha_atencion` con el timestamp actual.
    """
    alerta = db.query(EventoAlerta).filter(EventoAlerta.id == id).with_for_update().first()
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

    if alerta.estado == "atendida":
        if payload and payload.nota and payload.nota.strip() != (alerta.nota_atencion or ""):
            raise HTTPException(409, "La atención ya fue registrada; añada una intervención a la bitácora")
        return _mapear_alerta_out(alerta, db)

    # Actor from authenticated membership, never a client-provided ID.
    operador_id = actor_id(db)

    # Actualización atómica garantizando la restricción CHECK ck_alerta_atencion
    alerta.estado = "atendida"
    alerta.fecha_atencion = utc_now()
    alerta.atendida_por = operador_id

    if payload and payload.nota:
        alerta.nota_atencion = payload.nota.strip()
    record_action(db, alerta, "atendida", actor=operador_id, detail={"nota": alerta.nota_atencion}, registered=alerta.fecha_atencion)

    db.commit()
    db.refresh(alerta)

    return _mapear_alerta_out(alerta, db)


@router.patch("/{id}/resolver", response_model=AlertaOut, summary="Resolver alerta y registrar acción correctiva")
def resolver_alerta(
    id: int,
    payload: Optional[AlertaResolverIn] = None,
    db: Session = Depends(business_db("operations"))
):
    """
    TASK-BE-04B: Registra la resolución formal de una alerta enológica:
    - Cambia el estado a `'resuelta'`.
    - Registra el timestamp exacto de cierre en `fecha_resolucion`.
    - Si no tenía `fecha_atencion`, se fija para consistencia con `ck_alerta_atencion`.
    - Guarda la nota o acción correctiva en `nota_resolucion` para la auditoría de MTTR.
    """
    alerta = db.query(EventoAlerta).filter(EventoAlerta.id == id).with_for_update().first()
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta con ID {id} no encontrada."
        )

    if alerta.estado == "resuelta":
        if payload and payload.nota_resolucion and payload.nota_resolucion.strip() != (alerta.nota_resolucion or ""):
            raise HTTPException(409, "La resolución ya fue registrada; añada una intervención a la bitácora")
        return _mapear_alerta_out(alerta, db)
    note = payload.nota_resolucion.strip() if payload and payload.nota_resolucion else ""
    if alerta.version_regla and len(note) < 10:
        raise HTTPException(422, "Describa la revisión o intervención en al menos 10 caracteres")
    ahora = utc_now()
    alerta.estado = "resuelta"
    alerta.fecha_resolucion = ahora
    alerta.resuelta_por = actor_id(db)

    # Si no tenía fecha_atencion, registrarla para consistencia de auditoría y CHECKs
    if not alerta.fecha_atencion:
        alerta.fecha_atencion = ahora

    if not alerta.atendida_por:
        alerta.atendida_por = actor_id(db)

    # Registrar nota de acción correctiva
    if payload and payload.nota_resolucion:
        alerta.nota_resolucion = payload.nota_resolucion.strip()
    record_action(db, alerta, "resuelta", actor=actor_id(db), detail={"nota": alerta.nota_resolucion,
                  "estado_condicion": alerta.estado_condicion}, registered=ahora)
    if alerta.version_regla:
        db.add(BitacoraIntervencion(alerta_id=alerta.id, fermentacion_id=alerta.fermentacion_id,
            cuba_id=alerta.fermentacion.cuba_id, usuario_id=actor_id(db), fecha_registro=ahora,
            tipo_intervencion="nota", descripcion=f"Revisión del episodio #{alerta.id}: {note}"))

    db.commit()
    db.refresh(alerta)

    return _mapear_alerta_out(alerta, db)


@router.get("/{id}/eventos")
def eventos_alerta(id: int, db: Session = Depends(business_db("operations"))):
    if not db.query(EventoAlerta).filter_by(id=id).first():
        raise HTTPException(404, "Alerta no encontrada")
    events = db.query(AuditoriaAlerta).filter_by(alerta_id=id).order_by(AuditoriaAlerta.id).all()
    return [{"id": e.id, "accion": e.accion, "registrado_en": aware(e.registrado_en),
             "observado_en": aware(e.observado_en) if e.observado_en else None,
             "usuario_id": e.usuario_id, "mensaje_id": e.mensaje_id, "detalle": e.detalle} for e in events]
