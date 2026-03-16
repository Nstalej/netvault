"""
NetVault - Windows AD Agent - Data Collector
"""
import logging
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ldap3 import ALL, SUBTREE, Connection, Server, Tls

logger = logging.getLogger(__name__)

def _safe_get(entry: dict, key: str, default: Any = None) -> Any:
    val = entry.get(key)
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if len(val) > 0 else default
    return val


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, int):
        # Windows FileTime support
        if value <= 0:
            return None
        try:
            epoch_diff = 116444736000000000
            timestamp = (value - epoch_diff) / 10000000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        except Exception:
            return None
    if isinstance(value, str) and value.isdigit():
        return _to_iso(int(value))
    return str(value)


def _extract_cn(dn: str) -> str:
    if not dn:
        return ""
    for part in str(dn).split(","):
        part = part.strip()
        if part.upper().startswith("CN="):
            return part[3:]
    return str(dn)


def _group_scope(group_type: int) -> str:
    # AD groupType flags (scope bits)
    if group_type & 0x00000008:
        return "Universal"
    if group_type & 0x00000004:
        return "DomainLocal"
    if group_type & 0x00000002:
        return "Global"
    return "Unknown"

class ADCollector:
    def __init__(self, server: str, user: str, password: str, base_dn: str, use_ssl: bool = True):
        self.server_name = server
        self.user = user
        self.password = password
        self.base_dn = base_dn
        self.use_ssl = use_ssl
        self.connection: Optional[Connection] = None

    def connect(self) -> bool:
        """Establish connection to Active Directory"""
        try:
            tls = None
            if self.use_ssl:
                tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            
            server = Server(self.server_name, use_ssl=self.use_ssl, tls=tls, get_info=ALL)
            self.connection = Connection(
                server, 
                user=self.user, 
                password=self.password, 
                authentication='SIMPLE',
                auto_bind=True
            )
            logger.info(f"Connected to AD server: {self.server_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to AD: {str(e)}")
            return False

    def disconnect(self):
        """Close AD connection"""
        if self.connection:
            self.connection.unbind()
            self.connection = None

    def get_users(self) -> List[Dict[str, Any]]:
        """Collect all users and their key attributes"""
        if not self.connection:
            return []
        
        search_filter = "(&(objectCategory=person)(objectClass=user))"
        attributes = [
            'sAMAccountName', 'displayName', 'mail', 'userAccountControl', 
            'lastLogonTimestamp', 'pwdLastSet', 'lockoutTime', 'description',
            'distinguishedName', 'whenCreated', 'memberOf', 'department', 'title'
        ]
        
        self.connection.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        users = []
        for entry in self.connection.entries:
            user_data = entry.entry_attributes_as_dict
            # Decode userAccountControl safely
            uac_val = _safe_get(user_data, 'userAccountControl', 0)
            uac = int(uac_val) if uac_val else 0
            is_disabled = bool(uac & 2)
            
            lockout_val = _safe_get(user_data, 'lockoutTime', 0)
            if isinstance(lockout_val, datetime):
                is_locked = lockout_val.timestamp() > 0
            else:
                is_locked = int(lockout_val) > 0 if lockout_val else False

            groups_raw = user_data.get('memberOf', [])
            groups = groups_raw if isinstance(groups_raw, list) else [groups_raw] if groups_raw else []
            member_of = [_extract_cn(group) for group in groups]

            users.append(
                {
                    "sAMAccountName": _safe_get(user_data, 'sAMAccountName', ''),
                    "displayName": _safe_get(user_data, 'displayName', ''),
                    "mail": _safe_get(user_data, 'mail', ''),
                    "department": _safe_get(user_data, 'department', ''),
                    "title": _safe_get(user_data, 'title', ''),
                    "enabled": not is_disabled,
                    "locked": is_locked,
                    "lastLogon": _to_iso(_safe_get(user_data, 'lastLogonTimestamp')),
                    "passwordNeverExpires": bool(uac & 0x10000),
                    "memberOf": member_of,
                    # Keep compatibility fields used by current auditor.
                    "is_disabled": is_disabled,
                    "is_locked": is_locked,
                    "lastLogonTimestamp": _safe_get(user_data, 'lastLogonTimestamp'),
                    "userAccountControl": uac,
                }
            )
        
        return users

    def get_groups(self) -> List[Dict[str, Any]]:
        """Collect all groups and memberships"""
        if not self.connection:
            return []
        
        search_filter = "(objectClass=group)"
        attributes = ['sAMAccountName', 'cn', 'distinguishedName', 'member', 'description', 'groupType']
        
        self.connection.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        groups = []
        for entry in self.connection.entries:
            group_data = entry.entry_attributes_as_dict
            members_raw = group_data.get('member', [])
            members = members_raw if isinstance(members_raw, list) else [members_raw] if members_raw else []
            group_type_val = _safe_get(group_data, 'groupType', 0)
            group_type = int(group_type_val) if group_type_val else 0

            groups.append(
                {
                    "name": _safe_get(group_data, 'sAMAccountName', '') or _safe_get(group_data, 'cn', ''),
                    "members": [_extract_cn(member) for member in members],
                    "memberCount": len(members),
                    "scope": _group_scope(group_type),
                    # Compatibility fields for current auditor.
                    "sAMAccountName": _safe_get(group_data, 'sAMAccountName', ''),
                    "member": members,
                }
            )
        return groups

    def get_computers(self) -> List[Dict[str, Any]]:
        """Collect all domain-joined computers"""
        if not self.connection:
            return []
        
        search_filter = "(objectClass=computer)"
        attributes = [
            'sAMAccountName', 'dNSHostName', 'operatingSystem', 
            'operatingSystemVersion', 'lastLogonTimestamp', 'distinguishedName'
        ]
        
        self.connection.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        computers = []
        for entry in self.connection.entries:
            comp_data = entry.entry_attributes_as_dict
            hostname = _safe_get(comp_data, 'dNSHostName', '')
            sam = _safe_get(comp_data, 'sAMAccountName', '')
            if sam.endswith('$'):
                sam = sam[:-1]

            computers.append(
                {
                    "name": hostname or sam,
                    "os": _safe_get(comp_data, 'operatingSystem', ''),
                    "osVersion": _safe_get(comp_data, 'operatingSystemVersion', ''),
                    "lastLogon": _to_iso(_safe_get(comp_data, 'lastLogonTimestamp')),
                }
            )
        return computers

    def get_gpos(self) -> List[Dict[str, Any]]:
        """Collect Group Policy Objects"""
        if not self.connection:
            return []
        
        # GPOs are stored in CN=Policies,CN=System,BaseDN
        gpo_base = f"CN=Policies,CN=System,{self.base_dn}"
        search_filter = "(objectClass=groupPolicyContainer)"
        attributes = ['displayName', 'gPCFileSysPath', 'whenCreated', 'gPCMachineExtensionNames', 'flags']
        
        self.connection.search(
            search_base=gpo_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        gpos = []
        for entry in self.connection.entries:
            gpo_data = entry.entry_attributes_as_dict
            flags_val = _safe_get(gpo_data, 'flags', 0)
            flags = int(flags_val) if flags_val else 0
            status = "enabled" if flags == 0 else "partially_disabled"
            gpos.append(
                {
                    "name": _safe_get(gpo_data, 'displayName', ''),
                    "status": status,
                    "createdAt": _to_iso(_safe_get(gpo_data, 'whenCreated')),
                }
            )
        return gpos

    def get_dns(self) -> List[Dict[str, Any]]:
        """Collect DNS zones and records (simplified)"""
        if not self.connection:
            return []
        
        # DNS is often in DC=DomainDnsZones,DC=domain,DC=local
        dns_base = f"DC=DomainDnsZones,{self.base_dn}"
        search_filter = "(objectClass=dnsNode)"
        attributes = ['dc', 'dnsRecord', 'whenCreated']
        
        try:
            self.connection.search(
                search_base=dns_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes
            )
            
            dns_records = []
            for entry in self.connection.entries:
                dns_records.append(entry.entry_attributes_as_dict)
            return dns_records
        except Exception:
            # DomainDnsZones might not be accessible or might use a different DN
            return []

    def get_replication(self) -> List[Dict[str, Any]]:
        """Collect NTDS replication status (place-holder for future extension)"""
        return []

    def get_dhcp(self) -> List[Dict[str, Any]]:
        """Collect DHCP info (place-holder, usually requires Netsh or WMI)"""
        return []

    def collect_all(self) -> Dict[str, Any]:
        """Run all collection functions and return consolidated data"""
        if not self.connect():
            return {"error": "Connection failed"}
        
        try:
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "users": self.get_users(),
                "groups": self.get_groups(),
                "computers": self.get_computers(),
                "gpos": self.get_gpos(),
            }
            return data
        finally:
            self.disconnect()
