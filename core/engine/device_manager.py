"""
NetVault - Device Manager Engine
Main engine for managing network devices, credentials, and polling operations.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from connectors.base import ConnectionTestResult, get_connector
from core.database import crud
from core.database.db import DatabaseManager
from core.database.models import DeviceStatus
from core.engine.credential_vault import CredentialVault
from core.engine.logger import get_logger

logger = get_logger("netvault.engine.device_manager")


class DeviceManager:
    """
    Singleton engine that coordinates between API, Database, and Connectors.
    Handles device loading, connector instantiation, and parallel polling.
    """

    _instance: Optional["DeviceManager"] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeviceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Set up variables, initialization will happen in initialize()
        if not hasattr(self, "_initialized"):
            self._initialized = False
            self.db = None
            self.vault = None
            self._devices: Dict[int, Dict[str, Any]] = {}  # Cache of DB device configs
            self._connectors: Dict[int, Any] = {}  # Cache of connector instances
            self._cache: Dict[int, Dict[str, Any]] = {}  # Cache of latest poll data
            self._semaphore = asyncio.Semaphore(5)  # Default max concurrent polls
            self._polling_task: Optional[asyncio.Task] = None
            self._polling_running = False
            self._polling_interval_seconds = 300
            self._polling_last_run: Optional[str] = None
            self._polling_next_run: Optional[str] = None
            self._polling_cycle_summary: Dict[str, Any] = {}
            self._agent_offline_timeout_seconds = 120

    def initialize(self, db: DatabaseManager, vault: CredentialVault):
        if getattr(self, "_initialized", False):
            return
        self.db = db
        self.vault = vault
        self._initialized = True
        logger.info("Device Manager initialized")

    @classmethod
    def get_instance(cls) -> "DeviceManager":
        """Access the singleton instance of the Device Manager."""
        if cls._instance is None or not getattr(cls._instance, "_initialized", False):
            raise RuntimeError("DeviceManager not initialized. Call initialize() first.")
        return cls._instance

    async def load_devices(self):
        """Load all devices from the database into memory."""
        try:
            devices = await crud.list_devices(self.db)
            self._devices = {d["id"]: d for d in devices}
            logger.info(f"Loaded {len(self._devices)} devices from database")
        except Exception as e:
            logger.error(f"Failed to load devices from DB: {e}")

    async def get_connector(self, device_id: int) -> Optional[Any]:
        """Create or return a cached connector for a device."""
        if device_id in self._connectors:
            return self._connectors[device_id]

        device_cfg = self._devices.get(device_id)
        if not device_cfg:
            # Try reloading if not found in cache
            await self.load_devices()
            device_cfg = self._devices.get(device_id)

        if not device_cfg:
            logger.warning(f"Device ID {device_id} not found")
            return None

        connector_type = device_cfg.get("connector_type")
        connector_cls = get_connector(connector_type)

        if not connector_cls:
            logger.error(f"Connector type '{connector_type}' not registered")
            return None

        # Get credentials from vault
        # In current models, devices have a credential_id or we look up by name
        # The prompt says: "Retrieves decrypted credentials from CredentialVault for each device"
        # Let's check how credentials are stored. Based on core/engine/device_manager.py (old):
        # it used cred_id. Based on crud.py, we have get_credential(db, cred_id).
        # Based on credential_vault.py, it uses name.

        # We'll try to find the credential name from the device config or name
        config_json = device_cfg.get("config_json", {}) or {}
        cred_name = config_json.get("credential_name")
        if not cred_name:
            # Fallback: check if there's a credential_id in the device record
            cred_id = device_cfg.get("credential_id")
            if cred_id:
                cred_record = await crud.get_credential(self.db, cred_id)
                if cred_record:
                    cred_name = cred_record.get("name")

        if not cred_name:
            logger.warning(f"No credential associated with device {device_cfg.get('name')}")
            # Current NetVault connectors require credentials to initialize safely.
            return None
        else:
            credentials = await self.vault.get_credential(cred_name)
            if not credentials:
                logger.error(f"Credential '{cred_name}' not found in vault")
                return None

        try:
            merged_credentials = dict(credentials)
            for key, value in config_json.items():
                if key == "credential_name":
                    continue
                merged_credentials[key] = value

            if device_cfg.get("port"):
                merged_credentials["port"] = device_cfg.get("port")
            if not merged_credentials.get("device_type") and device_cfg.get("type"):
                merged_credentials["device_type"] = device_cfg.get("type")

            # Instantiate connector
            connector = connector_cls(
                device_id=str(device_id),
                device_ip=device_cfg.get("ip") or device_cfg.get("ip_address"),
                credentials=merged_credentials,
            )
            self._connectors[device_id] = connector
            return connector
        except Exception as e:
            logger.error(f"Failed to instantiate connector for device {device_id}: {e}")
            return None

    async def poll_device(self, device_id: int):
        """Connect, collect system_info + interfaces, and update DB status."""
        async with self._semaphore:
            device_cfg = self._devices.get(device_id)
            if not device_cfg:
                logger.warning(f"Cannot poll unknown device {device_id}")
                return

            name = device_cfg.get("name")
            ip = device_cfg.get("ip") or device_cfg.get("ip_address")
            start_time = time.time()

            logger.info(f"Polling device {name} ({ip})...")

            connector = await self.get_connector(device_id)
            if not connector:
                await self._update_device_status(device_id, DeviceStatus.OFFLINE)
                return

            try:
                # 1. Test connection/Connect
                connected = await connector.connect()
                if not connected:
                    logger.warning(f"Failed to connect to {name} ({ip})")
                    await self._update_device_status(device_id, DeviceStatus.OFFLINE)
                    return

                # 2. Collect basic data
                system_info = await connector.get_system_info()
                interfaces = await connector.get_interfaces()

                # Convert dataclasses to dicts if necessary (assuming they are serializable or handled by JSON)
                # For simplified cache, we store raw results
                poll_data = {
                    "system_info": system_info,
                    "interfaces": [vars(i) if hasattr(i, "__dict__") else i for i in interfaces],
                    "last_poll": datetime.now(timezone.utc).isoformat(),
                }

                self._cache[device_id] = poll_data

                # 3. Update Status
                status = DeviceStatus.ONLINE
                if not interfaces:
                    status = DeviceStatus.WARNING  # Connected but failed to get interfaces

                await self._update_device_status(device_id, status)

                duration = time.time() - start_time
                logger.info(f"Poll completed for {name} in {duration:.2f}s - {status}")

            except Exception as e:
                logger.exception(f"Unexpected error polling {name} ({ip}): {e}")
                await self._update_device_status(device_id, DeviceStatus.OFFLINE)
            finally:
                if connector.is_connected:
                    await connector.disconnect()

    async def poll_all(self, max_concurrent: int = 5):
        """Poll all devices in parallel with semaphore control."""
        # Update semaphore if requested
        if max_concurrent != self._semaphore._value:
            self._semaphore = asyncio.Semaphore(max_concurrent)

        await self.load_devices()
        tasks = [self.poll_device(device_id) for device_id in self._devices.keys()]
        if tasks:
            logger.info(f"Starting parallel poll of {len(tasks)} devices (max_concurrent={max_concurrent})")
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("All poll operations completed")

    async def run_poll_cycle(self) -> Dict[str, Any]:
        """Run one status polling cycle for all active devices and agents."""
        started = datetime.now(timezone.utc)
        await self.load_devices()

        active_ids: List[int] = []
        for device_id, device in self._devices.items():
            is_active = device.get("is_active", 1)
            if bool(is_active):
                active_ids.append(device_id)

        logger.info("Scheduled polling cycle started for %s active devices", len(active_ids))

        summary: Dict[str, Any] = {
            "started_at": started.isoformat(),
            "total_devices": len(active_ids),
            "online": 0,
            "offline": 0,
            "warning": 0,
            "failed": 0,
            "results": [],
        }

        async def _poll_single(device_id: int):
            device = self._devices.get(device_id, {})
            device_name = device.get("name", f"device-{device_id}")
            try:
                result = await self.test_device(device_id)
                refreshed = await crud.get_device(self.db, device_id)
                status_value = (
                    refreshed.get("status", DeviceStatus.UNKNOWN.value) if refreshed else DeviceStatus.UNKNOWN.value
                )

                if status_value == DeviceStatus.ONLINE.value:
                    summary["online"] += 1
                elif status_value == DeviceStatus.WARNING.value:
                    summary["warning"] += 1
                else:
                    summary["offline"] += 1

                entry = {
                    "device_id": device_id,
                    "name": device_name,
                    "status": status_value,
                    "latency_ms": result.latency_ms,
                    "error": result.error_message,
                }
                summary["results"].append(entry)
                logger.info(
                    "Poll result device=%s ip=%s status=%s latency_ms=%s error=%s",
                    device_name,
                    device.get("ip") or device.get("ip_address"),
                    status_value,
                    result.latency_ms,
                    result.error_message,
                )
            except Exception as exc:
                summary["failed"] += 1
                summary["offline"] += 1
                summary["results"].append(
                    {
                        "device_id": device_id,
                        "name": device_name,
                        "status": DeviceStatus.OFFLINE.value,
                        "latency_ms": 0,
                        "error": str(exc),
                    }
                )
                logger.error("Scheduled poll failed for %s: %s", device_name, exc)

        tasks = [_poll_single(device_id) for device_id in active_ids]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=False)

        agents_marked_offline = await self._check_agent_offline_status()
        summary["agents_marked_offline"] = agents_marked_offline
        summary["completed_at"] = datetime.now(timezone.utc).isoformat()

        self._polling_last_run = summary["completed_at"]
        self._polling_cycle_summary = summary

        logger.info(
            "Scheduled polling cycle completed total=%s online=%s warning=%s offline=%s failed=%s agents_offline=%s",
            summary["total_devices"],
            summary["online"],
            summary["warning"],
            summary["offline"],
            summary["failed"],
            summary["agents_marked_offline"],
        )

        return summary

    async def _check_agent_offline_status(self) -> int:
        """Mark agents offline when heartbeat is stale."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - self._agent_offline_timeout_seconds
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc).replace(tzinfo=None)

        stale_agents = await self.db.fetch_all(
            "SELECT id, name, last_heartbeat, status FROM agents WHERE last_heartbeat IS NULL OR last_heartbeat < ?",
            (cutoff_dt,),
        )

        updated_count = 0
        for agent in stale_agents:
            if str(agent.get("status") or "").lower() == "offline":
                continue
            await self.db.execute("UPDATE agents SET status = 'offline' WHERE id = ?", (agent["id"],))
            updated_count += 1
            logger.warning(
                "Agent marked offline due to stale heartbeat: id=%s name=%s last_heartbeat=%s",
                agent.get("id"),
                agent.get("name"),
                agent.get("last_heartbeat"),
            )

        return updated_count

    async def start_scheduled_polling(
        self,
        interval_minutes: int = 5,
        agent_offline_seconds: int = 120,
        device_concurrency: int = 10,
    ):
        """Start periodic async polling task."""
        if self._polling_task and not self._polling_task.done():
            logger.info("Scheduled polling already running")
            return

        self._polling_interval_seconds = max(60, int(interval_minutes) * 60)
        self._agent_offline_timeout_seconds = max(30, int(agent_offline_seconds))
        self._semaphore = asyncio.Semaphore(max(1, int(device_concurrency)))
        self._polling_running = True

        async def _loop():
            logger.info(
                "Starting scheduled polling loop interval=%ss agent_offline_timeout=%ss",
                self._polling_interval_seconds,
                self._agent_offline_timeout_seconds,
            )
            while self._polling_running:
                cycle_start = datetime.now(timezone.utc)
                next_ts = cycle_start.timestamp() + self._polling_interval_seconds
                self._polling_next_run = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat()

                try:
                    await self.run_poll_cycle()
                except Exception as exc:
                    logger.error("Scheduled polling cycle failed: %s", exc, exc_info=True)

                try:
                    await asyncio.sleep(self._polling_interval_seconds)
                except asyncio.CancelledError:
                    break

            logger.info("Scheduled polling loop stopped")

        self._polling_task = asyncio.create_task(_loop(), name="device-polling-loop")

    async def stop_scheduled_polling(self):
        """Stop periodic polling task."""
        self._polling_running = False
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        self._polling_task = None

    def get_polling_status(self) -> Dict[str, Any]:
        """Return current polling loop status and latest summary."""
        return {
            "running": bool(self._polling_task and not self._polling_task.done() and self._polling_running),
            "interval_seconds": self._polling_interval_seconds,
            "last_run": self._polling_last_run,
            "next_run": self._polling_next_run,
            "results_summary": self._polling_cycle_summary,
        }

    async def test_device(self, device_id: int) -> ConnectionTestResult:
        """Run test_connection(), persist status, and return result."""
        connector = await self.get_connector(device_id)
        if not connector:
            result = ConnectionTestResult(success=False, latency_ms=0, error_message="Could not initialize connector")
            await self._update_device_status(device_id, DeviceStatus.OFFLINE)
            return result

        try:
            result = await connector.test_connection()
            status = self._derive_status_from_test_result(result)

            await self._update_device_status(device_id, status)

            # Ensure update is persisted and cache has latest value.
            updated = await crud.get_device(self.db, device_id)
            if updated:
                self._devices[device_id] = updated

            return result
        except Exception as e:
            await self._update_device_status(device_id, DeviceStatus.OFFLINE)
            return ConnectionTestResult(success=False, latency_ms=0, error_message=str(e))

    @staticmethod
    def _derive_status_from_test_result(result: ConnectionTestResult) -> DeviceStatus:
        if result.success:
            return DeviceStatus.ONLINE

        error_text = (result.error_message or "").lower()
        auth_markers = [
            "authentication",
            "auth failed",
            "permission denied",
            "invalid password",
            "password",
            "credential",
        ]

        if any(marker in error_text for marker in auth_markers):
            return DeviceStatus.WARNING

        return DeviceStatus.OFFLINE

    async def get_device_status(self, device_id: int) -> str:
        """Return cached status without polling."""
        device = self._devices.get(device_id)
        if not device:
            # Fallback to DB
            device = await crud.get_device(self.db, device_id)
            if device:
                self._devices[device_id] = device
            else:
                return DeviceStatus.UNKNOWN.value
        return device.get("status", DeviceStatus.UNKNOWN.value)

    async def get_device_data(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Return cached data (system_info, interfaces, etc.)."""
        return self._cache.get(device_id)

    async def refresh_device_data(self, device_id: int):
        """Force full data collection (ARP, MAC, routes too)."""
        async with self._semaphore:
            connector = await self.get_connector(device_id)
            if not connector:
                return

            try:
                if not await connector.connect():
                    return

                # Collect EVERYTHING
                system_info = await connector.get_system_info()
                interfaces = await connector.get_interfaces()
                arp_table = await connector.get_arp_table()
                mac_table = await connector.get_mac_table()
                routes = await connector.get_routes()

                data = {
                    "system_info": system_info,
                    "interfaces": [vars(i) if hasattr(i, "__dict__") else i for i in interfaces],
                    "arp_table": [vars(a) if hasattr(a, "__dict__") else a for a in arp_table],
                    "mac_table": [vars(m) if hasattr(m, "__dict__") else m for m in mac_table],
                    "routes": [vars(r) if hasattr(r, "__dict__") else r for r in routes],
                    "last_refresh": datetime.now(timezone.utc).isoformat(),
                }

                self._cache[device_id] = data
                await self._update_device_status(device_id, DeviceStatus.ONLINE)
                logger.info(f"Full data refresh completed for device {device_id}")

            except Exception as e:
                logger.error(f"Error refreshing data for device {device_id}: {e}")
            finally:
                if connector.is_connected:
                    await connector.disconnect()

    async def _update_device_status(self, device_id: int, status: DeviceStatus | str):
        """Update device status in cache and database."""
        now = datetime.now()
        status_value = status.value if isinstance(status, DeviceStatus) else DeviceStatus(str(status).lower()).value

        # Update cache
        if device_id in self._devices:
            current_status = self._devices[device_id].get("status", DeviceStatus.UNKNOWN.value)
            self._devices[device_id]["status"] = status_value
            self._devices[device_id]["last_seen"] = now
            if current_status != status_value:
                self._devices[device_id]["last_status_change"] = now

        # Update DB
        try:
            await crud.update_device_status(self.db, device_id, status_value, now)
        except Exception as e:
            logger.error(f"Failed to update device {device_id} status in DB: {e}")


_DEVICE_MANAGER_INSTANCE: Optional[DeviceManager] = None


def get_device_manager(db: Optional[DatabaseManager] = None, vault: Optional[CredentialVault] = None) -> DeviceManager:
    """Access the singleton instance of the Device Manager."""
    global _DEVICE_MANAGER_INSTANCE
    if _DEVICE_MANAGER_INSTANCE is None:
        _DEVICE_MANAGER_INSTANCE = DeviceManager()

    if db is not None and vault is not None and not getattr(_DEVICE_MANAGER_INSTANCE, "_initialized", False):
        _DEVICE_MANAGER_INSTANCE.initialize(db, vault)

    if not getattr(_DEVICE_MANAGER_INSTANCE, "_initialized", False):
        raise ValueError("DatabaseManager and CredentialVault required for first initialization")

    return _DEVICE_MANAGER_INSTANCE
