"""Adversarial HTTP tests: two companies and mixed roles in two warehouses."""
from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import aliased
from fastapi import HTTPException

from app import models as m
from app.database import SessionLocal
from app.services.access import AccessContext, install_scope
from app.services.auth_service import create_access_token


@pytest.fixture
def tenants():
    with SessionLocal() as db:
        other = m.EmpresaCliente(nomb_emp="Foreign company")
        db.add(other); db.flush()
        second = m.Bodega(nombre="Same company restricted", empresa_id=1)
        foreign = m.Bodega(nombre="Foreign warehouse", empresa_id=other.id)
        db.add_all([second, foreign]); db.flush()
        roles = {r.codigo: r.id for r in db.query(m.Rol)}
        member = m.Usuario(nomb_compl="Scoped operator", correo_elec="operator@example.invalid",
                           empresa_id=1, rol="admin", activo=True)
        stranger = m.Usuario(nomb_compl="Foreign admin", correo_elec="foreign@example.invalid",
                             empresa_id=other.id, rol="admin", activo=True)
        db.add_all([member, stranger]); db.flush()
        db.add_all([
            m.UsuarioBodega(usuario_id=1, bodega_id=second.id, rol_id=roles["admin"]),
            m.UsuarioBodega(usuario_id=member.id, bodega_id=1, rol_id=roles["operador"]),
            m.UsuarioBodega(usuario_id=member.id, bodega_id=second.id, rol_id=roles["lector"]),
            m.UsuarioBodega(usuario_id=stranger.id, bodega_id=foreign.id, rol_id=roles["admin"]),
        ])
        refs = {}
        for label, warehouse, company in (("second", second, 1), ("foreign", foreign, other.id)):
            cube = m.Cuba(codigo=label.upper(), bodega_id=warehouse.id, cap_litros=10000)
            profile = m.PerfilFermentacion(nomb_perfil=label, bodega_id=warehouse.id,
                                           cepa_id=1, temp_min=18, temp_max=26, activo=True)
            device = m.Dispositivo(mac_address=label, empresa_id=company, modelo_id=1, tipo_dispositivo="DUAL")
            db.add_all([cube, profile, device]); db.flush()
            process = m.ProcesoFermentacion(cuba_id=cube.id, perfil_id=profile.id, estado="en_proceso")
            db.add(process); db.flush()
            alert = m.EventoAlerta(fermentacion_id=process.id, dispositivo_id=device.id,
                                  tipo_alerta="temp_alta", mensaje=label, severidad="critica")
            db.add_all([alert, m.AsignacionDispositivo(dispositivo_id=device.id, cuba_id=cube.id, activo=True),
                        m.LecturaTelemetria(dispositivo_id=device.id, fermentacion_id=process.id,
                                           temp_mosto=22, brix=18),
                        m.BitacoraIntervencion(usuario_id=stranger.id if label == "foreign" else 1,
                                              cuba_id=cube.id, fermentacion_id=process.id,
                                              tipo_intervencion="nota", descripcion=label)])
            db.flush()
            refs[label] = dict(cube=cube.id, process=process.id, profile=profile.id,
                               device=device.id, alert=alert.id, warehouse=warehouse.id)
        own_alert = m.EventoAlerta(fermentacion_id=1, dispositivo_id=1, tipo_alerta="temp_baja")
        db.add(own_alert); db.flush()
        refs.update(member=member.id, stranger=stranger.id, company=other.id, own_alert=own_alert.id)
        db.commit()
        return refs


def as_user(client, user):
    # A forged role claim in a legitimately signed token must not grant access.
    client.headers["Authorization"] = "Bearer " + create_access_token({"sub": user, "role": "admin"})


def test_company_lists_details_metrics_export_and_cache_isolation(client, tenants):
    foreign = tenants["foreign"]
    resources = {"cubas": "cube", "procesos": "process", "perfiles": "profile",
                 "dispositivos": "device", "alertas": "alert"}
    # Alternate identities to detect accidentally cached scope values.
    for user in (1, tenants["stranger"], 1):
        as_user(client, user)
        for resource, key in resources.items():
            response = client.get(f"/api/{resource}")
            assert response.status_code == 200, response.text
            ids = {row["id"] for row in response.json()}
            assert (foreign[key] in ids) == (user == tenants["stranger"])
    for resource, key in resources.items():
        assert client.get(f"/api/{resource}/{foreign[key]}").status_code == 404
    for suffix in ("historico", "ml-prediction"):
        assert client.get(f"/api/cubas/{foreign['cube']}/{suffix}").status_code == 404
    assert client.get(f"/api/procesos/{foreign['process']}/cinetica").status_code == 404
    assert client.post(f"/api/procesos/{foreign['process']}/regla-cinetica", json={}).status_code == 404
    notes = client.get("/api/bitacora").json()
    assert all(row["message"] != "foreign" for row in notes)
    assert client.get("/api/alertas/metricas").json()["total_alertas"] == 2
    csv = client.get("/api/alertas/exportar").text
    assert "FOREIGN" not in csv and "SECOND" in csv
    assert len(client.get("/api/usuarios").json()) == 2


def test_membership_roles_not_legacy_user_or_jwt_role(client, tenants):
    as_user(client, tenants["member"])
    identity = client.get("/api/auth/me").json()
    assert identity["company_admin"] is False
    assert {item["role"] for item in identity["memberships"]} == {"operador", "lector"}
    assert identity["role"] == "Roles por bodega"
    assert client.get("/api/cubas").status_code == 200
    assert client.get("/api/usuarios").status_code == 403
    assert client.put("/api/empresa", json={"brandName": "Attack"}).status_code == 403
    assert client.put("/api/perfiles/1", json={"temp_min": 10}).status_code == 403
    assert client.post("/api/cubas/1/simular-anomalia").status_code == 403
    # Reader on second warehouse, operator on the first: no implicit promotion.
    assert client.patch(f"/api/procesos/{tenants['second']['process']}/finalizar").status_code == 404
    assert client.post("/api/dispositivos/desvincular", json={
        "dispositivo_id": tenants["second"]["device"]}).status_code == 404
    assert client.patch("/api/procesos/1/finalizar").status_code == 200


def test_episode_history_and_linked_notes_respect_company_and_warehouse(client, tenants):
    foreign_id = tenants["foreign"]["alert"]
    with SessionLocal() as db:
        db.add(m.AuditoriaAlerta(alerta_id=foreign_id, accion="creada", registrado_en=datetime.now(), detalle={"secret": "foreign"}))
        db.commit()
    assert client.get(f"/api/alertas/{foreign_id}/eventos").status_code == 404
    assert client.get(f"/api/bitacora?alerta_id={foreign_id}").json() == []
    assert client.post("/api/bitacora", json={"type": "nota", "message": "Intento fuera de ámbito", "alerta_id": foreign_id}).status_code == 404
    as_user(client, tenants["member"])
    second_id = tenants["second"]["alert"]
    assert client.get(f"/api/alertas/{second_id}/eventos").status_code == 200  # Reader may inspect assigned warehouse.
    assert client.post("/api/bitacora", json={"type": "nota", "message": "Intento desde rol lector", "alerta_id": second_id}).status_code == 404


def test_unassigned_warehouse_is_not_readable_even_with_company_membership(client, tenants):
    with SessionLocal() as db:
        db.query(m.UsuarioBodega).filter_by(usuario_id=tenants["member"],
            bodega_id=tenants["second"]["warehouse"]).delete()
        db.commit()
    as_user(client, tenants["member"])
    for resource, key in {"cubas": "cube", "procesos": "process", "perfiles": "profile",
                          "dispositivos": "device", "alertas": "alert"}.items():
        assert client.get(f"/api/{resource}/{tenants['second'][key]}").status_code == 404
    assert client.get("/api/alertas/metricas").json()["total_alertas"] == 1
    assert "SECOND" not in client.get("/api/alertas/exportar").text
    assert client.get("/api/bodegas").json() == [{"id": 1, "nombre": "Bodega DEMO"}]


def test_user_creation_requires_password_warehouse_and_valid_role(client, tenants):
    payload = {"name": "New user", "email": "new@example.invalid", "role": "enologo"}
    assert client.post("/api/usuarios", json=payload).status_code == 422
    payload["password"] = "new-test-password-2026"
    assert client.post("/api/usuarios", json=payload).status_code == 422
    payload["bodega_id"] = tenants["foreign"]["warehouse"]
    assert client.post("/api/usuarios", json=payload).status_code == 404
    payload["bodega_id"] = tenants["second"]["warehouse"]
    result = client.post("/api/usuarios", json=payload)
    assert result.status_code == 201, result.text
    assert result.json()["memberships"] == [{"bodega_id": payload["bodega_id"],
        "bodega_nombre": "Same company restricted", "role": "enologo"}]
    with SessionLocal() as db:
        count = db.query(m.Usuario).count()
    payload["email"] = "foreign@example.invalid"
    assert client.post("/api/usuarios", json=payload).status_code == 409
    with SessionLocal() as db:
        assert db.query(m.Usuario).count() == count


def test_cross_scope_writes_are_rejected_without_partial_rows(client, tenants):
    foreign = tenants["foreign"]
    with SessionLocal() as db:
        before = db.query(m.Dispositivo).count()
    response = client.post("/api/dispositivos", json={
        "code": "NEW", "name": "New device",
        "mac": "01:02:03:04:05:06", "model": "Virtual legacy", "sensorType": "DUAL",
        "cubaId": str(foreign["cube"])})
    assert response.status_code == 404, response.text
    assert client.post("/api/dispositivos/vincular", json={
        "dispositivo_id": 1, "cuba_id": foreign["cube"]}).status_code == 404
    assert client.put("/api/perfiles/1", json={"bodega_id": foreign["warehouse"]}).status_code == 404
    assert client.patch(f"/api/usuarios/{tenants['stranger']}/estado", json={"active": False}).status_code == 404
    assert client.post("/api/bitacora", json={"type": "nota", "message": "Attack",
                                             "cuba": str(foreign["cube"])}).status_code == 404
    with SessionLocal() as db:
        assert db.query(m.Dispositivo).count() == before
        assert db.get(m.Usuario, tenants["stranger"]).activo


def test_actor_is_authenticated_user_and_last_admin_is_preserved(client, tenants):
    as_user(client, tenants["member"])
    response = client.patch(f"/api/alertas/{tenants['own_alert']}/atender",
                            json={"usuario_id": tenants["stranger"], "nota": "Inspección"})
    assert response.status_code == 200, response.text
    assert response.json()["atendida_por"] == tenants["member"]
    note = client.post("/api/bitacora", json={"type": "nota", "cuba": "1",
                                            "message": "Inspección", "author": "Foreign admin"})
    assert note.status_code == 201, note.text
    assert note.json()["author"] == "Scoped operator"
    as_user(client, 1)
    assert client.patch("/api/usuarios/1/estado", json={"active": False}).status_code == 409
    assert client.patch("/api/usuarios/1/rol", json={"role": "operario", "bodega_id": 1}).status_code == 409
    assert client.patch("/api/usuarios/1/rol", json={"role": "superadmin"}).status_code == 422


def test_inactive_company_and_revoked_membership_rechecked(client, tenants):
    as_user(client, tenants["member"])
    assert client.get("/api/cubas").status_code == 200
    with SessionLocal() as db:
        db.query(m.UsuarioBodega).filter_by(usuario_id=tenants["member"]).delete()
        db.commit()
    assert client.get("/api/cubas").status_code == 403
    as_user(client, tenants["stranger"])
    with SessionLocal() as db:
        db.get(m.EmpresaCliente, tenants["company"]).activo = False
        db.commit()
    assert client.get("/api/cubas").status_code == 403


def test_session_scope_covers_alias_count_identity_get_and_rejects_bypass(tenants):
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), False, "operations", False))
        assert db.get(m.Cuba, tenants["foreign"]["cube"]) is None
        assert db.query(m.Cuba).count() == 3
        alias = aliased(m.Cuba)
        assert len(db.scalars(select(alias)).all()) == 3
        assert len(db.query(m.Bodega).one().cubas) == 3
        for statement in (text('SELECT * FROM "CUBA"'), m.Cuba.__table__.select()):
            with pytest.raises(HTTPException):
                db.execute(statement)
        with pytest.raises(HTTPException):
            db.query(m.Cuba).update({"estado_operativo": "disponible"})


def test_flush_guards_cross_scope_references_and_historical_reparenting(tenants):
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1,), False, "operations", True))
        db.add(m.ProcesoFermentacion(cuba_id=tenants["foreign"]["cube"], perfil_id=1))
        with pytest.raises(HTTPException) as exc:
            db.flush()
        assert exc.value.status_code == 404
        db.rollback()
        db.add(m.Rol(codigo="superadmin"))
        with pytest.raises(HTTPException) as exc:
            db.flush()
        assert exc.value.status_code == 403
        db.rollback()
    with SessionLocal() as db:
        install_scope(db, AccessContext(1, 1, (1, tenants["second"]["warehouse"]),
                                        True, "profiles", True))
        profile = db.get(m.PerfilFermentacion, 1)
        profile.bodega_id = tenants["second"]["warehouse"]
        with pytest.raises(HTTPException) as exc:
            db.flush()
        assert exc.value.status_code == 409
        db.rollback()
