"""Reproduction of the supplied Gemini notebook, retained as an experimental baseline."""
import numpy as np
import pandas as pd

NOTEBOOK_SHA256 = "ab48004946ce7b34f4c68048fb624240c686ac3fc1ce94700d018779774c10f7"

def generate_windows(n_curvas=4000, seed=42):
    """Legacy synthetic windows. Preserves the supplied notebook distribution; not a validated fermentation or future-event model."""
    rng = np.random.RandomState(seed)
    registros = []
    for curva_id in range(n_curvas):
        es_parada = rng.choice([0, 1], p=[0.7, 0.3])
        brix_0 = rng.uniform(19.5, 23.0)
        k_e = rng.uniform(0.012, 0.022)
        t_inicio = rng.uniform(18, 95)
        if es_parada == 0:
            temp_base = rng.normal(22.5, 2.8)
            deriva_temp = rng.normal(0.0, 0.04)
            factor_freno = rng.uniform(0.65, 1.15)
        else:
            causa = rng.choice(['alta_temp', 'baja_temp', 'nutrientes'], p=[0.45, 0.25, 0.3])
            if causa == 'alta_temp':
                temp_base = rng.normal(28.5, 2.2)
                deriva_temp = rng.uniform(0.03, 0.12)
            elif causa == 'baja_temp':
                temp_base = rng.normal(15.0, 1.8)
                deriva_temp = rng.uniform(-0.1, -0.02)
            else:
                temp_base = rng.normal(23.0, 2.5)
                deriva_temp = rng.normal(0.01, 0.04)
            factor_freno = rng.uniform(0.05, 0.45)
        dt_simulado = 0.25
        ventana_brix = []
        ventana_temp = []
        for paso in range(12):
            t = t_inicio + paso * dt_simulado
            k_efectivo = k_e * factor_freno
            brix_teorico = brix_0 * np.exp(-k_efectivo * (t - t_inicio)) * np.exp(-k_e * t_inicio)
            ruido_brix = rng.normal(0, 0.08)
            ruido_temp = rng.normal(0, 0.15)
            brix_medido = max(1.0, brix_teorico + ruido_brix)
            temp_medida = temp_base + paso * deriva_temp + ruido_temp
            ventana_brix.append(brix_medido)
            ventana_temp.append(temp_medida)
        brix_actual = np.mean(ventana_brix[-3:])
        temp_actual = np.mean(ventana_temp[-3:])
        x_tiempo = np.arange(12)
        pendiente_brix = np.polyfit(x_tiempo, ventana_brix, 1)[0]
        pendiente_temp = np.polyfit(x_tiempo, ventana_temp, 1)[0]
        std_brix = np.std(ventana_brix)
        registros.append({'brix_suavizado': round(brix_actual, 2), 'temp_suavizada': round(temp_actual, 2), 'pendiente_brix_ventana': round(pendiente_brix, 4), 'pendiente_temp_ventana': round(pendiente_temp, 4), 'turbulencia_brix_std': round(std_brix, 4), 'riesgo_parada': es_parada})
    df = pd.DataFrame(registros)
    return df
