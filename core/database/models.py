"""
NetVault - Database Models and Schema
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import json

# ─── Pydantic Models ───

class DeviceModel(BaseModel):
    id: Optional[int] = None
    name: str
    type: str  # e.g., router, switch, firewall
    ip: str
    port: int = 161
    connector_type: str  # snmp, ssh, rest_api
    config_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "unknown"
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class AgentModel(BaseModel):
    id: Optional[int] = None
    name: str
    type: str  # e.g., windows_ad
    hostname: str
    ip: str
    status: str = "offline"
    last_heartbeat: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)

class AuditLogModel(BaseModel):
    id: Optional[int] = None
    device_id: int
    agent_id: Optional[int] = None
    audit_type: str  # snmp_scan, ssh_audit, ad_audit
    result_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "success"  # success, warning, error
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class AlertRuleModel(BaseModel):
    id: Optional[int] = None
    name: str
    condition_json: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"  # info, warning, critical
    enabled: bool = True
    created_at: Optional[datetime] = None

class AlertModel(BaseModel):
    id: Optional[int] = None
    rule_id: int
    device_id: int
    message: str
    severity: str
    acknowledged: bool = False
    triggered_at: Optional[datetime] = None

class CredentialStoreModel(BaseModel):
    id: Optional[int] = None
    name: str
    type: str  # snmp_v2, ssh_password, api_key
    encrypted_data: str  # Base64 encoded ciphertext
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ─── DeviceManager Models ───

class DeviceCreate(BaseModel):
    name: str
    ip_address: str
    type: str
    description: Optional[str] = None
    credential_id: Optional[int] = None
    is_active: bool = True

class Device(DeviceCreate):
    id: Optional[int] = None
    created_at: Optional[datetime] = None

class CredentialCreate(BaseModel):
    name: str
    username: str = "admin"
    password: str

class Credential(BaseModel):
    id: Optional[int] = None
    name: str
    username: str
    encrypted_password: str
    created_at: Optional[datetime] = None

# ─── SQL Schema ───

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sys_config (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    ip TEXT,
    ip_address TEXT,
    port INTEGER DEFAULT 161,
    connector_type TEXT,
    config_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'unknown',
    description TEXT,
    credential_id INTEGER,
    is_active INTEGER DEFAULT 1,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credential_id) REFERENCES credentials (id)
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    hostname TEXT NOT NULL,
    ip TEXT NOT NULL,
    status TEXT DEFAULT 'offline',
    last_heartbeat TIMESTAMP,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    agent_id INTEGER,
    audit_type TEXT NOT NULL,
    result_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'success',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices (id),
    FOREIGN KEY (agent_id) REFERENCES agents (id)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    condition_json TEXT DEFAULT '{}',
    severity TEXT DEFAULT 'info',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES alert_rules (id),
    FOREIGN KEY (device_id) REFERENCES devices (id)
);

CREATE TABLE IF NOT EXISTS credential_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    encrypted_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT 'admin',
    encrypted_password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Initial configuration
INITIAL_SQL = """
INSERT OR IGNORE INTO sys_config (key, value) VALUES ('db_version', '1');
"""
