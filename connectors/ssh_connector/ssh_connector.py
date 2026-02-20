"""
NetVault - SSH Network Connector
Implementation of SSH-based network device interaction using Paramiko.
"""

import asyncio
import time
import socket
import paramiko
from typing import Dict, List, Any, Optional
from datetime import datetime

from connectors.base import (
    BaseConnector, 
    ConnectionTestResult, 
    InterfaceInfo, 
    ArpEntry, 
    MacEntry, 
    RouteEntry, 
    AuditResult, 
    register_connector
)
from core.engine.logger import get_logger
from connectors.ssh_connector.parsers import mikrotik_parser, cisco_parser

logger = get_logger(__name__)


@register_connector("ssh")
class SSHConnector(BaseConnector):
    """
    SSH Connector for network devices.
    Supports MikroTik (RouterOS) and Cisco (IOS).
    """

    def __init__(self, device_id: str, device_ip: str, credentials: Dict[str, Any]):
        super().__init__(device_id, device_ip, credentials)
        self.port = credentials.get("port", 22)
        self.username = credentials.get("username")
        self.password = credentials.get("password")
        self.key_filename = credentials.get("key_filename")
        self.device_type = credentials.get("device_type", "auto") # auto, mikrotik, cisco
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.timeout = credentials.get("timeout", 10)

    async def connect(self) -> bool:
        """Establish SSH connection and detect device type."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connection parameters
            connect_kwargs = {
                "hostname": self.device_ip,
                "port": self.port,
                "username": self.username,
                "timeout": self.timeout,
                "look_for_keys": True,
                "allow_agent": True
            }
            
            if self.password:
                connect_kwargs["password"] = self.password
            if self.key_filename:
                connect_kwargs["key_filename"] = self.key_filename

            # Executing blocking paramiko call in a thread pool to keep it async-friendly
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.client.connect(**connect_kwargs))
            
            self._is_connected = True
            
            # Detect device type if set to auto
            if self.device_type == "auto":
                await self._detect_device_type()
                
            logger.info("Connected to %s (%s) via SSH", self.device_ip, self.device_type, extra={"device_id": self.device_id})
            return True
            
        except Exception as e:
            logger.error("Failed to connect to %s: %s", self.device_ip, str(e), extra={"device_id": self.device_id})
            self._is_connected = False
            return False

    async def disconnect(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("Disconnected from %s", self.device_ip, extra={"device_id": self.device_id})

    async def test_connection(self) -> ConnectionTestResult:
        """Test connection and measure latency."""
        start_time = time.time()
        try:
            success = await self.connect()
            latency = (time.time() - start_time) * 1000
            
            if success:
                await self.disconnect()
                return ConnectionTestResult(success=True, latency_ms=latency)
            else:
                return ConnectionTestResult(success=False, latency_ms=latency, error_message="Authentication failed or timeout")
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConnectionTestResult(success=False, latency_ms=latency, error_message=str(e))

    async def _execute_command(self, command: str) -> str:
        """Execute a command on the device and return the output."""
        if not self._is_connected:
            if not await self.connect():
                raise ConnectionError("Not connected to device")

        loop = asyncio.get_event_loop()
        def _exec():
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
            return stdout.read().decode('utf-8', errors='ignore')

        return await loop.run_in_executor(None, _exec)

    async def _detect_device_type(self):
        """Detect if the device is MikroTik or Cisco based on help/version output."""
        try:
            # Try a safe command that works on both or gives away the OS
            output = await self._execute_command("?")
            if "RouterOS" in output or "MikroTik" in output:
                self.device_type = "mikrotik"
            elif "Cisco" in output or "exec" in output:
                self.device_type = "cisco"
            else:
                # Try another command
                ver_output = await self._execute_command("show version")
                if "Cisco" in ver_output:
                    self.device_type = "cisco"
                else:
                    # Default/fallback
                    self.device_type = "unknown"
        except:
            self.device_type = "unknown"

    async def get_system_info(self) -> Dict[str, Any]:
        """Retrieve system info based on device type."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/system resource print")
            msg = mikrotik_parser.parse_system_resource(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show version")
            msg = cisco_parser.parse_show_version(output)
        else:
            msg = {"error": "Unsupported device type"}
            
        self._device_info = msg
        return msg

    async def get_interfaces(self) -> List[InterfaceInfo]:
        """Retrieve interfaces."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/interface print")
            return mikrotik_parser.parse_interfaces(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip interface brief")
            return cisco_parser.parse_show_interfaces(output)
        return []

    async def get_arp_table(self) -> List[ArpEntry]:
        """Retrieve ARP table."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/ip arp print")
            return mikrotik_parser.parse_arp_table(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip arp")
            return cisco_parser.parse_show_ip_arp(output)
        return []

    async def get_mac_table(self) -> List[MacEntry]:
        """Retrieve MAC table."""
        if self.device_type == "cisco":
            output = await self._execute_command("show mac address-table")
            return cisco_parser.parse_show_mac_address_table(output)
        # MikroTik MAC table is more complex depending on bridge, skipping for basic implementation
        return []

    async def get_routes(self) -> List[RouteEntry]:
        """Retrieve routing table."""
        if self.device_type == "mikrotik":
            output = await self._execute_command("/ip route print")
            return mikrotik_parser.parse_routes(output)
        elif self.device_type == "cisco":
            output = await self._execute_command("show ip route")
            return cisco_parser.parse_show_ip_route(output)
        return []

    async def run_audit(self) -> AuditResult:
        """Perform a basic audit."""
        result = AuditResult(device_name=self.device_ip)
        # Placeholder for audit logic
        # Could check for default passwords, open ports, etc.
        return result
