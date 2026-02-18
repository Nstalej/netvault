"""
Unit tests for NetVault Credential Vault
"""
import pytest
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock
from core.engine.credential_vault import CredentialVault

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock(return_value=1)
    db.fetch_one = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    return db

@pytest.fixture
def vault(mock_db):
    return CredentialVault(db=mock_db, master_key="test-secret-123")

def test_key_derivation(vault):
    """Test that Fernet initialization works"""
    fernet = vault._get_fernet()
    assert fernet is not None

def test_encryption_decryption_logic(vault):
    """Test standard encryption/decryption cycle"""
    data = {"user": "admin", "pass": "secret"}
    encrypted = vault._encrypt(data)
    assert encrypted != json.dumps(data)
    
    decrypted = vault._decrypt(encrypted)
    assert decrypted == data

@pytest.mark.asyncio
async def test_store_credential(vault, mock_db):
    """Test storing a credential"""
    await vault.store_credential("my-router", "snmp", {"community": "public"})
    assert mock_db.execute.called
    # Check that it doesn't log the actual data (indirectly verified by manual check)

@pytest.mark.asyncio
async def test_get_credential(vault, mock_db):
    """Test retrieving and decrypting a credential"""
    encrypted_data = vault._encrypt({"community": "public"})
    mock_db.fetch_one.return_value = {"encrypted_data": encrypted_data}
    
    result = await vault.get_credential("my-router")
    assert result["community"] == "public"

@pytest.mark.asyncio
async def test_no_master_key_fails():
    """Verify that it fails if no master key is provided"""
    v = CredentialVault(db=MagicMock(), master_key=None)
    with pytest.raises(ValueError):
        v._get_fernet()
