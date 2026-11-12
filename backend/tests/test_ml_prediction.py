"""
Pruebas unitarias y de integración para el Módulo de Inteligencia Artificial (ML)
Detección temprana de Paradas de Fermentación ("Stuck Fermentation").
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ml_service import evaluar_riesgo_parada_cuba
from app.database import SessionLocal
from app.models import Cuba, ProcesoFermentacion, LecturaTelemetria, EventoAlerta

client = TestClient(app)


def test_ml_service_insuficientes_lecturas():
    """Valida que con menos de 4 lecturas históricas retorne estado RECOLECTANDO_DATOS."""
    res = evaluar_riesgo_parada_cuba([20.0, 19.5, 19.0], [22.0, 22.1, 22.0])
    assert res["estado_ia"] == "RECOLECTANDO_DATOS"
    assert res["riesgo_pct"] == 0.0
    assert res["alerta_ia"] is False
    assert "mínimo 4" in res["mensaje"]


def test_ml_service_fermentacion_finalizada():
    """Valida que si brix_suavizado <= 2.5 retorne estado FINALIZADA."""
    res = evaluar_riesgo_parada_cuba([3.0, 2.4, 2.2, 2.0], [21.0, 21.0, 21.0, 21.0])
    assert res["estado_ia"] == "FINALIZADA"
    assert res["riesgo_pct"] == 0.0
    assert res["alerta_ia"] is False
    assert res["brix_suavizado"] <= 2.5


def test_ml_service_fermentacion_saludable():
    """Valida que con caída constante de Brix el modelo prediga riesgo NORMAL (< 40%)."""
    # 8 lecturas con pendiente negativa pronunciada y temp normal
    brix_saludable = [22.0, 21.2, 20.4, 19.6, 18.8, 18.0, 17.2, 16.4]
    temp_saludable = [22.0, 22.1, 22.0, 22.2, 22.1, 22.0, 22.1, 22.0]
    res = evaluar_riesgo_parada_cuba(brix_saludable, temp_saludable)
    assert res["estado_ia"] == "NORMAL"
    assert res["riesgo_pct"] < 40.0
    assert res["alerta_ia"] is False
    assert res["pendiente_brix_ventana"] < -0.05


def test_ml_service_parada_critica():
    """Valida que con azúcar estancado (~14.5) y alta temperatura el modelo prediga CRITICO (>= 70%)."""
    brix_estancado = [14.51, 14.50, 14.49, 14.50, 14.50, 14.52, 14.50, 14.51]
    temp_elevada = [29.0, 30.0, 30.8, 31.5, 32.0, 32.3, 32.5, 32.8]
    res = evaluar_riesgo_parada_cuba(brix_estancado, temp_elevada)
    assert res["estado_ia"] == "CRITICO"
    assert res["riesgo_pct"] >= 70.0
    assert res["alerta_ia"] is True
    assert "Riesgo crítico de parada" in res["mensaje"]


def test_api_obtener_prediccion_ml():
    """Valida el endpoint GET /api/cubas/{id}/ml-prediction."""
    res = client.get("/api/cubas/1/ml-prediction")
    assert res.status_code == 200
    data = res.json()
    assert "riesgo_pct" in data
    assert "estado_ia" in data
    assert "alerta_ia" in data
    assert "mensaje" in data


def test_api_simular_anomalia_y_generacion_alerta():
    """Valida el endpoint POST /api/cubas/{id}/simular-anomalia y creación de alerta."""
    cuba_id = 1
    res = client.post(f"/api/cubas/{cuba_id}/simular-anomalia")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["cuba_id"] == cuba_id
    assert data["lecturas_inyectadas"] >= 6
    assert data["prediccion_ml"]["estado_ia"] == "CRITICO"
    assert data["prediccion_ml"]["alerta_ia"] is True
    assert data["prediccion_ml"]["riesgo_pct"] >= 70.0

    # Verificar que se generó la alerta en la base de datos
    db = SessionLocal()
    try:
        proceso = (
            db.query(ProcesoFermentacion)
            .filter(ProcesoFermentacion.cuba_id == cuba_id, ProcesoFermentacion.estado == "en_proceso")
            .order_by(ProcesoFermentacion.id.desc())
            .first()
        )
        assert proceso is not None
        alerta = (
            db.query(EventoAlerta)
            .filter(
                EventoAlerta.fermentacion_id == proceso.id,
                EventoAlerta.tipo_alerta == "parada_fermentacion",
                EventoAlerta.estado == "pendiente"
            )
            .first()
        )
        assert alerta is not None
        assert alerta.severidad == "critica"
        assert "Predicción IA" in alerta.mensaje

        # Verificar anti-duplicidad: simular nuevamente no debe duplicar la alerta activa
        res_dup = client.post(f"/api/cubas/{cuba_id}/simular-anomalia")
        assert res_dup.status_code == 200
        conteo_alertas = (
            db.query(EventoAlerta)
            .filter(
                EventoAlerta.fermentacion_id == proceso.id,
                EventoAlerta.tipo_alerta == "parada_fermentacion",
                EventoAlerta.estado == "pendiente"
            )
            .count()
        )
        assert conteo_alertas == 1, "No debe duplicar alertas abiertas de parada de fermentación"
    finally:
        db.close()


def test_api_restaurar_normalidad():
    """Valida el endpoint POST /api/cubas/{id}/restaurar-normalidad."""
    cuba_id = 1
    res = client.post(f"/api/cubas/{cuba_id}/restaurar-normalidad")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["prediccion_ml"]["estado_ia"] == "NORMAL"
    assert data["prediccion_ml"]["alerta_ia"] is False
    assert data["prediccion_ml"]["riesgo_pct"] < 40.0

    # Verificar que la alerta previa fue resuelta
    db = SessionLocal()
    try:
        alertas_pendientes = (
            db.query(EventoAlerta)
            .filter(
                EventoAlerta.tipo_alerta == "parada_fermentacion",
                EventoAlerta.estado == "pendiente"
            )
            .count()
        )
        assert alertas_pendientes == 0
    finally:
        db.close()

