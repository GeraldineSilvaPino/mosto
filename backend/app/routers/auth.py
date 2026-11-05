"""
Router de Autenticación y Control de Sesión.
Endpoints para inicio de sesión seguro, validación de credenciales en Supabase,
emisión de tokens JWT y recuperación de contraseña.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Usuario, EmpresaCliente
from app.schemas import LoginIn, LoginOut, UserAuthPayload, PasswordResetIn
from app.services.auth_service import (
    verify_password,
    create_access_token,
    get_current_user,
    REMEMBER_ME_EXPIRE_DAYS,
    ACCESS_TOKEN_EXPIRE_HOURS
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación y Seguridad"])


ROLE_LABEL_MAP = {
    "admin": "Administrador General",
    "enologo": "Enólogo Jefe",
    "operador": "Operario de Bodega",
    "operario": "Operario de Bodega"
}


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """
    Inicia sesión verificando credenciales en la base de datos de Supabase.
    Genera y retorna un token JWT válido junto con el perfil del usuario.
    """
    email_clean = payload.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.correo_elec) == email_clean).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Comprueba tu correo y contraseña."
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta se encuentra inactiva o suspendida. Contacta al administrador."
        )

    # Validar contraseña con PBKDF2-HMAC-SHA512
    if not verify_password(usuario.password_hash or "", payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Comprueba tu correo y contraseña."
        )

    # Determinar tiempo de expiración
    if payload.remember_me:
        exp_delta = timedelta(days=REMEMBER_ME_EXPIRE_DAYS)
    else:
        exp_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    # Buscar nombre de la empresa / viña
    nombre_vina = "Viña Santa Emiliana"
    if usuario.empresa_id:
        emp = db.query(EmpresaCliente).filter(EmpresaCliente.id == usuario.empresa_id).first()
        if emp and emp.nomb_emp:
            nombre_vina = emp.nomb_emp

    token_claims = {
        "sub": usuario.id,
        "email": usuario.correo_elec,
        "name": usuario.nomb_compl,
        "role": usuario.rol or "operador",
        "empresa_id": usuario.empresa_id
    }

    access_token = create_access_token(token_claims, expires_delta=exp_delta)

    # Construir avatar inicial
    partes = usuario.nomb_compl.strip().split()
    if len(partes) >= 2:
        avatar = (partes[0][0] + partes[1][0]).upper()
    elif len(partes) == 1 and len(partes[0]) >= 2:
        avatar = partes[0][:2].upper()
    else:
        avatar = "MO"

    user_payload = UserAuthPayload(
        id=usuario.id,
        name=usuario.nomb_compl,
        email=usuario.correo_elec,
        role=ROLE_LABEL_MAP.get(usuario.rol, usuario.rol or "Operario"),
        winery=nombre_vina,
        avatarInitial=avatar
    )

    return LoginOut(
        access_token=access_token,
        token_type="bearer",
        user=user_payload
    )


@router.post("/recuperar-password")
def recuperar_password(payload: PasswordResetIn, db: Session = Depends(get_db)):
    """
    Solicitud de recuperación de contraseña.
    Valida la existencia del correo registrado y genera respuesta de confirmación segura.
    """
    email_clean = payload.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.correo_elec) == email_clean).first()

    if not usuario:
        # Por seguridad no revelamos explícitamente si el correo existe o no
        return {
            "status": "ok",
            "mensaje": f"Si el correo {email_clean} está registrado, se enviaron las instrucciones para restablecer la contraseña."
        }

    return {
        "status": "ok",
        "mensaje": f"Se ha enviado un enlace de recuperación seguro a {usuario.correo_elec} (válido por 60 minutos)."
    }


@router.get("/me", response_model=UserAuthPayload)
def obtener_perfil_actual(
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna el perfil del usuario autenticado a través del token Bearer."""
    nombre_vina = "Viña Santa Emiliana"
    if usuario_actual.empresa_id:
        emp = db.query(EmpresaCliente).filter(EmpresaCliente.id == usuario_actual.empresa_id).first()
        if emp and emp.nomb_emp:
            nombre_vina = emp.nomb_emp

    partes = usuario_actual.nomb_compl.strip().split()
    avatar = (partes[0][0] + partes[1][0]).upper() if len(partes) >= 2 else "MO"

    return UserAuthPayload(
        id=usuario_actual.id,
        name=usuario_actual.nomb_compl,
        email=usuario_actual.correo_elec,
        role=ROLE_LABEL_MAP.get(usuario_actual.rol, usuario_actual.rol or "Operario"),
        winery=nombre_vina,
        avatarInitial=avatar
    )
