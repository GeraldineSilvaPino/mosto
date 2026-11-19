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
    from app.models import ProcesoFermentacion
    from app.services.kinetics import FEATURES
    from app.services.kinetics_query import process_kinetics
    from app.services.simulation_time import process_clock_at, observation_end
    from app.services.telemetry_v2 import utc_now

    process = db.query(ProcesoFermentacion).filter_by(id=proceso_id).first()
    if process is None:
        return None
    cutoff = utc_now()
    end = observation_end(process, cutoff, process_clock_at(db, process.id, cutoff))
    result = process_kinetics(db, process, end, received_as_of=cutoff)
    feat = result['features']
    metrics = {
        'brix_suavizado': feat['brix_mean_1h'],
        'temp_suavizada': feat['temperature_mean_1h'],
        'pendiente_brix_ventana': feat['brix_slope_6h'],
        'pendiente_temp_ventana': feat['temperature_slope_6h'],
        'turbulencia_brix_std': feat['brix_residual_std'],
        'pendiente_unidad': 'hora', 'metodo': 'temporal_experimental'
    }
    pending = dict(riesgo_pct=None, estado_ia='RECOLECTANDO_DATOS', alerta_ia=False,
                   mensaje='Reuniendo lecturas suficientes para evaluar la tendencia.', **metrics)
    if result['evidence']['source'] != ['simulado']:
        return {**pending, 'estado_ia': 'NO_VALIDADO',
                'mensaje': 'Modelo experimental disponible solo para simulación.'}
    if not result['eligible']:
        return pending
    try:
        model = get_calibrated_model()
        if model is None:
            return {**pending, 'estado_ia': 'NO_VALIDADO', 'mensaje': 'Modelo temporal no disponible.'}
        x = np.array([[feat[k] for k in FEATURES]], dtype=float)
        score = model['classifier'].decision_function(x).reshape(-1, 1)
        prob = float(model['calibrator'].predict_proba(score)[0, 1])
        if not np.isfinite(prob) or not 0 <= prob <= 1:
            raise ValueError('Invalid model probability')
    except Exception as error:
        logger.error('Temporal inference failed: %s', type(error).__name__)
        return {**pending, 'estado_ia': 'ERROR', 'mensaje': 'No se pudo evaluar el modelo temporal.'}
    threshold = model.get('threshold', .2189)
    state = 'CRITICO' if prob >= .4 else 'ADVERTENCIA' if prob >= threshold else 'NORMAL'
    return dict(riesgo_pct=round(prob * 100, 1), estado_ia=state, alerta_ia=state == 'CRITICO',
                mensaje='Estimación experimental sobre las últimas 24 horas de simulación.', **metrics)


def ventana_modelo_legacy(db, proceso_id, limite):
    """Sample the continuous stream at the legacy model's 0.25 h training cadence."""
    from datetime import timedelta
    from app.models import LecturaTelemetria as Lectura
    from app.services.telemetry_v2 import utc_now

    query = db.query(Lectura.timestamp, Lectura.brix, Lectura.temp_mosto, Lectura.origen_dato).filter(
        Lectura.fermentacion_id == proceso_id, Lectura.lectura_valida.is_(True),
        Lectura.timestamp <= utc_now(), Lectura.brix.isnot(None), Lectura.temp_mosto.isnot(None)
    ).order_by(Lectura.timestamp.desc(), Lectura.id.desc())
    latest = query.first()
    if latest is None:
        return []
    source = query.filter(Lectura.origen_dato == latest.origen_dato)
    if latest.origen_dato != "simulado_legacy":
        return source.limit(limite).all()

    # Each pair of ESP packets describes one observation. Counting packets as
    # separate model steps makes ordinary fermentation look artificially flat.
    samples = [latest]
    for step in range(1, limite):
        target = latest.timestamp - timedelta(minutes=15 * step)
        sample = source.filter(Lectura.timestamp <= target,
                               Lectura.timestamp > target - timedelta(minutes=15)).first()
        if sample is None:
            break
        samples.append(sample)
    return samples


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
        if b is not None and t is not None and np.isfinite(float(b)) and np.isfinite(float(t))
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
            "mensaje": "El Brix medio de las últimas tres muestras está en el tramo final (≤ 2,5 °Bx). El modelo asigna 0 % de riesgo.",
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

    # Use one estimator throughout the window. The former hard thresholds at
    # Brix=20 and slope=-.01 replaced the model with 3-18%, causing jumps back
    # to ~98% for virtually identical readings on either side of a threshold.
    estado_ia = 'CRITICO' if riesgo_pct >= 70 else 'ADVERTENCIA' if riesgo_pct >= 40 else 'NORMAL'
    alerta_ia = estado_ia == 'CRITICO'
    mensaje = ('Riesgo crítico de parada' if alerta_ia else 'Estimación de riesgo') + f' en simulación: {riesgo_pct:.1f}%.'

    return {
        "riesgo_pct": riesgo_pct,
        "estado_ia": estado_ia,
        "alerta_ia": alerta_ia,
        "mensaje": mensaje,
        **metricas
    }

