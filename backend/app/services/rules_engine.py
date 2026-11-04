

"""
Motor de Reglas Enológicas y Detección de Anomalías (MOSTO)
TASK-BE-03A: Servicio de Detección de Desviaciones Térmicas y Acidez
Rama: feat/be-rules-thermal-ph

Evalúa lecturas de telemetría en tiempo real contra los perfiles óptimos de fermentación
de cada cuba y clasifica el desvío según severidades: 'media', 'alta', 'critica'.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    Cuba,
    ProcesoFermentacion,
    PerfilFermentacion,
    LecturaTelemetria
)

logger = logging.getLogger(__name__)


class RulesEngine:
    """
    Motor encargado de verificar parámetros enológicos y detectar desviaciones térmicas y de pH.
    """

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


# Instancia única para importación directa en servicios
rules_engine = RulesEngine()

