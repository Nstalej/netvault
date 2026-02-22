"""
NetVault - SNMP Connector
Implements network device monitoring via SNMP v2c and v3.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from pysnmp.hlapi.asyncio import *
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from pysnmp.error import PySnmpError

from connectors.base import (
    BaseConnector, 
    ConnectionTestResult, 
    InterfaceInfo, 
    ArpEntry, 
    MacEntry, 
    RouteEntry, 
    AuditResult, 
    AuditCheck,
    register_connector
)
from connectors.snmp import oids
from core.engine.logger import get_logger

logger = get_logger("connectors.snmp")

@register_connector("snmp")
class SNMPConnector(BaseConnector):
    """
    SNMP Connector for NetVault.
    Supports SNMPv2c and SNMPv3.
    """

    def __init__(self, device_id: str, device_ip: str, credentials: Dict[str, Any]):
        super().__init__(device_id, device_ip, credentials)
        self.port = credentials.get("port", 161)
        self.version = credentials.get("version", "v2c")
        self.timeout = credentials.get("timeout", 2)
        self.retries = credentials.get("retries", 1)
        
        self.snmp_engine = SnmpEngine()
        self.auth_data = self._build_auth_data()
        self.transport_target = None # Initialized in connect()
        self.context_data = ContextData()

    def _build_auth_data(self) -> Union[CommunityData, UsmUserData]:
        """Build SNMP authentication data based on version."""
        if self.version == "v2c":
            community = self.credentials.get("community", "public")
            return CommunityData(community)
        
        elif self.version == "v3":
            username = self.credentials.get("username")
            auth_key = self.credentials.get("auth_key")
            priv_key = self.credentials.get("priv_key")
            auth_proto = self._get_auth_proto(self.credentials.get("auth_proto", "sha"))
            priv_proto = self._get_priv_proto(self.credentials.get("priv_proto", "aes"))

            return UsmUserData(
                username,
                authKey=auth_key,
                privKey=priv_key,
                authProtocol=auth_proto,
                privProtocol=priv_proto
            )
        
        else:
            raise ValueError(f"Unsupported SNMP version: {self.version}")

    def _get_auth_proto(self, proto: str) -> Tuple:
        """Map string to pysnmp auth protocol."""
        protos = {
            "md5": usmHMACMD5AuthProtocol,
            "sha": usmHMACSHAAuthProtocol,
            "sha256": usmHMAC128SHA224AuthProtocol, # common mapping
            "none": usmNoAuthProtocol
        }
        return protos.get(proto.lower(), usmNoAuthProtocol)

    def _get_priv_proto(self, proto: str) -> Tuple:
        """Map string to pysnmp priv protocol."""
        protos = {
            "des": usmDESPrivProtocol,
            "aes": usmAesCfb128Protocol,
            "aes128": usmAesCfb128Protocol,
            "aes192": usmAesCfb192Protocol,
            "aes256": usmAesCfb256Protocol,
            "none": usmNoPrivProtocol
        }
        return protos.get(proto.lower(), usmNoPrivProtocol)

    async def connect(self) -> bool:
        """For SNMP, connection is stateless, but we verify connectivity."""
        try:
            if not self.transport_target:
                self.transport_target = await UdpTransportTarget(
                    (self.device_ip, self.port), 
                    timeout=self.timeout, 
                    retries=self.retries
                ).create()
                
            result = await self.test_connection()
            self._is_connected = result.success
            return result.success
        except Exception as e:
            logger.error(f"Failed to 'connect' to {self.device_ip}: {e}")
            self._is_connected = False
            return False

    async def disconnect(self):
        """No persistent connection to close for SNMP."""
        self._is_connected = False

    async def _get(self, oid: str) -> Optional[Any]:
        """Perform an SNMP GET operation."""
        try:
            errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                self.snmp_engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid))
            )

            if errorIndication:
                logger.error(f"SNMP GET Error for {self.device_ip} ({oid}): {errorIndication}")
                return None
            elif errorStatus:
                logger.error(f"SNMP GET Error for {self.device_ip} ({oid}): {errorStatus.prettyPrint()}")
                return None
            else:
                for varBind in varBinds:
                    return varBind[1]
        except Exception as e:
            logger.error(f"SNMP Exception for {self.device_ip} ({oid}): {e}")
            return None

    async def _walk(self, base_oid: str) -> List[Tuple[str, Any]]:
        """Perform an SNMP WALK (via nextCmd or bulkCmd)."""
        results = []
        try:
            # Prefer bulk_cmd for better performance if possible (v2c/v3)
            # v1 doesn't support bulk_cmd, but we only support v2c/v3
            iterator = bulk_cmd(
                self.snmp_engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                0, 25, # non-repeaters, max-repetitions
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            )

            async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
                if errorIndication:
                    logger.error(f"SNMP WALK Error for {self.device_ip} ({base_oid}): {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP WALK Error for {self.device_ip} ({base_oid}): {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        results.append((str(varBind[0]), varBind[1]))
        except Exception as e:
            logger.error(f"SNMP Walk Exception for {self.device_ip} ({base_oid}): {e}")
            
        return results

    async def test_connection(self) -> ConnectionTestResult:
        """Test connectivity by fetching sysDescr."""
        start_time = time.time()
        val = await self._get(oids.SYS_DESCR)
        latency = (time.time() - start_time) * 1000

        if val:
            return ConnectionTestResult(success=True, latency_ms=latency)
        else:
            return ConnectionTestResult(success=False, latency_ms=latency, error_message="Timeout or auth failure")

    async def get_system_info(self) -> Dict[str, Any]:
        """Retrieve system information and detect vendor."""
        # Use bulk get for system group
        info = {
            "name": str(await self._get(oids.SYS_NAME) or ""),
            "descr": str(await self._get(oids.SYS_DESCR) or ""),
            "uptime": str(await self._get(oids.SYS_UPTIME) or ""),
            "location": str(await self._get(oids.SYS_LOCATION) or ""),
            "contact": str(await self._get(oids.SYS_CONTACT) or ""),
        }

        # Vendor Detection
        info["vendor"] = "generic"
        descr_lower = info["descr"].lower()
        
        if "mikrotik" in descr_lower or "routeros" in descr_lower:
            info["vendor"] = "mikrotik"
            info["os"] = "RouterOS"
            ros_ver = await self._get(oids.MIKROTIK_ROUTEROS_VERSION)
            if ros_ver:
                info["os_version"] = str(ros_ver)
            board = await self._get(oids.MIKROTIK_MODEL)
            if board:
                info["model"] = str(board)

        elif "cisco" in descr_lower or "ios" in descr_lower:
            info["vendor"] = "cisco"
            info["os"] = "IOS"
            # Try to get more specific Cisco info
            model = await self._get(oids.CISCO_MODEL)
            if model:
                info["model"] = str(model)

        self._device_info = info
        return info

    async def get_interfaces(self) -> List[InterfaceInfo]:
        """Fetch and parse ifTable."""
        interfaces = {}
        
        # We need to map indexes to values
        walk_data = {
            "name": await self._walk(oids.IF_DESCR),
            "status": await self._walk(oids.IF_OPER_STATUS),
            "speed": await self._walk(oids.IF_SPEED),
            "mac": await self._walk(oids.IF_PHYS_ADDRESS),
            "in_octets": await self._walk(oids.IF_IN_OCTETS),
            "out_octets": await self._walk(oids.IF_OUT_OCTETS),
            "errors": await self._walk(oids.IF_IN_ERRORS) # Simplification: use in_errors
        }

        # Helper to extract index from OID string
        def get_idx(oid_str: str, base: str) -> str:
            return oid_str.replace(base + ".", "")

        for key, rows in walk_data.items():
            base_oid = getattr(oids, f"IF_{key.upper()}")
            for oid_str, val in rows:
                idx = get_idx(oid_str, base_oid)
                if idx not in interfaces:
                    interfaces[idx] = {}
                
                # Format value
                if key == "status":
                    interfaces[idx][key] = "up" if int(val) == 1 else "down"
                elif key == "mac":
                    # Mac address format check
                    try:
                        interfaces[idx][key] = ":".join([f"{b:02x}" for b in val.asOctets()])
                    except:
                        interfaces[idx][key] = str(val)
                else:
                    interfaces[idx][key] = val

        result = []
        for idx, data in interfaces.items():
            result.append(InterfaceInfo(
                name=str(data.get("name", f"port-{idx}")),
                status=data.get("status", "unknown"),
                speed=int(data.get("speed", 0)),
                mac=data.get("mac"),
                rx_bytes=int(data.get("in_octets", 0)),
                tx_bytes=int(data.get("out_octets", 0)),
                errors=int(data.get("errors", 0))
            ))
        
        return result

    async def get_arp_table(self) -> List[ArpEntry]:
        """Fetch and parse ipNetToMediaTable."""
        entries = []
        # Index is ifIndex.ipAddress
        rows = await self._walk(oids.IP_NET_TO_MEDIA_PHYS_ADDRESS)
        for oid_str, mac_val in rows:
            # OID format: ...4.22.1.2.ifIndex.ip1.ip2.ip3.ip4
            parts = oid_str.split('.')
            if_idx = parts[-5]
            ip_addr = ".".join(parts[-4:])
            
            try:
                mac = ":".join([f"{b:02x}" for b in mac_val.asOctets()])
            except:
                mac = str(mac_val)
                
            entries.append(ArpEntry(
                ip=ip_addr,
                mac=mac,
                interface=if_idx,
                type="dynamic" # Simplified
            ))
        return entries

    async def get_mac_table(self) -> List[MacEntry]:
        """Fetch and parse dot1dTpFdbTable."""
        entries = []
        # dot1dTpFdbPort gives us the mapping
        rows = await self._walk(oids.DOT1D_TP_FDB_PORT)
        for oid_str, port_val in rows:
            # OID format: ...17.4.3.1.2.m1.m2.m3.m4.m5.m6
            parts = oid_str.split('.')
            mac_parts = parts[-6:]
            mac = ":".join([f"{int(p):02x}" for p in mac_parts])

            entries.append(MacEntry(
                mac=mac,
                port=str(port_val),
                vlan=1, # BRIDGE-MIB dot1dTpFdbTable doesn't have VLAN info (needs Q-BRIDGE-MIB)
                type="learned"
            ))
        return entries

    async def get_routes(self) -> List[RouteEntry]:
        """Fetch and parse ipRouteTable."""
        entries = []
        # Similar logic to ARP
        rows = await self._walk(oids.IP_ROUTE_NEXT_HOP)
        for oid_str, hop_val in rows:
            parts = oid_str.split('.')
            dest_ip = ".".join(parts[-4:])
            
            entries.append(RouteEntry(
                destination=dest_ip,
                gateway=str(hop_val),
                interface="unknown", 
                metric=0,
                protocol="unknown"
            ))
        return entries

    async def run_audit(self) -> AuditResult:
        """Perform basic SNMP security audit."""
        checks = []
        
        # Check 1: SNMP Version
        if self.version == "v2c":
            checks.append(AuditCheck(
                name="SNMP Version Security",
                status="warning",
                message="Device is using SNMPv2c which transmits data in cleartext.",
                details={"recommendation": "Upgrade to SNMPv3 with AuthPriv for better security."}
            ))
        else:
            checks.append(AuditCheck(
                name="SNMP Version Security",
                status="pass",
                message="Device is using SNMPv3."
            ))

        # Check 2: Community String (if v2c)
        if self.version == "v2c" and self.credentials.get("community") in ["public", "private"]:
            checks.append(AuditCheck(
                name="Common Community String",
                status="fail",
                message=f"Device uses a common community string: {self.credentials.get('community')}",
                details={"recommendation": "Change the community string to something unique and complex."}
            ))

        return AuditResult(
            device_name=self.device_id,
            checks=checks,
            summary="Basic SNMP security audit completed."
        )
