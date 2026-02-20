"""
NetVault - Cisco IOS SSH Parser
Parses Cisco IOS CLI output into structured data classes.
"""

import re
from typing import Dict, List, Any, Optional
from connectors.base import InterfaceInfo, ArpEntry, MacEntry, RouteEntry


def parse_show_version(output: str) -> Dict[str, Any]:
    """
    Parses 'show version' output.
    Example:
    Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE7, RELEASE SOFTWARE (fc1)
    ...
    System image file is "flash:/c2960-lanbasek9-mz.122-55.SE7.bin"
    ...
    cisco WS-C2960-24TT-L (PowerPC405) processor (revision B0) with 65536K bytes of memory.
    Processor board ID FOC12345678
    ...
    """
    data = {}
    
    version_match = re.search(r"Version ([^,]+)", output)
    if version_match:
        data["os_version"] = version_match.group(1)
    
    model_match = re.search(r"cisco (\S+) \(([^)]+)\) processor", output, re.IGNORECASE)
    if model_match:
        data["model"] = model_match.group(1)
        data["cpu"] = model_match.group(2)
        
    uptime_match = re.search(r"uptime is ([^\n]+)", output)
    if uptime_match:
        data["uptime"] = uptime_match.group(1)
        
    memory_match = re.search(r"with (\d+)K bytes of memory", output)
    if memory_match:
        data["memory_total"] = f"{int(memory_match.group(1)) // 1024}MB"
        
    return {
        "model": data.get("model", "Cisco Device"),
        "os_version": data.get("os_version", "Unknown"),
        "uptime": data.get("uptime", "Unknown"),
        "cpu": data.get("cpu", "Unknown"),
        "memory_total": data.get("memory_total", "Unknown")
    }


def parse_show_interfaces(output: str) -> List[InterfaceInfo]:
    """
    Parses 'show interfaces' or 'show ip interface brief' output.
    Using 'show ip interface brief' for status and IP, which is more reliable for summary.
    Example:
    Interface              IP-Address      OK? Method Status                Protocol
    FastEthernet0/1        192.168.1.1     YES manual up                    up      
    FastEthernet0/2        unassigned      YES unset  down                  down    
    """
    interfaces = []
    lines = output.splitlines()
    
    # Pattern for ip interface brief
    pattern = re.compile(r"^(\S+)\s+(\S+)\s+(YES|NO)\s+(\S+)\s+(up|down|administratively down)\s+(up|down)")
    
    for line in lines:
        match = pattern.search(line)
        if match:
            name, ip, ok, method, status, proto = match.groups()
            actual_status = "up" if status == "up" and proto == "up" else "down"
            interfaces.append(InterfaceInfo(
                name=name,
                status=actual_status,
                ip=None if ip == "unassigned" else ip,
                mac=None # Needs 'show interfaces <name>' for MAC
            ))
            
    return interfaces


def parse_show_ip_arp(output: str) -> List[ArpEntry]:
    """
    Parses 'show ip arp' output.
    Example:
    Protocol  Address          Age (min)  Hardware Addr   Type   Interface
    Internet  192.168.1.1             -   0011.2233.4455  ARPA   FastEthernet0/1
    Internet  192.168.1.100          10   00aa.bbcc.ddee  ARPA   FastEthernet0/1
    """
    arp_entries = []
    lines = output.splitlines()
    
    # Protocol  Address          Age (min)  Hardware Addr   Type   Interface
    pattern = re.compile(r"\s*Internet\s+(\S+)\s+(\S+)\s+(\S+)\s+ARPA\s+(\S+)", re.IGNORECASE)
    
    for line in lines:
        if not line.strip(): continue
        match = pattern.search(line)
        if match:
            ip, age, mac, interface = match.groups()
            entry_type = "static" if age == "-" else "dynamic"
            # Normalize Cisco MAC 0011.2233.4455 to 00:11:22:33:44:55
            mac = mac.replace(".", "")
            mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))
            
            arp_entries.append(ArpEntry(
                ip=ip,
                mac=mac.upper(),
                interface=interface,
                type=entry_type
            ))
            
    return arp_entries


def parse_show_mac_address_table(output: str) -> List[MacEntry]:
    """
    Parses 'show mac address-table' output.
    Example:
              Mac Address Table
    -------------------------------------------
    Vlan    Mac Address       Type        Ports
    ----    -----------       ----        -----
       1    00aa.bbcc.ddee    DYNAMIC     Fa0/1
    """
    mac_entries = []
    lines = output.splitlines()
    
    pattern = re.compile(r"^\s*(\d+)\s+([0-9a-f\.]+)\s+(DYNAMIC|STATIC)\s+(\S+)", re.IGNORECASE)
    
    for line in lines:
        match = pattern.search(line)
        if match:
            vlan, mac, mtype, port = match.groups()
            mac = mac.replace(".", "")
            mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))
            
            mac_entries.append(MacEntry(
                mac=mac.upper(),
                port=port,
                vlan=int(vlan),
                type=mtype.lower()
            ))
            
    return mac_entries


def parse_show_ip_route(output: str) -> List[RouteEntry]:
    """
    Parses 'show ip route' output.
    Example:
    S*    0.0.0.0/0 [1/0] via 192.168.1.254
    C     192.168.1.0/24 is directly connected, FastEthernet0/1
    """
    routes = []
    lines = output.splitlines()
    
    # Simple patterns for Connected and Static routes
    connected_pattern = re.compile(r"^C\s+([\d\./]+) is directly connected, (\S+)")
    static_via_pattern = re.compile(r"^[S]\*?\s+([\d\./]+) \[(\d+)/(\d+)\] via ([\d\.]+)")
    
    for line in lines:
        conn_match = connected_pattern.search(line)
        if conn_match:
            dest, interface = conn_match.groups()
            routes.append(RouteEntry(
                destination=dest,
                gateway=interface,
                interface=interface,
                metric=0,
                protocol="connected"
            ))
            continue
            
        static_match = static_via_pattern.search(line)
        if static_match:
            dest, dist, met, gw = static_match.groups()
            routes.append(RouteEntry(
                destination=dest,
                gateway=gw,
                interface="", # Usually not in 'via' format
                metric=int(dist),
                protocol="static"
            ))
            
    return routes
