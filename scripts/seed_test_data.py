"""
NetVault - Seed Test Data
Populates the database with sample devices and credentials for testing.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.config import get_config
from core.database.db import DatabaseManager
from core.engine.credential_vault import CredentialVault
from core.database import crud
from core.database.models import DeviceModel

async def seed_data():
    config = get_config()
    db = DatabaseManager(config.database.db_path)
    await db.connect()
    
    vault = CredentialVault(db, master_key=config.security.credentials_master_key)
    
    print("Seeding credentials...")
    # MikroTik SSH Credential
    await vault.store_credential(
        name="mikrotik-ssh",
        credential_type="ssh_password",
        data={"username": "admin", "password": "password123"}
    )
    
    # Cisco SNMP Credential
    await vault.store_credential(
        name="cisco-snmp",
        credential_type="snmp_v2",
        data={"community": "public"}
    )
    
    # Sophos REST Credential
    await vault.store_credential(
        name="sophos-api",
        credential_type="api_key",
        data={"api_key": "SOPHOS-API-KEY-12345"}
    )
    
    print("Seeding devices...")
    # MikroTik Device
    mikrotik = DeviceModel(
        name="Core-Router-01",
        type="router",
        ip="192.168.1.1",
        port=22,
        connector_type="ssh",
        config_json={"credential_name": "mikrotik-ssh", "device_type": "mikrotik"},
        status="unknown"
    )
    await crud.create_device(db, mikrotik)
    
    # Cisco Device
    cisco = DeviceModel(
        name="Switch-Floor-1",
        type="switch",
        ip="192.168.1.10",
        port=161,
        connector_type="snmp",
        config_json={"credential_name": "cisco-snmp", "version": "v2c"},
        status="unknown"
    )
    await crud.create_device(db, cisco)
    
    # Sophos Device
    sophos = DeviceModel(
        name="Firewall-Main",
        type="firewall",
        ip="192.168.1.254",
        port=443,
        connector_type="rest_api",
        config_json={"credential_name": "sophos-api", "profile": "sophos_xg"},
        status="unknown"
    )
    await crud.create_device(db, sophos)
    
    print("Successfully seeded test data!")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(seed_data())
