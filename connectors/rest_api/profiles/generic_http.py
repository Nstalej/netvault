"""
NetVault - Generic HTTP Profile
Defines configurable endpoints for generic JSON-based REST APIs.
"""

from typing import Dict, List, Any, Optional
from connectors.base import InterfaceInfo, ArpEntry, RouteEntry

class GenericHTTPProfile:
    """
    Generic HTTP API Profile.
    Uses configurable endpoint mapping (JSON based).
    """
    
    def __init__(self, endpoint_map: Dict[str, str]):
        """
        Initialize with a map of functionality to endpoint path.
        Example: {"interfaces": "/api/v1/network/interfaces", "system": "/api/v1/system/status"}
        """
        self.endpoint_map = endpoint_map

    def get_endpoint(self, key: str) -> Optional[str]:
        """Returns the endpoint path for a given functionality key."""
        return self.endpoint_map.get(key)

    @classmethod
    def parse_system_info(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generic JSON parser for system info."""
        # This is a placeholder for more complex logic if needed,
        # but for generic we often just return the dict or map specific fields.
        return {
            "model": data.get("model") or data.get("device_model", "Generic"),
            "os": data.get("os_version") or data.get("firmware", "Unknown"),
            "uptime": data.get("uptime") or "Unknown"
        }

    @classmethod
    def parse_interfaces(cls, data: Any) -> List[InterfaceInfo]:
        """Generic JSON parser for interfaces."""
        interfaces = []
        # Expecting a list of interface objects
        if isinstance(data, list):
            for item in data:
                interfaces.append(InterfaceInfo(
                    name=item.get("name") or str(item.get("index")),
                    status="up" if item.get("status") in ["up", "online", 1, True] else "down",
                    ip=item.get("ip_address"),
                    mac=item.get("mac_address"),
                    rx_bytes=item.get("rx_bytes", 0),
                    tx_bytes=item.get("tx_bytes", 0)
                ))
        return interfaces
        
    @classmethod
    def parse_arp_table(cls, data: Any) -> List[ArpEntry]:
        """Generic JSON parser for ARP table."""
        arp_entries = []
        if isinstance(data, list):
            for item in data:
                arp_entries.append(ArpEntry(
                    ip=item.get("ip"),
                    mac=item.get("mac"),
                    interface=item.get("interface", "N/A"),
                    type=item.get("type", "dynamic")
                ))
        return arp_entries
