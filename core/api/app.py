"""
NetVault - FastAPI Application Factory
"""
import socket
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from core.config import Settings
from core.database.db import DatabaseManager
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager
from core.api.routes import devices, agents, audit, health, credentials, dashboard

logger = logging.getLogger("netvault.api")

def get_local_ip() -> str:
    """Auto-detect the container's IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the application"""
    config: Settings = app.state.config
    
    # Initialize Database (schema is auto-initialized inside connect())
    db = DatabaseManager(config.database.db_path)
    await db.connect()
    app.state.db = db

    # Initialize Security
    vault = CredentialVault(db, master_key=config.security.credentials_master_key)
    app.state.vault = vault
    
    # Initialize Core Engine
    device_manager = DeviceManager(db, vault)
    app.state.device_manager = device_manager
    
    logger.info("Core components initialized")
    
    yield
    
    # Shutdown
    await db.disconnect()
    logger.info("Application shutdown complete")

def create_app(config: Settings) -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title=config.app.name,
        version=config.app.version,
        description="Open source network monitoring & auditing platform",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Global state
    app.state.config = config
    app.state.start_time = datetime.now(timezone.utc)
    app.state.local_ip = get_local_ip()
    app.state.registered_agents = {}
    app.state.active_connectors = {}
    
    # ─── Include Routers ───
    app.include_router(dashboard.router)
    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(agents.router)
    app.include_router(audit.router)
    app.include_router(credentials.router)
    
    return app