"""
NetVault - Network Monitor & Auditor
Main Entry Point
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("netvault")


def load_config() -> dict:
    """Load configuration from settings.yml"""
    # Try production path first, then development path
    paths = [
        Path("/app/config/settings.yml"),
        Path("config/settings.yml"),
    ]
    
    for config_path in paths:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info(f"Config loaded from: {config_path}")
            return config
    
    logger.error("No configuration file found!")
    sys.exit(1)


def print_banner(config: dict, host: str, port: int):
    """Print startup banner"""
    name = config["app"]["name"]
    version = config["app"]["version"]
    desc = config["app"].get("description", "")
    
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
    config = load_config()
    
    dashboard_host = config["server"]["dashboard"]["host"]
    dashboard_port = config["server"]["dashboard"]["port"]
    
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