"""
NetVault - FastAPI Application Factory
"""
import os
import socket
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import Settings
from core.database.db import DatabaseManager
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import DeviceManager
from core.engine.audit_engine import AuditEngine
from core.engine.network_discovery import NetworkDiscoveryEngine
from core.engine.scheduler import get_scheduler
from core.api.routes import devices, agents, audit, health, credentials, dashboard, network

logger = logging.getLogger("netvault.api")


def get_local_ip(config_ip: Optional[str] = None) -> str:
    """Auto-detect the container's IP address or use config override"""
    env_ip = os.getenv("NETVAULT_SERVER_IP") or os.getenv("LOCAL_IP")
    if env_ip:
        return env_ip

    if config_ip and config_ip not in ["0.0.0.0", "::"]:
        return config_ip
        
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
    
    try:
        # Initialize Database (schema is auto-initialized inside connect())
        db = DatabaseManager(config.database.db_path)
        await db.connect()
        app.state.db = db

        # Initialize Security
        vault = CredentialVault(db, master_key=config.security.credentials_master_key)
        app.state.vault = vault
        
        # Initialize Core Engine
        from core.engine.device_manager import get_device_manager
        device_manager = get_device_manager(db, vault)
        app.state.device_manager = device_manager

        # Initialize Discovery Engine
        app.state.network_discovery = NetworkDiscoveryEngine(db)
        
        # Initialize Audit Engine
        audit_engine = AuditEngine(db, device_manager)
        app.state.audit_engine = audit_engine

        # Initialize and Start Scheduler
        scheduler = get_scheduler()
        await scheduler.start()
        app.state.scheduler = scheduler

        # Start periodic polling loop
        await device_manager.start_scheduled_polling(
            interval_minutes=config.polling.interval_minutes,
            agent_offline_seconds=config.polling.agent_offline_seconds,
            device_concurrency=config.polling.device_concurrency,
        )
        
        logger.info("Core components initialized")
        
        # Start MCP Server if enabled
        if config.modules.mcp_server or config.mcp.enabled:
            from core.mcp_server.server import start_mcp_server
            app.state.mcp_server = await start_mcp_server(db, device_manager, audit_engine)
            logger.info(f"MCP Server started on port {config.mcp.port}")
            
    except Exception as e:
        logger.critical(f"❌ FATAL: Startup failed: {e}", exc_info=True)
        # Re-raise to ensure the application fails to start
        raise

    logger.info("✅ All components initialized")
    yield
    
    # Shutdown
    try:
        if hasattr(app.state, 'device_manager'):
            await app.state.device_manager.stop_scheduled_polling()
        if hasattr(app.state, 'scheduler'):
            await app.state.scheduler.stop()
        if hasattr(app.state, 'db'):
            await app.state.db.disconnect()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

def create_app(config: Settings) -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title=config.app.name,
        version=config.app.version,
        description="Open source network monitoring & auditing platform",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        redirect_slashes=True
    )
    
    # Global state
    app.state.config = config
    app.state.start_time = datetime.now(timezone.utc)
    app.state.local_ip = get_local_ip(config.server.dashboard_host)
    app.state.registered_agents = {}
    app.state.active_connectors = {}
    
    # Static files and Templates
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "dashboard", "templates")
    static_dir = os.path.join(base_dir, "dashboard", "static")
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.state.templates = Jinja2Templates(directory=template_dir)

    # ─── Include Routers ───
    app.include_router(dashboard.router)
    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(agents.router)
    app.include_router(audit.router)
    app.include_router(credentials.router)
    app.include_router(network.router)

    existing_device_detail = any(
        getattr(route, "path", None) == "/devices/{device_id}" and "GET" in getattr(route, "methods", set())
        for route in app.routes
    )

    if not existing_device_detail:
        @app.get("/devices/{device_id}", response_class=HTMLResponse, include_in_schema=False)
        async def get_device_detail_page(request: Request, device_id: int):
            """Serve device detail page by id."""
            config = request.app.state.config
            return request.app.state.templates.TemplateResponse(
                "device_detail.html",
                {
                    "request": request,
                    "active_page": "devices",
                    "device_id": device_id,
                    "version": config.app.version,
                    "environment": config.app.environment,
                },
            )
    
    return app
