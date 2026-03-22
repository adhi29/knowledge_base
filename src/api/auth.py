"""JWT authentication helpers for FastAPI."""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from src.config import settings
from src.storage.database import get_user_by_username, get_user_by_id, create_user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Password helpers ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token helpers ──────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    user_id: str
    username: str
    role: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        if not user_id:
            raise credentials_exception
        return TokenData(user_id=user_id, username=username or "", role=role or "analyst")
    except JWTError:
        raise credentials_exception


# ── FastAPI dependency ─────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return decode_token(token)


def require_role(*roles: str):
    """Dependency factory: require one of the specified roles."""
    def _checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted for this endpoint.",
            )
        return current_user
    return _checker


# ── Login / Register helpers ───────────────────────────────────────────────────

def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def register_user(username: str, password: str, role: str = "analyst", department: Optional[str] = None) -> dict:
    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists.")

    valid_roles = {"analyst", "operations", "compliance", "admin"}
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {valid_roles}")

    user_id = str(uuid.uuid4())
    hashed  = hash_password(password)
    create_user(user_id, username, hashed, role, department)
    return {"user_id": user_id, "username": username, "role": role}
