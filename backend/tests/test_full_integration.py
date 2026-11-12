"""
Pruebas de integración automatizadas para los nuevos módulos:
Autenticación, Usuarios & Roles, Configuración de Empresa, Bitácora Enológica y Catálogos Maestros.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_auth_login_success_and_me():
    # 1. Login con enólogo
    res_enologo = client.post("/api/auth/login", json={
        "email": "enologo@mosto.cl",
        "password": "vinacura2024",
        "remember_me": True
    })
    assert res_enologo.status_code == 200
    data_enologo = res_enologo.json()
    assert "access_token" in data_enologo
    assert data_enologo["user"]["email"] == "enologo@mosto.cl"

    token = data_enologo["access_token"]

    # 2. Consultar perfil con Bearer token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "enologo@mosto.cl"


def test_auth_login_invalid_credentials():
    res = client.post("/api/auth/login", json={
        "email": "enologo@mosto.cl",
        "password": "clave_totalmente_incorrecta"
    })
    assert res.status_code == 401


def test_auth_password_recovery():
    res = client.post("/api/auth/recuperar-password", json={
        "email": "enologo@mosto.cl"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_usuarios_crud_and_status():
    # Listar
    res_list = client.get("/api/usuarios")
    assert res_list.status_code == 200
    usuarios = res_list.json()
    assert len(usuarios) >= 1

    # Crear nuevo usuario de prueba
    import time
    test_email = f"test.enologo.{int(time.time() * 1000)}@vinamosto.cl"
    res_crear = client.post("/api/usuarios", json={
        "name": "Enólogo de Pruebas",
        "email": test_email,
        "role": "enologo",
        "password": "testpassword2026"
    })
    assert res_crear.status_code in (200, 201)
    nuevo_id = res_crear.json()["id"]

    # Cambiar rol
    res_rol = client.patch(f"/api/usuarios/{nuevo_id}/rol", json={"role": "admin"})
    assert res_rol.status_code == 200
    assert res_rol.json()["role"] == "admin"

    # Suspender usuario
    res_estado = client.patch(f"/api/usuarios/{nuevo_id}/estado", json={"active": False})
    assert res_estado.status_code == 200
    assert res_estado.json()["active"] is False


def test_company_config_and_upgrade():
    # Obtener configuración
    res_get = client.get("/api/empresa")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "brandName" in data
    assert "saasQuota" in data
    capacidad_actual = data["saasQuota"]["maxCubas"]

    # Actualizar datos
    res_put = client.put("/api/empresa", json={
        "brandName": "Viña Santa Emiliana",
        "dailyEnologyReport": True
    })
    assert res_put.status_code == 200
    assert res_put.json()["brandName"] == "Viña Santa Emiliana"

    # Solicitar ampliación de cuota
    res_up = client.post("/api/empresa/ampliacion", json={"extra_cubas": 6})
    assert res_up.status_code == 200
    assert res_up.json()["nueva_capacidad"] == capacidad_actual + 6


def test_binnacle_flow():
    # Listar entradas
    res_list = client.get("/api/bitacora")
    assert res_list.status_code == 200
    entradas = res_list.json()
    assert isinstance(entradas, list)

    # Registrar nueva entrada
    res_post = client.post("/api/bitacora", json={
        "type": "nota",
        "cuba": "cuba-01",
        "message": "Prueba automatizada de registro de intervención enológica",
        "author": "Enología & Control"
    })
    assert res_post.status_code == 201
    entry = res_post.json()
    assert entry["type"] == "nota"
    assert "Prueba automatizada" in entry["message"]


def test_master_catalogs():
    res_cepas = client.get("/api/cepas")
    assert res_cepas.status_code == 200
    assert len(res_cepas.json()) >= 1

    res_mat = client.get("/api/materiales-cuba")
    assert res_mat.status_code == 200
    assert len(res_mat.json()) >= 1

