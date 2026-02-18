"""
NetVault - Expanded Database Verification Script
Tests all new models and CRUD helpers.
"""
import asyncio
import os
import json
from core.database.db import DatabaseManager
from core.database.models import (
    DeviceModel, AgentModel, AuditLogModel, 
    AlertRuleModel, AlertModel, CredentialStoreModel
)
from core.database import crud

async def verify():
    print("--- Expanded Database Verification ---")
    
    db_path = "test_expanded.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = DatabaseManager(db_path)
    await db.connect()
    
    # 1. Test Device CRUD
    print("\n[DEV] Testing Device CRUD...")
    dev = DeviceModel(
        name="Core-SW01",
        type="switch",
        ip="10.0.0.5",
        connector_type="snmp",
        config_json={"community": "private"}
    )
    dev_id = await crud.create_device(db, dev)
    print(f"  - Device created with ID: {dev_id}")
    
    retrieved_dev = await crud.get_device(db, dev_id)
    assert retrieved_dev["name"] == "Core-SW01"
    assert retrieved_dev["config_json"]["community"] == "private"
    print("  - Device retrieval & JSON parsing: OK")
    
    # 2. Test Agent CRUD
    print("\n[AGENT] Testing Agent CRUD...")
    agent = AgentModel(
        name="AD-Scanner-01",
        type="windows_ad",
        hostname="SRV-AD-01",
        ip="10.0.0.10"
    )
    agent_id = await crud.create_agent(db, agent)
    await crud.update_agent_heartbeat(db, agent_id)
    print("  - Agent creation & heartbeat: OK")
    
    # 3. Test Audit Log CRUD
    print("\n[AUDIT] Testing Audit Log CRUD...")
    log = AuditLogModel(
        device_id=dev_id,
        agent_id=agent_id,
        audit_type="snmp_config_backup",
        result_json={"status": "complete", "backup_size": "12KB"}
    )
    log_id = await crud.create_audit_log(db, log)
    logs = await crud.list_audit_logs(db, dev_id)
    assert len(logs) == 1
    assert logs[0]["result_json"]["backup_size"] == "12KB"
    print("  - Audit log creation & filter: OK")
    
    # 4. Test Alerts
    print("\n[ALERT] Testing Alerts...")
    rule_id = await crud.create_alert_rule(db, AlertRuleModel(
        name="High CPU",
        condition_json={"metric": "cpu", "op": ">", "val": 90},
        severity="critical"
    ))
    await crud.trigger_alert(db, AlertModel(
        rule_id=rule_id,
        device_id=dev_id,
        message="CPU is at 95%",
        severity="critical"
    ))
    active = await crud.list_active_alerts(db)
    assert len(active) == 1
    print("  - Alert rule & trigger: OK")
    
    # 5. Test Credentials
    print("\n[CRED] Testing CredentialStore...")
    cred_id = await crud.create_credential(db, CredentialStoreModel(
        name="Router-SSH",
        type="ssh_password",
        encrypted_data="S01FUmV0X0VOQ1JZUFRFRA==" # Mock encrypted data
    ))
    retrieved_cred = await crud.get_credential(db, cred_id)
    assert retrieved_cred["name"] == "Router-SSH"
    print("  - Credential storage: OK")
    
    await db.disconnect()
    os.remove(db_path)
    print("\n--- All Database Checks Passed! ---")

if __name__ == "__main__":
    asyncio.run(verify())
