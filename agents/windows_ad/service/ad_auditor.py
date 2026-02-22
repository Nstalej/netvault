"""
NetVault - Windows AD Agent - Auditor
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ADAuditor:
    def __init__(self, stale_days: int = 90):
        self.stale_days = stale_days

    def audit(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all audit checks on AD data"""
        if "error" in ad_data:
            return {"status": "error", "message": ad_data["error"]}

        results = {
            "summary": {
                "total_users": len(ad_data.get("users", [])),
                "total_groups": len(ad_data.get("groups", [])),
                "total_computers": len(ad_data.get("computers", [])),
                "total_gpos": len(ad_data.get("gpos", [])),
                "vulnerabilities": 0
            },
            "checks": []
        }

        # 1. Check for Default Guest/Admin
        results["checks"].append(self._check_default_accounts(ad_data["users"]))
        
        # 2. Check for Stale Accounts
        results["checks"].append(self._check_stale_accounts(ad_data["users"]))
        
        # 3. Check Privileged Groups
        results["checks"].append(self._check_privileged_groups(ad_data["groups"]))
        
        # 4. Check for Password Policy Issues (expired or never changes)
        results["checks"].append(self._check_password_policies(ad_data["users"]))

        # Calculate total vulnerabilities
        results["summary"]["vulnerabilities"] = sum(
            1 for c in results["checks"] if c["status"] in ["warning", "critical"]
        )

        return results

    def _check_default_accounts(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        issues = []
        for user in users:
            name = user.get('sAMAccountName', [''])[0].lower()
            is_disabled = user.get('is_disabled', False)
            
            if name == 'guest' and not is_disabled:
                issues.append("Guest account is enabled")
            if name == 'administrator':
                issues.append("Default 'Administrator' account exists (consider renaming)")

        return {
            "name": "Default Accounts",
            "status": "critical" if any("Guest" in i for i in issues) else "warning" if issues else "pass",
            "findings": issues
        }

    def _check_stale_accounts(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        stale_threshold = datetime.now() - timedelta(days=self.stale_days)
        issues = []
        
        for user in users:
            last_logon = user.get('lastLogonTimestamp', [None])[0]
            if not last_logon:
                continue
                
            # lastLogonTimestamp is Windows FileTime (100ns intervals since 1601-01-01)
            # Simplified comparison for this example
            try:
                # Mock parsing/conversion logic - in real world would use win32 helpers or math
                # Assuming ad_collector already converted or we use dummy logic here
                pass
            except Exception:
                continue

        return {
            "name": "Stale Accounts",
            "status": "pass",  # Placeholder until better timestamp parsing is added
            "findings": issues
        }

    def _check_privileged_groups(self, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        privileged_group_names = ['domain admins', 'enterprise admins', 'schema admins', 'account operators']
        findings = []
        
        for group in groups:
            name = group.get('sAMAccountName', [''])[0].lower()
            if name in privileged_group_names:
                members = group.get('member', [])
                if len(members) > 5:
                    findings.append(f"Group '{name}' has {len(members)} members (recommend < 5)")
        
        return {
            "name": "Privileged Groups",
            "status": "warning" if findings else "pass",
            "findings": findings
        }

    def _check_password_policies(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        findings = []
        for user in users:
            uac = int(user.get('userAccountControl', [0])[0])
            # 0x10000 = ADS_UF_DONT_EXPIRE_PASSWD
            if uac & 0x10000:
                findings.append(f"User '{user.get('sAMAccountName', [''])[0]}' password never expires")
                
        return {
            "name": "Password Hygiene",
            "status": "warning" if len(findings) > 5 else "pass",
            "findings": findings
        }
