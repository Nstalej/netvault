"""
NetVault - Health and Info Routes
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, Depends, Request

from core.api.deps import get_current_user, require_admin
from core.config import Settings

router = APIRouter(tags=["system"])
v1_router = APIRouter(prefix="/api/v1", tags=["system-v1"])


@router.get("/health")
@v1_router.get("/health")
async def health_check(request: Request):
    """System health check for Docker and monitoring"""
    checks = {
        "database": hasattr(request.app.state, "db") and request.app.state.db is not None,
        "vault": hasattr(request.app.state, "vault") and request.app.state.vault is not None,
        "device_manager": hasattr(request.app.state, "device_manager") and request.app.state.device_manager is not None,
    }
    all_ok = all(checks.values())

    config: Settings = request.app.state.config
    start_time: datetime = request.app.state.start_time

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()

    return {
        "status": "healthy" if all_ok else "degraded",
        "components": checks,
        "app": config.app.name,
        "version": config.app.version,
        "uptime_seconds": round(uptime, 1),
        "ip": request.app.state.local_ip,
    }


@router.get("/api/info")
async def api_info(request: Request):
    """Detailed system and API information"""
    config: Settings = request.app.state.config
    return {
        "app": config.app.name,
        "version": config.app.version,
        "description": config.app.description,
        "ip": request.app.state.local_ip,
        "modules": {
            "dashboard": config.modules.dashboard,
            "api": config.modules.api,
            "mcp_server": config.modules.mcp_server,
            "scheduler": config.modules.scheduler,
            "alerts": config.modules.alerts,
        },
        "endpoints": {
            "health": "/health",
            "info": "/api/info",
            "docs": "/docs",
            "dashboard": "/",
            "devices": "/api/devices",
            "agents": "/api/agents",
            "audit": "/api/audit",
            "credentials": "/api/credentials",
        },
    }


@router.get("/api/logs")
async def get_logs(
    request: Request,
    lines: int = 100,
    _=Depends(get_current_user),
):
    """Fetch the last N lines from the application log file"""
    config: Settings = request.app.state.config
    log_file = config.logging.file

    if not log_file or not os.path.exists(log_file):
        # Fallback to current directory logs if config path fails
        alt_path = Path("logs/netvault.log")
        if alt_path.exists():
            log_file = alt_path
        else:
            return {"logs": [], "error": "Log file not found"}

    try:
        with open(log_file, "r") as f:
            # Simple tail implementation
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]

            parsed_logs = []
            for line in last_lines:
                try:
                    parsed_logs.append(json.loads(line))
                except:
                    parsed_logs.append({"message": line.strip(), "level": "INFO", "timestamp": ""})

            return {"logs": parsed_logs}
    except Exception as e:
        return {"logs": [], "error": str(e)}


@router.get("/api/settings")
async def get_settings(request: Request, _=Depends(require_admin)):
    """Get dynamic settings from database and config"""
    db = request.app.state.db
    config = request.app.state.config

    # Load overrides from database
    db_settings = await db.fetch_all("SELECT key, value FROM sys_config")
    settings_map = {row["key"]: row["value"] for row in db_settings}

    return {
        "app_name": config.app.name,
        "version": config.app.version,
        "retention_days": int(settings_map.get("retention_days", config.audit.retention_days)),
        "dashboard_port": config.server.dashboard_port,
        "environment": config.app.environment,
    }


@router.post("/api/settings")
async def update_settings(request: Request, data: Dict[str, Any], _=Depends(require_admin)):
    """Update dynamic settings in database"""
    db = request.app.state.db

    for key, value in data.items():
        await db.execute("INSERT OR REPLACE INTO sys_config (key, value) VALUES (?, ?)", (key, str(value)))

    return {"status": "success", "message": "Settings updated successfully"}
