"""
NetVault - Health and Info Routes
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Request

from core.config import Settings

router = APIRouter(tags=["system"])

@router.get("/api/v1/health")
async def health_check(request: Request):
    """System health check for Docker and monitoring"""
    checks = {
        "database": hasattr(request.app.state, 'db') and request.app.state.db is not None,
        "vault": hasattr(request.app.state, 'vault') and request.app.state.vault is not None,
        "device_manager": hasattr(request.app.state, 'device_manager') and request.app.state.device_manager is not None,
    }
    all_ok = all(checks.values())
    
    config: Settings = request.app.state.config
    start_time: datetime = request.app.state.start_time
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
    
    return {
        "status": "healthy" if all_ok else "degraded",
        "components": checks,
        "app": config.app.name,
        "version": config.app.version,
        "uptime_seconds": round(uptime, 1),
        "ip": request.app.state.local_ip
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
            "alerts": config.modules.alerts
        },
        "endpoints": {
            "health": "/health",
            "info": "/api/info",
            "docs": "/docs",
            "dashboard": "/",
            "devices": "/api/devices",
            "agents": "/api/agents",
            "audit": "/api/audit",
            "credentials": "/api/credentials"
        }
    }
