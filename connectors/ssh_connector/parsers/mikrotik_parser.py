"""
NetVault - MikroTik SSH Parser
Parses MikroTik RouterOS CLI output into structured data classes.
"""

import re
from typing import Dict, List, Any, Optional
from connectors.base import InterfaceInfo, ArpEntry, RouteEntry


def parse_system_resource(output: str) -> Dict[str, Any]:
    """
    Parses '/system resource print' output.
    Example:
          uptime: 5d21h34m56s
         version: 7.12.1 (stable)
      build-time: Nov/23/2023 12:45:04
     factory-software: 6.48.6
      free-memory: 110.4MiB
     total-memory: 128.0MiB
             cpu: MIPS 24Kc V7.4
       cpu-count: 1
    """
    data = {}
    for line in output.splitlines():
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    
    return {
        "model": data.get("board-name", "MikroTik"),
        "os_version": data.get("version", "Unknown"),
        "uptime": data.get("uptime", "Unknown"),
        "cpu": data.get("cpu", "Unknown"),
        "memory_total": data.get("total-memory", "Unknown"),
        "memory_free": data.get("free-memory", "Unknown")
    }


def parse_interfaces(output: str) -> List[InterfaceInfo]:
    """
    Parses '/interface print detail' or '/interface print' output.
    RouterOS 7 format (tabular or tabular with flags):
    Flags: R - RUNNING; S - SLAVE
    Columns: NAME, TYPE, ACTUAL-MTU, L2MTU, MAX-L2MTU, MAC-ADDRESS
    #    NAME       TYPE     ACTUAL-MTU  L2MTU  MAX-L2MTU  MAC-ADDRESS      
    0 RS ether1     ether          1500   1500       4074  48:8F:5A:XX:XX:XX
    """
    interfaces = []
    lines = output.splitlines()
    
    # Simple line-by-line parsing for common fields
    # Example regex for: 0 RS ether1     ether          1500 ...
    pattern = re.compile(r"^\s*\d+\s+([RXS]*)\s+(\S+)\s+(\S+)\s+(\d+)")
    
    for line in lines:
        match = pattern.search(line)
        if match:
            flags, name, if_type, mtu = match.groups()
            status = "up" if "R" in flags else "down"
            
            # Note: RX/TX bytes usually come from '/interface print stats'
            interfaces.append(InterfaceInfo(
                name=name,
                status=status,
                mac=None, # Will be filled if found in line
                ip=None   # Requires '/ip address print'
            ))
            
    return interfaces


def parse_arp_table(output: str) -> List[ArpEntry]:
    """
    Parses '/ip arp print' output.
    Flags: D - DYNAMIC; I - INVALID, H - DHCP, C - COMPLETE
    Columns: ADDRESS, MAC-ADDRESS, INTERFACE
    #   ADDRESS         MAC-ADDRESS       INTERFACE
    0 D 192.168.88.254  48:8F:5A:XX:XX:XX bridge   
    """
    arp_entries = []
    lines = output.splitlines()
    
    # Regex for: 0 D 192.168.88.254  48:8F:5A:XX:XX:XX bridge
    pattern = re.compile(r"^\s*\d+\s+([DIHC]*)\s+([\d\.]+)\s+([0-9A-F:]+)\s+(\S+)")
    
    for line in lines:
        match = pattern.search(line)
        if match:
            flags, ip, mac, interface = match.groups()
            entry_type = "dynamic" if "D" in flags else "static"
            arp_entries.append(ArpEntry(
                ip=ip,
                mac=mac,
                interface=interface,
                type=entry_type
            ))
            
    return arp_entries


def parse_routes(output: str) -> List[RouteEntry]:
    """
    Parses '/ip route print' output.
    Flags: D - DYNAMIC; A - ACTIVE, C - CONNECTED, S - STATIC
    Columns: DST-ADDRESS, GATEWAY, DISTANCE
    #      DST-ADDRESS        GATEWAY         DISTANCE
    0  As  0.0.0.0/0          192.168.88.1           1
    1  DAC 192.168.88.0/24    bridge                 0
    """
    routes = []
    lines = output.splitlines()
    
    # Regex for: 0  As  0.0.0.0/0          192.168.88.1           1
    pattern = re.compile(r"^\s*\d+\s+([DACS]*)\s+([\d\./]+)\s+(\S+)\s+(\d+)")
    
    for line in lines:
        match = pattern.search(line)
        if match:
            flags, destination, gateway, distance = match.groups()
            protocol = "static"
            if "C" in flags: protocol = "connected"
            elif "D" in flags: protocol = "dynamic"
            
            routes.append(RouteEntry(
                destination=destination,
                gateway=gateway,
                interface="", # Usually interface is gateway if it's connected
                metric=int(distance),
                protocol=protocol
            ))
            
    return routes
