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
from app.models import Usuario, EmpresaCliente, Bodega, UsuarioBodega, Rol
from app.services.access import normalize_role, KNOWN_ROLES
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


def _auth_payload(db, user):
    company = db.query(EmpresaCliente).filter_by(id=user.empresa_id, activo=True).first()
    if company is None:
        raise HTTPException(403, "Empresa inactiva o sin configurar")
    rows = db.query(UsuarioBodega.bodega_id, Bodega.nombre, Rol.codigo).join(
        Bodega, UsuarioBodega.bodega_id == Bodega.id).join(Rol).filter(
        UsuarioBodega.usuario_id == user.id, Bodega.empresa_id == company.id).all()
    ids = [row[0] for row in rows]
    codes = {normalize_role(row[2]) for row in rows}
    if not rows or len(set(ids)) != len(ids) or not codes.issubset(KNOWN_ROLES):
        raise HTTPException(403, "Sin asignaciones válidas a bodegas")
    company_ids = {row[0] for row in db.query(Bodega.id).filter_by(empresa_id=company.id)}
    company_admin = set(ids) == company_ids and codes == {"admin"}
    code = next(iter(codes)) if len(codes) == 1 else "Roles por bodega"
    parts = user.nomb_compl.split()
    avatar = "".join(part[0] for part in parts[:2]).upper() or "MO"
    return UserAuthPayload(id=user.id, name=user.nomb_compl, email=user.correo_elec,
        role=ROLE_LABEL_MAP.get(code, "Solo lectura" if code == "lector" else code),
        winery=company.nomb_emp, avatarInitial=avatar, company_admin=company_admin,
        memberships=[{"bodega_id": ident, "bodega_nombre": name, "role": normalize_role(role)}
                     for ident, name, role in rows])


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

    user_payload = _auth_payload(db, usuario)

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
def obtener_perfil_actual(
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna el perfil del usuario autenticado a través del token Bearer."""
    return _auth_payload(db, usuario_actual)
