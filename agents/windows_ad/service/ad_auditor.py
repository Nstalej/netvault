"""
NetVault - Windows AD Agent - Auditor
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def _safe_get(entry: dict, key: str, default: Any = None) -> Any:
    val = entry.get(key)
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if len(val) > 0 else default
    return val

def _now_aware() -> datetime:
    return datetime.now(timezone.utc)

def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        val_int = int(value)
        if val_int == 0:
            return None
        EPOCH_DIFF = 116444736000000000
        timestamp = (val_int - EPOCH_DIFF) / 10000000
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc)
        except:
            return None
    return None

class ADAuditor:
    def __init__(self, stale_days: int = 90):
        self.stale_days = stale_days
        self.EPOCH_DIFF = 116444736000000000

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
        results["checks"].append(self._check_default_accounts(ad_data.get("users", [])))
        
        # 2. Check for Stale Accounts
        results["checks"].append(self._check_stale_accounts(ad_data.get("users", [])))
        
        # 3. Check Privileged Groups
        results["checks"].append(self._check_privileged_groups(ad_data.get("groups", [])))
        
        # 4. Check for Password Policy Issues (expired or never changes)
        results["checks"].append(self._check_password_policies(ad_data.get("users", [])))

        # Calculate total vulnerabilities
        results["summary"]["vulnerabilities"] = sum(
            1 for c in results["checks"] if c["status"] in ["warning", "critical"]
        )

        return results

    def _check_default_accounts(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        issues = []
        for user in users:
            name = str(_safe_get(user, 'sAMAccountName', '')).lower()
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

    def _filetime_to_datetime(self, filetime: int) -> datetime:
        """Convert Windows FileTime to Python datetime"""
        timestamp = (filetime - self.EPOCH_DIFF) / 10000000
        return datetime.fromtimestamp(timestamp, timezone.utc)

    def _check_stale_accounts(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        stale_threshold = _now_aware() - timedelta(days=self.stale_days)
        issues = []
        
        for user in users:
            last_logon_raw = _safe_get(user, 'lastLogonTimestamp')
            last_logon_dt = _to_datetime(last_logon_raw)
            if not last_logon_dt:
                continue
                
            try:
                if last_logon_dt < stale_threshold:
                    name = str(_safe_get(user, 'sAMAccountName', ''))
                    days_inactive = (_now_aware() - last_logon_dt).days
                    issues.append(f"User '{name}' has been inactive for {days_inactive} days")
            except Exception as e:
                logger.error(f"Error parsing lastLogonTimestamp for user: {e}")
                continue

        return {
            "name": "Stale Accounts",
            "status": "warning" if issues else "pass",
            "findings": issues
        }

    def _check_privileged_groups(self, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        privileged_group_names = ['domain admins', 'enterprise admins', 'schema admins', 'account operators']
        findings = []
        
        for group in groups:
            name = str(_safe_get(group, 'sAMAccountName', '')).lower()
            if name in privileged_group_names:
                members_raw = group.get('member', [])
                members = members_raw if isinstance(members_raw, list) else [members_raw] if members_raw else []
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
            uac_val = _safe_get(user, 'userAccountControl', 0)
            uac = int(uac_val) if uac_val else 0
            if uac & 0x10000:
                name = str(_safe_get(user, 'sAMAccountName', ''))
                findings.append(f"User '{name}' password never expires")
                
        return {
            "name": "Password Hygiene",
            "status": "warning" if len(findings) > 5 else "pass",
            "findings": findings
        }
