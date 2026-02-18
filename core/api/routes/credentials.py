"""
NetVault - Secure Credential management routes
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.engine.credential_vault import CredentialVault
from core.database.db import DatabaseManager

router = APIRouter(prefix="/api/credentials", tags=["credentials"])

def get_vault(request: Request) -> CredentialVault:
    return request.app.state.vault

@router.get("/", response_model=List[Dict[str, Any]])
async def list_credentials(vault: CredentialVault = Depends(get_vault)):
    """List all stored credentials (metadata only, no secrets revealed)"""
    return await vault.list_credentials()

class CredentialRequest(BaseModel):
    name: str
    type: str
    data: Dict[str, Any]

@router.post("/", status_code=status.HTTP_201_CREATED)
async def store_credential(
    cred: CredentialRequest, 
    vault: CredentialVault = Depends(get_vault)
):
    """Securely store a new network credential (SNMP community, SSH password, etc.)"""
    try:
        cred_id = await vault.store_credential(cred.name, cred.type, cred.data)
        return {"id": cred_id, "name": cred.name, "message": "Credential stored securely"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{name}")
async def update_credential(
    name: str, 
    data: Dict[str, Any], 
    vault: CredentialVault = Depends(get_vault)
):
    """Update an existing credential's encrypted data"""
    try:
        await vault.update_credential(name, data)
        return {"name": name, "message": "Credential updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{name}")
async def delete_credential(
    name: str, 
    vault: CredentialVault = Depends(get_vault)
):
    """Permanently delete a credential from the vault"""
    await vault.delete_credential(name)
    return {"message": f"Credential '{name}' deleted"}
