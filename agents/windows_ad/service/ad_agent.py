"""
NetVault - Windows AD Agent - Main Service
"""
import os
import time
import asyncio
import logging
import yaml
import socket
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

#from ad_collector import ADCollector
#from ad_auditor import ADAuditor
from agents.windows_ad.service.ad_collector import ADCollector
from agents.windows_ad.service.ad_auditor import ADAuditor

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ADAgent")

class ADAgent:
    def __init__(self, config_path: str = "config.yml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.server_url = self.config['netvault']['server_url'].rstrip('/')
        self.token = self.config['netvault']['agent_token']
        self.agent_id = None
        self.hostname = socket.gethostname()
        self.ip = socket.gethostbyname(self.hostname)
        
        self.collector = ADCollector(
            server=self.config['ad']['server'],
            user=self.config['ad']['user'],
            password=self.config['ad']['password'],
            base_dn=self.config['ad']['base_dn'],
            use_ssl=self.config['ad'].get('use_ssl', True)
        )
        self.auditor = ADAuditor()

    def _load_config(self) -> Dict[str, Any]:
        load_dotenv()
        if not os.path.exists(self.config_path):
            logger.error(f"Config file not found: {self.config_path}")
            # Minimal default for testing
            return {
                'netvault': {'server_url': 'http://localhost:8000', 'agent_token': 'dev-token'},
                'ad': {'server': 'localhost', 'user': 'admin', 'password': 'password', 'base_dn': 'DC=domain,DC=local'}
            }
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Override with environment variables if present
        if os.getenv('AGENT_TOKEN'):
            config['netvault']['agent_token'] = os.getenv('AGENT_TOKEN')
            
        return config

    async def register(self) -> bool:
        """Register agent with NetVault server"""
        url = f"{self.server_url}/api/agents/register"
        payload = {
            "name": f"AD Agent ({self.hostname})",
            "type": "windows_ad",
            "hostname": self.hostname,
            "ip": self.ip,
            "status": "online",
            "config_json": {
                "ad_server": self.config['ad']['server'],
                "base_dn": self.config['ad']['base_dn']
            }
        }
        
        headers = {"X-Agent-Token": self.token}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code in [201, 200]:
                    self.agent_id = response.json().get("agent_id")
                    logger.info(f"Agent registered successfully. ID: {self.agent_id}")
                    return True
                else:
                    logger.error(f"Registration failed: {response.status_code} - {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Error during registration: {str(e)}")
                return False

    async def send_heartbeat(self):
        """Send heartbeat to server"""
        if not self.agent_id:
            return
            
        url = f"{self.server_url}/api/agents/{self.agent_id}/heartbeat"
        headers = {"X-Agent-Token": self.token}
        
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, headers=headers, timeout=5)
                logger.debug("Heartbeat sent")
            except Exception as e:
                logger.warning(f"Heartbeat failed: {str(e)}")

    async def run_audit(self):
        """Perform AD audit and send results"""
        logger.info("Starting AD audit...")
        ad_data = self.collector.collect_all()
        audit_results = self.auditor.audit(ad_data)
        
        # In a real implementation, we would POST this to /api/audit/logs or similar
        # For now, we log the summary
        logger.info(f"Audit completed. Vulnerabilities found: {audit_results['summary']['vulnerabilities']}")
        
        # TODO: Implement POST to NetVault audit endpoint
        # url = f"{self.server_url}/api/audit/submit"
        # ...

    async def main_loop(self):
        """Main operational loop"""
        if not await self.register():
            logger.error("Could not register. Retrying in 60s...")
            await asyncio.sleep(60)
            return

        last_audit = 0
        audit_interval = 3600 * 24 # Daily
        
        while True:
            await self.send_heartbeat()
            
            # Check if it's time for an audit
            if time.time() - last_audit > audit_interval:
                await self.run_audit()
                last_audit = time.time()
                
            await asyncio.sleep(30)

if __name__ == "__main__":
    agent = ADAgent()
    asyncio.run(agent.main_loop())
