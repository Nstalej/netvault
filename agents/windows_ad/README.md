# NetVault Windows Active Directory Agent

This agent provides remote Active Directory auditing capabilities for the NetVault platform.

## Features
- Self-registration with NetVault server
- Real-time heartbeat monitoring
- AD User/Group/Computer/GPO data collection
- Security audit checks (stale accounts, password policies, etc.)
- Runs as a Windows Service

## Installation

1. **Prerequisites**:
   - Windows Server 2016+
   - Python 3.11+
   - Network access to Domain Controller (LDAP/S)
   - Network access to NetVault Server (HTTPS)

2. **Quick Install (PowerShell)**:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
   ./installer/install.ps1
   ```

3. **Manual Configuration**:
   Edit `config.yml` in the service directory:
   ```yaml
   netvault:
     server_url: "http://<netvault-ip>:8000"
     agent_token: "your-auth-token"
   ad:
     server: "dc01.domain.local"
     use_ssl: true
     base_dn: "DC=domain,DC=local"
   ```

## Development
- `service/ad_agent.py`: Main service logic
- `service/ad_collector.py`: AD query engine
- `service/ad_auditor.py`: Audit rules and checks
