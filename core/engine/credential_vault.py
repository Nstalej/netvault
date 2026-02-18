"""
NetVault - Secure Credential Vault
Handles encryption and storage of sensitive device credentials.
"""
import os
import json
import base64
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.database.db import DatabaseManager
from core.database.models import CredentialStoreModel

logger = logging.getLogger("netvault.vault")

class CredentialVault:
    """Secure vault for managing encrypted infrastructure credentials"""
    
    def __init__(self, db: DatabaseManager, master_key: Optional[str] = None):
        self.db = db
        # Use provided key or fetch from environment
        self.master_key = master_key or os.getenv("CREDENTIALS_MASTER_KEY")
        self._fernet: Optional[Fernet] = None

    def _get_fernet(self) -> Fernet:
        """Initialize Fernet using PBKDF2 key derivation from master key"""
        if self._fernet:
            return self._fernet
            
        if not self.master_key:
            logger.critical("CREDENTIALS_MASTER_KEY is not set!")
            raise ValueError("CREDENTIALS_MASTER_KEY environment variable is required")

        # Static salt for consistent key derivation across restarts
        # In a multi-tenant environment, this would be per-tenant
        salt = b'netvault_static_salt_01' 
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        self._fernet = Fernet(key)
        return self._fernet

    def _encrypt(self, data: dict) -> str:
        """Encrypt dictionary to base64 string"""
        json_str = json.dumps(data)
        return self._get_fernet().encrypt(json_str.encode()).decode()

    def _decrypt(self, encrypted_str: str) -> dict:
        """Decrypt base64 string to dictionary"""
        decrypted_bytes = self._get_fernet().decrypt(encrypted_str.encode())
        return json.loads(decrypted_bytes.decode())

    # ---- Public API (string-based) ----
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string. Wrapper used by verify scripts and higher-level code.
        Internally stores it as {"value": "..."} to reuse dict-based encryption.
        """
        return self._encrypt({"value": plaintext})

    def decrypt(self, token: str) -> str:
        """
        Decrypt token back to plaintext string.
        If payload is dict-like, it tries to extract 'value' (or the only value if single-key dict).
        """
        data = self._decrypt(token)
        if isinstance(data, dict):
            if "value" in data:
                return data["value"]
            if len(data) == 1:
                return next(iter(data.values()))
        # Fallback (shouldn't happen for string encryption)
        return str(data)

    # ---- Optional: explicit dict API (keeps intent clear) ----
    def encrypt_dict(self, data: dict) -> str:
        return self._encrypt(data)

    def decrypt_dict(self, token: str) -> dict:
        return self._decrypt(token)

    async def store_credential(self, name: str, credential_type: str, data: dict) -> int:
        """Encrypt and store a new credential in the database"""
        encrypted_data = self._encrypt(data)
        
        query = """
        INSERT INTO credential_store (name, type, encrypted_data)
        VALUES (?, ?, ?)
        """
        params = (name, credential_type, encrypted_data)
        cred_id = await self.db.execute(query, params)
        
        logger.info(f"Credential '{name}' (type: {credential_type}) stored successfully")
        return cred_id

    async def get_credential(self, name: str) -> Optional[dict]:
        """Fetch and decrypt a credential by its name"""
        query = "SELECT encrypted_data FROM credential_store WHERE name = ?"
        row = await self.db.fetch_one(query, (name,))
        
        if not row:
            logger.warning(f"Credential '{name}' not found")
            return None
            
        logger.info(f"Accessing credential: {name}")
        return self._decrypt(row["encrypted_data"])

    async def update_credential(self, name: str, data: dict):
        """Update existing credential data"""
        encrypted_data = self._encrypt(data)
        
        query = """
        UPDATE credential_store 
        SET encrypted_data = ?, updated_at = CURRENT_TIMESTAMP
        WHERE name = ?
        """
        await self.db.execute(query, (encrypted_data, name))
        logger.info(f"Credential '{name}' updated")

    async def delete_credential(self, name: str):
        """Remove a credential from the vault"""
        await self.db.execute("DELETE FROM credential_store WHERE name = ?", (name,))
        logger.inform(f"Credential '{name}' deleted")

    async def list_credentials(self) -> List[Dict[str, Any]]:
        """List all stored credentials (metadata only)"""
        query = "SELECT id, name, type, created_at, updated_at FROM credential_store"
        rows = await self.db.fetch_all(query)
        return [dict(row) for row in rows]
