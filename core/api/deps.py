"""
NetVault - API auth dependencies
"""

from typing import Dict, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.database import crud
from core.database.db import DatabaseManager
from core.database.models import UserRole
from core.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    user = await crud.get_user_by_email(db, email)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


async def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


async def require_editor_or_above(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") == UserRole.VIEWER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor role required")
    return current_user
