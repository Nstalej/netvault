"""
NetVault - Windows AD Agent - Data Collector
"""
import logging
from typing import List, Dict, Any, Optional
from ldap3 import Server, Connection, ALL, SUBTREE, ALL_ATTRIBUTES, Tls
from datetime import datetime
import ssl

logger = logging.getLogger(__name__)

def _safe_get(entry: dict, key: str, default: Any = None) -> Any:
    val = entry.get(key)
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if len(val) > 0 else default
    return val

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
            'distinguishedName', 'whenCreated', 'memberOf'
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
            user_data['is_disabled'] = bool(uac & 2)
            
            lockout_val = _safe_get(user_data, 'lockoutTime', 0)
            if isinstance(lockout_val, datetime):
                user_data['is_locked'] = lockout_val.timestamp() > 0
            else:
                user_data['is_locked'] = int(lockout_val) > 0 if lockout_val else False
                
            users.append(user_data)
        
        return users

    def get_groups(self) -> List[Dict[str, Any]]:
        """Collect all groups and memberships"""
        if not self.connection:
            return []
        
        search_filter = "(objectClass=group)"
        attributes = ['sAMAccountName', 'distinguishedName', 'member', 'description']
        
        self.connection.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        groups = []
        for entry in self.connection.entries:
            groups.append(entry.entry_attributes_as_dict)
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
            computers.append(entry.entry_attributes_as_dict)
        return computers

    def get_gpos(self) -> List[Dict[str, Any]]:
        """Collect Group Policy Objects"""
        if not self.connection:
            return []
        
        # GPOs are stored in CN=Policies,CN=System,BaseDN
        gpo_base = f"CN=Policies,CN=System,{self.base_dn}"
        search_filter = "(objectClass=groupPolicyContainer)"
        attributes = ['displayName', 'gPCFileSysPath', 'whenCreated', 'gPCMachineExtensionNames']
        
        self.connection.search(
            search_base=gpo_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes
        )
        
        gpos = []
        for entry in self.connection.entries:
            gpos.append(entry.entry_attributes_as_dict)
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
                "timestamp": None,  # Will be set by auditor or agent
                "users": self.get_users(),
                "groups": self.get_groups(),
                "computers": self.get_computers(),
                "gpos": self.get_gpos(),
                "dns": self.get_dns()
            }
            return data
        finally:
            self.disconnect()
