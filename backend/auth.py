"""
Système d'authentification sécurisé avec JWT et Argon2
"""
import logging
import os
import re
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from sqlalchemy.orm import Session
from backend.models import User

# Configuration de sécurité
logger = logging.getLogger(__name__)
DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


def _load_secret_key() -> str:
    """Charger la cle JWT et bloquer les secrets faibles en production."""
    secret_key = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY).strip()
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment in {"production", "prod"} and (
        secret_key == DEFAULT_SECRET_KEY or len(secret_key) < 32
    ):
        raise RuntimeError(
            "SECRET_KEY doit etre defini avec au moins 32 caracteres en production."
        )

    if secret_key == DEFAULT_SECRET_KEY or len(secret_key) < 32:
        logger.warning(
            "SECRET_KEY faible ou par defaut: a remplacer avant tout deploiement."
        )

    return secret_key


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

# Contexte pour hachage des mots de passe avec Argon2
# Argon2 n'a pas de limite de longueur de mot de passe (contrairement à bcrypt)
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# ============================================================
# SCHEMAS PYDANTIC
# ============================================================

class UserRegisterRequest(BaseModel):
    """Schéma pour l'enregistrement"""
    username: str
    email: EmailStr
    password: str
    full_name: str
    department: Optional[str] = None

class UserLoginRequest(BaseModel):
    """Schéma pour la connexion"""
    username: str
    password: str

class TokenResponse(BaseModel):
    """Schéma pour le token de réponse"""
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str
    expires_in: int

class UserResponse(BaseModel):
    """Schéma pour les informations utilisateur"""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    department: Optional[str]
    is_active: bool
    must_change_password: bool
    last_login: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class CurrentUser(BaseModel):
    """Utilisateur actuellement authentifié"""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    must_change_password: bool

# ============================================================
# FONCTIONS DE HACHAGE ET VÉRIFICATION
# ============================================================

def hash_password(password: str) -> str:
    """Hacher un mot de passe avec Argon2
    
    Argon2 supporte les mots de passe de n'importe quelle longueur,
    contrairement à bcrypt qui a une limite de 72 bytes.
    C'est l'algorithme recommandé par OWASP.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifier un mot de passe avec Argon2"""
    return pwd_context.verify(plain_password, hashed_password)

def validate_password_strength(
    password: str,
    username: str = "",
    email: str = "",
    full_name: str = "",
) -> list[str]:
    """Retourner les criteres manquants pour un mot de passe robuste."""
    errors = []
    normalized_password = (password or "").lower()
    identity_parts = [
        username,
        (email or "").split("@")[0],
        *re.split(r"\s+", full_name or ""),
    ]

    if len(password or "") < 10:
        errors.append("au moins 10 caracteres")
    if not re.search(r"[a-z]", password or ""):
        errors.append("une lettre minuscule")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("une lettre majuscule")
    if not re.search(r"\d", password or ""):
        errors.append("un chiffre")
    if not re.search(r"[^A-Za-z0-9]", password or ""):
        errors.append("un caractere special")

    for part in identity_parts:
        part = (part or "").strip().lower()
        if len(part) >= 4 and part in normalized_password:
            errors.append("ne pas contenir le nom, l'utilisateur ou l'email")
            break

    return errors


# ============================================================
# GESTION DES JWT TOKENS
# ============================================================

def create_access_token(
    data: Dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Créer un JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[Dict]:
    """Décoder et valider un JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return payload
    except JWTError:
        return None

# ============================================================
# GESTION DES UTILISATEURS
# ============================================================

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Récupérer un utilisateur par son nom d'utilisateur"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Récupérer un utilisateur par son email"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Récupérer un utilisateur par son ID"""
    return db.query(User).filter(User.id == user_id).first()

def register_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str,
    department: Optional[str] = None
) -> Optional[User]:
    """Créer un nouvel utilisateur"""
    
    # Vérifier les doublons
    if get_user_by_username(db, username):
        return None
    if get_user_by_email(db, email):
        return None
    
    # Créer l'utilisateur
    if validate_password_strength(password, username, email, full_name):
        return None

    password_hash = hash_password(password)
    new_user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        department=department,
        role="viewer"  # Rôle par défaut
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(
    db: Session,
    username: str,
    password: str
) -> Optional[User]:
    """Authentifier un utilisateur"""
    user = get_user_by_username(db, username)
    
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    
    # Mettre à jour le dernier login
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    db.expunge(user)
    
    return user

def create_user_token(user, expires_delta: Optional[timedelta] = None) -> TokenResponse:
    """Créer un token pour un utilisateur (SAFE dict, pas ORM)"""

    user_data = user if isinstance(user, dict) else {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }

    access_token_expires = expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    access_token = create_access_token(
        data={
            "sub": str(user_data["id"]),
            "username": user_data["username"],
            "role": user_data["role"]
        },
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user_data["id"]),
        username=user_data["username"],
        role=user_data["role"],
        expires_in=int(access_token_expires.total_seconds())
    )

# ============================================================
# CONTRÔLE D'ACCÈS BASÉ SUR LES RÔLES
# ============================================================

def check_role(user: User, required_role: str) -> bool:
    """Vérifier si l'utilisateur a le rôle requis"""
    role_hierarchy = {
        "admin": ["admin", "engineer", "viewer"],
        "engineer": ["engineer", "viewer"],
        "viewer": ["viewer"]
    }
    
    allowed_roles = role_hierarchy.get(user.role, [])
    return required_role in allowed_roles

def require_role(required_role: str):
    """Décorateur pour vérifier le rôle"""
    async def verify_role(current_user: CurrentUser) -> CurrentUser:
        if not check_role(User(role=current_user.role), required_role):
            raise PermissionError(f"Rôle requis: {required_role}")
        return current_user
    return verify_role

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_current_user(token: str, db: Session) -> Optional[CurrentUser]:
    """Obtenir l'utilisateur actuel à partir du token"""
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    user = get_user_by_id(db, user_id)
    
    if not user or not user.is_active:
        return None
    
    return CurrentUser(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        must_change_password=bool(user.must_change_password),
    )
