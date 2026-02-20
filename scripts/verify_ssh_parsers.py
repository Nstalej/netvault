"""
Verification script for SSH Connector Parsers
"""
# Avoid importing from connectors/__init__.py which triggers all connectors
import sys
import os
sys.path.append(os.getcwd())

from connectors.ssh_connector.parsers import mikrotik_parser, cisco_parser
from connectors.base import InterfaceInfo, ArpEntry, RouteEntry, MacEntry

def test_mikrotik_parsers():
    print("Testing MikroTik Parsers...")
    
    # Test System Resource
    output = """
          uptime: 5d21h34m56s
         version: 7.12.1 (stable)
      build-time: Nov/23/2023 12:45:04
     factory-software: 6.48.6
      free-memory: 110.4MiB
     total-memory: 128.0MiB
             cpu: MIPS 24Kc V7.4
       cpu-count: 1
      board-name: hAP ac2
    """
    res = mikrotik_parser.parse_system_resource(output)
    print(f"System Info: {res}")
    assert res['model'] == "hAP ac2"
    assert res['os_version'] == "7.12.1 (stable)"

    # Test Interfaces
    output = """
Flags: R - RUNNING; S - SLAVE
#    NAME       TYPE     ACTUAL-MTU  L2MTU  MAX-L2MTU  MAC-ADDRESS      
0 RS ether1     ether          1500   1500       4074  48:8F:5A:11:22:33
1  S ether2     ether          1500   1500       4074  48:8F:5A:11:22:34
    """
    ifaces = mikrotik_parser.parse_interfaces(output)
    print(f"Interfaces: {ifaces}")
    assert len(ifaces) == 2
    assert ifaces[0].name == "ether1"
    assert ifaces[0].status == "up"
    assert ifaces[1].status == "down"

    # Test ARP
    output = """
#   ADDRESS         MAC-ADDRESS       INTERFACE
0 D 192.168.88.254  48:8F:5A:AA:BB:CC bridge   
1   192.168.88.10   48:8F:5A:DD:EE:FF ether1
    """
    arp = mikrotik_parser.parse_arp_table(output)
    print(f"ARP Table: {arp}")
    assert len(arp) == 2
    assert arp[0].ip == "192.168.88.254"
    assert arp[0].type == "dynamic"
    assert arp[1].type == "static"

    print("MikroTik Parsers: PASS\n")


def test_cisco_parsers():
    print("Testing Cisco IOS Parsers...")
    
    # Test Show Version
    output = """
Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE7, RELEASE SOFTWARE (fc1)
uptime is 2 weeks, 3 days, 15 hours, 44 minutes
cisco WS-C2960-24TT-L (PowerPC405) processor (revision B0) with 65536K bytes of memory.
    """
    res = cisco_parser.parse_show_version(output)
    print(f"System Info: {res}")
    assert res['model'] == "WS-C2960-24TT-L"
    assert res['os_version'] == "12.2(55)SE7"

    # Test Interfaces
    output = """
Interface              IP-Address      OK? Method Status                Protocol
FastEthernet0/1        192.168.1.1     YES manual up                    up      
FastEthernet0/2        unassigned      YES unset  down                  down    
    """
    ifaces = cisco_parser.parse_show_interfaces(output)
    print(f"Interfaces: {ifaces}")
    assert len(ifaces) == 2
    assert ifaces[0].name == "FastEthernet0/1"
    assert ifaces[0].status == "up"

    # Test ARP
    output = """
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  192.168.1.1             -   0011.2233.4455  ARPA   FastEthernet0/1
Internet  192.168.1.100          10   00aa.bbcc.ddee  ARPA   FastEthernet0/1
    """
    arp = cisco_parser.parse_show_ip_arp(output)
    print(f"ARP Table: {arp}")
    assert len(arp) == 2
    assert arp[0].ip == "192.168.1.1"
    assert arp[0].mac == "00:11:22:33:44:55"

    print("Cisco IOS Parsers: PASS\n")


if __name__ == "__main__":
    try:
        test_mikrotik_parsers()
        test_cisco_parsers()
        print("All parsing tests PASSED!")
    except Exception as e:
        print(f"Tests FAILED: {e}")
        import traceback
        traceback.print_exc()
