"""
NetVault - Configuration Module
Centralized settings management using Pydantic v2 and YAML.
"""
import os
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger("netvault.config")

class AppConfig(BaseModel):
    name: str = "NetVault"
    version: str = "0.1.0"
    description: str = "Network Monitor & Auditor"
    environment: str = Field(default="development", alias="ENVIRONMENT")

class MCPConfig(BaseModel):
    port: int = Field(default=8444, alias="MCP_PORT")
    enabled: bool = Field(default=False, alias="MCP_ENABLED")
    auth_token: str = Field(default="mcp-default-token", alias="MCP_AUTH_TOKEN")

class ServerConfig(BaseModel):
    dashboard_host: str = Field(default="0.0.0.0", alias="DASHBOARD_HOST")
    dashboard_port: int = Field(default=8080, alias="DASHBOARD_PORT")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8443, alias="API_PORT")

class DatabaseConfig(BaseModel):
    db_path: str = Field(default="data/netvault.db", alias="DATABASE_URL")
    pool_size: int = 5

class SecurityConfig(BaseModel):
    secret_key: str = Field(default="insecure-default-secret-key", alias="SECRET_KEY")
    credentials_master_key: str = Field(..., alias="CREDENTIALS_MASTER_KEY")
    agent_auth_token: str = Field(..., alias="AGENT_AUTH_TOKEN")

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Optional[str] = "logs/netvault.log"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    max_size_mb: int = 10
    backup_count: int = 5

class PollingConfig(BaseModel):
    interval_minutes: int = 5

class AuditConfig(BaseModel):
    default_interval_minutes: int = 60
    scheduled_time: str = "02:00"
    retention_days: int = 90
    max_concurrent_audits: int = 5

class AgentsConfig(BaseModel):
    auth_required: bool = True
    heartbeat_interval_seconds: int = 30
    timeout_seconds: int = 120

class ModulesConfig(BaseModel):
    dashboard: bool = True
    api: bool = True
    mcp_server: bool = False
    scheduler: bool = True
    alerts: bool = False

class Settings(BaseSettings):
    """Main settings class merging YAML and Environment Variables"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    app: AppConfig = AppConfig()
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    security: Optional[SecurityConfig] = None
    logging: LoggingConfig = LoggingConfig()
    modules: ModulesConfig = ModulesConfig()
    polling: PollingConfig = PollingConfig()
    audit: AuditConfig = AuditConfig()
    agents: AgentsConfig = AgentsConfig()

    # Flat env-var fields used to build SecurityConfig
    secret_key: str = Field(default="insecure-default-secret-key", alias="SECRET_KEY")
    credentials_master_key: str = Field(..., alias="CREDENTIALS_MASTER_KEY")
    agent_auth_token: str = Field(..., alias="AGENT_AUTH_TOKEN")
    
    # MCP server specific (pulled from env)
    mcp_port: int = Field(default=8444, alias="MCP_PORT")
    mcp_enabled: bool = Field(default=False, alias="MCP_ENABLED")
    mcp_auth_token: str = Field(default="mcp-default-token", alias="MCP_AUTH_TOKEN")

    # Raw device inventory
    inventory: List[Dict[str, Any]] = []

    @model_validator(mode="after")
    def build_security(self) -> "Settings":
        self.security = SecurityConfig(
            SECRET_KEY=self.secret_key,
            CREDENTIALS_MASTER_KEY=self.credentials_master_key,
            AGENT_AUTH_TOKEN=self.agent_auth_token,
        )
        self.mcp = MCPConfig(
            port=self.mcp_port,
            enabled=self.mcp_enabled,
            auth_token=self.mcp_auth_token
        )
        return self

    mcp: MCPConfig = MCPConfig()

def find_config_file(filename: str) -> Optional[Path]:
    """Find a configuration file in common locations"""
    paths = [
        Path(f"/app/config/{filename}"),
        Path(f"config/{filename}"),
        Path(filename)
    ]
    for path in paths:
        if path.exists():
            return path
    return None

def load_yaml(path: Path) -> Dict[str, Any]:
    """Safely load a YAML file"""
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load YAML from {path}: {e}")
        return {}

@lru_cache()
def get_config() -> Settings:
    """Singleton configuration loader"""
    # 1. Load basic settings from YAML
    settings_path = find_config_file("settings.yml")
    yaml_data = {}
    if settings_path:
        yaml_data = load_yaml(settings_path)
        logger.info(f"Loaded base settings from {settings_path}")
    else:
        logger.warning("settings.yml not found, using defaults and environment variables")

    # 2. Load device inventory from YAML
    devices_path = find_config_file("devices.yml")
    inventory = []
    if devices_path:
        inventory_data = load_yaml(devices_path)
        inventory = inventory_data.get("devices", [])
        logger.info(f"Loaded {len(inventory)} devices from {devices_path}")

    # 3. Create Settings object (Pydantic will merge with ENV vars)
    try:
        # Map YAML structure to Pydantic model structure if needed
        # (Assuming YAML structure matches model structure)
        config_dict = yaml_data.copy()
        config_dict["inventory"] = inventory
        
        # Initialize Settings - this will pull from ENV vars as well
        settings = Settings(**config_dict)
        return settings
    except Exception as e:
        logger.critical(f"Configuration validation failed: {e}")
        # In production, we want to fail fast
        import sys
        sys.exit(1)
