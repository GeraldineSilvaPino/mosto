"""
Servicio de Autenticación, Hashing Seguro de Contraseñas y Gestión de JWT.
Utiliza PBKDF2-HMAC-SHA512 nativo (criptográficamente seguro y compatible con cualquier entorno sin dependencias C)
y PyJWT para firma y verificación de tokens de acceso.
"""
import os
import hashlib
import binascii
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mosto_enologia_secret_key_2026_super_secure_jwt")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REMEMBER_ME_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Genera hash criptográfico seguro PBKDF2-HMAC-SHA512 con salt aleatorio."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')


def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verifica si la contraseña ingresada coincide con el hash almacenado."""
    if not stored_password:
        return False
    try:
        salt = stored_password[:64]
        stored_hash = stored_password[64:]
        pwdhash = hashlib.pbkdf2_hmac('sha512', provided_password.encode('utf-8'), salt.encode('ascii'), 100000)
        pwdhash = binascii.hexlify(pwdhash).decode('ascii')
        return pwdhash == stored_hash
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Genera token JWT firmado con claims de usuario."""
    to_encode = data.copy()
    # RFC 7519: claim 'sub' debe ser string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida firma y expiración de un JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        print(f"Aviso al decodificar JWT: {e}")
        return None


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """Dependencia para requerir un usuario autenticado con Bearer token."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Token Bearer ausente o inválido.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado o inválido. Por favor inicia sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identificador de usuario inválido en token.")

    usuario = db.query(Usuario).filter(Usuario.id == user_id, Usuario.activo == True).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado en el sistema.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return usuario
