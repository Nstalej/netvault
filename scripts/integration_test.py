"""
NetVault - Comprehensive Integration Test Script
Verifies all modules and end-to-end functionality.
"""
import asyncio
import os
import sys
import httpx
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_result(name, success, message=""):
    status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
    msg = f" - {message}" if message else ""
    print(f"[{status}] {name}{msg}")
    return success

async def run_tests(args):
    results = []
    print(f"{BOLD}Starting NetVault Integration Tests...{RESET}\n")

    # 1. Module Imports
    try:
        import core.main
        import core.config
        import core.database.db
        import core.engine.device_manager
        import connectors.snmp.snmp_connector
        import connectors.ssh_connector.ssh_connector
        results.append(print_result("Module Imports", True))
    except ImportError as e:
        results.append(print_result("Module Imports", False, str(e)))

    # 2. Config Loading
    try:
        from core.config import get_config
        config = get_config()
        results.append(print_result("Config Loading", config is not None))
    except Exception as e:
        results.append(print_result("Config Loading", False, str(e)))

    # 3. Database Connection
    from core.database.db import DatabaseManager
    db = DatabaseManager(config.database.db_path)
    try:
        await db.connect()
        results.append(print_result("Database Connection", True))
    except Exception as e:
        results.append(print_result("Database Connection", False, str(e)))

    # 4. Credential Vault
    from core.engine.credential_vault import CredentialVault
    vault = CredentialVault(db, master_key=config.security.credentials_master_key)
    try:
        creds = {"user": "test", "pass": "secret"}
        await vault.store_credential("test-vault", "ssh", creds)
        retrieved = await vault.get_credential("test-vault")
        success = retrieved == creds
        results.append(print_result("Credential Vault (Store/Retrieve)", success))
        await vault.delete_credential("test-vault")
    except Exception as e:
        results.append(print_result("Credential Vault", False, str(e)))

    # API Tests
    async with httpx.AsyncClient(base_url=args.server_url) as client:
        # 5, 6, 11. API Device CRUD & Info
        try:
            # Health
            resp = await client.get("/health")
            results.append(print_result("API Health Endpoint", resp.status_code == 200))

            # Create Device
            device_data = {
                "name": "Test-Device",
                "type": "switch",
                "ip": "127.0.0.1",
                "port": 161,
                "connector_type": "snmp",
                "config": {"credential_name": "test-cred"}
            }
            resp = await client.post("/api/devices/", json=device_data)
            if resp.status_code == 201:
                device_id = resp.json()["id"]
                # Verify config_json (Issue 1)
                resp_get = await client.get(f"/api/devices/{device_id}")
                success = resp_get.json().get("config_json", {}).get("credential_name") == "test-cred"
                results.append(print_result("API Device Creation (config_json check)", success))
                
                # Update
                await client.put(f"/api/devices/{device_id}", json={"status": "testing"})
                # Delete
                await client.delete(f"/api/devices/{device_id}")
                results.append(print_result("API Device CRUD", True))
            else:
                results.append(print_result("API Device CRUD", False, f"POST failed: {resp.status_code}"))
        except Exception as e:
            results.append(print_result("API Endpoints", False, str(e)))

    # 7, 8, 9. Connector & DeviceManager (Manual if IP provided)
    if args.test_device_ip:
        try:
            from core.engine.device_manager import get_device_manager
            manager = get_device_manager(db, vault)
            
            # Create credential for testing
            await vault.store_credential("test-ssh", "ssh", {"username": args.test_device_user, "password": args.test_device_password})
            
            # Create device in DB
            from core.database.models import DeviceModel
            from core.database import crud
            test_dev = DeviceModel(
                name="Integration-Test-SSH",
                type="router",
                ip=args.test_device_ip,
                connector_type="ssh",
                config_json={"credential_name": "test-ssh", "device_type": "mikrotik"}
            )
            dev_id = await crud.create_device(db, test_dev)
            
            # Test connectivity
            print(f"Testing connectivity to {args.test_device_ip}...")
            result = await manager.test_device(dev_id)
            results.append(print_result("SSH Connector Functionality", result.success, result.error_message))
            
            # Cleanup
            await crud.delete_device(db, dev_id)
            await vault.delete_credential("test-ssh")
        except Exception as e:
            results.append(print_result("DeviceManager/Connector Test", False, str(e)))

    # 12, 13. UI
    async with httpx.AsyncClient(base_url=args.server_url) as client:
        try:
            resp = await client.get("/")
            results.append(print_result("Dashboard Load", resp.status_code == 200))
            resp = await client.get("/docs")
            results.append(print_result("Swagger Load", resp.status_code == 200))
        except Exception as e:
            results.append(print_result("UI Load", False, str(e)))

    # Summary
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"\n{BOLD}Integration Test Summary:{RESET}")
    print(f"Total:  {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    await db.disconnect()
    
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NetVault Integration Test")
    parser.add_argument("--server-url", default="http://localhost:8080", help="NetVault server URL")
    parser.add_argument("--test-device-ip", help="Real device IP for connectivity test")
    parser.add_argument("--test-device-user", default="admin", help="SSH User")
    parser.add_argument("--test-device-password", help="SSH Password")
    
    args = parser.parse_args()
    asyncio.run(run_tests(args))
