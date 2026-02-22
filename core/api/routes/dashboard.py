"""
NetVault - Dashboard Router
Serves the main real-time monitoring interface using Jinja2 templates.
"""
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from core.config import get_config

router = APIRouter(tags=["Dashboard"])

def get_templates(request: Request):
    return request.app.state.templates

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request, templates=Depends(get_templates)):
    """Serve the main monitoring dashboard"""
    config = request.app.state.config
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "version": config.app.version,
        "environment": config.app.environment,
        "local_ip": request.app.state.local_ip
    })

@router.get("/devices", response_class=HTMLResponse)
async def get_devices_page(request: Request, templates=Depends(get_templates)):
    """Serve the device management page"""
    config = request.app.state.config
    return templates.TemplateResponse("devices.html", {
        "request": request,
        "active_page": "devices",
        "version": config.app.version,
        "environment": config.app.environment
    })

@router.get("/agents", response_class=HTMLResponse)
async def get_agents_page(request: Request, templates=Depends(get_templates)):
    """Serve the remote agents page"""
    config = request.app.state.config
    # Pass the agent auth token from environment/config if available
    agent_token = os.getenv("AGENT_AUTH_TOKEN", "AGENT_AUTH_TOKEN_NOT_SET")
    
    return templates.TemplateResponse("agents.html", {
        "request": request,
        "active_page": "agents",
        "version": config.app.version,
        "environment": config.app.environment,
        "agent_auth_token": agent_token
    })

@router.get("/audit", response_class=HTMLResponse)
async def get_audit_page(request: Request, templates=Depends(get_templates)):
    """Serve the audit results page"""
    config = request.app.state.config
    return templates.TemplateResponse("audit.html", {
        "request": request,
        "active_page": "audit",
        "version": config.app.version,
        "environment": config.app.environment
    })

@router.get("/settings", response_class=HTMLResponse)
async def get_settings_page(request: Request, templates=Depends(get_templates)):
    """Serve the application settings page"""
    config = request.app.state.config
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_page": "settings",
        "config": config,
        "version": config.app.version,
        "environment": config.app.environment
    })
