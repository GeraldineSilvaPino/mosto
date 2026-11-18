"""
Servicio de Inferencia de Machine Learning (MOSTO)
Detección Temprana de Paradas de Fermentación ("Stuck Fermentation").
Modelo: GradientBoostingClassifier con 5 features enológicas.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import warnings

# Compatibilidad para des-serialización de Cython en scikit-learn
import sys
try:
    import sklearn._loss._loss
    sys.modules['_loss'] = sklearn._loss._loss
except (ImportError, AttributeError):
    pass

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Ubicación del archivo de modelo serializado
MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "modelo_parada_fermentacion.pkl"
CALIBRATED_MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "calibrated_kinetics_model.joblib"

# Singleton en memoria para carga única
_model_instance = None
_calibrated_model_instance = None


def get_model():
    """Carga y retorna la instancia singleton del modelo en memoria."""
    global _model_instance
    if _model_instance is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"No se encontró el modelo de Machine Learning en: {MODEL_PATH}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _model_instance = joblib.load(MODEL_PATH)
        logger.info(f"[MLService] Modelo cargado exitosamente desde {MODEL_PATH}")
    return _model_instance


def get_calibrated_model():
    """Carga y retorna el modelo cinético calibrado temporal."""
    global _calibrated_model_instance
    if _calibrated_model_instance is None:
        if not CALIBRATED_MODEL_PATH.exists():
            logger.warning("[MLService] Modelo calibrado no encontrado en %s", CALIBRATED_MODEL_PATH)
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _calibrated_model_instance = joblib.load(CALIBRATED_MODEL_PATH)
        logger.info(f"[MLService] Modelo cinético calibrado cargado exitosamente desde {CALIBRATED_MODEL_PATH}")
    return _calibrated_model_instance


def evaluar_proceso_cinetica(db, proceso_id: int) -> Optional[Dict[str, Any]]:
    """
    Evalúa la cinética y riesgo predictivo de parada sobre la telemetría v2 auditada.
    Utiliza el clasificador logístico calibrado y proyector Ridge (contrato kinetics-v1).
    """
    from datetime import datetime, timezone
    from app.models import MensajeTelemetria, ProcesoFermentacion
    from app.services.kinetics import Observation, extract, FEATURES
    from app.services.telemetry_v2 import aware

    proceso = db.query(ProcesoFermentacion).filter_by(id=proceso_id).first()
    if not proceso:
        return None

    last_msg = db.query(MensajeTelemetria).filter_by(fermentacion_id=proceso_id).order_by(MensajeTelemetria.observado_en.desc()).first()
    if not last_msg:
        return {
            "riesgo_pct": None,
            "estado_ia": "RECOLECTANDO_DATOS",
            "alerta_ia": False,
            "mensaje": "Sin telemetría disponible para cálculo predictivo.",
            "brix_suavizado": None,
            "temp_suavizada": None,
            "pendiente_brix_ventana": None,
            "pendiente_temp_ventana": None,
            "turbulencia_brix_std": None,
        }

    as_of = max(datetime.now(timezone.utc), aware(last_msg.observado_en))
    rows = (
        db.query(MensajeTelemetria)
        .filter(
            MensajeTelemetria.fermentacion_id == proceso_id,
            MensajeTelemetria.observado_en <= as_of,
        )
        .order_by(MensajeTelemetria.observado_en)
        .all()
    )

    obs = [
        Observation(
            process_id=r.fermentacion_id,
            observed_at=aware(r.observado_en),
            received_at=aware(r.recibido_en),
            brix=r.brix,
            temperature=r.temperatura,
            brix_quality=r.calidad_brix,
            temperature_quality=r.calidad_temperatura,
            calibration_id=r.calibracion_id,
            device_id=r.dispositivo_id,
            source=r.origen,
        )
        for r in rows
    ]

    res = extract(
        obs,
        process_id=proceso_id,
        process_start=aware(proceso.fecha_inicio),
        as_of=as_of,
        received_as_of=as_of,
    )
    feat = res["features"]
    model_data = get_calibrated_model()

    # Si la fermentación concluyó
    last_brix = feat["brix_mean_1h"] if feat["brix_mean_1h"] is not None else rows[-1].brix
    if last_brix is not None and last_brix <= 2.5:
        return {
            "riesgo_pct": 0.0,
            "estado_ia": "FINALIZADA",
            "alerta_ia": False,
            "mensaje": "Fermentación concluida normalmente (Brix aparente <= 2.5).",
            "brix_suavizado": round(float(last_brix), 2),
            "temp_suavizada": round(float(rows[-1].temperatura), 2),
            "pendiente_brix_ventana": 0.0,
            "pendiente_temp_ventana": 0.0,
            "turbulencia_brix_std": 0.0,
        }

    if res["eligible"] and model_data:
        classifier = model_data["classifier"]
        calibrator = model_data["calibrator"]
        forecaster = model_data["forecaster"]
        threshold = model_data.get("threshold", 0.2189)

        X = np.array([[feat[k] for k in FEATURES]], dtype=float)
        score = classifier.decision_function(X).reshape(-1, 1)
        prob = float(calibrator.predict_proba(score)[0, 1])
        riesgo_pct = round(prob * 100.0, 1)
        forecast_brix = float(forecaster.predict(X)[0])

        if prob >= 0.40:
            estado_ia = "CRITICO"
            alerta_ia = True
            mensaje = (
                f"Riesgo crítico de parada detectado ({riesgo_pct}%). "
                f"Caída de Brix estancada ({feat['brix_slope_6h']:+.4f} °Bx/h en 6h). "
                f"Proyección a 24h: {forecast_brix:.2f} °Bx."
            )
        elif prob >= threshold:
            estado_ia = "ADVERTENCIA"
            alerta_ia = False
            mensaje = (
                f"Ralentización de fermentación detectada ({riesgo_pct}%). "
                f"Tasa de caída {feat['brix_slope_6h']:+.4f} °Bx/h. "
                f"Proyección a 24h: {forecast_brix:.2f} °Bx."
            )
        else:
            estado_ia = "NORMAL"
            alerta_ia = False
            mensaje = (
                f"Cinética de fermentación saludable ({riesgo_pct}% de riesgo). "
                f"Consumo de azúcar a {feat['brix_slope_6h']:+.4f} °Bx/h. "
                f"Proyección a 24h: {forecast_brix:.2f} °Bx."
            )

        return {
            "riesgo_pct": riesgo_pct,
            "estado_ia": estado_ia,
            "alerta_ia": alerta_ia,
            "mensaje": mensaje,
            "brix_suavizado": round(float(feat["brix_mean_1h"]), 2) if feat["brix_mean_1h"] is not None else None,
            "temp_suavizada": round(float(feat["temperature_mean_1h"]), 2) if feat["temperature_mean_1h"] is not None else None,
            "pendiente_brix_ventana": round(float(feat["brix_slope_6h"]), 4) if feat["brix_slope_6h"] is not None else None,
            "pendiente_temp_ventana": round(float(feat["temperature_slope_6h"]), 4) if feat["temperature_slope_6h"] is not None else None,
            "turbulencia_brix_std": round(float(feat["brix_residual_std"]), 4) if feat["brix_residual_std"] is not None else None,
        }
    else:
        # Fase inicial (<24 horas acumuladas o período lag de inicio)
        recent = rows[-12:]
        b = [r.brix for r in recent if r.brix is not None]
        t = [r.temperatura for r in recent if r.temperatura is not None]
        hrs = np.array([(aware(r.observado_en) - aware(recent[0].observado_en)).total_seconds() / 3600 for r in recent])

        slope_b = float(np.polyfit(hrs, b, 1)[0]) if len(hrs) > 1 and hrs[-1] > 0 else 0.0
        slope_t = float(np.polyfit(hrs, t, 1)[0]) if len(hrs) > 1 and hrs[-1] > 0 else 0.0
        std_b = float(np.std(b)) if b else 0.0
        mean_b = float(np.mean(b[-3:])) if b else None
        mean_t = float(np.mean(t[-3:])) if t else None

        age = feat.get("age_hours", len(rows) * 5 / 60)
        if mean_t is not None and mean_t > 30.0:
            riesgo_pct = round(min(88.0, 45.0 + (mean_t - 30.0) * 8.0), 1)
            estado_ia = "CRITICO" if riesgo_pct >= 70.0 else "ADVERTENCIA"
            alerta_ia = bool(riesgo_pct >= 70.0)
            mensaje = (
                f"Estrés térmico severo ({mean_t:.1f} °C) en fase temprana ({age:.1f}h). "
                f"Riesgo elevado de parada por choque térmico en levaduras."
            )
        elif mean_t is not None and mean_t < 15.0:
            riesgo_pct = 52.0
            estado_ia = "ADVERTENCIA"
            alerta_ia = False
            mensaje = f"Inercia térmica baja ({mean_t:.1f} °C). Cinética ralentizada por baja temperatura."
        else:
            riesgo_pct = 3.0
            estado_ia = "NORMAL"
            alerta_ia = False
            mensaje = (
                f"Fase de inicio de fermentación ({age:.1f}h de evolución). "
                f"Cinética nominal en curso; velocidad Brix: {slope_b:+.4f} °Bx/h. "
                f"Banda térmica óptima ({mean_t:.1f} °C)."
            )

        return {
            "riesgo_pct": riesgo_pct,
            "estado_ia": estado_ia,
            "alerta_ia": alerta_ia,
            "mensaje": mensaje,
            "brix_suavizado": round(mean_b, 2) if mean_b is not None else None,
            "temp_suavizada": round(mean_t, 2) if mean_t is not None else None,
            "pendiente_brix_ventana": round(slope_b, 4),
            "pendiente_temp_ventana": round(slope_t, 4),
            "turbulencia_brix_std": round(std_b, 4),
        }


def evaluar_riesgo_parada_cuba(
    lecturas_brix: List[float],
    lecturas_temp: List[float]
) -> Dict[str, Any]:
    """
    Evalúa el riesgo de parada de fermentación en una cuba a partir de las series históricas
    de grados Brix y temperatura (orden cronológico ascendente: de más antigua a más reciente).

    Retorna un diccionario con:
    - riesgo_pct: float (0.0 a 100.0) o None cuando falta la estimación
    - estado_ia: "RECOLECTANDO_DATOS" | "FINALIZADA" | "NORMAL" | "ADVERTENCIA" | "CRITICO"
    - alerta_ia: bool (True si riesgo_pct >= 70.0)
    - mensaje: str
    - brix_suavizado: float | None
    - temp_suavizada: float | None
    - pendiente_brix_ventana: float | None
    - pendiente_temp_ventana: float | None
    - turbulencia_brix_std: float | None
    """
    # Filtrar valores nulos o inválidos conservando sincronía
    pares_validos = [
        (float(b), float(t))
        for b, t in zip(lecturas_brix, lecturas_temp)
        if b is not None and t is not None
    ]

    # Regla 1: Mínimo 4 lecturas históricas para calcular pendientes y suavizado
    if len(pares_validos) < 4:
        return {
            "riesgo_pct": None,
            "estado_ia": "RECOLECTANDO_DATOS",
            "alerta_ia": False,
            "mensaje": "Calibrando ventana temporal (mínimo 4 lecturas)...",
            "brix_suavizado": None,
            "temp_suavizada": None,
            "pendiente_brix_ventana": None,
            "pendiente_temp_ventana": None,
            "turbulencia_brix_std": None
        }

    # Extraer las últimas n lecturas (idealmente hasta 12 para la ventana temporal)
    ventana = pares_validos[-12:]
    n = len(ventana)

    arr_brix = np.array([p[0] for p in ventana], dtype=float)
    arr_temp = np.array([p[1] for p in ventana], dtype=float)

    # 1. brix_suavizado: promedio (np.mean) de las últimas 3 lecturas de Brix
    brix_suavizado = float(np.mean(arr_brix[-3:]))

    # 2. temp_suavizada: promedio (np.mean) de las últimas 3 lecturas de temperatura
    temp_suavizada = float(np.mean(arr_temp[-3:]))

    # 3. pendiente_brix_ventana: pendiente lineal sobre la ventana de lecturas disponibles
    x_axis = np.arange(n)
    pendiente_brix_ventana = float(np.polyfit(x_axis, arr_brix, 1)[0])

    # 4. pendiente_temp_ventana: pendiente lineal sobre la ventana de lecturas disponibles
    pendiente_temp_ventana = float(np.polyfit(x_axis, arr_temp, 1)[0])

    # 5. turbulencia_brix_std: desviación estándar (np.std) de grados Brix en la ventana
    turbulencia_brix_std = float(np.std(arr_brix))

    metricas = {
        "brix_suavizado": round(brix_suavizado, 2),
        "temp_suavizada": round(temp_suavizada, 2),
        "pendiente_brix_ventana": round(pendiente_brix_ventana, 4),
        "pendiente_temp_ventana": round(pendiente_temp_ventana, 4),
        "turbulencia_brix_std": round(turbulencia_brix_std, 4)
    }

    # Regla 2: Si brix_suavizado <= 2.5, fermentación concluida normalmente
    if brix_suavizado <= 2.5:
        return {
            "riesgo_pct": 0.0,
            "estado_ia": "FINALIZADA",
            "alerta_ia": False,
            "mensaje": "Fermentación concluida normalmente (Brix <= 2.5)",
            **metricas
        }

    # Construir DataFrame con las 5 features exactas en el orden en que fue entrenado el modelo
    feature_names = [
        "brix_suavizado",
        "temp_suavizada",
        "pendiente_brix_ventana",
        "pendiente_temp_ventana",
        "turbulencia_brix_std"
    ]
    df_features = pd.DataFrame([{
        "brix_suavizado": brix_suavizado,
        "temp_suavizada": temp_suavizada,
        "pendiente_brix_ventana": pendiente_brix_ventana,
        "pendiente_temp_ventana": pendiente_temp_ventana,
        "turbulencia_brix_std": turbulencia_brix_std
    }])[feature_names]

    try:
        model = get_model()
        # predict_proba retorna probabilidades [prob_normal, prob_parada]
        prob_parada = float(model.predict_proba(df_features)[0][1])
        riesgo_pct = round(prob_parada * 100.0, 1)
    except Exception as error:
        logger.error("Error de inferencia del baseline: %s", type(error).__name__)
        return {
            "riesgo_pct": None,
            "estado_ia": "ERROR",
            "alerta_ia": False,
            "mensaje": "No se pudo calcular la estimación de riesgo.",
            **metricas
        }

    # Calibración enológica sobre inferencia:
    # 1. En fase inicial (Brix > 20.0 °Bx) con temperatura en banda óptima (18 - 26.5 °C),
    #    la fermentación se encuentra en período lag/adaptación. El micro-ruido del sensor
    #    en lecturas de 5s no debe disparar falsas paradas críticas.
    if brix_suavizado > 20.0 and 18.0 <= temp_suavizada <= 26.5:
        riesgo_pct = round(max(2.5, min(9.5, 4.0 + max(0.0, pendiente_brix_ventana) * 50.0)), 1)
        estado_ia = "NORMAL"
        alerta_ia = False
        mensaje = f"Fase de inicio / adaptación (Brix {brix_suavizado:.1f} °Bx). Cinética nominal en curso a {temp_suavizada:.1f} °C."
    elif 18.0 <= temp_suavizada <= 26.5 and pendiente_brix_ventana < -0.01:
        riesgo_pct = round(max(1.0, min(18.0, 8.0 + (pendiente_brix_ventana + 0.03) * 150.0)), 1)
        estado_ia = "NORMAL"
        alerta_ia = False
        mensaje = f"Cinética de fermentación saludable ({riesgo_pct}% de riesgo). Consumo normal de azúcares."
    elif temp_suavizada > 30.0:
        riesgo_pct = round(min(95.0, 65.0 + (temp_suavizada - 30.0) * 5.0), 1)
        estado_ia = "CRITICO" if riesgo_pct >= 70.0 else "ADVERTENCIA"
        alerta_ia = bool(riesgo_pct >= 70.0)
        mensaje = f"Alerta térmica: temperatura elevada ({temp_suavizada:.1f} °C). Riesgo de parada por choque térmico."
    elif temp_suavizada < 16.0:
        riesgo_pct = round(min(80.0, 50.0 + (16.0 - temp_suavizada) * 6.0), 1)
        estado_ia = "ADVERTENCIA"
        alerta_ia = False
        mensaje = f"Temperatura baja ({temp_suavizada:.1f} °C). Cinética ralentizada por frío."
    else:
        # Clasificación estándar calibrada para fase media
        if riesgo_pct >= 70.0:
            estado_ia = "CRITICO"
            alerta_ia = True
            mensaje = f"Riesgo crítico de parada de fermentación ({riesgo_pct}%). Estancamiento de consumo de azúcar detectado."
        elif riesgo_pct >= 40.0:
            estado_ia = "ADVERTENCIA"
            alerta_ia = False
            mensaje = f"Riesgo moderado de estancamiento ({riesgo_pct}%). Monitorear evolución térmica y azúcares."
        else:
            estado_ia = "NORMAL"
            alerta_ia = False
            mensaje = f"Cinética de fermentación saludable ({riesgo_pct}% de riesgo). Consumo normal de azúcares."

    return {
        "riesgo_pct": riesgo_pct,
        "estado_ia": estado_ia,
        "alerta_ia": alerta_ia,
        "mensaje": mensaje,
        **metricas
    }

