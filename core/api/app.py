"""
NetVault - FastAPI Application Factory
"""
import socket
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse


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


def create_app(config: dict) -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title=config["app"]["name"],
        version=config["app"]["version"],
        description="Open source network monitoring & auditing platform",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Global state
    app.state.config = config
    app.state.start_time = datetime.now(timezone.utc)
    app.state.local_ip = get_local_ip()
    app.state.registered_agents = {}
    app.state.active_connectors = {}
    
    # ─── Routes ───
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for Docker and monitoring"""
        uptime = (datetime.now(timezone.utc) - app.state.start_time).total_seconds()
        return {
            "status": "healthy",
            "app": config["app"]["name"],
            "version": config["app"]["version"],
            "ip": app.state.local_ip,
            "uptime_seconds": round(uptime, 1),
            "agents_connected": len(app.state.registered_agents),
            "connectors_active": len(app.state.active_connectors)
        }
    
    @app.get("/api/info")
    async def api_info():
        """API information and available endpoints"""
        return {
            "app": config["app"]["name"],
            "version": config["app"]["version"],
            "description": config["app"].get("description", ""),
            "ip": app.state.local_ip,
            "endpoints": {
                "health": "GET /health",
                "info": "GET /api/info",
                "docs": "GET /docs",
                "dashboard": "GET /",
                "devices": "GET /api/devices (Phase 3)",
                "agents": "GET /api/agents (Phase 5)",
                "audit": "POST /api/audit/run (Phase 3)",
            },
            "modules": {
                "dashboard": config["modules"]["dashboard"],
                "api": config["modules"]["api"],
                "mcp_server": config["modules"]["mcp_server"],
                "scheduler": config["modules"]["scheduler"],
            }
        }
    
    @app.get("/api/agents/register", tags=["agents"])
    async def agent_register_info():
        """Info about how remote agents can register"""
        return {
            "message": "Agent registration endpoint (Phase 5)",
            "instructions": {
                "1": "Download the Windows AD agent from /api/agents/download/windows-ad",
                "2": "Install on your Windows server with access to Active Directory",
                "3": "Configure the agent with this server's IP and auth token",
                "4": "The agent will register automatically on startup"
            },
            "server_ip": app.state.local_ip,
            "auth_required": config["agents"]["auth_required"]
        }

    @app.get("/api/agents/download/{agent_type}")
    async def download_agent(agent_type: str):
        """Placeholder for agent download (Phase 5)"""
        available = ["windows-ad"]
        if agent_type not in available:
            return {"error": f"Agent '{agent_type}' not found", "available": available}
        return {
            "message": f"Agent '{agent_type}' download will be available in Phase 5",
            "agent_type": agent_type,
            "status": "coming_soon"
        }
    
    # ─── Dashboard ───
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Main dashboard page"""
        uptime = datetime.now(timezone.utc) - app.state.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        ip = app.state.local_ip
        port = config["server"]["dashboard"]["port"]
        version = config["app"]["version"]
        agents_count = len(app.state.registered_agents)
        connectors_count = len(app.state.active_connectors)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetVault — Network Monitor & Auditor</title>
    <meta http-equiv="refresh" content="30">
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-card: #1e293b;
            --border: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #38bdf8;
            --success: #4ade80;
            --warning: #fbbf24;
            --danger: #f87171;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        .header {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            font-size: 1.5rem;
            color: var(--accent);
        }}
        .header h1 span {{ color: var(--text-muted); font-weight: 400; font-size: 0.875rem; }}
        .header .status-badge {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(74, 222, 128, 0.1);
            border: 1px solid rgba(74, 222, 128, 0.3);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            color: var(--success);
            font-size: 0.875rem;
            font-weight: 600;
        }}
        .dot {{
            width: 8px; height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .main {{
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 2rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
        }}
        .card-label {{
            color: var(--text-muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        .card-value {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        .card-sub {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }}
        .section-title {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .module-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        .module-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .module-name {{
            font-weight: 500;
        }}
        .tag {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .tag-active {{ background: rgba(74,222,128,0.15); color: var(--success); }}
        .tag-pending {{ background: rgba(251,191,36,0.15); color: var(--warning); }}
        .tag-disabled {{ background: rgba(100,116,139,0.15); color: var(--text-muted); }}
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.8rem;
        }}
        .footer a {{ color: var(--accent); text-decoration: none; }}
        .info-row {{
            display: flex; gap: 2rem; flex-wrap: wrap;
            margin-top: 0.5rem;
        }}
        .info-item {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        .info-item strong {{ color: var(--text-primary); }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ NetVault <span>v{version}</span></h1>
        <div class="status-badge">
            <span class="dot"></span> System Online
        </div>
    </div>
    
    <div class="main">
        <!-- Metrics Cards -->
        <div class="grid">
            <div class="card">
                <div class="card-label">Server IP</div>
                <div class="card-value" style="font-size:1.25rem; color:var(--accent);">{ip}</div>
                <div class="card-sub">Port {port}</div>
            </div>
            <div class="card">
                <div class="card-label">Uptime</div>
                <div class="card-value">{hours}h {minutes}m</div>
                <div class="card-sub">{seconds}s</div>
            </div>
            <div class="card">
                <div class="card-label">Connectors</div>
                <div class="card-value">{connectors_count}</div>
                <div class="card-sub">Active connections</div>
            </div>
            <div class="card">
                <div class="card-label">Remote Agents</div>
                <div class="card-value">{agents_count}</div>
                <div class="card-sub">Connected agents</div>
            </div>
        </div>
        
        <!-- Modules Status -->
        <div class="section-title">System Modules</div>
        <div class="module-list">
            <div class="module-item">
                <span class="module-name">🌐 Web Dashboard</span>
                <span class="tag tag-active">Active</span>
            </div>
            <div class="module-item">
                <span class="module-name">⚡ REST API</span>
                <span class="tag tag-active">Active</span>
            </div>
            <div class="module-item">
                <span class="module-name">📡 SNMP Connector</span>
                <span class="tag tag-pending">Phase 3</span>
            </div>
            <div class="module-item">
                <span class="module-name">🔌 SSH Connector</span>
                <span class="tag tag-pending">Phase 3</span>
            </div>
            <div class="module-item">
                <span class="module-name">🪟 Windows AD Agent</span>
                <span class="tag tag-pending">Phase 5</span>
            </div>
            <div class="module-item">
                <span class="module-name">🤖 MCP Server (AI)</span>
                <span class="tag tag-disabled">Phase 4</span>
            </div>
        </div>
        
        <!-- Quick Info -->
        <div style="margin-top:2rem;">
            <div class="section-title">Quick Links</div>
            <div class="info-row">
                <div class="info-item">📖 <a href="/docs" style="color:var(--accent);">API Documentation</a></div>
                <div class="info-item">❤️ <a href="/health" style="color:var(--accent);">Health Check</a></div>
                <div class="info-item">ℹ️ <a href="/api/info" style="color:var(--accent);">System Info</a></div>
                <div class="info-item">📦 <a href="/api/agents/register" style="color:var(--accent);">Agent Setup</a></div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        NetVault — Open Source Network Monitor & Auditor<br>
        <a href="https://github.com/YOUR_USER/netvault" target="_blank">GitHub Repository</a>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html)
    
    return app