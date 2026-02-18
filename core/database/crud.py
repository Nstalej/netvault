"""
NetVault - Database CRUD Helpers
Async functions for interacting with all database models.
"""
import json
import logging
from typing import List, Optional, Any, Dict
from datetime import datetime

from core.database.db import DatabaseManager
from core.database.models import (
    DeviceModel, AgentModel, AuditLogModel, 
    AlertRuleModel, AlertModel, CredentialStoreModel
)

logger = logging.getLogger("netvault.crud")

# ─── Device CRUD ───

async def create_device(db: DatabaseManager, device: DeviceModel) -> int:
    query = """
    INSERT INTO devices (name, type, ip, port, connector_type, config_json, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        device.name, device.type, device.ip, device.port, 
        device.connector_type, json.dumps(device.config_json), device.status
    )
    return await db.execute(query, params)

async def get_device(db: DatabaseManager, device_id: int) -> Optional[Dict[str, Any]]:
    row = await db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
    if row:
        row = dict(row)
        row["config_json"] = json.loads(row["config_json"])
    return row

async def list_devices(db: DatabaseManager) -> List[Dict[str, Any]]:
    rows = await db.fetch_all("SELECT * FROM devices")
    result = []
    for row in rows:
        d = dict(row)
        d["config_json"] = json.loads(d["config_json"])
        result.append(d)
    return result

async def update_device(db: DatabaseManager, device_id: int, data: Dict[str, Any]):
    if "config_json" in data:
        data["config_json"] = json.dumps(data["config_json"])
    
    data["updated_at"] = datetime.now()
    
    keys = [f"{k} = ?" for k in data.keys()]
    query = f"UPDATE devices SET {', '.join(keys)} WHERE id = ?"
    params = list(data.values()) + [device_id]
    await db.execute(query, tuple(params))

async def delete_device(db: DatabaseManager, device_id: int):
    await db.execute("DELETE FROM devices WHERE id = ?", (device_id,))

# ─── Agent CRUD ───

async def create_agent(db: DatabaseManager, agent: AgentModel) -> int:
    query = """
    INSERT INTO agents (name, type, hostname, ip, status, config_json)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        agent.name, agent.type, agent.hostname, agent.ip, 
        agent.status, json.dumps(agent.config_json)
    )
    return await db.execute(query, params)

async def get_agent(db: DatabaseManager, agent_id: int) -> Optional[Dict[str, Any]]:
    row = await db.fetch_one("SELECT * FROM agents WHERE id = ?", (agent_id,))
    if row:
        row = dict(row)
        row["config_json"] = json.loads(row["config_json"])
    return row

async def update_agent_heartbeat(db: DatabaseManager, agent_id: int, status: str = "online"):
    await db.execute(
        "UPDATE agents SET last_heartbeat = CURRENT_TIMESTAMP, status = ? WHERE id = ?",
        (status, agent_id)
    )

# ─── Audit Log CRUD ───

async def create_audit_log(db: DatabaseManager, log: AuditLogModel) -> int:
    query = """
    INSERT INTO audit_logs (device_id, agent_id, audit_type, result_json, status, completed_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        log.device_id, log.agent_id, log.audit_type, 
        json.dumps(log.result_json), log.status, log.completed_at
    )
    return await db.execute(query, params)

async def list_audit_logs(db: DatabaseManager, device_id: Optional[int] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM audit_logs"
    params = ()
    if device_id:
        query += " WHERE device_id = ?"
        params = (device_id,)
    
    rows = await db.fetch_all(query, params)
    result = []
    for row in rows:
        d = dict(row)
        d["result_json"] = json.loads(d["result_json"])
        result.append(d)
    return result

# ─── Alert Rule and Alert CRUD ───

async def create_alert_rule(db: DatabaseManager, rule: AlertRuleModel) -> int:
    query = """
    INSERT INTO alert_rules (name, condition_json, severity, enabled)
    VALUES (?, ?, ?, ?)
    """
    params = (rule.name, json.dumps(rule.condition_json), rule.severity, 1 if rule.enabled else 0)
    return await db.execute(query, params)

async def trigger_alert(db: DatabaseManager, alert: AlertModel) -> int:
    query = """
    INSERT INTO alerts (rule_id, device_id, message, severity, acknowledged)
    VALUES (?, ?, ?, ?, ?)
    """
    params = (alert.rule_id, alert.device_id, alert.message, alert.severity, 0)
    return await db.execute(query, params)

async def list_active_alerts(db: DatabaseManager) -> List[Dict[str, Any]]:
    rows = await db.fetch_all("SELECT * FROM alerts WHERE acknowledged = 0")
    return [dict(row) for row in rows]

# ─── Credential Store CRUD ───

async def create_credential(db: DatabaseManager, cred: CredentialStoreModel) -> int:
    query = """
    INSERT INTO credential_store (name, type, encrypted_data)
    VALUES (?, ?, ?)
    """
    params = (cred.name, cred.type, cred.encrypted_data)
    return await db.execute(query, params)

async def get_credential(db: DatabaseManager, cred_id: int) -> Optional[Dict[str, Any]]:
    row = await db.fetch_one("SELECT * FROM credential_store WHERE id = ?", (cred_id,))
    return dict(row) if row else None
