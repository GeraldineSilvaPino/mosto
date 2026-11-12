# Módulo de Machine Learning — Predicción Temprana de Paradas de Fermentación

Este directorio contiene los artefactos, datos y especificación técnica del modelo de Machine Learning integrado en la plataforma **MOSTO** para la detección y predicción temprana de paradas de fermentación (*"Stuck Fermentation"*).

---

## 1. Contexto y Problema Enológico

La parada de fermentación ocurre cuando las levaduras detienen prematuramente el consumo de azúcares antes de alcanzar la sequedad deseada, dejando un nivel residual alto de grados Brix y elevando el riesgo de contaminación microbiana y degradación organoléptica del vino.

Detectar este estancamiento de forma reactiva (días después) genera pérdidas económicas sustanciales. El objetivo de este módulo es predecir con anticipación la probabilidad de estancamiento evaluando continuamente la cinética de consumo de azúcar y la temperatura de las cubas mediante lecturas de telemetría IoT.

---

## 2. Modelo de Machine Learning

- **Algoritmo:** `GradientBoostingClassifier` (scikit-learn).
- **Archivo serializado:** `backend/app/ml/modelo_parada_fermentacion.pkl`.
- **Dataset de referencia:** `backend/app/ml/dataset_fermentacion_kontogiannis.csv`.

### Features de Entrada (Exactamente 5, en orden estricto):

| # | Nombre de Feature | Descripción Enológica | Cálculo Matemático / Algorítmico |
|---|-------------------|------------------------|----------------------------------|
| 1 | `brix_suavizado` | Nivel actual de azúcar mitigando ruido de sensor | Promedio de las últimas 3 lecturas: $\bar{B} = \frac{1}{3} \sum_{i=1}^3 B_i$ |
| 2 | `temp_suavizada` | Temperatura media reciente de la cuba (°C) | Promedio de las últimas 3 lecturas: $\bar{T} = \frac{1}{3} \sum_{i=1}^3 T_i$ |
| 3 | `pendiente_brix_ventana` | Velocidad de consumo de azúcar (°Bx/muestra) | Pendiente lineal $m_B$ vía `np.polyfit(..., 1)` en ventana de 4 a 12 lecturas |
| 4 | `pendiente_temp_ventana` | Tasa de calentamiento o enfriamiento (°C/muestra) | Pendiente lineal $m_T$ vía `np.polyfit(..., 1)` en la misma ventana |
| 5 | `turbulencia_brix_std` | Inestabilidad o dispersión en la medición de azúcar | Desviación estándar muestral: $\sigma_B = \text{std}(\text{ventana\_brix})$ |

### Reglas de Negocio y Clasificación

El servicio de inferencia (`backend/app/services/ml_service.py`) aplica los siguientes criterios deterministas previos y posteriores a la inferencia:

1. **Ventana Mínima de Calibración:**
   - Si la cuba tiene menos de 4 lecturas históricas:
     - `riesgo_pct`: `0.0%`
     - `estado_ia`: `"RECOLECTANDO_DATOS"`
     - `alerta_ia`: `False`
     - `mensaje`: *"Calibrando ventana temporal (mínimo 4 lecturas)..."*
2. **Fermentación Concluida Normal:**
   - Si `brix_suavizado <= 2.5`:
     - `riesgo_pct`: `0.0%`
     - `estado_ia`: `"FINALIZADA"`
     - `alerta_ia`: `False`
     - `mensaje`: *"Fermentación concluida normalmente (Brix <= 2.5)"*
3. **Inferencia con Gradient Boosting (`predict_proba`):**
   - **`riesgo_pct >= 70.0%`**: Estado `"CRITICO"` con `alerta_ia = True`. Genera alerta en el sistema.
   - **`40.0% <= riesgo_pct < 70.0%`**: Estado `"ADVERTENCIA"` con `alerta_ia = False`. Monitoreo preventivo.
   - **`riesgo_pct < 40.0%`**: Estado `"NORMAL"` con `alerta_ia = False`. Cinética saludable.

---

## 3. Arquitectura y Componentes Implementados

### 3.1 Backend (`FastAPI` & `SQLAlchemy`)

1. **`backend/app/services/ml_service.py`:**
   - Implementa patrón Singleton con carga diferida y en memoria del archivo `.pkl`.
   - Incorpora parche de compatibilidad Cython (`sys.modules['_loss'] = sklearn._loss._loss`) para deserialización segura entre versiones de scikit-learn.
   - Función principal: `evaluar_riesgo_parada_cuba(lecturas_brix, lecturas_temp) -> dict`.

2. **`backend/app/services/rules_engine.py`:**
   - Función `evaluar_alerta_ia_parada(db, cuba, telemetria)`: Al ingresar telemetría en una fermentación activa, obtiene las últimas 12 lecturas cronológicas y consulta `ml_service`.
   - Si `alerta_ia == True`, crea un registro `EventoAlerta` (`tipo_alerta="parada_fermentacion"`, `severidad="critica"`, `met_dispar="modelo_ia_ml"`).
   - Implementa filtro deduplicador para evitar alertas duplicadas mientras exista una alerta activa (`pendiente` o `atendida`) para la misma cuba.

3. **`backend/app/routers/cubas.py`:**
   - `GET /api/cubas/{cuba_id}`: Devuelve el detalle enriquecido con el objeto `prediccion_ml`.
   - `GET /api/cubas/{cuba_id}/ml-prediction`: Endpoint REST ligero para consultar el estado del modelo en tiempo real.
   - `POST /api/cubas/{cuba_id}/simular-anomalia`: Endpoint de demostración. Inyecta lecturas sintéticas con azúcar estancado (~14.5 °Bx) y sobrecalentamiento (~31.5 °C) vinculadas al dispositivo asignado para satisfacer triggers de PostgreSQL.
   - `POST /api/cubas/{cuba_id}/restaurar-normalidad`: Resuelve la alerta activa y reinyecta lecturas con descenso normal de Brix.

4. **`backend/app/schemas.py`:**
   - `MLPredictionOut`: Esquema Pydantic con `riesgo_pct`, `estado_ia`, `alerta_ia`, métricas calculadas y diagnóstico.
   - `SimulacionAnomaliaOut`: Esquema de respuesta para las acciones de prueba y demo.

---

### 3.2 Simulador IoT de Hardware (`backend/scripts/simulate_esp.py`)

- Actualizado para generar curvas de fermentación realistas cada 5 segundos:
  - **Cubas normales:** Caída constante de azúcar (-0.03 a -0.06 °Bx por tick) a temperaturas óptimas (21 °C – 24 °C).
  - **Parada forzada:** Parámetros CLI `--stuck-cuba <CUBA_ID>`, `--stuck-after <TICKS>` o flag interactivo para simular el estancamiento de azúcar (> 10 °Bx plano) con hipertermia (30 °C – 33 °C) y comprobar el disparo de la alerta en vivo.

---

### 3.3 Frontend (`Vue 3`, `Tailwind CSS`, `Chart.js`)

1. **`frontend/src/views/CubaDetailView.vue`:**
   - Sección destacada: **"Predicción IA — Riesgo de Parada de Fermentación"**.
   - **Medidor circular SVG:** Muestra el porcentaje de riesgo con gradiente de color dinámico y animación de pulso cuando entra en estado crítico.
   - **Badges semánticos:** `CRÍTICO` (rojo), `ADVERTENCIA` (ámbar), `NORMAL` (verde) y `CALIBRANDO` (azul/gris).
   - **Tarjetas de telemetría explicable:** Muestran la velocidad de consumo de azúcar (°Bx/h), Brix actual suavizado, temperatura suavizada e inestabilidad del sensor.
   - **Controles de demostración en vivo:** Botón *"Simular Parada (Demo IA)"* y *"Restaurar Normalidad"*, permitiendo ver en tiempo real cómo cambia la aguja y se genera la alerta.

2. **`frontend/src/views/DashboardView.vue`:**
   - Insignia de estado IA visible directamente en las tarjetas de cubas y en la tabla de ranking de fermentación.

3. **`frontend/src/services/cubaService.js`:**
   - Métodos API: `obtenerPrediccionML()`, `simularAnomalia()` y `restaurarNormalidad()`.

---

## 4. Guía de Ejecución y Pruebas

### 4.1 Ejecución de Pruebas Automatizadas

```bash
# Activar entorno virtual
cd backend
venv\Scripts\activate

# Ejecutar suite de pruebas del modelo ML
pytest tests/test_ml_prediction.py -v
```

### 4.2 Demostración en Vivo

1. Iniciar el backend FastAPI:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
2. Iniciar el simulador con parada programada:
   ```bash
   python scripts/simulate_esp.py --stuck-cuba 1 --stuck-after 8
   ```
3. O bien, desde la interfaz web en el detalle de la cuba, presionar el botón **"Simular Parada (Demo IA)"**.
