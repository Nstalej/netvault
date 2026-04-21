"""
NetVault - Secure Credential management routes
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.api.deps import get_current_user, require_editor_or_above
from core.engine.credential_vault import CredentialVault

router = APIRouter(tags=["credentials"], dependencies=[Depends(get_current_user)])

SENSITIVE_FIELDS = {
    "password",
    "auth_password",
    "priv_password",
    "token",
    "api_key",
    "secret",
}


def get_vault(request: Request) -> CredentialVault:
    return request.app.state.vault


@router.get("/api/credentials", response_model=List[Dict[str, Any]])
async def list_credentials(vault: CredentialVault = Depends(get_vault)):
    """List all stored credentials (metadata only, no secrets revealed)"""
    return await vault.list_credentials()


@router.get("/api/credentials/{name}", response_model=Dict[str, Any])
async def get_credential(name: str, vault: CredentialVault = Depends(get_vault)):
    """Retrieve a credential including decrypted payload for editing/usage."""
    record = await vault.get_credential_record(name)
    if not record:
        raise HTTPException(status_code=404, detail=f"Credential '{name}' not found")

    data = record.get("data", {})
    masked_fields = [key for key in data if key in SENSITIVE_FIELDS and data.get(key)]

    return {
        "name": record["name"],
        "type": record["type"],
        "data": data,
        "masked_fields": masked_fields,
    }


class CredentialRequest(BaseModel):
    name: str
    type: str
    data: Dict[str, Any]


class CredentialUpdateRequest(BaseModel):
    type: str
    data: Dict[str, Any]


def _require(data: Dict[str, Any], key: str, message: str):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise HTTPException(status_code=422, detail=message)


def validate_credential_payload(credential_type: str, data: Dict[str, Any]) -> None:
    if credential_type == "ssh":
        _require(data, "username", "SSH credential requires 'username'")
        if not data.get("password") and not data.get("key_filename"):
            raise HTTPException(status_code=422, detail="SSH credential requires either 'password' or 'key_filename'")
    elif credential_type == "rest":
        _require(data, "auth_type", "REST credential requires 'auth_type'")
        auth_type = data.get("auth_type")
        if auth_type == "bearer":
            _require(data, "token", "REST bearer auth requires 'token'")
        elif auth_type == "api_key":
            _require(data, "api_key", "REST api_key auth requires 'api_key'")
        elif auth_type == "basic":
            _require(data, "username", "REST basic auth requires 'username'")
            _require(data, "password", "REST basic auth requires 'password'")


@router.post("/api/credentials", status_code=status.HTTP_201_CREATED)
async def store_credential(
    cred: CredentialRequest,
    vault: CredentialVault = Depends(get_vault),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Securely store a new network credential (SNMP community, SSH password, etc.)"""
    try:
        validate_credential_payload(cred.type, cred.data)
        cred_id = await vault.store_credential(cred.name, cred.type, cred.data)
        return {"id": cred_id, "name": cred.name, "message": "Credential stored securely"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/credentials/{name}")
async def update_credential(
    name: str,
    payload: CredentialUpdateRequest,
    vault: CredentialVault = Depends(get_vault),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Update an existing credential's encrypted data."""
    try:
        validate_credential_payload(payload.type, payload.data)
        await vault.update_credential(name, payload.type, payload.data)
        return {"name": name, "message": "Credential updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/credentials/{name}")
async def delete_credential(
    name: str,
    vault: CredentialVault = Depends(get_vault),
    _: Dict[str, Any] = Depends(require_editor_or_above),
):
    """Permanently delete a credential from the vault"""
    await vault.delete_credential(name)
    return {"message": f"Credential '{name}' deleted"}
