"""
Verification script for DeviceManager.
Tests initialization, device loading, and polling with a mock connector.
"""
import asyncio
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from core.database.db import DatabaseManager
from core.database import models, crud
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import get_device_manager
from core.engine.logger import setup_logging
from core.config import get_config
from connectors.base import BaseConnector, register_connector, ConnectionTestResult, InterfaceInfo

# Mock Connector for testing
@register_connector("mock")
class MockConnector(BaseConnector):
    async def connect(self) -> bool:
        self._is_connected = True
        return True

    async def disconnect(self):
        self._is_connected = False

    async def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(success=True, latency_ms=10.5)

    async def get_system_info(self) -> Dict[str, Any]:
        return {"model": "MockDevice", "os": "MockOS", "uptime": "10 days"}

    async def get_interfaces(self) -> List[InterfaceInfo]:
        return [
            InterfaceInfo(name="eth0", status="up", speed=1000, mac="00:11:22:33:44:55", ip="192.168.1.1"),
            InterfaceInfo(name="eth1", status="down")
        ]

    async def get_arp_table(self) -> List[Any]: return []
    async def get_mac_table(self) -> List[Any]: return []
    async def get_routes(self) -> List[Any]: return []
    async def run_audit(self) -> Any: return None

async def run_verification():
    print("--- Starting DeviceManager Verification ---")
    
    # 1. Setup
    config = get_config()
    setup_logging(config)
    
    test_db_path = "data/test_netvault.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = DatabaseManager(test_db_path)
    await db.connect()
    
    vault = CredentialVault(db, master_key="test-master-key")
    
    # 2. Add Test Credential
    await vault.store_credential("test-cred", "ssh_password", {"username": "admin", "password": "password123"})
    
    # 3. Add Test Device
    device_data = models.DeviceModel(
        name="Test-Router",
        type="router",
        ip="127.0.0.1",
        connector_type="mock",
        config_json={"credential_name": "test-cred"}
    )
    device_id = await crud.create_device(db, device_data)
    print(f"Added test device with ID: {device_id}")
    
    # 4. Initialize DeviceManager
    from core.engine.device_manager import get_device_manager
    manager = get_device_manager(db, vault)
    
    # 5. Load and Poll
    await manager.load_devices()
    print("Loading devices...")
    
    print("Polling device...")
    await manager.poll_device(device_id)
    
    # 6. Verify Results
    status = await manager.get_device_status(device_id)
    print(f"Device Status: {status}")
    
    data = await manager.get_device_data(device_id)
    print(f"Cached Data: {json.dumps(data, indent=2)}")
    
    # Verify DB update
    db_device = await crud.get_device(db, device_id)
    print(f"DB Status: {db_device['status']}")
    print(f"DB Last Seen: {db_device['last_seen']}")
    
    # 7. Test parallel polling
    print("Testing parallel polling...")
    await manager.poll_all(max_concurrent=2)
    
    # 8. Cleanup
    await db.disconnect()
    # os.remove(test_db_path)
    print("--- Verification Completed ---")

if __name__ == "__main__":
    asyncio.run(run_verification())
