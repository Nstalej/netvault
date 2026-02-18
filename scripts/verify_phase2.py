"""
NetVault - Phase 2 Verification Script
Tests core components: DB, Vault, and DeviceManager without starting the web server.
"""
import asyncio
import os
from core.database.db import DatabaseManager
from core.database.models import SCHEMA_SQL, DeviceCreate
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager

async def verify():
    print("--- Phase 2 Verification ---")
    
    # 1. Test Vault
    print("\n[V] Testing CredentialVault...")
    vault = CredentialVault("test-master-key-123")
    secret = "NetVaultPassword2026!"
    encrypted = vault.encrypt(secret)
    decrypted = vault.decrypt(encrypted)
    assert secret == decrypted
    print("  - Encryption/Decryption: OK")
    
    # 2. Test Database & DeviceManager
    print("\n[DB] Testing DatabaseManager & DeviceManager...")
    db_path = "test_netvault.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = DatabaseManager(db_path)
    await db.connect()
    await db.initialize_schema(SCHEMA_SQL)
    
    manager = DeviceManager(db, vault)
    
    # 3. Add a device
    print("\n[DEV] Adding test device...")
    device_in = DeviceCreate(
        name="MikroTik-GW",
        ip_address="192.168.88.1",
        type="snmp",
        description="Core Gateway"
    )
    dev_id = await manager.add_device(device_in, password="router_password")
    print(f"  - Device added with ID: {dev_id}")
    
    # 4. Verify device insertion
    devices = await manager.get_all_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "MikroTik-GW"
    print("  - Device retrieval: OK")
    
    # 5. Verify credential storage
    cred_id = devices[0]["credential_id"]
    cred = await manager.get_credential(cred_id)
    assert cred["password"] == "router_password"
    print("  - Credential storage & decryption: OK")
    
    await db.disconnect()
    os.remove(db_path)
    print("\n--- Verification Successful! ---")

if __name__ == "__main__":
    asyncio.run(verify())
