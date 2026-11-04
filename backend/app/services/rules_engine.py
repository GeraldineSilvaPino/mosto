"""
Motor de Reglas Enológicas y Detección de Anomalías (MOSTO)
TASK-BE-03A: Servicio de Detección de Desviaciones Térmicas y Acidez
TASK-BE-03B: Disparador de Alertas con Control Anti-Spam (Debounce)
Rama: feat/be-rules-alert-dispatcher

Evalúa lecturas de telemetría en tiempo real contra los perfiles óptimos de fermentación
de cada cuba, clasifica el desvío según severidades ('media', 'alta', 'critica') y
persiste las alertas en Supabase evitando saturación mediante ventana de enfriamiento (cooldown).
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Cuba,
    ProcesoFermentacion,
    PerfilFermentacion,
    LecturaTelemetria,
    EventoAlerta
)

logger = logging.getLogger(__name__)


class RulesEngine:
    """
    Motor encargado de verificar parámetros enológicos, detectar desviaciones térmicas y de pH,
    y despachar eventos de alerta en base de datos con control anti-spam.
    """

    # Ventana de enfriamiento temporal (Debounce anti-spam): 15 minutos
    COOLDOWN_MINUTOS = 15

    # Umbrales de desvío de temperatura (°C) sobre la banda óptima
    DELTA_TEMP_ALTA = 1.5      # > 1.5 °C de desvío = severidad 'alta'
    DELTA_TEMP_CRITICA = 3.0   # > 3.0 °C de desvío = severidad 'critica'

    # Umbrales de desvío de pH sobre la banda óptima
    DELTA_PH_ALTA = 0.20       # > 0.20 de desvío = severidad 'alta'
    DELTA_PH_CRITICA = 0.40    # > 0.40 de desvío = severidad 'critica'

    # Perfil por defecto enológico para contingencias (si la cuba no tiene perfil explícito)
    FALLBACK_TEMP_MIN = 18.0
    FALLBACK_TEMP_MAX = 28.0
    FALLBACK_PH_MIN = 3.20
    FALLBACK_PH_MAX = 3.80

    def clasificar_severidad_temperatura(self, delta: float) -> str:
        """
        Determina la severidad en función de la magnitud del desvío térmico (delta >= 0).
        - delta > 3.0 °C  -> 'critica'
        - delta > 1.5 °C  -> 'alta'
        - delta > 0.0 °C  -> 'media'
        """
        if delta > self.DELTA_TEMP_CRITICA:
            return "critica"
        elif delta > self.DELTA_TEMP_ALTA:
            return "alta"
        return "media"

    def clasificar_severidad_ph(self, delta: float) -> str:
        """
        Determina la severidad en función de la magnitud del desvío de pH (delta >= 0).
        - delta > 0.40 -> 'critica'
        - delta > 0.20 -> 'alta'
        - delta > 0.00 -> 'media'
        """
        if delta > self.DELTA_PH_CRITICA:
            return "critica"
        elif delta > self.DELTA_PH_ALTA:
            return "alta"
        return "media"

    def obtener_perfil_activo(
        self,
        db: Session,
        cuba_id: int,
        fermentacion_id: Optional[int] = None
    ) -> Optional[PerfilFermentacion]:
        """
        Recupera el perfil de fermentación asignado al proceso activo de la cuba.
        """
        proceso = None

        # 1. Buscar primero por fermentacion_id si viene en la lectura
        if fermentacion_id:
            proceso = (
                db.query(ProcesoFermentacion)
                .filter(ProcesoFermentacion.id == fermentacion_id)
                .first()
            )

        # 2. Si no, buscar el proceso activo vinculado a la cuba
        if not proceso:
            proceso = (
                db.query(ProcesoFermentacion)
                .filter(
                    ProcesoFermentacion.cuba_id == cuba_id,
                    ProcesoFermentacion.estado.in_(["en_proceso", "en_fermentacion", "activo"])
                )
                .order_by(desc(ProcesoFermentacion.fecha_inicio))
                .first()
            )

        if proceso and proceso.perfil_id:
            perfil = (
                db.query(PerfilFermentacion)
                .filter(PerfilFermentacion.id == proceso.perfil_id)
                .first()
            )
            if perfil:
                return perfil

        # 3. Fallback: perfil activo general si no está asociado a un proceso
        return (
            db.query(PerfilFermentacion)
            .filter(PerfilFermentacion.activo == True)
            .first()
        )

    def evaluar_lectura(
        self,
        db: Session,
        lectura: LecturaTelemetria,
        cuba_id: int
    ) -> List[Dict[str, Any]]:
        """
        Evalúa una lectura contra los límites térmicos y de acidez del perfil de la cuba.

        Retorna una lista de diccionarios con las anomalías detectadas.
        Si la lectura está dentro de los rangos óptimos, retorna [].
        """
        anomalias: List[Dict[str, Any]] = []

        # 1. Obtener el perfil enológico aplicable
        perfil = self.obtener_perfil_activo(
            db=db,
            cuba_id=cuba_id,
            fermentacion_id=lectura.fermentacion_id
        )

        # Definir límites objetivos (usando perfil o fallback seguro)
        temp_min = float(perfil.temp_min) if (perfil and perfil.temp_min is not None) else self.FALLBACK_TEMP_MIN
        temp_max = float(perfil.temp_max) if (perfil and perfil.temp_max is not None) else self.FALLBACK_TEMP_MAX
        ph_min = float(perfil.ph_min) if (perfil and perfil.ph_min is not None) else self.FALLBACK_PH_MIN
        ph_max = float(perfil.ph_max) if (perfil and perfil.ph_max is not None) else self.FALLBACK_PH_MAX

        # 2. EVALUACIÓN DE TEMPERATURA
        if lectura.temp_mosto is not None:
            temp_actual = float(lectura.temp_mosto)

            # Regla: Temperatura por sobre el máximo óptimo
            if temp_actual > temp_max:
                desvio = round(temp_actual - temp_max, 2)
                severidad = self.clasificar_severidad_temperatura(desvio)
                anomalias.append({
                    "tipo_alerta": "temperatura_alta",
                    "severidad": severidad,
                    "met_dispar": "temp_mosto",
                    "valor_leido": temp_actual,
                    "limite_esperado": temp_max,
                    "desvio": desvio,
                    "descripcion": (
                        f"Temperatura del mosto ({temp_actual} °C) excede el límite máximo "
                        f"óptimo ({temp_max} °C) en +{desvio} °C."
                    ),
                    "cuba_id": cuba_id,
                    "fermentacion_id": lectura.fermentacion_id
                })

            # Regla: Temperatura bajo el mínimo óptimo
            elif temp_actual < temp_min:
                desvio = round(temp_min - temp_actual, 2)
                severidad = self.clasificar_severidad_temperatura(desvio)
                anomalias.append({
                    "tipo_alerta": "temperatura_baja",
                    "severidad": severidad,
                    "met_dispar": "temp_mosto",
                    "valor_leido": temp_actual,
                    "limite_esperado": temp_min,
                    "desvio": desvio,
                    "descripcion": (
                        f"Temperatura del mosto ({temp_actual} °C) está por debajo del límite "
                        f"mínimo óptimo ({temp_min} °C) en -{desvio} °C."
                    ),
                    "cuba_id": cuba_id,
                    "fermentacion_id": lectura.fermentacion_id
                })

        # 3. EVALUACIÓN DE pH
        if lectura.ph is not None:
            ph_actual = float(lectura.ph)

            # Regla: pH bajo el mínimo óptimo (hiperacidez)
            if ph_actual < ph_min:
                desvio = round(ph_min - ph_actual, 2)
                severidad = self.clasificar_severidad_ph(desvio)
                anomalias.append({
                    "tipo_alerta": "ph_bajo",
                    "severidad": severidad,
                    "met_dispar": "ph",
                    "valor_leido": ph_actual,
                    "limite_esperado": ph_min,
                    "desvio": desvio,
                    "descripcion": (
                        f"Nivel de pH ({ph_actual}) por debajo del rango óptimo "
                        f"mínimo ({ph_min}) en -{desvio} unidades."
                    ),
                    "cuba_id": cuba_id,
                    "fermentacion_id": lectura.fermentacion_id
                })

            # Regla: pH sobre el máximo óptimo (riesgo microbiológico)
            elif ph_actual > ph_max:
                desvio = round(ph_actual - ph_max, 2)
                severidad = self.clasificar_severidad_ph(desvio)
                anomalias.append({
                    "tipo_alerta": "ph_alto",
                    "severidad": severidad,
                    "met_dispar": "ph",
                    "valor_leido": ph_actual,
                    "limite_esperado": ph_max,
                    "desvio": desvio,
                    "descripcion": (
                        f"Nivel de pH ({ph_actual}) excede el rango óptimo "
                        f"máximo ({ph_max}) en +{desvio} unidades."
                    ),
                    "cuba_id": cuba_id,
                    "fermentacion_id": lectura.fermentacion_id
                })

        return anomalias

    def debe_suprimir_alerta(
        self,
        db: Session,
        fermentacion_id: Optional[int],
        tipo_alerta: str
    ) -> bool:
        """
        Filtro de enfriamiento temporal (Debounce anti-spam):
        Verifica si ya existe una alerta activa del mismo tipo para esta fermentación
        generada hace menos de COOLDOWN_MINUTOS (15 minutos).
        """
        if not fermentacion_id:
            return False

        limite_cooldown = datetime.utcnow() - timedelta(minutes=self.COOLDOWN_MINUTOS)

        alerta_reciente = (
            db.query(EventoAlerta)
            .filter(
                EventoAlerta.fermentacion_id == fermentacion_id,
                EventoAlerta.tipo_alerta == tipo_alerta,
                EventoAlerta.timestamp >= limite_cooldown,
                EventoAlerta.estado.in_(["pendiente", "atendida"])
            )
            .first()
        )

        return alerta_reciente is not None

    def procesar_alertas_lectura(
        self,
        db: Session,
        lectura: LecturaTelemetria,
        cuba_id: int,
        dispositivo_id: Optional[int] = None
    ) -> List[EventoAlerta]:
        """
        TASK-BE-03B: Evalúa la lectura y persiste eventos de alerta en EVENTO_ALERTA
        con estado 'pendiente', aplicando el filtro de enfriamiento de 15 minutos.
        """
        anomalias = self.evaluar_lectura(db=db, lectura=lectura, cuba_id=cuba_id)
        alertas_generadas: List[EventoAlerta] = []

        for anomalia in anomalias:
            ferm_id = anomalia.get("fermentacion_id")
            tipo = anomalia["tipo_alerta"]

            # Comprobar si está en periodo de enfriamiento anti-spam
            if self.debe_suprimir_alerta(db=db, fermentacion_id=ferm_id, tipo_alerta=tipo):
                logger.info(
                    f"[Anti-Spam] Alerta '{tipo}' para cuba {cuba_id} (proceso {ferm_id}) "
                    f"suprimida: existe alerta activa generada hace menos de {self.COOLDOWN_MINUTOS} min."
                )
                continue

            # Crear y persistir la nueva alerta
            nueva_alerta = EventoAlerta(
                dispositivo_id=dispositivo_id or lectura.dispositivo_id,
                fermentacion_id=ferm_id,
                timestamp=datetime.utcnow(),
                tipo_alerta=tipo,
                severidad=anomalia["severidad"],
                met_dispar=anomalia.get("met_dispar", "sensor_iot"),
                mensaje=anomalia.get("mensaje", f"Alerta {tipo}"),
                valor_registrado=anomalia.get("valor_actual"),
                valor_limite=anomalia.get("limite_esperado"),
                estado="pendiente"
            )
            db.add(nueva_alerta)
            alertas_generadas.append(nueva_alerta)

        if alertas_generadas:
            db.commit()
            for alerta in alertas_generadas:
                db.refresh(alerta)
            logger.info(
                f"[Alertas] Se persistieron {len(alertas_generadas)} nuevas alertas para la cuba {cuba_id}."
            )

        return alertas_generadas


# Instancia única para importación directa en servicios
rules_engine = RulesEngine()
