"""
NetVault - Sophos XG/XGS Profile
Defines endpoints and XML parsing for Sophos REST API.
"""

from typing import Dict, List, Any, Optional
from lxml import etree
from connectors.base import InterfaceInfo, ArpEntry, RouteEntry, AuditCheck, AuditResult

class SophosProfile:
    """
    Sophos XG/XGS API Profile.
    Handles XML request generation and response parsing.
    """
    
    API_PATH = "/webconsole/APIController"
    PORT = 4444
    
    @staticmethod
    def get_login_xml(username: str, password: str) -> str:
        """Generate login XML for authentication."""
        # Sophos XG API usually requires credentials in every request XML OR via a separate login
        # However, the most common way is to include <Login> in the request XML.
        return f"""
        <Login>
            <UserName>{username}</UserName>
            <Password>{password}</Password>
        </Login>
        """

    @staticmethod
    def wrap_request(login_xml: str, action: str, entity: str, filter_xml: str = "") -> str:
        """Wraps a request in the Sophos XML structure."""
        return f"""
        <Request>
            {login_xml}
            <{action}>
                <{entity}>{filter_xml}</{entity}>
            </{action}>
        </Request>
        """

    @classmethod
    def parse_interfaces(cls, xml_content: bytes) -> List[InterfaceInfo]:
        """Parses Sophos interface XML response."""
        interfaces = []
        try:
            root = etree.fromstring(xml_content)
            # Sophos response structure: <Response><Interface><Name>...</Name>...</Interface></Response>
            for iface_node in root.xpath("//Interface"):
                name = iface_node.xpath("string(Name)")
                status_raw = iface_node.xpath("string(Status)") # e.g., "1" for UP
                status = "up" if status_raw == "1" else "down"
                
                interfaces.append(InterfaceInfo(
                    name=name,
                    status=status,
                    ip=iface_node.xpath("string(IPAddress)"),
                    mac=iface_node.xpath("string(MACAddress)"),
                    rx_bytes=int(iface_node.xpath("string(RxBytes)") or 0),
                    tx_bytes=int(iface_node.xpath("string(TxBytes)") or 0)
                ))
        except Exception as e:
            # Logger would be used in the connector, here we just return what we found
            pass
        return interfaces

    @classmethod
    def parse_arp_table(cls, xml_content: bytes) -> List[ArpEntry]:
        """Parses Sophos ARP table XML response."""
        arp_entries = []
        try:
            root = etree.fromstring(xml_content)
            for entry_node in root.xpath("//ARPTable/Entry"):
                arp_entries.append(ArpEntry(
                    ip=entry_node.xpath("string(IPAddress)"),
                    mac=entry_node.xpath("string(MACAddress)"),
                    interface=entry_node.xpath("string(Interface)"),
                    type="dynamic" # Default for Sophos if not specified
                ))
        except Exception:
            pass
        return arp_entries

    @classmethod
    def parse_routes(cls, xml_content: bytes) -> List[RouteEntry]:
        """Parses Sophos routing table XML response."""
        routes = []
        try:
            root = etree.fromstring(xml_content)
            for route_node in root.xpath("//RoutingTable/Route"):
                routes.append(RouteEntry(
                    destination=route_node.xpath("string(Destination)"),
                    gateway=route_node.xpath("string(Gateway)"),
                    interface=route_node.xpath("string(Interface)"),
                    metric=int(route_node.xpath("string(Metric)") or 0),
                    protocol=route_node.xpath("string(Protocol)")
                ))
        except Exception:
            pass
        return routes

    @classmethod
    def parse_system_info(cls, xml_content: bytes) -> Dict[str, Any]:
        """Parses Sophos system status XML response."""
        info = {}
        try:
            root = etree.fromstring(xml_content)
            info["model"] = root.xpath("string(//SystemStatus/Model)")
            info["os"] = root.xpath("string(//SystemStatus/FirmwareVersion)")
            info["uptime"] = root.xpath("string(//SystemStatus/Uptime)")
            info["serial"] = root.xpath("string(//SystemStatus/SerialNumber)")
        except Exception:
            pass
        return info
