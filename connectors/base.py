"""
NetVault - Network Connector Base Module
Defines the abstract base class and data structures for all network device connectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Callable


@dataclass
class ConnectionTestResult:
    """Result of a connection test attempt."""
    success: bool
    latency_ms: float
    error_message: Optional[str] = None


@dataclass
class InterfaceInfo:
    """Information about a network interface."""
    name: str
    status: str  # up/down
    speed: Optional[int] = None  # in bits per second
    mac: Optional[str] = None
    ip: Optional[str] = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    errors: int = 0


@dataclass
class ArpEntry:
    """ARP table entry."""
    ip: str
    mac: str
    interface: str
    type: str  # static/dynamic


@dataclass
class MacEntry:
    """MAC address table entry."""
    mac: str
    port: str
    vlan: int
    type: str  # static/dynamic/learned


@dataclass
class RouteEntry:
    """Routing table entry."""
    destination: str
    gateway: str
    interface: str
    metric: int
    protocol: str


@dataclass
class AuditCheck:
    """A single audit check result."""
    name: str
    status: str  # pass/warning/fail
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class AuditResult:
    """Complete audit run result."""
    device_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checks: List[AuditCheck] = field(default_factory=list)
    summary: str = ""


class BaseConnector(ABC):
    """
    Abstract Base Class for all network connectors.
    Each connector type (SNMP, SSH, REST) must inherit from this and implement its methods.
    """

    def __init__(self, device_id: str, device_ip: str, credentials: Dict[str, Any]):
        self.device_id = device_id
        self.device_ip = device_ip
        self.credentials = credentials
        self._is_connected = False
        self._device_info = {}

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the device."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Cleanly close the connection."""
        pass

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Test if the device is reachable and credentials work."""
        pass

    @abstractmethod
    async def get_system_info(self) -> Dict[str, Any]:
        """Retrieve general system information (model, OS, uptime)."""
        pass

    @abstractmethod
    async def get_interfaces(self) -> List[InterfaceInfo]:
        """Retrieve list of all network interfaces and their status."""
        pass

    @abstractmethod
    async def get_arp_table(self) -> List[ArpEntry]:
        """Retrieve the device's ARP table."""
        pass

    @abstractmethod
    async def get_mac_table(self) -> List[MacEntry]:
        """Retrieve the device's MAC address table."""
        pass

    @abstractmethod
    async def get_routes(self) -> List[RouteEntry]:
        """Retrieve the device's routing table."""
        pass

    @abstractmethod
    async def run_audit(self) -> AuditResult:
        """Perform a security and configuration audit of the device."""
        pass

    @property
    def is_connected(self) -> bool:
        """Returns True if the connector is currently connected to the device."""
        return self._is_connected

    @property
    def device_info(self) -> Dict[str, Any]:
        """Returns cached or retrieved device system information."""
        return self._device_info


# Connector Registry
_CONNECTOR_REGISTRY: Dict[str, Type[BaseConnector]] = {}


def register_connector(name: str):
    """Decorator to register a connector class in the registry."""
    def decorator(cls: Type[BaseConnector]):
        _CONNECTOR_REGISTRY[name] = cls
        return cls
    return decorator


def get_connector(name: str) -> Optional[Type[BaseConnector]]:
    """Retrieve a connector class by its registered name."""
    return _CONNECTOR_REGISTRY.get(name)


def list_connectors() -> List[str]:
    """Return a list of all registered connector names."""
    return list(_CONNECTOR_REGISTRY.keys())