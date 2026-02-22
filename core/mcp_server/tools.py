"""
NetVault - MCP Tools
Implementation of MCP tools for AI-powered network analysis.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from core.database import crud
from core.database.db import DatabaseManager
from core.engine.device_manager import DeviceManager
from core.engine.audit_engine import AuditEngine
from core.engine.logger import get_logger

logger = get_logger("netvault.mcp.tools")

class MCPToolProvider:
    """
    Provides NetVault data and actions for MCP tools.
    Initialized with references to core engines.
    """
    def __init__(self, db: DatabaseManager, device_manager: DeviceManager, audit_engine: AuditEngine):
        self.db = db
        self.device_manager = device_manager
        self.audit_engine = audit_engine

    async def list_devices(self) -> List[Dict[str, Any]]:
        """List all monitored devices with their basic status."""
        devices = await crud.list_devices(self.db)
        # Simplify for AI: remove config_json, keep relevant fields
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "ip": d["ip"],
                "type": d["type"],
                "status": d["status"],
                "last_seen": d.get("last_seen")
            } for d in devices
        ]

    async def get_device_details(self, device_name_or_ip: str) -> Dict[str, Any]:
        """Get full details for a specific device by name or IP."""
        devices = await crud.list_devices(self.db)
        device = next((d for d in devices if d["name"] == device_name_or_ip or d["ip"] == device_name_or_ip), None)
        if not device:
            return {"error": f"Device '{device_name_or_ip}' not found"}
        
        # Add latest poll data if available
        cache_data = await self.device_manager.get_device_data(device["id"])
        if cache_data:
            device["latest_data"] = cache_data
            
        return device

    async def get_device_interfaces(self, device_name_or_ip: str) -> List[Dict[str, Any]]:
        """Retrieve the interface table for a specific device."""
        device = await self._find_device(device_name_or_ip)
        if not device:
            return [{"error": f"Device '{device_name_or_ip}' not found"}]
        
        data = await self.device_manager.get_device_data(device["id"])
        if not data or "interfaces" not in data:
            # Try refreshing if no cache
            await self.device_manager.poll_device(device["id"])
            data = await self.device_manager.get_device_data(device["id"])
            
        return data.get("interfaces", []) if data else []

    async def get_arp_table(self, device_name_or_ip: str) -> List[Dict[str, Any]]:
        """Retrieve the ARP table for a specific device."""
        device = await self._find_device(device_name_or_ip)
        if not device:
            return [{"error": f"Device '{device_name_or_ip}' not found"}]
        
        data = await self.device_manager.get_device_data(device["id"])
        if not data or "arp_table" not in data:
            await self.device_manager.refresh_device_data(device["id"])
            data = await self.device_manager.get_device_data(device["id"])
            
        return data.get("arp_table", []) if data else []

    async def get_mac_table(self, device_name_or_ip: str) -> List[Dict[str, Any]]:
        """Retrieve the MAC address table for a specific device."""
        device = await self._find_device(device_name_or_ip)
        if not device:
            return [{"error": f"Device '{device_name_or_ip}' not found"}]
        
        data = await self.device_manager.get_device_data(device["id"])
        if not data or "mac_table" not in data:
            await self.device_manager.refresh_device_data(device["id"])
            data = await self.device_manager.get_device_data(device["id"])
            
        return data.get("mac_table", []) if data else []

    async def run_audit(self, device_name_or_ip: str) -> Dict[str, Any]:
        """Trigger a security audit for a device and return the result."""
        device = await self._find_device(device_name_or_ip)
        if not device:
            return {"error": f"Device '{device_name_or_ip}' not found"}
        
        result = await self.audit_engine.run_device_audit(device["id"])
        if not result:
            return {"error": "Audit failed or could not be triggered"}
            
        return self.audit_engine._result_to_dict(result)

    async def get_audit_history(self, device_name_or_ip: str, days: int = 7) -> List[Dict[str, Any]]:
        """Retrieve past audit results for a device."""
        device = await self._find_device(device_name_or_ip)
        if not device:
            return [{"error": f"Device '{device_name_or_ip}' not found"}]
        
        logs = await crud.list_audit_logs(self.db, device["id"])
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Filter by date and return
        history = []
        for log in logs:
            completed_at = log.get("completed_at")
            if isinstance(completed_at, str):
                completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            
            if completed_at >= cutoff:
                history.append(log)
        
        return history

    async def get_network_topology(self) -> Dict[str, Any]:
        """Retrieve the discovered network topology map."""
        # This is simplified: return all devices and their connections if known
        devices = await crud.list_devices(self.db)
        links = []
        
        # Try to build links from MAC tables
        all_data = {d["id"]: await self.device_manager.get_device_data(d["id"]) for d in devices}
        
        # Very basic topology logic: if Device A sees Device B's MAC on port X
        # For now return nodes and any discovered neighbors
        return {
            "nodes": [
                {"id": d["id"], "name": d["name"], "type": d["type"], "ip": d["ip"]}
                for d in devices
            ],
            "links": links # Placeholder for future link discovery
        }

    async def get_alerts(self, severity: Optional[str] = None, acknowledged: bool = False) -> List[Dict[str, Any]]:
        """Retrieve current alerts filtered by severity and status."""
        alerts = await crud.list_active_alerts(self.db)
        if severity:
            alerts = [a for a in alerts if a["severity"].lower() == severity.lower()]
        return alerts

    async def search_device_by_mac(self, mac_address: str) -> List[Dict[str, Any]]:
        """Find which device and port has a specific MAC address."""
        devices = await crud.list_devices(self.db)
        results = []
        for d in devices:
            data = await self.device_manager.get_device_data(d["id"])
            if not data: continue
            
            mac_table = data.get("mac_table", [])
            for entry in mac_table:
                e_mac = entry.get("mac") if isinstance(entry, dict) else getattr(entry, "mac", None)
                if e_mac and e_mac.lower() == mac_address.lower():
                    results.append({
                        "switch_name": d["name"],
                        "switch_ip": d["ip"],
                        "port": entry.get("port") if isinstance(entry, dict) else getattr(entry, "port", None),
                        "vlan": entry.get("vlan") if isinstance(entry, dict) else getattr(entry, "vlan", None)
                    })
        return results

    async def search_device_by_ip(self, ip_address: str) -> Dict[str, Any]:
        """Find device information by its IP address."""
        devices = await crud.list_devices(self.db)
        device = next((d for d in devices if d["ip"] == ip_address), None)
        if device:
            return device
        
        # Search in ARP tables
        for d in devices:
            data = await self.device_manager.get_device_data(d["id"])
            if not data: continue
            
            arp_table = data.get("arp_table", [])
            for entry in arp_table:
                e_ip = entry.get("ip") if isinstance(entry, dict) else getattr(entry, "ip", None)
                if e_ip == ip_address:
                    return {
                        "info": "IP found in ARP table",
                        "mac": entry.get("mac") if isinstance(entry, dict) else getattr(entry, "mac", None),
                        "discovered_on": d["name"],
                        "interface": entry.get("interface") if isinstance(entry, dict) else getattr(entry, "interface", None)
                    }
        
        return {"error": f"IP {ip_address} not found in inventory or ARP tables"}

    async def get_ad_users(self) -> List[Dict[str, Any]]:
        """Retrieve list of AD users from connected agents."""
        # Simplified: query database for latest agent data
        # Agents store their data in result_json of audit logs or similar
        # For Phase 5, this will be more robust. Now we check 'agents' table.
        agents = await self.db.fetch_all("SELECT * FROM agents WHERE type = 'windows_ad'")
        # Placeholder result
        return [{"message": "AD agent integration is pending Phase 5", "count": len(agents)}]

    async def get_ad_groups(self) -> List[Dict[str, Any]]:
        """Retrieve list of AD groups from connected agents."""
        return [{"message": "AD agent integration is pending Phase 5"}]

    async def get_ad_gpo_status(self) -> Dict[str, Any]:
        """Retrieve GPO health check status."""
        return {"message": "AD agent integration is pending Phase 5"}

    async def _find_device(self, name_or_ip: str) -> Optional[Dict[str, Any]]:
        devices = await crud.list_devices(self.db)
        return next((d for d in devices if d["name"] == name_or_ip or d["ip"] == name_or_ip), None)
