"""
Router de Configuración de Empresa, Viña y Cuotas SaaS (Módulo 5).
Gestiona la ficha de identidad, datos fiscales, opciones operativas y capacidades contratadas.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmpresaCliente, Bodega, Cuba, Usuario
from app.schemas import EmpresaOut, EmpresaUpdateIn, AmpliacionCuotaIn, SaasQuotaDTO

router = APIRouter(prefix="/api/empresa", tags=["Configuración de Empresa y Viña"])


def _obtener_o_crear_empresa_y_bodega(db: Session) -> tuple[EmpresaCliente, Bodega]:
    """Obtiene el registro principal de la empresa y bodega o inicializa los valores oficiales."""
    empresa = db.query(EmpresaCliente).first()
    if not empresa:
        empresa = EmpresaCliente(
            nomb_emp="Viña Santa Emiliana",
            email_emp="contacto@santaemiliana.cl",
            direccion_emp="Ruta K-60, Km 14.5, San Javier",
            rut="76.432.891-K",
            razon_social="Agrícola y Vitivinícola Santa Emiliana S.A.",
            giro="Elaboración y Envasado de Vinos y Mostos",
            telefono="+56 73 245 8890",
            max_cubas=24,
            max_usuarios=15,
            plan_nombre="Plan Bodega Industrial",
            ciclo_facturacion="Anual (Renovación: Nov 2027)",
            reporte_diario=True,
            alertas_sms=True
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)

    bodega = db.query(Bodega).filter(Bodega.empresa_id == empresa.id).first()
    if not bodega:
        bodega = Bodega(
            nombre="Planta Principal · Bodega Central",
            direccion=empresa.direccion_emp or "Ruta K-60, Km 14.5, San Javier",
            empresa_id=empresa.id,
            valle_vitivinicola="Valle del Maule",
            comuna="San Javier",
            region="Región del Maule, Chile"
        )
        db.add(bodega)
        db.commit()
        db.refresh(bodega)

    return empresa, bodega


@router.get("", response_model=EmpresaOut)
def obtener_configuracion_empresa(db: Session = Depends(get_db)):
    """Retorna la ficha de la empresa, bodega y las cuotas de consumo SaaS en tiempo real."""
    empresa, bodega = _obtener_o_crear_empresa_y_bodega(db)

    # Calcular cuotas reales basadas en los registros actuales de la base de datos
    total_cubas = db.query(Cuba).count()
    total_usuarios_activos = db.query(Usuario).filter(Usuario.activo == True).count()

    cuota_dto = SaasQuotaDTO(
        planName=empresa.plan_nombre or "Plan Bodega Industrial",
        billingCycle=empresa.ciclo_facturacion or "Anual (Renovación: Nov 2027)",
        status="Activo" if empresa.activo else "Suspendido",
        usedCubas=max(total_cubas, 1),
        maxCubas=empresa.max_cubas or 24,
        usedUsers=max(total_usuarios_activos, 1),
        maxUsers=empresa.max_usuarios or 15
    )

    return EmpresaOut(
        brandName=empresa.nomb_emp,
        facility=bodega.nombre,
        valley=bodega.valle_vitivinicola or "Valle del Maule",
        logoUrl=empresa.logo_url or "",
        taxId=empresa.rut or "76.432.891-K",
        legalName=empresa.razon_social or "Agrícola y Vitivinícola Santa Emiliana S.A.",
        taxCategory=empresa.giro or "Elaboración y Envasado de Vinos y Mostos",
        address=bodega.direccion or empresa.direccion_emp or "Ruta K-60, Km 14.5",
        region=bodega.region or "Región del Maule, Chile",
        contactEmail=empresa.email_emp or "contacto@santaemiliana.cl",
        contactPhone=empresa.telefono or "+56 73 245 8890",
        dailyEnologyReport=bool(empresa.reporte_diario),
        smsCriticalAlerts=bool(empresa.alertas_sms),
        saasQuota=cuota_dto
    )


@router.put("", response_model=EmpresaOut)
def actualizar_configuracion_empresa(payload: EmpresaUpdateIn, db: Session = Depends(get_db)):
    """Actualiza los datos de identidad, fiscales y operativos de la viña en Supabase."""
    empresa, bodega = _obtener_o_crear_empresa_y_bodega(db)

    if payload.brandName is not None:
        empresa.nomb_emp = payload.brandName.strip()
    if payload.logoUrl is not None:
        empresa.logo_url = payload.logoUrl
    if payload.taxId is not None:
        empresa.rut = payload.taxId.strip()
    if payload.legalName is not None:
        empresa.razon_social = payload.legalName.strip()
    if payload.taxCategory is not None:
        empresa.giro = payload.taxCategory.strip()
    if payload.contactEmail is not None:
        empresa.email_emp = payload.contactEmail.strip()
    if payload.contactPhone is not None:
        empresa.telefono = payload.contactPhone.strip()
    if payload.dailyEnologyReport is not None:
        empresa.reporte_diario = payload.dailyEnologyReport
    if payload.smsCriticalAlerts is not None:
        empresa.alertas_sms = payload.smsCriticalAlerts

    if payload.facility is not None:
        bodega.nombre = payload.facility.strip()
    if payload.valley is not None:
        bodega.valle_vitivinicola = payload.valley.strip()
    if payload.address is not None:
        bodega.direccion = payload.address.strip()
        empresa.direccion_emp = payload.address.strip()
    if payload.region is not None:
        bodega.region = payload.region.strip()

    db.commit()
    db.refresh(empresa)
    db.refresh(bodega)

    return obtener_configuracion_empresa(db=db)


@router.post("/ampliacion")
def ampliar_capacidad_cubas(payload: AmpliacionCuotaIn, db: Session = Depends(get_db)):
    """Amplía la cuota de cubas contratadas para el monitoreo IoT."""
    empresa, _ = _obtener_o_crear_empresa_y_bodega(db)
    empresa.max_cubas = (empresa.max_cubas or 24) + payload.extra_cubas
    db.commit()
    db.refresh(empresa)

    return {
        "status": "ok",
        "mensaje": f"Capacidad ampliada exitosamente a {empresa.max_cubas} cubas.",
        "nueva_capacidad": empresa.max_cubas
    }
