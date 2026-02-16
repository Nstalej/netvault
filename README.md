# 🛡️ NetVault — Network Monitor & Auditor

Open source network monitoring and auditing platform. Docker-based, MCP-ready,
with a web dashboard for real-time infrastructure visibility.

## Features

- **Network Device Monitoring** — SNMP, SSH, and REST API connectors for
  MikroTik, Cisco, Sophos, and other network equipment
- **Active Directory Auditing** — Remote Windows agent for AD health checks,
  GPO verification, user auditing, and replication monitoring
- **Web Dashboard** — Real-time status, audit results, and alerts
- **MCP Integration** — Connect with Claude AI or other LLMs for intelligent
  network analysis
- **Modular Architecture** — Enable only what you need, add connectors as
  your infrastructure grows
- **Docker-First** — Deploy anywhere with `docker compose up -d`

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/nstalej/netvault.git
cd netvault
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings (timezone, ports, secret keys)
```

### 3. Launch

```bash
docker compose up -d
```

### 4. Access the dashboard

Open your browser: `http://YOUR_SERVER_IP:8080`

## Architecture

```
[Claude/AI] ←→ [MCP Server] ←→ [Core Engine] ←→ [Network Devices]
                                      ↑
                                [Web Dashboard]
                                      ↑
                              [Remote Agents] → [Windows AD]
```

## Development Setup

```bash
# Clone
git clone https://github.com/nstalej/netvault.git
cd netvault

# Create Conda environment
conda env create -f environment.yml
conda activate netvault

# Copy config
cp .env.example .env

# Run locally
python -m core.main
```

## Windows AD Agent

The Windows agent runs on your Domain Controller (or any server with AD access)
and reports back to the NetVault container.

Download and installation instructions: see `agents/windows_ad/README.md`
