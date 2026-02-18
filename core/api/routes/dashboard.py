"""
NetVault - Dashboard Router
Serves the main real-time monitoring interface.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone

router = APIRouter(tags=["Dashboard"])

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the real-time monitoring dashboard"""
    app = request.app
    config = app.state.config
    version = config.app.version
    ip = app.state.local_ip
    port = config.server.dashboard_port
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetVault Dashboard — v{version}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-card: #1e293b;
            --border: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #38bdf8;
            --accent-hover: #0ea5e9;
            --success: #4ade80;
            --warning: #fbbf24;
            --danger: #f87171;
            --glass: rgba(30, 41, 59, 0.7);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            padding-bottom: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        
        .logo {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .status-badge {{
            background: rgba(74, 222, 128, 0.1);
            color: var(--success);
            padding: 0.4rem 0.8rem;
            border-radius: 99px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid rgba(74, 222, 128, 0.2);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .dot {{
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
            100% {{ opacity: 1; }}
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            transition: transform 0.2s, border-color 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}
        
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
        }}
        
        .stat-sub {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }}
        
        .dashboard-layout {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
        }}
        
        .panel {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        
        .panel-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        
        th {{
            text-align: left;
            color: var(--text-muted);
            font-weight: 500;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border);
        }}
        
        td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        
        tr:last-child td {{ border: none; }}
        
        .status-pill {{
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .status-up {{ background: rgba(74, 222, 128, 0.1); color: var(--success); }}
        .status-down {{ background: rgba(248, 113, 113, 0.1); color: var(--danger); }}
        .status-unknown {{ background: rgba(148, 163, 184, 0.1); color: var(--text-muted); }}
        
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            gap: 0.5rem;
            text-decoration: none;
            width: 100%;
            margin-bottom: 0.5rem;
        }}
        
        .btn-primary {{ background: var(--accent); color: #000; }}
        .btn-primary:hover {{ background: var(--accent-hover); }}
        
        .btn-outline {{ 
            background: transparent; 
            border: 1px solid var(--border); 
            color: var(--text-primary); 
        }}
        .btn-outline:hover {{ border-color: var(--accent); color: var(--accent); }}
        
        footer {{
            margin-top: 3rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        footer a {{ color: var(--accent); text-decoration: none; }}
        
        .text-accent {{ color: var(--accent); }}
        .loading {{ opacity: 0.5; pointer-events: none; }}
        
        @media (max-width: 900px) {{
            .dashboard-layout {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container" id="app-container">
        <header>
            <div class="logo">🛡️ NetVault <span>Monitoring</span></div>
            <div class="status-badge">
                <span class="dot"></span> 
                <span id="system-status">System Online</span>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Network Devices</div>
                <div class="stat-value text-accent" id="count-devices">0</div>
                <div class="stat-sub" id="ip-display">IP: {ip}:{port}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Remote Agents</div>
                <div class="stat-value" id="count-agents">0</div>
                <div class="stat-sub" id="agent-status">Awaiting data...</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Stored Credentials</div>
                <div class="stat-value" id="count-credentials">0</div>
                <div class="stat-sub">Encrypted Vault</div>
            </div>
        </div>
        
        <div class="dashboard-layout">
            <div class="main-content">
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">Network Inventory</div>
                        <button class="btn-outline" style="width: auto; padding: 0.4rem 0.8rem;" onclick="refreshData()">Refresh</button>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Type</th>
                                <th>IP Address</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="devices-table">
                            <tr><td colspan="4" style="text-align:center; padding: 2rem;">Loading devices...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">Recent Audits</div>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Device</th>
                                <th>Action</th>
                                <th>Result</th>
                            </tr>
                        </thead>
                        <tbody id="audits-body">
                            <tr><td colspan="4" style="text-align:center; padding: 2rem;">No recent audits</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="sidebar">
                <div class="panel">
                    <div class="panel-title" style="margin-bottom: 1.2rem;">Quick Actions</div>
                    <button class="btn btn-primary" id="btn-audit" onclick="runAudit()">Run Global Audit</button>
                    <button class="btn btn-outline" id="btn-test" onclick="testDevices()">Test All Connectivity</button>
                </div>
                
                <div class="panel">
                    <div class="panel-title" style="margin-bottom: 1.2rem;">System Health</div>
                    <div style="font-size: 0.9rem; color: var(--text-secondary);">
                        <p style="margin-bottom: 0.5rem;">Uptime: <span id="uptime-val" class="text-accent">0h 0m</span></p>
                        <p style="margin-bottom: 0.5rem;">Environment: <span style="text-transform: capitalize;" class="text-accent">{config.app.environment}</span></p>
                        <p>API Version: <span class="text-accent">{version}</span></p>
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            NetVault v{version} &bull; <a href="/docs" target="_blank">Open API Documentation</a> &bull; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
        </footer>
    </div>

    <script>
        async function fetchData(url, options = {{}}) {{
            try {{
                const response = await fetch(url, options);
                if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
                return await response.json();
            }} catch (e) {{
                console.error(`Error fetching ${{url}}:`, e);
                return null;
            }}
        }}

        async function refreshData() {{
            const app = document.getElementById('app-container');
            app.classList.add('loading');
            
            // 1. Devices
            const devices = await fetchData('/api/devices');
            if (devices) {{
                document.getElementById('count-devices').textContent = devices.length;
                const table = document.getElementById('devices-table');
                table.innerHTML = devices.length === 0 ? 
                    '<tr><td colspan="4" style="text-align:center; padding: 2rem;">No devices found.</td></tr>' :
                    devices.map(d => `
                        <tr>
                            <td><strong>${{d.name}}</strong></td>
                            <td>${{d.type}}</td>
                            <td><code>${{d.ip}}</code></td>
                            <td><span class="status-pill status-${{d.status || 'unknown'}}">${{d.status || 'UNKNOWN'}}</span></td>
                        </tr>
                    `).join('');
            }}

            // 2. Agents
            const agents = await fetchData('/api/agents');
            if (agents) {{
                document.getElementById('count-agents').textContent = agents.length;
                const onlineCount = agents.filter(a => a.status === 'online').length;
                document.getElementById('agent-status').textContent = `${{onlineCount}} online of ${{agents.length}} registered`;
            }}

            // 3. Credentials
            const creds = await fetchData('/api/credentials');
            if (creds) {{
                document.getElementById('count-credentials').textContent = creds.length;
            }}

            // 4. Audits
            const audits = await fetchData('/api/audit/results?limit=5');
            if (audits) {{
                const body = document.getElementById('audits-body');
                body.innerHTML = audits.length === 0 ?
                    '<tr><td colspan="4" style="text-align:center; padding: 2rem;">No audit logs available.</td></tr>' :
                    audits.map(a => `
                        <tr>
                            <td style="font-size: 0.75rem; color: var(--text-muted);">${{new Date(a.timestamp).toLocaleString()}}</td>
                            <td>${{a.device_id || 'Global'}}</td>
                            <td>${{a.action}}</td>
                            <td><span style="color: ${{a.result === 'success' ? 'var(--success)' : 'var(--danger)'}}">${{a.result}}</span></td>
                        </tr>
                    `).join('');
            }}
            
            // 5. Uptime & Status
            const health = await fetchData('/health');
            if (health) {{
                const sec = health.uptime_seconds || 0;
                const h = Math.floor(sec / 3600);
                const m = Math.floor((sec % 3600) / 60);
                document.getElementById('uptime-val').textContent = `${{h}}h ${{m}}m`;
            }}

            app.classList.remove('loading');
        }}

        async function runAudit() {{
            if (!confirm('Start global network audit?')) return;
            const btn = document.getElementById('btn-audit');
            btn.disabled = true;
            btn.textContent = 'Running...';
            
            await fetchData('/api/audit/run', {{ method: 'POST' }});
            
            setTimeout(() => {{
                btn.disabled = false;
                btn.textContent = 'Run Global Audit';
                refreshData();
            }}, 2000);
        }}

        async function testDevices() {{
            const btn = document.getElementById('btn-test');
            btn.disabled = true;
            btn.textContent = 'Testing...';
            
            const devices = await fetchData('/api/devices');
            if (devices) {{
                for (const d of devices) {{
                    await fetchData(`/api/devices/${{d.id}}/test`, {{ method: 'POST' }});
                }}
            }}
            
            setTimeout(() => {{
                btn.disabled = false;
                btn.textContent = 'Test All Connectivity';
                refreshData();
            }}, 2000);
        }}

        // Initial load and periodic refresh
        refreshData();
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
