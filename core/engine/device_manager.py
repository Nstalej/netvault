"""
NetVault - Device Manager
Core logic for managing network devices and their credentials.
"""
import logging
from typing import List, Optional
from datetime import datetime, timezone

from core.database.db import DatabaseManager
from core.database.models import Device, DeviceCreate, Credential, CredentialCreate
from core.engine.credential_vault import CredentialVault

logger = logging.getLogger("netvault.engine")

class DeviceManager:
    """Coordinates device operations between DB and Vault"""
    
    def __init__(self, db: DatabaseManager, vault: CredentialVault):
        self.db = db
        self.vault = vault

    async def add_device(self, device_data: DeviceCreate, password: Optional[str] = None) -> int:
        """Add a new device, optionally creating a credential first"""
        credential_id = device_data.credential_id
        
        if password and not credential_id:
            # Create a default credential for this device
            cred_name = f"Cred-{device_data.name}"
            credential_id = await self.create_credential(
                CredentialCreate(
                    name=cred_name,
                    username="admin", # Default or from input
                    password=password
                )
            )
            
        query = """
        INSERT INTO devices (name, ip_address, type, description, credential_id, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            device_data.name,
            device_data.ip_address,
            device_data.type,
            device_data.description,
            credential_id,
            1 if device_data.is_active else 0
        )
        return await self.db.execute(query, params)

    async def get_all_devices(self) -> List[dict]:
        """Fetch all devices from the database"""
        return await self.db.fetch_all("SELECT * FROM devices")

    async def get_device(self, device_id: int) -> Optional[dict]:
        """Fetch a single device by ID"""
        return await self.db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    async def create_credential(self, cred_data: CredentialCreate) -> int:
        """Encrypt password and store credential in DB"""
        encrypted_pw = self.vault.encrypt(cred_data.password)
        query = """
        INSERT INTO credentials (name, username, encrypted_password)
        VALUES (?, ?, ?)
        """
        return await self.db.execute(query, (cred_data.name, cred_data.username, encrypted_pw))

    async def get_credential(self, cred_id: int) -> Optional[dict]:
        """Fetch credential and decrypt password"""
        row = await self.db.fetch_one("SELECT * FROM credentials WHERE id = ?", (cred_id,))
        if row:
            row['password'] = self.vault.decrypt(row['encrypted_password'])
        return row

    async def log_audit(self, target_type: str, target_id: int, action: str, status: str, message: str):
        """Record an action in the audit log"""
        query = """
        INSERT INTO audit_logs (target_type, target_id, action, status, message)
        VALUES (?, ?, ?, ?, ?)
        """
        await self.db.execute(query, (target_type, target_id, action, status, message))
        logger.info(f"Audit: {action} on {target_type} {target_id} - {status}: {message}")
