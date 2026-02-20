"""
NetVault - Audit Engine
Orchestrates network and device-level security and configuration audits.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from core.database.db import DatabaseManager
from core.database import crud
from core.database.models import AuditLogModel, AlertModel
from core.engine.device_manager import DeviceManager, get_device_manager
from core.engine.logger import get_logger
from connectors.base import AuditResult, AuditCheck

logger = get_logger("netvault.engine.audit_engine")

class AuditEngine:
    """
    Singleton engine that performs network-wide and device-specific audits.
    Integrates with DeviceManager to access connectors and DatabaseManager for storage.
    """
    _instance: Optional['AuditEngine'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AuditEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self, db: DatabaseManager, device_manager: DeviceManager):
        # Ensure __init__ only runs once if singleton
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.db = db
        self.device_manager = device_manager
        self._initialized = True
        logger.info("Audit Engine initialized")

    @classmethod
    def get_instance(cls) -> 'AuditEngine':
        """Access the singleton instance of the Audit Engine."""
        if cls._instance is None:
            raise RuntimeError("AuditEngine not initialized. Call __init__ first.")
        return cls._instance

    async def run_device_audit(self, device_id: int) -> Optional[AuditResult]:
        """
        Run a full audit on a single device and store results in the database.
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting audit for device {device_id}")

        connector = await self.device_manager.get_connector(device_id)
        if not connector:
            logger.error(f"Failed to get connector for device {device_id}")
            return None

        try:
            # 1. Connect
            if not await connector.connect():
                logger.error(f"Failed to connect to device {device_id} for audit")
                return None

            # 2. Run Audit
            result: AuditResult = await connector.run_audit()
            
            # 3. Process results
            status = "success"
            fail_count = 0
            warning_count = 0
            
            for check in result.checks:
                if check.status == "fail":
                    fail_count += 1
                elif check.status == "warning":
                    warning_count += 1
            
            if fail_count > 0:
                status = "error"
            elif warning_count > 0:
                status = "warning"

            # 4. Save to DB
            log_entry = AuditLogModel(
                device_id=device_id,
                audit_type=f"{connector.__class__.__name__.lower()}_audit",
                result_json=self._result_to_dict(result),
                status=status,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc)
            )
            await crud.create_audit_log(self.db, log_entry)

            # 5. Trigger alerts for failures
            if status in ["error", "warning"]:
                for check in result.checks:
                    if check.status in ["fail", "warning"]:
                        alert = AlertModel(
                            rule_id=0,  # Generic audit rule
                            device_id=device_id,
                            message=f"Audit {check.status.upper()}: {check.name} - {check.message}",
                            severity="critical" if check.status == "fail" else "warning"
                        )
                        await crud.trigger_alert(self.db, alert)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Audit completed for device {device_id} in {duration:.2f}s. Result: {status}")
            
            return result

        except Exception as e:
            logger.exception(f"Error during device audit for {device_id}: {e}")
            return None
        finally:
            if connector.is_connected:
                await connector.disconnect()

    async def run_network_audit(self) -> AuditResult:
        """
        Audit all devices and perform cross-device network level checks.
        """
        start_time = datetime.now(timezone.utc)
        logger.info("Starting global network audit")
        
        # 1. Ensure all devices are loaded and cached
        await self.device_manager.load_devices()
        devices = self.device_manager._devices
        
        network_checks = []
        
        # 2. Gather data from all online devices
        online_device_ids = [did for did, d in devices.items() if d.get("status") == "online"]
        
        # Refresh data for all online devices (gets ARP, MAC, routes)
        refresh_tasks = [self.device_manager.refresh_device_data(did) for did in online_device_ids]
        await asyncio.gather(*refresh_tasks, return_exceptions=True)
        
        # 3. Perform cross-device checks
        all_data = {did: self.device_manager._cache.get(did) for did in online_device_ids if self.device_manager._cache.get(did)}
        logger.debug(f"Gathered audit data from {len(all_data)} devices: {list(all_data.keys())}")
        
        # Duplicate IP Detection
        dup_ips = self._check_duplicate_ips(all_data)
        for ip, macs in dup_ips.items():
            network_checks.append(AuditCheck(
                name="Duplicate IP Detection",
                status="fail",
                message=f"IP {ip} is associated with multiple MAC addresses: {', '.join(macs)}",
                details={"ip": ip, "macs": macs}
            ))

        # Duplicate MAC Detection
        dup_macs = self._check_duplicate_macs(all_data)
        for mac, ports in dup_macs.items():
            network_checks.append(AuditCheck(
                name="Duplicate MAC Detection",
                status="warning",
                message=f"MAC {mac} seen on multiple ports/devices: {', '.join(ports)}",
                details={"mac": mac, "ports": ports}
            ))

        # Orphan Device Detection
        orphans = self._check_orphan_devices(all_data, devices)
        for ip in orphans:
            network_checks.append(AuditCheck(
                name="Orphan Device Detection",
                status="warning",
                message=f"Device with IP {ip} found in ARP tables but not in NetVault inventory",
                details={"ip": ip}
            ))

        # VLAN Consistency (Placeholder logic)
        vlan_issues = self._check_vlan_consistency(all_data)
        for issue in vlan_issues:
            network_checks.append(AuditCheck(**issue))

        # 4. Summary and Storage
        status = "success"
        if any(c.status == "fail" for c in network_checks):
            status = "error"
        elif any(c.status == "warning" for c in network_checks):
            status = "warning"

        result = AuditResult(
            device_name="Global Network",
            timestamp=datetime.now(timezone.utc),
            checks=network_checks,
            summary=f"Found {len(dup_ips)} duplicate IPs, {len(dup_macs)} duplicate MACs, and {len(orphans)} orphan devices."
        )

        # Store global audit log (using device_id=0 for global)
        log_entry = AuditLogModel(
            device_id=0,
            audit_type="network_audit",
            result_json=self._result_to_dict(result),
            status=status,
            started_at=start_time,
            completed_at=datetime.now(timezone.utc)
        )
        await crud.create_audit_log(self.db, log_entry)

        # 5. Trigger alerts for network issues
        for check in result.checks:
            if check.status in ["fail", "warning"]:
                alert = AlertModel(
                    rule_id=0,  # Generic network audit rule
                    device_id=0, # Global
                    message=f"Network {check.status.upper()}: {check.name} - {check.message}",
                    severity="critical" if check.status == "fail" else "warning"
                )
                await crud.trigger_alert(self.db, alert)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"Network audit completed in {duration:.2f}s. Result: {status}")
        
        return result

    async def run_security_audit(self) -> AuditResult:
        """
        Perform focused security checks across all devices.
        Currently focuses on generic best practices.
        """
        logger.info("Security audit triggered (placeholder implementation)")
        return await self.run_network_audit()

    async def get_audit_results(self, device_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve historical audit logs from database."""
        logs = await crud.list_audit_logs(self.db, device_id)
        # Reverse to get latest first if not already
        logs.reverse()
        return logs[:limit]

    async def get_audit_detail(self, audit_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific audit result."""
        row = await self.db.fetch_one("SELECT * FROM audit_logs WHERE id = ?", (audit_id,))
        if row:
            d = dict(row)
            import json
            d["result_json"] = json.loads(d["result_json"])
            return d
        return None

    # ─── Internal Check Logic ───

    def _check_duplicate_ips(self, all_data: Dict[int, Any]) -> Dict[str, List[str]]:
        """Detect duplicate IPs in combined ARP tables."""
        ip_map = {} # ip -> set(mac)
        for did, data in all_data.items():
            arp_table = data.get("arp_table", [])
            for entry in arp_table:
                # Handle both dicts and dataclasses
                ip = entry.get("ip") if isinstance(entry, dict) else getattr(entry, "ip", None)
                mac = entry.get("mac") if isinstance(entry, dict) else getattr(entry, "mac", None)
                if ip and mac:
                    if ip not in ip_map:
                        ip_map[ip] = set()
                    ip_map[ip].add(mac)
        
        return {ip: list(macs) for ip, macs in ip_map.items() if len(macs) > 1}

    def _check_duplicate_macs(self, all_data: Dict[int, Any]) -> Dict[str, List[str]]:
        """Detect duplicate MACs across MAC address tables."""
        mac_map = {} # mac -> set(device_id:port)
        for did, data in all_data.items():
            mac_table = data.get("mac_table", [])
            for entry in mac_table:
                # Handle both dicts and dataclasses
                mac = entry.get("mac") if isinstance(entry, dict) else getattr(entry, "mac", None)
                port = entry.get("port") if isinstance(entry, dict) else getattr(entry, "port", None)
                if mac and port:
                    if mac not in mac_map:
                        mac_map[mac] = set()
                    mac_map[mac].add(f"device_{did}:{port}")
        
        return {mac: list(ports) for mac, ports in mac_map.items() if len(ports) > 1}

    def _check_orphan_devices(self, all_data: Dict[int, Any], inventory: Dict[int, Any]) -> List[str]:
        """Detect IPs in ARP tables that are NOT in our managed inventory."""
        known_ips = set()
        for d in inventory.values():
            if d.get("ip"):
                known_ips.add(d.get("ip"))
            if d.get("ip_address"):
                known_ips.add(d.get("ip_address"))
                
        arp_ips = set()
        for data in all_data.values():
            for entry in data.get("arp_table", []):
                # Handle both dicts and dataclasses
                ip = entry.get("ip") if isinstance(entry, dict) else getattr(entry, "ip", None)
                if ip:
                    arp_ips.add(ip)
        
        return list(arp_ips - known_ips)

    def _check_vlan_consistency(self, all_data: Dict[int, Any]) -> List[Dict[str, Any]]:
        """Basic check for VLAN consistency (placeholder)."""
        issues = []
        return issues

    def _result_to_dict(self, result: AuditResult) -> Dict[str, Any]:
        """Convert AuditResult dataclass to a JSON-serializable dictionary."""
        return {
            "device_name": result.device_name,
            "timestamp": result.timestamp.isoformat() if isinstance(result.timestamp, datetime) else result.timestamp,
            "summary": result.summary,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details
                } for c in result.checks
            ]
        }

_AUDIT_ENGINE_INSTANCE: Optional[AuditEngine] = None

def get_audit_engine(db: Optional[DatabaseManager] = None, device_manager: Optional[DeviceManager] = None) -> AuditEngine:
    """Access the singleton instance of the Audit Engine."""
    global _AUDIT_ENGINE_INSTANCE
    if _AUDIT_ENGINE_INSTANCE is None:
        if db is None or device_manager is None:
            raise ValueError("DatabaseManager and DeviceManager required for first initialization")
        _AUDIT_ENGINE_INSTANCE = AuditEngine(db, device_manager)
    return _AUDIT_ENGINE_INSTANCE
