"""
NetVault - Authentication security helpers
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    settings = get_config()
    to_encode = data.copy()
    hours = max(1, int(getattr(settings.security, "access_token_expire_hours", 8)))
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=hours))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.security.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    settings = get_config()
    try:
        payload = jwt.decode(token, settings.security.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
