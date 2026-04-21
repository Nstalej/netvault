"""
NetVault - Authentication routes
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.api.deps import get_current_user, get_db, require_admin
from core.database import crud
from core.database.db import DatabaseManager
from core.database.models import UserRole
from core.security import create_access_token, get_password_hash, verify_password

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    locale: str = "en"
    is_active: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    role: str = UserRole.VIEWER.value
    locale: str = "en"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    locale: Optional[str] = None
    is_active: Optional[bool] = None


def _public_user(user: Dict[str, Any]) -> UserPublic:
    return UserPublic(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        role=user.get("role", UserRole.VIEWER.value),
        locale=user.get("locale", "en"),
        is_active=bool(user.get("is_active", True)),
    )


@router.post("/api/auth/login", response_model=TokenResponse)
@router.post("/api/v1/auth/login", response_model=TokenResponse, include_in_schema=False)
async def login(request: LoginRequest, db: DatabaseManager = Depends(get_db)):
    user = await crud.get_user_by_email(db, request.email.strip().lower())
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": user["email"], "role": user.get("role", UserRole.VIEWER.value)})
    return TokenResponse(access_token=token, user=_public_user(user))


@router.get("/api/auth/me", response_model=UserPublic)
@router.get("/api/v1/auth/me", response_model=UserPublic, include_in_schema=False)
async def me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return _public_user(current_user)


@router.post("/api/auth/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@router.post(
    "/api/v1/auth/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED, include_in_schema=False
)
async def create_user(
    user_data: UserCreate,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
):
    existing = await crud.get_user_by_email(db, user_data.email.strip().lower())
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user_id = await crud.create_user(
        db,
        email=user_data.email.strip().lower(),
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        locale=user_data.locale,
    )
    created = await crud.get_user_by_id(db, user_id)
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user")
    return _public_user(created)


@router.get("/api/auth/users", response_model=List[UserPublic])
@router.get("/api/v1/auth/users", response_model=List[UserPublic], include_in_schema=False)
async def list_users(
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
):
    users = await crud.list_users(db)
    return [_public_user(user) for user in users]


@router.patch("/api/auth/users/{user_id}", response_model=UserPublic)
@router.patch("/api/v1/auth/users/{user_id}", response_model=UserPublic, include_in_schema=False)
async def update_user(
    user_id: int,
    updates: UserUpdate,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
):
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payload = updates.model_dump(exclude_none=True)
    if payload:
        await crud.update_user(db, user_id, payload)

    refreshed = await crud.get_user_by_id(db, user_id)
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _public_user(refreshed)
