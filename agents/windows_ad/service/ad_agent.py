"""
NetVault - Windows AD Agent - Main Service
"""
import asyncio
import logging
import os
import socket
import time
from datetime import datetime
from typing import Any, Dict, List

import httpx
import yaml
from dotenv import load_dotenv

try:
    from agents.windows_ad.service.ad_auditor import ADAuditor
    from agents.windows_ad.service.ad_collector import ADCollector
except ImportError:
    from ad_auditor import ADAuditor
    from ad_collector import ADCollector

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ADAgent")


def _trim_list(values: List[Any], max_items: int = 1500) -> List[Any]:
    if len(values) <= max_items:
        return values
    return values[:max_items]


def _essential_ad_data(ad_data: Dict[str, Any]) -> Dict[str, Any]:
    if "error" in ad_data:
        return {"error": ad_data["error"]}

    users = _trim_list(ad_data.get("users", []), max_items=2000)
    groups = _trim_list(ad_data.get("groups", []), max_items=1000)
    computers = _trim_list(ad_data.get("computers", []), max_items=3000)
    gpos = _trim_list(ad_data.get("gpos", []), max_items=500)

    # Keep only required/essential fields in payload.
    safe_users = [
        {
            "sAMAccountName": u.get("sAMAccountName", ""),
            "displayName": u.get("displayName", ""),
            "mail": u.get("mail", ""),
            "department": u.get("department", ""),
            "title": u.get("title", ""),
            "enabled": bool(u.get("enabled", True)),
            "locked": bool(u.get("locked", False)),
            "lastLogon": u.get("lastLogon"),
            "passwordNeverExpires": bool(u.get("passwordNeverExpires", False)),
            "memberOf": u.get("memberOf", []),
            # compatibility fields for auditor
            "is_disabled": bool(u.get("is_disabled", not bool(u.get("enabled", True)))),
            "is_locked": bool(u.get("is_locked", bool(u.get("locked", False)))),
            "lastLogonTimestamp": u.get("lastLogonTimestamp") or u.get("lastLogon"),
            "userAccountControl": u.get("userAccountControl", 0),
        }
        for u in users
    ]

    safe_groups = [
        {
            "name": g.get("name", ""),
            "members": g.get("members", []),
            "memberCount": int(g.get("memberCount", len(g.get("members", [])))),
            "scope": g.get("scope", "Unknown"),
            # compatibility fields for auditor
            "sAMAccountName": g.get("sAMAccountName", g.get("name", "")),
            "member": g.get("member", g.get("members", [])),
        }
        for g in groups
    ]

    safe_computers = [
        {
            "name": c.get("name", ""),
            "os": c.get("os", ""),
            "lastLogon": c.get("lastLogon"),
        }
        for c in computers
    ]

    safe_gpos = [
        {
            "name": gpo.get("name", ""),
            "status": gpo.get("status", "unknown"),
        }
        for gpo in gpos
    ]

    return {
        "users": safe_users,
        "groups": safe_groups,
        "computers": safe_computers,
        "gpos": safe_gpos,
    }

class ADAgent:
    def __init__(self, config_path: str = "config.yml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.server_url = self.config['netvault']['server_url'].rstrip('/')
        self.token = self.config['netvault']['agent_token']
        self.agent_id = None
        self.hostname = socket.gethostname()
        self.ip = self.config['netvault'].get('agent_ip', socket.gethostbyname(self.hostname))
        
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
        
        with open(self.config_path, 'r', encoding='utf-8-sig') as f:
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

        # Include only essential AD detail fields in payload.
        audit_results["data"] = _essential_ad_data(ad_data)
        
        url = f"{self.server_url}/api/audit/results"
        payload = {
            "device_id": 0,  # 0 or a specific AD controller device ID if known
            "agent_id": self.agent_id,
            "audit_type": "ad_audit",
            "result_json": audit_results,
            "status": "success",
            "completed_at": datetime.utcnow().isoformat()
        }
        headers = {"X-Agent-Token": self.token}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=15)
                if response.status_code in [200, 201]:
                    logger.info("Audit results sent successfully")
                else:
                    logger.error(f"Failed to send audit results: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Error sending audit results: {str(e)}")

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
