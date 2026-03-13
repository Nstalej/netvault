from connectors.ssh_connector.parsers import cisco_parser, mikrotik_parser

MIKROTIK_SYSTEM_RESOURCE = """
             uptime: 5d21h34m56s
            version: 7.12.1 (stable)
         board-name: RB750Gr3
                cpu: MIPS 24Kc V7.4
       total-memory: 128.0MiB
        free-memory: 110.4MiB
""".strip()

MIKROTIK_INTERFACES = """
Flags: R - RUNNING; S - SLAVE
#    NAME       TYPE     ACTUAL-MTU  L2MTU  MAX-L2MTU  MAC-ADDRESS
0 RS ether1     ether          1500   1500       4074  48:8F:5A:AA:BB:CC
1    ether2     ether          1500   1500       4074  48:8F:5A:AA:BB:CD
""".strip()

MIKROTIK_ARP = """
#   ADDRESS         MAC-ADDRESS       INTERFACE
0 D 192.168.88.254  48:8F:5A:AA:BB:CC bridge
1   192.168.88.2    4C:5E:0C:11:22:33 ether1
""".strip()

MIKROTIK_ROUTES = """
#      DST-ADDRESS        GATEWAY         DISTANCE
0  As  0.0.0.0/0          192.168.88.1           1
1  DAC 192.168.88.0/24    bridge                 0
""".strip()

CISCO_SHOW_VERSION = """
Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE7, RELEASE SOFTWARE (fc1)
cisco WS-C2960-24TT-L (PowerPC405) processor (revision B0) with 65536K bytes of memory.
Switch uptime is 2 weeks, 1 day, 3 hours, 2 minutes
""".strip()

CISCO_SHOW_INTERFACES = """
Interface              IP-Address      OK? Method Status                Protocol
FastEthernet0/1        192.168.1.1     YES manual up                    up
FastEthernet0/2        unassigned      YES unset  down                  down
""".strip()

CISCO_SHOW_IP_ARP = """
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  192.168.1.1             -   0011.2233.4455  ARPA   FastEthernet0/1
Internet  192.168.1.100          10   00aa.bbcc.ddee  ARPA   FastEthernet0/1
""".strip()

CISCO_MAC_TABLE = """
          Mac Address Table
-------------------------------------------
Vlan    Mac Address       Type        Ports
----    -----------       ----        -----
   1    00aa.bbcc.ddee    DYNAMIC     Fa0/1
  10    0011.2233.4455    STATIC      Fa0/2
""".strip()

CISCO_IP_ROUTE = """
S*    0.0.0.0/0 [1/0] via 192.168.1.254
C     192.168.1.0/24 is directly connected, FastEthernet0/1
""".strip()


def test_mikrotik_parse_system_resource():
    parsed = mikrotik_parser.parse_system_resource(MIKROTIK_SYSTEM_RESOURCE)
    assert parsed["model"] == "RB750Gr3"
    assert parsed["os_version"].startswith("7.12")
    assert parsed["uptime"] == "5d21h34m56s"
    assert "MIPS" in parsed["cpu"]
    assert parsed["memory_total"] == "128.0MiB"


def test_mikrotik_parse_interfaces():
    interfaces = mikrotik_parser.parse_interfaces(MIKROTIK_INTERFACES)
    assert len(interfaces) == 2
    assert interfaces[0].name == "ether1"
    assert interfaces[0].status == "up"
    assert interfaces[1].status == "down"


def test_mikrotik_parse_interfaces_empty():
    interfaces = mikrotik_parser.parse_interfaces("")
    assert interfaces == []


def test_mikrotik_parse_arp_table():
    entries = mikrotik_parser.parse_arp_table(MIKROTIK_ARP)
    assert len(entries) == 2
    assert entries[0].ip == "192.168.88.254"
    assert entries[0].mac == "48:8F:5A:AA:BB:CC"
    assert entries[0].interface == "bridge"


def test_mikrotik_parse_arp_dynamic_vs_static():
    entries = mikrotik_parser.parse_arp_table(MIKROTIK_ARP)
    assert entries[0].type == "dynamic"
    assert entries[1].type == "static"


def test_mikrotik_parse_routes():
    routes = mikrotik_parser.parse_routes(MIKROTIK_ROUTES)
    assert len(routes) == 2
    assert routes[0].destination == "0.0.0.0/0"
    assert routes[0].gateway == "192.168.88.1"
    assert routes[0].protocol == "static"


def test_mikrotik_parse_routes_connected():
    routes = mikrotik_parser.parse_routes(MIKROTIK_ROUTES)
    connected = [route for route in routes if route.protocol == "connected"]
    assert connected
    assert connected[0].gateway == "bridge"


def test_cisco_parse_show_version():
    parsed = cisco_parser.parse_show_version(CISCO_SHOW_VERSION)
    assert parsed["model"] == "WS-C2960-24TT-L"
    assert parsed["os_version"] == "12.2(55)SE7"


def test_cisco_parse_show_interfaces():
    interfaces = cisco_parser.parse_show_interfaces(CISCO_SHOW_INTERFACES)
    assert len(interfaces) == 2
    assert interfaces[0].name == "FastEthernet0/1"
    assert interfaces[0].status == "up"
    assert interfaces[0].ip == "192.168.1.1"


def test_cisco_parse_show_ip_arp():
    arp = cisco_parser.parse_show_ip_arp(CISCO_SHOW_IP_ARP)
    assert len(arp) == 2
    assert arp[0].mac == "00:11:22:33:44:55"
    assert arp[1].ip == "192.168.1.100"


def test_cisco_parse_mac_address_table():
    table = cisco_parser.parse_show_mac_address_table(CISCO_MAC_TABLE)
    assert len(table) == 2
    assert table[0].mac == "00:AA:BB:CC:DD:EE"
    assert table[0].port == "Fa0/1"
    assert table[0].vlan == 1


def test_cisco_parse_show_ip_route():
    routes = cisco_parser.parse_show_ip_route(CISCO_IP_ROUTE)
    assert len(routes) == 2
    assert routes[0].destination == "0.0.0.0/0"
    assert routes[0].gateway == "192.168.1.254"
    assert routes[0].protocol == "static"
