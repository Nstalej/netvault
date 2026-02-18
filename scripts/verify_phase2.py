"""
NetVault - Phase 2 Verification Script
Tests core components: DB, Vault, and DeviceManager without starting the web server.
"""

import asyncio
import os
import sys
from pathlib import Path

# Asegura que "core/" sea importable aunque no tengas PYTHONPATH seteado
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.database.db import DatabaseManager
from core.database.models import SCHEMA_SQL, DeviceCreate
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager


async def verify():
    print("--- Phase 2 Verification ---")

    # 1. Test Vault
    print("\n[V] Testing CredentialVault...")

    master_key = os.getenv("CREDENTIALS_MASTER_KEY")
    if not master_key:
        raise ValueError(
            "CREDENTIALS_MASTER_KEY no está seteada en el entorno. "
            "Cárgala desde tu .env antes de correr este script."
        )

    vault = CredentialVault(master_key)

    secret = "NetVaultPassword2026!"
    encrypted = vault.encrypt(secret)
    decrypted = vault.decrypt(encrypted)
    assert secret == decrypted
    print("  - Encryption/Decryption: OK")

    # 2. Test Database & DeviceManager
    print("\n[DB] Testing DatabaseManager & DeviceManager...")

    # Usa un DB de PRUEBA para no tocar tu DB real
    db_path = os.getenv("VERIFY_DB_PATH", "test_netvault.db")

    # Solo borra si es un db de prueba (seguro)
    cleanup_db = os.getenv("VERIFY_KEEP_DB", "0") != "1"
    if cleanup_db and Path(db_path).exists() and Path(db_path).name.startswith("test_"):
        os.remove(db_path)

    db = DatabaseManager(db_path)
    await db.connect()

    # Mantengo esto porque tu script original lo llama
    # (si tu DatabaseManager ya auto-inicializa, esto no debería romper)
    await db.initialize_schema(SCHEMA_SQL)

    manager = DeviceManager(db, vault)

    # Credenciales del equipo (no las hardcodees; pásalas por env)
    router_user = os.getenv("ROUTER_USERNAME", "admin")
    router_pass = os.getenv("ROUTER_PASSWORD", "")

    if not router_pass:
        raise ValueError(
            "ROUTER_PASSWORD no está seteada. "
            "Setea ROUTER_PASSWORD (por ejemplo en tu sesión PowerShell) para continuar."
        )

    # 3. Add a device
    print("\n[DEV] Adding test device...")

    device_in = DeviceCreate(
        name="MikroTik-SW",
        ip="192.168.2.3",
        connector_type="snmp",   # o "ssh" si así lo vas a manejar luego
        type="switch",           # <-- ESTE ERA EL CAMBIO CRÍTICO
        description="MikroTik Switch (Core)"
    )

    dev_id = await manager.add_device(device_in, username=router_user, password=router_pass)
    print(f"  - Device added with ID: {dev_id}")

    # 4. Verify device insertion
    devices = await manager.get_all_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "MikroTik-SW"
    print("  - Device retrieval: OK")

    # 5. Verify credential storage
    cred_id = devices[0]["credential_id"]
    cred = await manager.get_credential(cred_id)
    assert cred["password"] == router_pass
    print("  - Credential storage & decryption: OK")

    await db.disconnect()

    # Limpieza: solo borra si es db de prueba y si cleanup_db está activo
    if cleanup_db and Path(db_path).exists() and Path(db_path).name.startswith("test_"):
        os.remove(db_path)

    print("\n--- Verification Successful! ---")


if __name__ == "__main__":
    asyncio.run(verify())
