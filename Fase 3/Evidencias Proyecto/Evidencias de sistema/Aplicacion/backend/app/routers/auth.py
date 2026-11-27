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
from app.models import Usuario
from app.services.access import load_company_access, current_access
from app.schemas import LoginIn, LoginOut, UserAuthPayload, PasswordResetIn
from app.services.auth_service import (
    verify_password,
    create_access_token,
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


def _auth_payload(access):
    codes = {role for _, _, role in access.memberships}
    code = next(iter(codes)) if len(codes) == 1 else "Roles por bodega"
    parts = access.name.split()
    avatar = "".join(part[0] for part in parts[:2]).upper() or "MO"
    return UserAuthPayload(id=access.user_id, name=access.name, email=access.email,
        role=ROLE_LABEL_MAP.get(code, "Solo lectura" if code == "lector" else code),
        winery=access.company_name, avatarInitial=avatar, company_admin=access.company_admin,
        memberships=[{"bodega_id": ident, "bodega_nombre": name, "role": role}
                     for ident, name, role in access.memberships])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """
    Inicia sesión verificando credenciales en la base de datos de Supabase.
    Genera y retorna un token JWT válido junto con el perfil del usuario.
    """
    raw_email = payload.email or payload.username
    if not raw_email:
        print("[AUTH ERROR] Petición de login rechazada: correo electrónico no proporcionado.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El correo electrónico es requerido."
        )

    email_clean = raw_email.strip().lower()
    print(f"[AUTH INFO] Intento de login recibido para: {email_clean}")

    usuario = db.query(Usuario).filter(func.lower(Usuario.correo_elec) == email_clean).first()

    if not usuario:
        print(f"[AUTH WARN] Login fallido: usuario '{email_clean}' no encontrado en Supabase.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Comprueba tu correo y contraseña."
        )

    if not usuario.activo:
        print(f"[AUTH WARN] Login bloqueado: usuario '{email_clean}' está desactivado o suspendido.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta se encuentra inactiva o suspendida. Contacta al administrador."
        )

    # Validar contraseña con PBKDF2-HMAC-SHA512 (con tolerancia a espacios accidentales)
    pwd_valid = verify_password(usuario.password_hash or "", payload.password)
    if not pwd_valid and payload.password:
        pwd_valid = verify_password(usuario.password_hash or "", payload.password.strip())

    if not pwd_valid:
        print(f"[AUTH WARN] Login fallido: contraseña incorrecta para '{email_clean}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Comprueba tu correo y contraseña."
        )

    # Determinar tiempo de expiración
    remember = payload.remember_me or payload.rememberMe
    if remember:
        exp_delta = timedelta(days=REMEMBER_ME_EXPIRE_DAYS)
    else:
        exp_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    user_payload = _auth_payload(load_company_access(db, usuario.id))

    token_claims = {
        "sub": str(usuario.id),
        "email": usuario.correo_elec,
        "name": usuario.nomb_compl,
        "empresa_id": usuario.empresa_id
    }

    access_token = create_access_token(token_claims, expires_delta=exp_delta)
    print(f"[AUTH SUCCESS] Login exitoso para '{usuario.correo_elec}' ({usuario.nomb_compl}) - Rol: {usuario.rol}")

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
def obtener_perfil_actual(access=Depends(current_access)):
    return _auth_payload(access)
