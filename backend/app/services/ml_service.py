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

# Singleton en memoria para carga única
_model_instance = None


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


def evaluar_riesgo_parada_cuba(
    lecturas_brix: List[float],
    lecturas_temp: List[float]
) -> Dict[str, Any]:
    """
    Evalúa el riesgo de parada de fermentación en una cuba a partir de las series históricas
    de grados Brix y temperatura (orden cronológico ascendente: de más antigua a más reciente).

    Retorna un diccionario con:
    - riesgo_pct: float (0.0 a 100.0)
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
            "riesgo_pct": 0.0,
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
    except Exception as e:
        logger.error(f"[MLService] Error ejecutando inferencia del modelo: {e}")
        return {
            "riesgo_pct": 0.0,
            "estado_ia": "ERROR",
            "alerta_ia": False,
            "mensaje": f"Error en inferencia de IA: {str(e)}",
            **metricas
        }

    # Clasificación según umbrales de negocio
    if riesgo_pct >= 70.0:
        estado_ia = "CRITICO"
        alerta_ia = True
        mensaje = f"Predicción IA: Riesgo crítico de parada de fermentación ({riesgo_pct}%). Estancamiento de consumo de azúcar detectado."
    elif riesgo_pct >= 40.0:
        estado_ia = "ADVERTENCIA"
        alerta_ia = False
        mensaje = f"Predicción IA: Riesgo moderado de estancamiento ({riesgo_pct}%). Monitorear evolución térmica y azúcares."
    else:
        estado_ia = "NORMAL"
        alerta_ia = False
        mensaje = f"Predicción IA: Cinética de fermentación saludable ({riesgo_pct}% de riesgo). Consumo normal de azúcares."

    return {
        "riesgo_pct": riesgo_pct,
        "estado_ia": estado_ia,
        "alerta_ia": alerta_ia,
        "mensaje": mensaje,
        **metricas
    }

