"""
NetVault - Network Monitor & Auditor
Main Entry Point
"""
import logging
import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from core.config import Settings, get_config
from core.engine.logger import setup_logging, get_logger, log_system_info

# Initial temporary logger for startup errors before config is fully loaded
logging.basicConfig(level=logging.INFO)
logger = get_logger("netvault")


def print_banner(config: Settings, host: str, port: int):
    """Print startup banner"""
    name = config.app.name
    version = config.app.version
    desc = config.app.description
    
    banner = f"""
╔══════════════════════════════════════════════════╗
║                                                  ║
║   ███╗   ██╗███████╗████████╗██╗   ██╗ █████╗   ║
║   ████╗  ██║██╔════╝╚══██╔══╝██║   ██║██╔══██╗  ║
║   ██╔██╗ ██║█████╗     ██║   ██║   ██║███████║  ║
║   ██║╚██╗██║██╔══╝     ██║   ╚██╗ ██╔╝██╔══██║  ║
║   ██║ ╚████║███████╗   ██║    ╚████╔╝ ██║  ██║  ║
║   ╚═╝  ╚═══╝╚══════╝   ╚═╝     ╚═══╝  ╚═╝  ╚═╝  ║
║                                                  ║
║   {desc:<49}║
║   Version: {version:<39}║
║                                                  ║
╠══════════════════════════════════════════════════╣
║   Dashboard:  http://{host}:{port:<24}║
║   API Docs:   http://{host}:{port}/docs{' '*16}║
╚══════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    """Main entry point"""
    from core.config import get_config
    config = get_config()
    
    # Initialize structured logging
    setup_logging(config)
    log_system_info(config)
    
    dashboard_host = config.server.dashboard_host
    dashboard_port = config.server.dashboard_port
    
    print_banner(config, dashboard_host, dashboard_port)
    
    logger.info("Starting NetVault...")
    
    from core.api.app import create_app
    app = create_app(config)
    
    uvicorn.run(
        app,
        host=dashboard_host,
        port=dashboard_port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
