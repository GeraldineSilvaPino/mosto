"""Explicit fixtures for the isolated legacy demo; never called by HTTP GET."""
from datetime import datetime, timedelta, timezone
from .models import (EmpresaCliente, Bodega, TipoMaterialCuba, Cepa, Cuba,
                     PerfilFermentacion, ProcesoFermentacion, Usuario, Rol,
                     UsuarioBodega, ModeloDispositivo, Dispositivo, AsignacionDispositivo)
from .services.auth_service import hash_password


def provision_demo_catalogs(db):
    """Explicit and idempotent catalog upgrade for an isolated demo database."""
    for code in ("admin", "enologo", "operador", "lector"):
        if not db.query(Rol).filter_by(codigo=code).first():
            db.add(Rol(codigo=code))
    if not db.query(ModeloDispositivo).filter_by(modelo="ESP32-WROOM-32D").first():
        db.add(ModeloDispositivo(marca="Espressif", modelo="ESP32-WROOM-32D"))
    db.flush()


def seed_demo(db, password: str, *, process_starts=None, commit=True):
    if not password or len(password) < 12:
        raise ValueError("Demo password must contain at least 12 characters")
    if db.query(EmpresaCliente).first():
        raise ValueError("Demo initialization requires an empty database; no existing records are replaced")
    company = EmpresaCliente(nomb_emp="MOSTO DEMO · Datos simulados", email_emp="demo@example.invalid",
                             reporte_diario=False, alertas_sms=False)
    material = TipoMaterialCuba(nombre="Acero inoxidable")
    grape = Cepa(nombre_variedad="Cabernet Sauvignon", tipo_uva="Tinto")
    role = Rol(codigo="admin", descripcion="Administrador demo")
    model = ModeloDispositivo(marca="MOSTO DEMO", modelo="Virtual legacy", arquitectura="simulated")
    db.add_all([company, material, grape, role, model]); db.flush()
    provision_demo_catalogs(db)
    winery = Bodega(nombre="Bodega DEMO", empresa_id=company.id)
    user = Usuario(nomb_compl="Operador DEMO", correo_elec="demo@example.invalid", empresa_id=company.id,
                   rol="admin", activo=True, password_hash=hash_password(password))
    db.add_all([winery, user]); db.flush()
    profile = PerfilFermentacion(nomb_perfil="Perfil DEMO", bodega_id=winery.id, cepa_id=grape.id,
                                temp_min=18, temp_max=26, ph_min=3, ph_max=4, brix_caida_min_dia=.5)
    db.add(profile); db.flush()
    db.add(UsuarioBodega(usuario_id=user.id, bodega_id=winery.id, rol_id=role.id))
    for index in range(1, 4):
        cuba = Cuba(codigo=f"DEMO-{index:02}", bodega_id=winery.id, material_id=material.id,
                    cap_litros=10000, estado_operativo="en_uso")
        device = Dispositivo(mac_address=f"02:00:00:00:00:{index:02X}", empresa_id=company.id,
                             modelo_id=model.id, tipo_dispositivo="DUAL", firmware_version="demo", estado="activo")
        db.add_all([cuba, device]); db.flush()
        now = datetime.now(timezone.utc)
        start = (process_starts or {}).get(index, now - timedelta(days=1))
        db.add(ProcesoFermentacion(cuba_id=cuba.id, perfil_id=profile.id, volumen_litros=8500,
                                  brix_inicial=24, brix_objetivo=2, estado="en_proceso",
                                  fecha_inicio=start, fecha_estimada_fin=start + timedelta(days=14)))
        db.add(AsignacionDispositivo(dispositivo_id=device.id, cuba_id=cuba.id, activo=True,
                                     asignado_en=start))
    db.flush()
    if commit:
        db.commit()
