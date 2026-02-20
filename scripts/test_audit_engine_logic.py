
import asyncio
import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Mocking and setup for verification
from core.database.db import DatabaseManager
from core.database.models import AuditLogModel, AlertModel, DeviceModel
from core.database import crud
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager, get_device_manager
from core.engine.audit_engine import AuditEngine, get_audit_engine
from connectors.base import AuditResult, AuditCheck, ArpEntry, MacEntry

async def test_audit_engine():
    print("Starting Audit Engine Verification...")
    
    # Initialize DB (in-memory for test if possible, or just use a test file)
    db_path = "test_netvault.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            print(f"Warning: Could not remove {db_path}, it might be in use. Continuing anyway...")
    
    db = DatabaseManager(db_path)
    await db.connect()
    
    # Initialize Schema (should be handled by DatabaseManager if it calls SCHEMA_SQL)
    from core.database.models import SCHEMA_SQL
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip():
            await db.execute(statement)

    # Initialize Vault
    master_key = "test-master-key-32-chars-long-!!!"
    vault = CredentialVault(master_key)
    
    # Initialize Device Manager
    device_manager = DeviceManager(db, vault)
    
    # Initialize Audit Engine
    audit_engine = AuditEngine(db, device_manager)
    
    print("Engines initialized.")

    # 1. Setup Test Devices in DB
    dev1 = DeviceModel(name="Switch-01", type="switch", ip="192.168.1.1", connector_type="snmp")
    dev2 = DeviceModel(name="Switch-02", type="switch", ip="192.168.1.2", connector_type="snmp")
    did1 = await crud.create_device(db, dev1)
    did2 = await crud.create_device(db, dev2)
    
    await device_manager.load_devices()
    print(f"Created test devices: {did1}, {did2}")

    # Set status in DB and reload
    await crud.update_device(db, did1, {"status": "online"})
    await crud.update_device(db, did2, {"status": "online"})
    await device_manager.load_devices()

    # 2. Mock some data in cache for Network Audit
    # We'll simulate that we polled these devices
    device_manager._cache[did1] = {
        "status": "online",
        "arp_table": [
            {"ip": "192.168.1.10", "mac": "00:11:22:33:44:55"},
            {"ip": "192.168.1.11", "mac": "00:11:22:33:44:66"}
        ],
        "mac_table": [
            {"mac": "00:11:22:33:44:55", "port": "GigabitEthernet1/0/1"},
            {"mac": "AA:BB:CC:DD:EE:FF", "port": "GigabitEthernet1/0/2"}
        ]
    }
    device_manager._cache[did2] = {
        "status": "online",
        "arp_table": [
            {"ip": "192.168.1.10", "mac": "00:11:22:33:44:AA"}, # Duplicate IP (1.10 has two macs)
            {"ip": "192.168.1.12", "mac": "AA:BB:CC:DD:EE:FF"}  # Duplicate MAC (AA... seen on did1 and did2)
        ],
        "mac_table": [
            {"mac": "AA:BB:CC:DD:EE:FF", "port": "GigabitEthernet1/0/1"}
        ]
    }
    
    # Mark devices as online in cache/memory
    device_manager._devices[did1]["status"] = "online"
    device_manager._devices[did2]["status"] = "online"

    print(f"Online Device IDs: {[did for did, d in device_manager._devices.items() if d.get('status') == 'online']}")
    print(f"Cache Keys: {list(device_manager._cache.keys())}")

    # 3. Run Network Audit
    print("Running Network Audit...")
    try:
        async def mock_refresh(device_id):
            print(f"Mock refresh for {device_id}")
            pass
        
        device_manager.refresh_device_data = mock_refresh
        
        network_result = await audit_engine.run_network_audit()
        
        print("\nNetwork Audit Results:")
        print(f"Summary: {network_result.summary}")
        for check in network_result.checks:
            print(f" - [{check.status}] {check.name}: {check.message}")

        # 4. Verify Database Entries
        logs = await crud.list_audit_logs(db)
        print(f"\nAudit Logs in DB: {len(logs)}")
        for log in logs:
            print(f" - Log ID {log['id']}: Device {log['device_id']}, Type {log['audit_type']}, Status {log['status']}")

        alerts = await crud.list_active_alerts(db)
        print(f"\nActive Alerts in DB: {len(alerts)}")

    finally:
        # Cleanup
        await db.disconnect()
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except:
            pass
        print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(test_audit_engine())
